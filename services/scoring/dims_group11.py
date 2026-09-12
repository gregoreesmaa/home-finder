"""Group 11 OSM livability dimensions: batch B2 (issue #97).

Params (this agent only — sibling batches own disjoint sets):
* p88  school bus route accessibility
* p101 specialized recreation proximity
* p124 specialized medical access
* p190 foraging and natural resources access
* p317 local park maintenance and enforcement (stub: unmappable, see below)

Style mirrors services/scoring/livability.py: every scorer is pure and
offline-tested — (origin, pois) -> (Optional[int 0..100], Estonian reason).
Network lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Tag verification (2026-09-12, done once by the author, NOT at runtime):
* taginfo global counts: amenity=hospital 217361, amenity=dentist 160043,
  leisure=sports_centre 268586 / stadium 52022 / swimming_pool 3043612 /
  water_park 13310 / ice_rink 10040 / golf_course 39626 /
  fitness_centre 107554 / sports_hall 47746, natural=scrub 5713164,
  natural=heath 676891 — all established tags.
* One Harjumaa Overpass count (bbox 58.9,23.5,59.7,25.6, osm base
  2026-09-12T14:06:51Z): 2353 matching objects across the three selectors.
* route=school_bus has 2 uses GLOBALLY: real school-bus routes are not
  mapped, so p88 is a labelled school+bus-stop PROXY (every reason says
  "hinnang"/estimate, never a claimed route).
* p317 is unmappable: no OSM tag encodes park upkeep/enforcement quality,
  so it is an honest stub like livability.dim_air. The spare params
  (p11/p17/p51/p53/p54) are undefined in this repo (no parameters doc),
  so no substitute is invented.

Integration (deliberately NOT done here): extending livability.OVERPASS_QUERY
with GROUP11_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP11_POI_KIND,
and rebalancing livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be
one joint change across all 9 parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every sibling.
The live-path cache key (liv_pois3) needs a version bump at that point.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _band, _count_within_m, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# Radii are judgment calls: hospitals/specialists are sparse (5 km),
# suburban sports facilities sit further out than corner shops (2 km),
# scrub/heath matches the existing natural=wood radius (1.5 km).
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP11_POI_KIND = [
    ("amenity", {"hospital": "hospital", "dentist": "dentist"}),
    ("leisure", {"sports_centre": "rec_special", "sports_hall": "rec_special",
                 "stadium": "rec_special", "swimming_pool": "rec_special",
                 "water_park": "rec_special", "ice_rink": "rec_special",
                 "golf_course": "rec_special", "fitness_centre": "rec_special"}),
    ("natural", {"scrub": "scrub", "heath": "scrub"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP11_OVERPASS_FRAGMENT = """
  node["amenity"~"hospital|dentist"](around:5000,{lat},{lon});
  node["leisure"~"sports_centre|sports_hall|stadium|swimming_pool|water_park|ice_rink|golf_course|fitness_centre"](around:2000,{lat},{lon});
  node["natural"~"scrub|heath"](around:1500,{lat},{lon});
  way["amenity"~"hospital|dentist"](around:5000,{lat},{lon});
  way["leisure"~"sports_centre|sports_hall|stadium|swimming_pool|water_park|ice_rink|golf_course|fitness_centre"](around:2000,{lat},{lon});
  way["natural"~"scrub|heath"](around:1500,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 11 kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP11_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p88: school bus route accessibility (labelled proxy — see module docstring).
# School leg uses amenity=school only (kindergartens have no school bus);
# the bus leg reuses the existing bus_stop kind, so no new fetch is needed
# for it.
# ---------------------------------------------------------------------------

def dim_school_bus(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p88: school within reach AND a bus stop to serve it (estimate)."""
    if not origin or pois is None:
        return None, "Koolibussi info puudub"
    m_school = _nearest_m(origin, pois, {"school"})
    if m_school is None:
        return 15, "Kool üle 1,5 km – koolibussiühendus ebaselge (hinnang)"
    base = _band(m_school, [(600, 100), (1000, 85), (1500, 70)])
    assert base is not None
    if _count_within_m(origin, pois, {"bus_stop"}, 500) >= 1:
        return base, "Koolibussi hinnang: kool %s, bussipeatus 500 m raadiuses" % _fmt_m(m_school)
    m_stop = _nearest_m(origin, pois, {"bus_stop"})
    capped = min(base, 45)
    if m_stop is None:
        return capped, "Koolibussi hinnang: kool %s, bussipeatus üle 1,5 km" % _fmt_m(m_school)
    return capped, "Koolibussi hinnang: kool %s, lähim peatus %s" % (_fmt_m(m_school), _fmt_m(m_stop))


# ---------------------------------------------------------------------------
# p101: specialized recreation proximity (stadium / pool / sports centre…).
# Generic parks/playgrounds stay in the green dim; this is the specialised
# tier only.
# ---------------------------------------------------------------------------

def dim_rec_special(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p101: nearest specialised sports facility (OSM leisure=* tier)."""
    if not origin or pois is None:
        return None, "Erisportimise info puudub"
    m = _nearest_m(origin, pois, {"rec_special"})
    if m is None:
        return 25, "Spordikeskus/ujula/staadion üle 2 km"
    s = _band(m, [(800, 100), (1500, 80), (2000, 60)])
    return s, "Lähim erisport (staadion/ujula/spordikeskus) %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p124: specialized medical access (hospital / dentist; GP-level clinic and
# doctors stay in the generic services dim).
# ---------------------------------------------------------------------------

def dim_medical_special(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """p124: nearest hospital or dentist (sparse tier, 5 km window)."""
    if not origin or pois is None:
        return None, "Eriarstiabi info puudub"
    m = _nearest_m(origin, pois, {"hospital", "dentist"})
    if m is None:
        return 25, "Haigla/hambaarst üle 5 km"
    s = _band(m, [(2000, 100), (3500, 80), (5000, 60)])
    return s, "Lähim haigla/hambaarst %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p190: foraging and natural resources access (forest + scrub/heath for
# berries/mushrooms; farmland is excluded — no public access right signal).
# ---------------------------------------------------------------------------

def dim_forage(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p190: nearest forest/scrub foraging land (mets/võsa)."""
    if not origin or pois is None:
        return None, "Korjealade info puudub"
    m = _nearest_m(origin, pois, {"forest", "scrub"})
    if m is None:
        return 20, "Korjeala (mets/võsa) üle 1,5 km"
    s = _band(m, [(600, 100), (1000, 80), (1500, 60)])
    return s, "Lähim korjeala (mets/võsa) %s" % _fmt_m(m)


# ---------------------------------------------------------------------------
# p317: local park maintenance and enforcement — honest stub (dim_air
# precedent). No OSM tag encodes upkeep quality; a guess would punish
# well-kept areas and reward neglected ones at random.
# ---------------------------------------------------------------------------

def dim_park_upkeep() -> Score:
    """p317: stub — no open data source for upkeep quality."""
    return None, "Pargihoolduse info puudub (avatud andmed puuduvad)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP11_DIMS: Dict[str, Tuple[str, Callable[..., Score]]] = {
    "school_bus": ("Koolibussiühendus", dim_school_bus),
    "rec_special": ("Erisport ja vaba aeg", dim_rec_special),
    "medical_special": ("Eriarstiabi", dim_medical_special),
    "forage": ("Korjealad (seen/mari)", dim_forage),
    "park_upkeep": ("Pargihooldus", dim_park_upkeep),
}


def score_group11(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 11 dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP11_DIMS.items():
        v, reason = fn(origin, pois) if param != "park_upkeep" else fn()
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
