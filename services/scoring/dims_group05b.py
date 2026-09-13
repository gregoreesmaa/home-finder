"""Group 5 plans per-listing dimensions, batch B (issue #162).

Params (this agent only — sibling batches own disjoint sets):
* p106 urban farming capability (mapped garden/allotment proximity hinnang)
* p107 livestock/equestrian zoning (ALWAYS None — single site, do not fake)
* p146 future neighborhood density (mapped construction proximity hinnang)
* p186 gray-water system legality (ALWAYS None — no keys, do not fake)
* p188 dark sky compliance (ALWAYS None — p63 owns the signal, do not fake)

HONESTY (AGENTS.md section 7.2): the PLANK WFS (planeeringud.ee) and
the Tallinna Planeeringute Register are NOT in the 2026-09-12
snapshot, so p107/p186/p188 stay NULL with a buyer-check reason, and
p106/p146 are coarse OSM-derived PROXIES. Reasons say "hinnang"
(estimate) and name what is missing — never a soil survey, a zoning
ruling, a legality verdict, or an IDA designation.

Style mirrors services/scoring/livability.py and sibling batch
dims_group03d.py (#154): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #154).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
garden areas and construction polygons, PR #118):
* garden predicate (landuse=allotments OR (leisure=garden AND
  (garden:type=community OR garden:style=kitchen))): 353 kept
  county-wide (155 community/kitchen + 198 allotments), 115 in the
  Tallinn window (76 after the 20 m dedupe: Raadiku peenrad,
  Kalamaja ürdiaed, Krulli aed...) — dense enough for a
  nearest-distance dim AND the map
  (apps/web/lib/layers_group05b.ts). leisure=garden WITHOUT
  garden:type (2988 residential backyards in the window) is OUT
  (a private backyard is not growing opportunity);
  landuse=orchard is OUT (p409 agrifield #143 already scores
  farmland/meadow/orchard — keeping it here would re-skin it).
* construction predicate (landuse=construction): 332 kept
  county-wide, 177 in the Tallinn window (138 after the 20 m
  dedupe: Hipodroomi kvartal, City Plaza 2, Reaalkooli
  juurdeehitus...). Untagged relation members (barrier=gate/access
  fragments) drop out in keep_buildout.
* equestrian tags (leisure=horse_riding, sport=equestrian,
  building=stable/stables): 84 kept county-wide but the WHOLE
  Tallinn window holds ONE site (Veskimetsa, Paldiski mnt 135 —
  8 ring/pitch twins) — no honest city gradient exists.
* graywater keys (graywater/greywater/wastewater=graywater):
  ZERO matches in the whole PBF — p186 has nothing to calibrate
  against.
* dark-sky signal (lit=yes + highway=street_lamp): owned by p63's
  darksky proxy (layers_genv.ts GENV batch — same tags, same
  darksky-walk-raster.json); a second p188 gradient on identical
  tags would re-skin that layer, and compliance itself is an
  IDA-designation legal fact.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p106/p146 bands track the moorage dim (#154) loosely (facility
  near = high): <=150 m scores 85, <=400 m 70, <=800 m 55,
  <=1500 m 40; nothing mapped in radius scores 25 (weak — the
  permit/capability itself stays a per-parcel KOV fact, the reason
  says so). buildout green = developing/growing: a buyer wanting
  stillness reads a HIGH buildout score as "busy" — the reason
  names the construction so both readings stay honest.
* p107/p186/p188 return None for EVERY input including missing
  origin: inventing a gradient from zero/owned signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  KOV/IDA check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP05B_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP05B_POI_KIND, centroiding way
geometries to points (gardens/construction are ways/relations; raw
way nodes would multi-count — residual twin risk per PR #118 must
be noted by the hook author), and rebalancing livability.WEIGHTS
must be one joint change across all parameter batches — existing
tests pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would
break every sibling.
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


def _nearest_m(origin: Tuple[float, float], pois: List[dict], kinds: set) -> Optional[float]:
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
# Radii are judgment calls: gardens dense in town (800 m search),
# construction sparse inland (2 km). Both node[...] and way[...] lines
# are required (nwr/ parity): gardens/construction are ways/relations;
# node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP05B_OVERPASS_FRAGMENT = """
  node["leisure"="garden"](around:800,{lat},{lon});
  node["landuse"="allotments"](around:800,{lat},{lon});
  node["landuse"="construction"](around:2000,{lat},{lon});
  way["leisure"="garden"](around:800,{lat},{lon});
  way["landuse"="allotments"](around:800,{lat},{lon});
  way["landuse"="construction"](around:2000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "garden" = community garden / allotment for the farming dim
#: (garden:type check stays in kinds_from_tags — a private backyard
#: never maps); "buildsite" = mapped construction for the density
#: dim.
GROUP05B_POI_KIND = [
    ("leisure", {"garden": "garden"}),
    ("landuse", {"allotments": "garden", "construction": "buildsite"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 5-batch-B kind matching the OSM tags, else None. Pure.

    leisure=garden without garden:type=community (or garden:style=
    kitchen) maps to None — a private backyard is not growing
    opportunity; landuse=orchard maps to None (p409 agrifield's
    signal — keeping it here would re-skin that layer).
    """
    tags = tags or {}
    if tags.get("landuse") == "allotments":
        return "garden"
    if tags.get("landuse") == "construction":
        return "buildsite"
    if tags.get("leisure") == "garden" and (
        tags.get("garden:type") == "community" or tags.get("garden:style") == "kitchen"
    ):
        return "garden"
    return None


# ---------------------------------------------------------------------------
# p106: urban farming capability (mapped-garden proximity hinnang).
# ---------------------------------------------------------------------------

def dim_gardens(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p106: growing-opportunity goodness from nearest mapped garden."""
    if not origin or pois is None:
        return None, "Aiandusinfo puudub (kogukonnaaedade hetktõmmis)"
    m = _nearest_m(origin, pois, {"garden"})
    if m is None:
        return 25, "Kogukonnaaed 800 m raadiuses kaardistamata (hinnang, nõrk); viljakus ise on krundi-põhine fakt"
    s = _band(m, [(150, 85), (400, 70), (800, 55), (1500, 40)])
    assert s is not None
    if s <= 40:
        return s, "Kasvatusvõimalus (hinnang): lähim kogukonnaaed %s — kaugel" % _fmt_m(m)
    return s, "Kasvatusvõimalus (hinnang): lähim kogukonnaaed %s (muld krundi-põhine)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p146: future neighborhood density (mapped-construction proximity hinnang).
# ---------------------------------------------------------------------------

def dim_buildout(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p146: densification-pressure goodness from nearest mapped build site."""
    if not origin or pois is None:
        return None, "Ehitusinfo puudub (ehitusplatside hetktõmmis)"
    m = _nearest_m(origin, pois, {"buildsite"})
    if m is None:
        return 25, "Ehitusplats 2 km raadiuses kaardistamata (hinnang, nõrk — valmis/rahulik piirkond)"
    s = _band(m, [(150, 85), (400, 70), (800, 55), (1500, 40)])
    assert s is not None
    if s <= 40:
        return s, "Tihenemissurve (hinnang): lähim ehitus %s — kaugel (valmis piirkond)" % _fmt_m(m)
    return s, "Tihenemissurve (hinnang): lähim ehitus %s — piirkond tiheneb" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p107/p186/p188: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-parcel/per-register fact with no honest area signal; the
# scorer reports the gap with a concrete buyer check instead of a
# faked number.
# ---------------------------------------------------------------------------

def dim_livestock(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p107: NULL — equestrian zoning needs the KOV plan (single site, no map)."""
    return None, "Loomapidamise tsoon teadmata (KOV planeering/e loomapidamiseeskiri; hetktõmmises üksik ratsakeskus)"


def dim_graywater(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p186: NULL — gray-water legality needs the KOV ehitusmäärus (no map)."""
    return None, "Hallvee lubatavus teadmata (KOV ehitusmäärus + liitumistingimused; hetktõmmises pole hallveeandmeid)"


def dim_darksky(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p188: NULL — dark-sky compliance needs the IDA register (no map)."""
    return None, "Pimeda taeva vastavus teadmata (IDA register/KOV valgustusnõuded; valgusproksi kuulub p63-le)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP05B_DIMS: Dict[str, Tuple[str, object]] = {
    "gardens": ("Kogukonnaaiad (proksi)", dim_gardens),
    "livestock": ("Loomapidamine (kontroll)", dim_livestock),
    "buildout": ("Ehitustegevus (proksi)", dim_buildout),
    "graywater": ("Hallvesi (kontroll)", dim_graywater),
    "darksky": ("Pime taevas (kontroll)", dim_darksky),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP05B_PARAM_IDS = {
    "gardens": 106,
    "livestock": 107,
    "buildout": 146,
    "graywater": 186,
    "darksky": 188,
}


def score_group05b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 5-batch-B dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP05B_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
