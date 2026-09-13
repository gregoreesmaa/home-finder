"""Group 5 plans-A per-listing dimensions, batch A (issue #161).

Params (this agent only — sibling batches own disjoint sets):
* p42 future development (mapped construction-activity hinnang)
* p44 rental potential (mapped apartment-stock hinnang)
* p45 adaptability (ALWAYS None — per-building fact, do not fake)
* p47 zoning laws (ALWAYS None — per-parcel decree, do not fake)
* p74 rental restrictions (ALWAYS None — per-parcel decree, do not fake)

HONESTY (AGENTS.md section 7.2): the Rahandusministeerium PLANK
register and the Tallinna Planeeringute Register (TPR) are NOT in
the 2026-09-12 snapshot, so p45/p47/p74 stay NULL with a buyer-check
reason, and p42/p44 are coarse OSM-derived PROXIES. Reasons say
"hinnang" (estimate) and name what is missing — never a planning
decision, a rent register, or euros.

Style mirrors services/scoring/livability.py and sibling batch
dims_group08b.py (#168): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #168).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
footprints and construction areas, PR #118):
* dev predicate (landuse=construction OR building=construction):
  1053 kept county-wide, merging to 518 deduped sites (156 in the
  Tallinn window) — sparse enough for a nearest-distance dim AND
  the map (apps/web/lib/layers_group05a.ts). Closed-ring export
  duals collapse to one bbox center (see batch_g05a_plans.py
  read_site_points); untagged referrer nodes drop out.
* apt predicate (building=apartments ONLY): 13952 kept county-wide,
  merging to 6842 deduped footprints (5827 in the Tallinn window).
  Staircase entrances and ADS address points carry no building tag,
  so one footprint casts exactly one vote. Student-pressure tags
  (dormitory/university) are OUT: p386 rentbleed's signal (#133).
* adaptability: OSM maps footprints, never remodelability (EHR
  series, load-bearing walls) — nothing to calibrate against.
* zoning: OSM landuse=* is descriptive (what is built), never the
  prescriptive PLANK/TPR decree — painting it as zoning would be
  fake precision. Commercial-zone nearness stays p223's proxy.
* rental restrictions: 25 tourism=apartment objects are short-stay
  SUPPLY, not restriction — zero signal by construction.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p42 bands track construction lumpiness loosely (single sites are
  sparse: <=200 m scores 80, <=500 m 65, <=1 km 50, <=2 km 35,
  beyond 30 with a weak reason). Under 200 m the reason flags the
  upside AND the crane-nuisance check; the dim never issues a plan
  ruling ("kontrolli planeeringute registrist", never kehtestatud).
* p44 bands track stock density loosely (apartments are dense in
  town: <=100 m scores 85, <=250 m 75, <=500 m 60, <=1 km 45,
  beyond 30 with a weak reason). The dim never issues euros
  ("hinnang, mitte üüriregister").
* p45/p47/p74 return None for EVERY input including missing
  origin: inventing a gradient from zero signal would be fake
  precision (OTA PR #131 precedent). The reasons point at the
  EHR/listing, PLANK/TPR-register and KOV checks the buyer must do
  instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP05A_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP05A_POI_KIND, centroiding way
geometries to points (sites/stock are ways/relations; raw way
nodes would multi-count — residual twin risk per PR #118 must be
noted by the hook author), and rebalancing livability.WEIGHTS must
be one joint change across all parameter batches — existing tests
pin set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break
every sibling.
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
# Radii are judgment calls: construction sites sparse (1.5 km search),
# apartment stock dense in town (800 m). Both node[...] and way[...]
# lines are required (nwr/ parity): sites/stock are ways/relations;
# node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP05A_OVERPASS_FRAGMENT = """
  node["landuse"="construction"](around:1500,{lat},{lon});
  node["building"~"construction|apartments"](around:1500,{lat},{lon});
  way["landuse"="construction"](around:1500,{lat},{lon});
  way["building"~"construction|apartments"](around:1500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "devsite" = mapped construction site for the development dim;
#: "apartstock" = mapped apartment building for the rental dim
#: (dormitory/university stay p386 rentbleed's — zero overlap here).
GROUP05A_POI_KIND = [
    ("landuse", {"construction": "devsite"}),
    ("building", {"construction": "devsite", "apartments": "apartstock"}),
]


def _first_val(value) -> str:
    return str(value).split(";")[0].strip() if value is not None else ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 5-batch-A kind matching the OSM tags, else None. Pure.

    landuse=construction and building=construction map to devsite;
    building=apartments maps to apartstock; entrances, addresses and
    student-pressure tags (dormitory/university) map to None.
    """
    tags = tags or {}
    if _first_val(tags.get("landuse")) == "construction":
        return "devsite"
    b = _first_val(tags.get("building"))
    if b == "construction":
        return "devsite"
    if b == "apartments":
        return "apartstock"
    return None


# ---------------------------------------------------------------------------
# p42: future development (mapped-construction-activity hinnang).
# ---------------------------------------------------------------------------

def dim_ehitus(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p42: development-upside goodness from nearest mapped site."""
    if not origin or pois is None:
        return None, "Ehitusinfo puudub (planeeringute hetktõmmis)"
    m = _nearest_m(origin, pois, {"devsite"})
    if m is None:
        return 30, "Ehitusplats 1,5 km raadiuses kaardistamata (hinnang, nõrk); plaani kontrolli planeeringute registrist"
    s = _band(m, [(200, 80), (500, 65), (1000, 50), (2000, 35)])
    assert s is not None
    if s <= 50:
        return s, "Arengupotentsiaal (hinnang): lähim ehitusplats %s — kaugel; planeeringuotsust mõõdetud pole" % _fmt_m(m)
    return s, "Arengupotentsiaal (hinnang): ehitus %s — piirkond areneb (kraanamüra võimalik)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p44: rental potential (mapped-apartment-stock hinnang).
# ---------------------------------------------------------------------------

def dim_korterstock(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p44: rental-market goodness from nearest mapped apartment stock."""
    if not origin or pois is None:
        return None, "Korterelamute info puudub (hoonete hetktõmmis)"
    m = _nearest_m(origin, pois, {"apartstock"})
    if m is None:
        return 30, "Korterelamu 800 m raadiuses kaardistamata (hinnang, nõrk); üüri kontrolli kuulutustelt, mitte kaardilt"
    s = _band(m, [(100, 85), (250, 75), (500, 60), (1000, 45)])
    assert s is not None
    if s <= 45:
        return s, "Üüripotentsiaal (hinnang): lähim korterelamu %s — kaugel; eurosid mõõdetud pole" % _fmt_m(m)
    return s, "Üüripotentsiaal (hinnang): korterelamustik %s — likviidne üüriturg (mitte üüriregister)" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p45/p47/p74: documented no-map registry NULLs (OTA PR #131 precedent).
# Each is a per-building/per-parcel legal fact with no honest area
# signal; the scorer reports the gap with a concrete buyer check
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_adapt(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p45: NULL — adaptability needs EHR structural facts (no map)."""
    return None, "Kohandatavus teadmata (EHR seeria/kandvad seinad; hoone jalajälg ei ütle ümberehitust — kontrolli kuulutusest/EHR-st)"


def dim_zoning(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p47: NULL — zoning needs the PLANK/TPR decree per parcel (no map)."""
    return None, "Sihtotstarve teadmata (PLANK/TPR krundi-põhine; OSM maakasutus on kirjeldav, mitte määrus — kontrolli planeeringute registrist)"


def dim_rentrestr(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p74: NULL — rental restrictions need the KOV decree (no map)."""
    return None, "Üüripiirangud teadmata (KOV määrus/Riigi Teataja; lühiajalise üüri reeglid — kontrolli KOV-st)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP05A_DIMS: Dict[str, Tuple[str, object]] = {
    "adapt": ("Kohandatavus (kontroll)", dim_adapt),
    "zoning": ("Tsooniseadus (kontroll)", dim_zoning),
    "rentrestr": ("Üüripiirangud (kontroll)", dim_rentrestr),
    "ehitus": ("Ehitusaktiivsus (proksi)", dim_ehitus),
    "korterstock": ("Korterelamustik (proksi)", dim_korterstock),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP05A_PARAM_IDS = {
    "adapt": 45,
    "zoning": 47,
    "rentrestr": 74,
    "ehitus": 42,
    "korterstock": 44,
}


def score_group05a(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 5-batch-A dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP05A_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
