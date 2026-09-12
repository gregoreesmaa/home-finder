"""Vegetation + street-ops OSM dimensions (issue #122).

Params (this agent only — sibling batches own disjoint sets; p319 lives in
parameters3.md section 5.10 Group 10, the rest in section 5.18 Group 18,
re-derived here from OSM vegetation/power/highway tags because the Group 18
primaries — Maa-amet 3D meshes, PVLib ray-tracing, VIIRS — carry no tree,
leaf, trimming-registry, or snowplow signal, and the Group 10 primaries —
KKIS/ETAK utility registries, TTJA coverage — carry no trimming ordinance):
* p65  mature tree liability (mapped mature-canopy density, INVERTED burden)
* p259 tree root mapping (same trees, hyper-local root-zone half, INVERTED)
* p395 fallen leaf burden (deciduous proximity, INVERTED burden)
* p319 tree trimming ordinances (line-corridor/tree overlap PROXY, hinnang)
* p446 snowplow berms (road-class snow proxy, PROXY, hinnang)

HONESTY (AGENTS.md section 7.2): municipal trimming registries and plow
routes are NOT in the snapshot, so p319/p446 MUST be honestly-labeled
proxies — every reason says "hinnang", and LAYER_META below carries
"(hinnang)" in the title/legend/source for both. p65/p259/p395 read mapped
OSM trees ("kaardistatud"), never surveyed arborist data.

Style mirrors services/scoring/livability.py: every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100], Estonian reason).
Network lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability): a future central
hook may import this module from livability.py, and importing livability
here would turn that into a cycle (same precedent as PRs #100/#106/#113).

Tag verification (2026-09-12, done once by the author with osmium against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime):
* natural=tree: 43522 nodes, ALL Points. leaf_type broadleaved 24683 /
  needleleaved 4038 / mixed 1; leaf_cycle deciduous 23804 / evergreen 3730.
  Maturity signals: height on 856 nodes, diameter 621, circumference 78,
  diameter_crown 68, denotation avenue 1504 / urban 1219 / park 97.
* natural=tree_row: 1583 (LineStrings — way geometry, needs centroid);
  natural=wood: 7178 (MultiPolygons — needs centroid). leaf_type on these
  area features: broadleaved 1827 / mixed 1283 / needleleaved 452.
* power=line/minor_line: 1154 true ways (ALL LineStrings — corridor
  geometry, needs centroid handling; the 12066 extra Points in the raw
  export are referenced member nodes, not mapped poles).
* highway ways: arterial motorway|trunk|primary|secondary 4979 (group 18
  probe); tertiary 5245 / residential 10454 / unclassified 4757 (this
  author, same snapshot, w/ filter + LineString check).

Extraction MUST use nwr/ (PR #118: node-only drops way-mapped features):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/natural=tree nwr/natural=tree_row nwr/natural=wood \
      nwr/power=line nwr/power=minor_line \
      -o /tmp/hf-veg.pbf --overwrite
  osmium export -u type_id /tmp/hf-veg.pbf -o /tmp/hf-veg.geojson
Way geometries need centroid handling on the live path (Overpass
`out center`); residual twin risk (node+area twins ~20 m apart
double-counting, layers.md open issue) is NOT deduped here — noted for
the central hook and the PR.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Burden direction: p65/p259/p395 are INVERTED (nearer/ denser mapped
  canopy -> lower score). A mature tree is an amenity too, but the
  parameter names the LIABILITY/burden half, matching the p82-arterial
  precedent; reasons name the distance so tree-loving buyers can judge.
* p65 vs p259 are DISTINCT halves of the same trees (brief requirement):
  p65 reads 200 m mature-canopy DENSITY (storm-fall/branch exposure grows
  with how many big crowns surround the plot); p259 reads 100 m NEAREST
  distance (root intrusion threatens only the adjacent plot). Different
  radii, different reducers (count vs nearest), documented + tested.
* Mature = parsed height >= 8 m, or circumference/diameter/diameter_crown
  present, or denotation in {avenue, park, landmark, natural_monument,
  memorial}. 8 m is the Tallinn street-tree "large" break, not a survey.
* Deciduous = leaf_type in {broadleaved, mixed} or leaf_cycle ==
  deciduous. Unknown-leaf trees score the moderate path, never the worst
  band — guessing leaf habit would fake precision. Evergreens read as
  generic trees (winter shade, not leaf litter).
* p65 fall-zone: nearest mature <= 25 m caps the score at 25 (one crown
  overhead dominates any count band).
* p65 fallback (no mature within 200 m): generic canopy within 500 m ->
  70, none -> 85. Absence of MAPPED mature trees is weak evidence (park
  trees map sparsely), so the floor stays high.
* p319 proxy: trimming duty follows line corridors — listing within
  500 m of a power=line corridor AND mapped trees within 100 m -> 45
  (trimming-exposure); near corridor without nearby trees -> 70; far from
  corridors -> 80. The reason always says "hinnang" + "register puudub".
* p446 proxy: plow priority follows road class (riigimaanteed first, big
  berms at arterial kerbs). Nearest arterial <= 100 m -> 40 (berm wall at
  the driveway); <= 300 m -> 60; else local street <= 150 m -> 75;
  <= 500 m -> 85; no mapped road within 500 m -> 55 (probably an
  unmapped private tee with uncertain winter service — mid, not bad).
  "service" highway is excluded (yards/driveways plow privately).
* One POI carries one kind. Priority: power_line > mature_decid >
  mature_tree > decid_tree > tree/wood > plow_arterial > plow_local, so a
  way-center feeds exactly one scorer. maxspeed is NOT re-read here —
  Group 18 owns maxspeed tiers; every maxspeed way already has a highway
  class, so class-only keeps the batches disjoint.

Delivery (stated per the task brief): scorer dims ONLY, no raster masters.
Why: (1) four of five dims are way-geometry (tree_row corridors, wood
polygons, power-line corridors, road classes), not the point-kernel shape
the walk-raster pipeline stamps — corridor rasters need a new
length-weighted builder, not a reuse; (2) five county+metro masters means
five full-Harjumaa stamp runs plus hook edits to layers.ts/snapshot.ts,
which already collide with open sibling PRs; (3) the repo precedent (PRs
#101/#106/#113) is scorer-first with one central integration later.
LAYER_META below stages the honest web labels for that follow-up.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with VEG_OVERPASS_FRAGMENT (routing natural/
power/highway tags through kinds_from_tags, with `out center` for way
centroids), livability._POI_KIND with VEG_POI_KIND, and rebalancing
livability.WEIGHTS must be one joint change across all parameter batches —
existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would
break every sibling.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Parsed tree height at or above this reads as mature ("large" street-tree
#: break used by Tallinn haljastus practice; a mapping heuristic, not survey).
MATURE_HEIGHT_M = 8.0
#: denotation=* values that mark a deliberately planted/managed large tree.
MATURE_DENOTATION = frozenset(
    {"avenue", "park", "landmark", "natural_monument", "memorial"})
#: leaf_type values that shed (mixed stands shed too).
DECIDUOUS_LEAF = frozenset({"broadleaved", "mixed"})
#: leaf_cycle value that sheds.
DECIDUOUS_CYCLE = "deciduous"
#: Highway classes plowed first (riigimaantee tier) — big kerb berms.
PLOW_ARTERIAL = frozenset({"motorway", "trunk", "primary", "secondary"})
#: Highway classes plowed routinely with smaller berms.
PLOW_LOCAL = frozenset(
    {"tertiary", "residential", "unclassified", "living_street"})

# ---------------------------------------------------------------------------
# Local pure helpers (livability-shaped; see module docstring for why local).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _band(value: Optional[float], bands: List[Tuple[float, int]]) -> Optional[int]:
    """First score whose threshold covers the value; None stays None."""
    if value is None:
        return None
    for limit, pts in bands:
        if value <= limit:
            return pts
    return bands[-1][1]


def _nearest_m(origin: Tuple[float, float], pois: List[dict], kinds: set) -> Optional[float]:
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            d = _haversine_m(origin, p["lat"], p["lon"])
            if best is None or d < best:
                best = d
    return best


def _count_within_m(
    origin: Tuple[float, float], pois: List[dict], kinds: set, radius_m: float
) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _parse_height(value: object) -> Optional[float]:
    """Parse an OSM height tag ('12', '13 m', '10;12') to metres."""
    if not isinstance(value, str):
        return None
    first = value.strip().split(";")[0].strip().rstrip("m").strip()
    try:
        v = float(first.replace(",", "."))
    except ValueError:
        return None
    return v if v > 0 else None


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radii are judgment calls: canopy density reads at 200 m, leaf litter at
# 150 m, root zones at 100 m — the fragment fetches 500 m so every scorer
# sees its full window plus fallback context. Corridors (power/roads) read
# at neighbourhood scale (500 m).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on
#: integration. Ways MUST come back via `out center` (centroid handling —
#: tree_row/wood/power/highway are way geometry, PR #118 nwr/ rule).
VEG_OVERPASS_FRAGMENT = """
  node["natural"="tree"](around:500,{lat},{lon});
  way["natural"~"tree|tree_row|wood"](around:500,{lat},{lon});
  way["power"~"line|minor_line"](around:500,{lat},{lon});
  way["highway"~"motorway|trunk|primary|secondary|tertiary|residential|unclassified|living_street"](around:500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND. Maturity
#: (height threshold, denotation set) and deciduous (leaf_type/leaf_cycle)
#: splits need kinds_from_tags below — the static table alone cannot split
#: them, so the central hook must route these keys through kinds_from_tags.
VEG_POI_KIND = [
    ("natural", {"tree": "tree", "tree_row": "tree", "wood": "wood"}),
    ("power", {"line": "power_line", "minor_line": "power_line"}),
    ("highway", {"motorway": "plow_arterial", "trunk": "plow_arterial",
                 "primary": "plow_arterial", "secondary": "plow_arterial",
                 "tertiary": "plow_local", "residential": "plow_local",
                 "unclassified": "plow_local",
                 "living_street": "plow_local"}),
]

#: All tree-ish kinds (canopy/root/leaf scorers read subsets of this).
TREE_KINDS = frozenset(
    {"mature_tree", "mature_decid", "decid_tree", "tree", "wood"})
#: Kinds with mapped mature crowns (p65 density half).
MATURE_KINDS = frozenset({"mature_tree", "mature_decid"})
#: Kinds that shed leaves (p395 burden half).
DECID_KINDS = frozenset({"decid_tree", "mature_decid"})


def _is_mature(tags: dict) -> bool:
    """Mapped maturity signal: tall, measured, or planted-as-large."""
    h = _parse_height(tags.get("height"))
    if h is not None and h >= MATURE_HEIGHT_M:
        return True
    for key in ("circumference", "diameter", "diameter_crown"):
        if isinstance(tags.get(key), str) and tags[key].strip():
            return True
    den = tags.get("denotation", "")
    den = den.split(";")[0].strip() if isinstance(den, str) else ""
    return den in MATURE_DENOTATION


def _is_deciduous(tags: dict) -> bool:
    """Mapped shed signal via leaf_type or leaf_cycle."""
    lt = tags.get("leaf_type", "")
    lt = lt.split(";")[0].strip() if isinstance(lt, str) else ""
    if lt in DECIDUOUS_LEAF:
        return True
    lc = tags.get("leaf_cycle", "")
    lc = lc.split(";")[0].strip() if isinstance(lc, str) else ""
    return lc == DECIDUOUS_CYCLE


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First vegetation/street-ops kind matching the OSM tags, else None.

    Pure. Priority (documented judgment call): power_line > mature_decid >
    mature_tree > decid_tree > tree/wood > plow_arterial > plow_local, so
    one way-center feeds exactly one scorer.
    """
    if not isinstance(tags, dict):
        return None
    pw = tags.get("power", "")
    pw = pw.split(";")[0].strip() if isinstance(pw, str) else ""
    if pw in ("line", "minor_line"):
        return "power_line"
    nat = tags.get("natural", "")
    nat = nat.split(";")[0].strip() if isinstance(nat, str) else ""
    if nat in ("tree", "tree_row"):
        mature, decid = _is_mature(tags), _is_deciduous(tags)
        if mature and decid:
            return "mature_decid"
        if mature:
            return "mature_tree"
        if decid:
            return "decid_tree"
        return "tree"
    if nat == "wood":
        return "wood"
    hw = tags.get("highway", "")
    hw = hw.split(";")[0].strip() if isinstance(hw, str) else ""
    if hw in PLOW_ARTERIAL:
        return "plow_arterial"
    if hw in PLOW_LOCAL:
        return "plow_local"
    return None


# ---------------------------------------------------------------------------
# p65: mature tree liability — mapped mature-canopy DENSITY (200 m).
# INVERTED burden: denser big crowns -> lower score (storm-fall exposure).
# ---------------------------------------------------------------------------

def dim_mature_tree(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p65: storm-fall liability from mapped mature canopy density."""
    if not origin or pois is None:
        return None, "Puude info puudub"
    n = _count_within_m(origin, pois, MATURE_KINDS, 200)
    if n > 0:
        s = _band(n, [(1, 60), (2, 45)])
        assert s is not None
        s = min(s, 30) if n >= 5 else s
        m = _nearest_m(origin, pois, MATURE_KINDS)
        assert m is not None
        if m <= 25:
            return 20, ("Suur puu %s kaugusel – tormikahju oht krundil "
                        "(kaardistatud haljastus)" % _fmt_m(m))
        return s, ("Kaardistatud suuri puid 200 m raadiuses: %d "
                   "(tormiohu hinnang)" % n)
    m_any = _nearest_m(origin, pois, TREE_KINDS)
    if m_any is not None and m_any <= 500:
        return 70, ("Suuri puid kaardistamata, haljastust %s kaugusel "
                    "(tormiohu hinnang)" % _fmt_m(m_any))
    return 85, ("Kaardistatud puid läheduses pole – tormioht väike "
                "(haljastuse kaardistus võib olla lünklik)")


# ---------------------------------------------------------------------------
# p259: tree root mapping — NEAREST tree distance (100 m half).
# INVERTED: closer crowns -> lower score (foundation/drain intrusion risk).
# Distinct half from p65 by design: nearest-distance at 100 m, not
# 200 m density — a lone street tree threatens pipes; liability needs mass.
# ---------------------------------------------------------------------------

def dim_tree_roots(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p259: root-intrusion exposure from the nearest mapped tree/wood."""
    if not origin or pois is None:
        return None, "Puuuurte info puudub"
    m = _nearest_m(origin, pois, TREE_KINDS)
    if m is None or m > 100:
        return 90, ("Lähim kaardistatud puu kaugemal kui 100 m – "
                    "juurekahju oht väike")
    s = _band(m, [(10, 25), (20, 45), (40, 65), (100, 80)])
    assert s is not None
    return s, "Lähim kaardistatud puu %s (juurekahju hinnang)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p395: fallen leaf burden — deciduous proximity (150 m).
# INVERTED burden: more shedding crowns -> lower score (autumn gutter/yard
# work). Unknown-leaf trees take the moderate path, never the worst band.
# ---------------------------------------------------------------------------

def dim_leaf_burden(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p395: autumn leaf burden from mapped deciduous trees."""
    if not origin or pois is None:
        return None, "Lehekoormuse info puudub"
    n = _count_within_m(origin, pois, DECID_KINDS, 150)
    if n > 0:
        s = _band(n, [(1, 65), (2, 50)])
        assert s is not None
        s = min(s, 30) if n >= 6 else s
        return s, ("Kaardistatud lehtpuid 150 m raadiuses: %d "
                   "(sügisese lehekoormuse hinnang)" % n)
    m_gen = _nearest_m(origin, pois, TREE_KINDS)
    if m_gen is not None and m_gen <= 150:
        return 65, ("Puid %s kaugusel, lehetüüp kaardistamata – "
                    "lehekoormus võimalik" % _fmt_m(m_gen))
    return 90, "Lehtpuid 150 m raadiuses kaardistamata – lehekoormus väike"


# ---------------------------------------------------------------------------
# p319: tree trimming ordinances — line-corridor/tree overlap PROXY.
# Municipal trimming registries are NOT in the snapshot: this scores the
# physical exposure (trees where corridor-clearance duty applies), honestly
# labeled "hinnang" + "register puudub" in every reason.
# ---------------------------------------------------------------------------

def dim_trimming(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p319: trimming-duty exposure proxy (power corridor x nearby trees)."""
    if not origin or pois is None:
        return None, "Hoolduslõikuse info puudub"
    m_line = _nearest_m(origin, pois, {"power_line"})
    if m_line is None or m_line > 500:
        return 80, ("Elektriliini koridor kaugemal kui 500 m – "
                    "hoolduslõikuse kohustus väike "
                    "(hinnang, register puudub)")
    m_tree = _nearest_m(origin, pois, TREE_KINDS)
    if m_tree is not None and m_tree <= 100:
        return 45, ("Puud %s kaugusel liinikoridorist (%s) – "
                    "hoolduslõikuse mõjuala (hinnang, register puudub)"
                    % (_fmt_m(m_tree), _fmt_m(m_line)))
    return 70, ("Liinikoridor %s, puid läheduses kaardistamata – "
                "hoolduslõikuse mõju mõõdukas (hinnang, register puudub)"
                % _fmt_m(m_line))


# ---------------------------------------------------------------------------
# p446: snowplow berms — road-class snow proxy. Plow routes are NOT in the
# snapshot: class stands in for plow priority (arterials first, biggest
# kerb berms). INVERTED near arterials (berm wall at the driveway).
# ---------------------------------------------------------------------------

def dim_snowplow(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p446: plow-berm burden estimate from the nearest mapped road class."""
    if not origin or pois is None:
        return None, "Lumesaha info puudub"
    m_art = _nearest_m(origin, pois, {"plow_arterial"})
    if m_art is not None and m_art <= 300:
        s = _band(m_art, [(100, 40), (300, 60)])
        assert s is not None
        return s, ("Magistraal %s – sahavallide koormus talvel "
                   "(teesklassi hinnang, sahaplaan puudub)" % _fmt_m(m_art))
    m_loc = _nearest_m(origin, pois, {"plow_local"})
    if m_loc is not None and m_loc <= 500:
        s = _band(m_loc, [(150, 75), (500, 85)])
        assert s is not None
        return s, ("Kohalik tee %s – sahavallid mõõdukad "
                   "(teesklassi hinnang)" % _fmt_m(m_loc))
    return 55, ("Kaardistatud teed 500 m raadiuses pole – talihooldus "
                "teadmata (hinnang, eratee võimalik)")


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
VEG_DIMS = (
    ("mature_tree", "p65", dim_mature_tree),
    ("tree_roots", "p259", dim_tree_roots),
    ("leaf_burden", "p395", dim_leaf_burden),
    ("trimming", "p319", dim_trimming),
    ("snowplow", "p446", dim_snowplow),
)


def score_veg(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five vegetation/street-ops dims for one listing (entry point for
    the weight-rebalance follow-up; keys match VEG_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in VEG_DIMS}


#: Honest Estonian web labels for the follow-up layers batch. p319/p446 say
#: "hinnang" in the title itself — never bare "trimming"/"snowplow".
LAYER_META = {
    "mature_tree": {
        "param": 65,
        "title": "Suured puud (tormioht)",
        "good": "roheline = suuri puid läheduses kaardistamata",
        "bad": "punane = tihe suurevõraline haljastus",
        "source": "kohalik hetktõmmis 2026-09-12 (natural=tree/tree_row/wood)",
    },
    "tree_roots": {
        "param": 259,
        "title": "Puuuurte mõjuala",
        "good": "roheline = puud kaugemal kui 100 m",
        "bad": "punane = puu krundi kõrval",
        "source": "kohalik hetktõmmis 2026-09-12 (natural=tree/tree_row/wood)",
    },
    "leaf_burden": {
        "param": 395,
        "title": "Lehekoormus",
        "good": "roheline = lehtpuid läheduses kaardistamata",
        "bad": "punane = palju lehtpuid (sügisene koormus)",
        "source": "kohalik hetktõmmis 2026-09-12 (leaf_type/leaf_cycle)",
    },
    "trimming": {
        "param": 319,
        "title": "Hoolduslõikus (hinnang)",
        "good": "roheline = liinikoridor kaugel (hinnang)",
        "bad": "punane = puud liinikoridoris (hinnang)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(puud + power=line; hinnang, register puudub)"),
    },
    "snowplow": {
        "param": 446,
        "title": "Sahavallid (hinnang)",
        "good": "roheline = rahulik kohalik tee (hinnang)",
        "bad": "punane = magistraali sahavall (hinnang)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(teesklass; hinnang, sahaplaan puudub)"),
    },
}
