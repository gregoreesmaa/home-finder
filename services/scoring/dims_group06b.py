"""Group 6 heritage-leftover per-listing dimensions, batch G06B (issue #139).

Params (this agent only — sibling batches own disjoint sets):
* p352 plaster/lath repair craft (mapped plaster-building density proxy)
* p353 antique hardware availability (mapped antiques-shop BOOLEAN proxy)
* p354 heritage foundation settling (geotechnical — documented no-map)
* p355 historical society friction (inverse-density process heuristic)
* p356 balloon framing fire risk (mapped wooden-house distance proxy)
* p359 asbestos siding lifespan (zero mapped signal — documented no-map)
* p360 deed historical provenance (archive fact — documented no-map)

HONESTY (AGENTS.md section 7.2): the Muinsuskaitseamet heritage registry
(register.muinsuskaitseamet.ee) and the Maa-amet mka:ehitis /
mka:kaitsevoond WFS layers are NOT in the 2026-09-12 snapshot, so every
scorer below is an honestly-labeled OSM-derived PROXY or an explicit
None stub. Reasons must say "kaardistatud" (mapped) and "hinnang"
(estimate), never claim a registry verdict, a craft guarantee, a stock
figure, a geotechnical survey, a lab result, or a deed chain.

Style mirrors services/scoring/livability.py and sibling batch
dims_group06.py (#138): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
only in livability.fetch_pois; this module adds no network calls, only
the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or the sibling
batches): a future central hook may import this module alongside them,
and importing any of them here would turn that into a cycle (same
precedent as batch B3, PR #100, and siblings #105/#107/#121/#138).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf,
NOT at runtime; extraction used nwr/ filters throughout — node-only
would silently drop way-mapped houses, PR #118):
* nwr/building:material: 11371 features — plaster 4396, wood 2376,
  brick 1969, asbestos 0 (hence the p359 no-map: zero signal).
* nwr/shop=antiques: 14 (13 Tallinn Old Town + 1 Rapla).

Judgment calls (reviewable per AGENTS.md section 7.5):
* p352 counts mapped plaster buildings within 500 m (the map layer's
  walk-kernel sigma). Bands are modest and zero is 30, not 0: OSM
  material tagging is thin (most houses carry no material tag), so no
  mapped plaster nearby is weak evidence of no craft need nearby.
* p353 is the only BOOLEAN dim: 1 when a mapped antiques dealer sits
  within 2 km (the sparse-tier query radius — 14 dealers county-wide
  cannot support a 500 m radius), else 0, always "mark unverified" per
  parameters3.md ("Default FALSE; mark unverified"): a shop is foot
  traffic for second-hand hardware, never a stock guarantee.
* p355 is the deliberate PARALLEL of #138's p320 commission heuristic
  from the same honest source (mapped heritage density): society
  coordination need grows with heritage clustering. Same soft bands
  (25..90, never 0/100). Kept as its own dim because parameters3.md
  scores p320/p355 separately; a future registry WFS would split them.
  It counts the G06 "heritage" kind (see dims_group06.py), NOT a G06B
  kind — no second gradient, no fake differentiation.
* p356 scores NEAREST mapped wooden-house distance (the map layer's
  inverse-distance shape): the adjacent wooden neighbour drives
  fire-spread attention. Bands stay soft (20..95, never 0/100):
  wood-material mapping is THIN (Kalamaja's wooden houses are mostly
  untagged), so far-from-mapped-wood reads 95 with a thin-mapping
  caveat, never a clean bill of construction.
* p354/p359/p360 are constant-None stubs WITH registry entries (not
  omitted): omitting them would let a downstream scorer silently treat
  them as 0/neutral. Settling needs a geotechnical survey, asbestos a
  lab, provenance an archive lookup — none is predictable from mapped
  density, and guessing would be fake precision.
* "plasterbld" / "antiqueshop" / "woodbld" kinds are disjoint from all
  sibling batches (novel kind strings; dims_group06 mentions heritage
  windmills only to EXCLUDE them from vibration scoring, and p355
  reuses the G06 "heritage" kind on purpose — documented above).

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP06B_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP06B_POI_KIND (via kinds_from_tags
below), centroiding way geometries to points (plaster/wood houses are
usually area-mapped; raw way nodes would multi-count — residual twin
risk per PR #118 must be noted by the hook author), and rebalancing
livability.WEIGHTS must be one joint change across all parameter
batches — existing tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS
edits would break every sibling.
"""

import math
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

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


def _count_within_m(origin: Tuple[float, float], pois: List[dict],
                    kinds: set, radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


def _nearest_within_m(origin: Tuple[float, float], pois: List[dict],
                      kinds: set) -> Optional[float]:
    best: Optional[float] = None
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            d = _haversine_m(origin, p["lat"], p["lon"])
            if best is None or d < best:
                best = d
    return best


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# The fragment queries at 2 km (sparse tier — 14 dealers and thin
# material tagging cannot support a tighter radius); the p352 scorer
# counts within PLASTER_RADIUS_M 500 m (the map layer's walk-kernel
# sigma, so the per-listing dim agrees with the map about what
# "nearby" means), p353 booleans within ANTIQUES_RADIUS_M 2 km, and
# p356 reads nearest-wood distance outright. Node AND way lines are
# required (nwr/ parity): houses are usually area-mapped; node-only
# drops them.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP06B_OVERPASS_FRAGMENT = """
  node["building:material"](around:2000,{lat},{lon});
  node["shop"="antiques"](around:2000,{lat},{lon});
  way["building:material"](around:2000,{lat},{lon});
  way["shop"="antiques"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: building:material is value-routed through kinds_from_tags (plaster
#: vs wood share one key); shop=antiques maps directly.
GROUP06B_POI_KIND = [
    ("building:material", {"plaster": "plasterbld", "wood": "woodbld"}),
    ("shop", {"antiques": "antiqueshop"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 6B kind matching the OSM tags, else None. Pure.

    building:material=plaster -> "plasterbld" (p352 craft-need proxy);
    building:material=wood -> "woodbld" (p356 fire-spread proxy);
    shop=antiques -> "antiqueshop" (p353 availability proxy). All other
    materials (brick, concrete, ...) and shops map to None: they carry
    no G06B signal. Multi-values ("plaster;brick") take the first
    segment.
    """
    tags = tags or {}
    mat = str(tags.get("building:material", "")).split(";")[0].strip()
    if mat == "plaster":
        return "plasterbld"
    if mat == "wood":
        return "woodbld"
    if str(tags.get("shop", "")).split(";")[0].strip() == "antiques":
        return "antiqueshop"
    return None


# ---------------------------------------------------------------------------
# p352: plaster/lath repair craft (mapped-plaster density proxy).
# ---------------------------------------------------------------------------

#: Plaster-density count radius in metres (map sigma parity).
PLASTER_RADIUS_M = 500.0


def dim_plaster_craft(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p352: mapped plaster buildings within 500 m (käsitöö-hinnang)."""
    if not origin or pois is None:
        return None, "Krohvitöö info puudub"
    n = _count_within_m(origin, pois, {"plasterbld"}, PLASTER_RADIUS_M)
    if n == 0:
        return 30, ("Kaardistatud krohvfassaadiga hooneid 500 m raadiuses pole "
                    "(käsitöö-hinnang, mitte registriotsus; materjali "
                    "kaardistus on hõre — käsitööline võib siiski leiduda)")
    s = _band(n, [(1, 50), (3, 70), (6, 85), (float("inf"), 100)])
    return s, ("Kaardistatud krohvfassaadiga hooneid 500 m raadiuses: %d "
               "(käsitöö-hinnang, mitte seisukorraotsus)") % n


# ---------------------------------------------------------------------------
# p353: antique hardware availability (mapped-dealer BOOLEAN proxy).
# ---------------------------------------------------------------------------

#: Dealer search radius in metres (sparse tier — 14 dealers county-wide).
ANTIQUES_RADIUS_M = 2000.0


def dim_antiques(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p353: 1/0 — mapped antiques dealer within 2 km (saadavus-hinnang).

    Boolean per parameters3.md ("Default FALSE; mark unverified"): the
    score says a dealer is near, never that hardware is in stock.
    """
    if not origin or pois is None:
        return None, "Antiigipoodide info puudub"
    d = _nearest_within_m(origin, pois, {"antiqueshop"})
    if d is None or d > ANTIQUES_RADIUS_M:
        return 0, ("Kaardistatud antiigipoodi 2 km raadiuses pole "
                   "(saadavus-hinnang täpsustamata)")
    return 1, ("Kaardistatud antiigipood %s kaugusel (saadavus "
               "täpsustamata — kauplus ≠ furnituuriladu)" % _fmt_m(d))


# ---------------------------------------------------------------------------
# p354: heritage foundation settling — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_settling(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p354: ALWAYS None — settling is geotechnical, unmapped."""
    return None, ("Vundamendi vajumise hinnangut snapshots anda ei saa — "
                  "vajab geotehnilist ekspertiisi (pinnas/vesi; lähedased "
                  "muinsusobjektid vajumist ei ennusta)")


# ---------------------------------------------------------------------------
# p355: historical society friction (inverse-density heuristic).
# ---------------------------------------------------------------------------

#: Society-friction count radius in metres (G06 heritage-kind parity).
SOCIETY_RADIUS_M = 800.0


def dim_society(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p355: society-friction heuristic — HIGHER score = LESS friction.

    Deliberate parallel of #138's p320 commission heuristic from the
    same honest source (mapped heritage density, kind "heritage"):
    dense heritage predicts Muinsuskaitseamet/selts coordination need.
    Bands are soft (25..90): proximity predicts coordination
    likelihood, never a named society decision. No second map gradient
    (see GROUP06B_NO_MAP) — the dim reuses the G06 kind on purpose.
    """
    if not origin or pois is None:
        return None, "Seltsiliikumise info puudub"
    n = _count_within_m(origin, pois, {"heritage"}, SOCIETY_RADIUS_M)
    if n == 0:
        return 90, ("Läheduses kaardistatud muinsusobjekte pole — "
                    "seltsi kooskõlastuse tõenäosus väike (hinnang, "
                    "mitte seltsiotsus)")
    s = _band(n, [(1, 70), (3, 55), (6, 40), (float("inf"), 25)])
    return s, ("Kaardistatud muinsusobjekte 800 m raadiuses: %d — "
               "miljööalal tõenäoline kooskõlastusvajadus "
               "(hinnang, mitte seltsiotsus)") % n


# ---------------------------------------------------------------------------
# p356: balloon framing fire risk (nearest-mapped-wood proxy).
# ---------------------------------------------------------------------------

def dim_woodfire(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p356: nearest mapped wooden house (tuleleviku-hinnang).

    Inverse like the map layer: the adjacent wooden neighbour drives
    the score DOWN. Bands stay soft (20..95, never 0/100): material
    mapping is thin, so far-from-mapped-wood is low-attention with a
    caveat, never a construction verdict.
    """
    if not origin or pois is None:
        return None, "Puithoonete tuleohutuse info puudub"
    d = _nearest_within_m(origin, pois, {"woodbld"})
    if d is None:
        return 95, ("Kaardistatud puithooneid läheduses pole "
                    "(tuleleviku-hinnang; materjali kaardistus on hõre — "
                    "kaardistamata puithooned ei loe)")
    s = _band(d, [(50, 20), (150, 40), (300, 60), (600, 80), (float("inf"), 95)])
    return s, ("Lähim kaardistatud puithoone %s kaugusel "
               "(tuleleviku-hinnang, mitte konstruktsiooniuuring)" % _fmt_m(d))


# ---------------------------------------------------------------------------
# p359: asbestos siding lifespan — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_asbestos(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p359: ALWAYS None — zero asbestos tags mapped, needs a lab."""
    return None, ("Asbesti hinnangut snapshots anda ei saa — hetktõmmises "
                  "pole ühtegi building:material=asbestos silti (kontrollitud; "
                  "kaardistamata ≠ puudub), vajab laboriuuringut")


# ---------------------------------------------------------------------------
# p360: deed historical provenance — documented no-map (None stub).
# ---------------------------------------------------------------------------

def dim_provenance(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p360: ALWAYS None — provenance is an archive chain, unmapped."""
    return None, ("Kinnistu päritoluahela hinnangut snapshots anda ei saa — "
                  "vajab arhiivipäringut (kinnistusraamat / Muinsuskaitseameti "
                  "register; start_date ei ole päritolutõend)")


#: Registry for the central weight-rebalance follow-up: (dims key, param id, fn).
GROUP06B_DIMS = (
    ("plaster_craft", "p352", dim_plaster_craft),
    ("antiques", "p353", dim_antiques),
    ("settling", "p354", dim_settling),
    ("society", "p355", dim_society),
    ("woodfire", "p356", dim_woodfire),
    ("asbestos", "p359", dim_asbestos),
    ("provenance", "p360", dim_provenance),
)


def score_group06b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All seven Group 6 batch-G06B dims for one listing (entry point for
    the weight-rebalance follow-up; keys match GROUP06B_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP06B_DIMS}
