"""Group 15 education + Group 11 leftover dimensions (issue #116).

Five pure, offline-tested scorers in the `dim_*` style of livability.py:
each takes `(origin, pois)` and returns `(score|None, Estonian reason)`.
Scores are absolute 0..100; `None` is returned ONLY when the origin or
the POI list itself is missing (never as a guess).

Params (this agent only — sibling batches own disjoint sets):

* p130 school catchment lotteries -> school-CHOICE density proxy
  (deduped `amenity=school` count within 1.5 km).
* p314 school redistricting vulnerability -> single-dependency proxy
  (deduped `amenity=school` count within 2 km; few schools = exposed).
* p338 aquatic weed management programs -> inland-water proximity proxy
  (`natural=water` / `water=pond|lake|reservoir|basin|river`).
* p442 seasonal festival disruption -> event-venue proximity, INVERTED
  (`amenity=events_venue|marketplace`, `tourism=attraction`).
* p462 stadium and event traffic -> stadium proximity, INVERTED
  (`leisure=stadium` only; pitches do not draw event traffic).

HONESTY (load-bearing, AGENTS.md section 7.2): the EHIS lottery /
redistricting internals, the weed-management activity, and the festival
calendar are NOT in the 2026-09-12 snapshot, so every title, legend,
source and reason says "proksi"/"hinnang" (proxy/estimate) and names
the OSM tags measured. p130/p314 are NEVER presented as official
lottery odds; p462/p442 state their green/red direction explicitly
(green = far/calm, red = near/disruption).

Tag verification (2026-09-12, local snapshot files only, no network):
* derived-schools.json: 342 amenity=school (301 unique coords; 41
  node+way-centre dupes -> scorers dedupe, documented below).
* harju-amenities.geojson (147295 features): leisure=stadium 55 (all
  polygons/ways, centroids used), amenity=events_venue 41,
  amenity=marketplace 38, tourism=attraction 98, natural=water 18
  (Multi)Polygons/Lines + water=pond|basin|river 12.
* Disjoint from sibling batch B1 (#98): theatre/museum/gallery stay
  p89 culture, community_centre/townhall stay p87 community.

Calibration locked 2026-09-12 from snapshot probes
(Balti/Viru/Kadriorg/Oismae/Lasnamae/Viimsi/rural/airport):
* p130 100*S/(S+6), S = schools/1.5km: Balti ~85, Lasnamae ~57,
  Viimsi ~50, airport ~40, rural 0.
* p314 100*S/(S+2), S = schools/2km: Balti ~97, Lasnamae ~86,
  Viimsi ~75, rural 0 (discriminates the sparse end by design).
* p338 100*600/(d+600): Balti (888 m) 40, Viru (1720 m) 26.
* p442 100*d/(d+500): Balti (219 m) 30, rural (12.6 km) 96.
* p462 100*d/(d+800): Viru (306 m, Kalevi) 28, Balti (2150 m) 73.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP15_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP15_POI_KIND, and rebalancing
livability.WEIGHTS (+ apps/web/lib/weights.ts sync) must be one joint
change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
`school` and `water` kinds already flow through the live path;
`stadium`/`venue` need the mapping below at that point.
"""

from typing import Callable, Dict, List, Optional, Tuple

from livability import _count_within_m, _fmt_m, _nearest_m

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

# ---------------------------------------------------------------------------
# Calibration (mirrored in apps/web/lib/layers_group15.ts GROUP15_CAL and
# scripts/build/batch_g15_edu.py G15_CAL — drift-checked by tests).
# ---------------------------------------------------------------------------

#: Schools within this radius count as catchment choice (p130).
CHOICE_RADIUS_M = 1500.0
#: Saturation midpoint for the choice count (p130).
CHOICE_HALF = 6.0
#: Wider radius for the dependency proxy (p314).
DEPEND_RADIUS_M = 2000.0
#: Saturation midpoint for the dependency count (p314).
DEPEND_HALF = 2.0
#: Water-amenity half-distance in metres (p338): 50 at 600 m.
WATER_HALF_M = 600.0
#: Festival-quiet half-distance in metres (p442): 50 at 500 m.
VENUE_HALF_M = 500.0
#: Stadium-quiet half-distance in metres (p462): 50 at 800 m.
STADIUM_HALF_M = 800.0

# ---------------------------------------------------------------------------
# New POI kinds + Overpass fragment for the live path.
# `school` and `water` already exist in livability._POI_KIND; only
# `stadium` and `venue` are new. Stadium/venue radii are wider than the
# shared 1500 m amenity window (stadiums are sparse county-wide).
# ---------------------------------------------------------------------------

#: Extra (tagkey, {tagvalue: kind}) rows for livability._POI_KIND.
GROUP15_POI_KIND = [
    ("leisure", {"stadium": "stadium"}),
    ("amenity", {"events_venue": "venue", "marketplace": "venue"}),
    ("tourism", {"attraction": "venue"}),
]

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP15_OVERPASS_FRAGMENT = """
  node["leisure"="stadium"](around:3000,{lat},{lon});
  node["amenity"~"events_venue|marketplace"](around:2000,{lat},{lon});
  node["tourism"="attraction"](around:2000,{lat},{lon});
  way["leisure"="stadium"](around:3000,{lat},{lon});
  way["amenity"~"events_venue|marketplace"](around:2000,{lat},{lon});
  way["tourism"="attraction"](around:2000,{lat},{lon});"""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 15 kind matching the OSM tags, else None. Pure."""
    for tagkey, mapping in GROUP15_POI_KIND:
        val = (tags or {}).get(tagkey, "").split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


def _saturate(count: int, half: float) -> int:
    """Unweighted count -> 0..100: 100*S/(S+half); 0 stays 0 (evidence)."""
    return int(round(100.0 * count / (count + half)))


def _deduped(pois: List[dict], kinds: set) -> List[dict]:
    """POIs of the given kinds with identical coords collapsed to one.

    The snapshot carries node+way-centre dupes (41 school pairs); without
    this, counts double-book a single school. 1e-6 deg is ~10 cm, so no
    two real schools ever share a key.
    """
    seen: set = set()
    out: List[dict] = []
    for p in pois:
        if p.get("kind") not in kinds or p.get("lat") is None:
            continue
        key = (p["kind"], round(p["lat"], 6), round(p["lon"], 6))
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _count_deduped(origin: Tuple[float, float], pois: List[dict],
                   kinds: set, radius_m: float) -> int:
    return _count_within_m(origin, _deduped(pois, kinds), kinds, radius_m)


# ---------------------------------------------------------------------------
# p130: school catchment lotteries -> school-CHOICE density proxy.
# More mapped schools within walking range = more catchment options.
# ---------------------------------------------------------------------------

def dim_school_choice(origin: Optional[Tuple[float, float]],
                      pois: Optional[List[dict]]) -> Score:
    """p130: catchment-choice proxy (OSM school density, NOT lottery odds)."""
    if not origin or pois is None:
        return None, "Koolivaliku info puudub"
    n = _count_deduped(origin, pois, {"school"}, CHOICE_RADIUS_M)
    if n == 0:
        return 0, "Koolivaliku proksi: kaardistatud koole 1,5 km raadiuses pole"
    return (_saturate(n, CHOICE_HALF),
            "Koolivaliku proksi: %d kooli 1,5 km raadiuses (OSM)" % n)


# ---------------------------------------------------------------------------
# p314: school redistricting vulnerability -> single-dependency proxy.
# Homes served by few schools within 2 km are most exposed when municipal
# catchment boundaries shift; dense school cover reads stable.
# ---------------------------------------------------------------------------

def dim_redistrict(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p314: redistricting-exposure proxy (OSM school density, inverted)."""
    if not origin or pois is None:
        return None, "Piirimuutuste info puudub"
    n = _count_deduped(origin, pois, {"school"}, DEPEND_RADIUS_M)
    if n == 0:
        return 0, "Haavatavuse proksi: kaardistatud koole 2 km raadiuses pole"
    return (_saturate(n, DEPEND_HALF),
            "Haavatavuse proksi: %d kooli 2 km raadiuses (OSM)" % n)


# ---------------------------------------------------------------------------
# p338: aquatic weed management programs -> inland-water proximity proxy.
# Waterfront amenity framing (green near): managed urban water is the
# desirable end. Weed-management ACTIVITY is not in OSM — said plainly.
# ---------------------------------------------------------------------------

def dim_water_weed(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p338: inland-water proximity proxy (management activity unknown)."""
    if not origin or pois is None:
        return None, "Veekogude info puudub"
    best = _nearest_m(origin, pois, {"water"})
    if best is None:
        return 0, "Veekogu-proksi: kaardistatud veekogu läheduses pole"
    s = int(round(100.0 * WATER_HALF_M / (best + WATER_HALF_M)))
    return s, "Veekogu-proksi: lähim veekogu %s (hooldusinfo OSM-is puudub)" % _fmt_m(best)


# ---------------------------------------------------------------------------
# p442/p462: INVERTED venue/stadium proximity (red near, green far).
# ---------------------------------------------------------------------------

def _quiet(d_m: float, half_m: float) -> int:
    """Distance -> calmness 0..100: 0 on the source, 50 at half_m."""
    return int(round(100.0 * d_m / (d_m + half_m)))


def dim_festival(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p442: festival-disruption proxy (near venue = low score, red)."""
    if not origin or pois is None:
        return None, "Ürituspaikade info puudub"
    m = _nearest_m(origin, pois, {"venue"})
    if m is None:
        return 100, "Festivali-proksi: kaardistatud ürituspaik 2 km+ kaugusel"
    return (_quiet(m, VENUE_HALF_M),
            "Festivali-proksi: lähim ürituspaik %s" % _fmt_m(m))


def dim_stadium(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p462: stadium-traffic proxy (near stadium = low score, red)."""
    if not origin or pois is None:
        return None, "Staadionite info puudub"
    m = _nearest_m(origin, pois, {"stadium"})
    if m is None:
        return 100, "Staadioni-proksi: kaardistatud staadion 3 km+ kaugusel"
    return (_quiet(m, STADIUM_HALF_M),
            "Staadioni-proksi: lähim staadion %s" % _fmt_m(m))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP15_DIMS: Tuple[Tuple[str, str, Callable], ...] = (
    ("school_choice", "p130", dim_school_choice),
    ("redistrict", "p314", dim_redistrict),
    ("water_weed", "p338", dim_water_weed),
    ("festival", "p442", dim_festival),
    ("stadium", "p462", dim_stadium),
)


def score_group15(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 15 dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP15_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP15_DIMS}
