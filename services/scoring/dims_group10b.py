"""Group 10 utility-grid OSM proximity dimensions, batch B (issue #107).

Params (this agent only — sibling batch #105/#106 owns p52/p135/p211/p214/p404):
* p56  power grid reliability (mapped-substation redundancy density)
* p213 microgrid and community solar (mapped solar-generator density)
* p216 cell tower shadow zones (mapped-mast coverage gap, inverted)
* p420 emergency services grid (mapped response-site proximity)
* p476 underground utility clustering (mapped underground-cable density)

HONESTY (AGENTS.md section 7.2): registry reliability data (SAIDI/outage
statistics, Elering/Elektrilevi feeds, measured broadband or response
times) is NOT in the 2026-09-12 snapshot, so every scorer below is an
honestly-labeled OSM-derived PROXY. Titles, legends, and reasons must say
"kaardistatud" (mapped) and "hinnang" (estimate), never claim measured
reliability, generation output, signal coverage, or response times.

Style mirrors services/scoring/livability.py and the sibling batch-B
module dims_group10.py: every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
only in livability.fetch_pois; this module adds no network calls, only
the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or dims_group10):
a future central hook may import this module alongside them, and
importing either here would turn that into a cycle (same precedent as
batch B3, PR #100, and sibling batch #106).

Tag verification (2026-09-12, done once by the author with osmium
tags-count against ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf,
NOT at runtime):
* power=substation: 641 tag uses (sibling #106 counted 1120 features
  node+way combined; either way dense enough for a redundancy count).
* power=generator: 1853 uses; generator:source=solar: 1787 uses —
  rooftop PV nodes, dense enough for a neighbourhood solar count.
* man_made=mast: 219 points (sibling-verified; shared with p52).
* amenity=fire_station: 30; amenity=police: 21; amenity=hospital: 21;
  emergency=ambulance_station: 5 (~77 response sites; the 723
  emergency=fire_hydrant nodes are hydrants, NOT response sites, and
  are deliberately excluded).
* power=cable: 41 uses; location=underground: 205 uses (57 of them
  power-tagged) — sparse, so absence scores neutral-honest, never zero.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p56 counts substations within 3 km (redundancy depth) instead of
  nearest distance, so it stays disjoint from sibling p211 (nearest
  substation). More mapped feeds nearby = higher score; zero mapped
  feeds = 35, not 15, because rural feeds are thinly mapped yet the
  grid still reaches the house.
* p213 counts solar generators within 2 km. These are overwhelmingly
  rooftop PV nodes, so the metric is really "mapped neighbourhood PV
  uptake" — the reason says so instead of claiming community-microgrid
  capacity, which OSM cannot see.
* p216 counts masts within 5 km (coverage gap) instead of nearest
  distance, so it stays disjoint from sibling p52 (nearest mast).
  Zero masts in 5 km = 25 (possible shadow zone); the reason stresses
  that unmapped masts and terrain also shape real coverage.
* p420 scores nearest mapped response site (fire/police/hospital/
  ambulance). Clinics (amenity=clinic, 54) are excluded: they are
  daytime care, not the emergency grid. Hydrants/defibrillators are
  equipment, not dispatchable sites — also excluded.
* p476 counts mapped underground power features within 1 km. Burial is
  rarely mapped, so absence = 55 with an explicit "may exist unmapped"
  reason — never a fake-buried low score, never a fake-clear high one.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP10B_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP10B_POI_KIND (solar/underground-aware
via kinds_from_tags, so the hook must route power tags through it),
and rebalancing livability.WEIGHTS must be one joint change across all
parameter batches — existing tests pin set(WEIGHTS) exactly, so
per-batch WEIGHTS edits would break every sibling.
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


def _count_within_m(origin: Tuple[float, float], pois: List[dict],
                    kinds: set, radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radii are judgment calls: masts and response sites are sparse (5 km),
# substations mid-density (3 km), rooftop PV denser (2 km), buried cables
# sparse but hyperlocal (1 km).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP10B_OVERPASS_FRAGMENT = """
  node["man_made"="mast"](around:5000,{lat},{lon});
  node["power"="substation"](around:3000,{lat},{lon});
  node["power"="generator"](around:2000,{lat},{lon});
  node["power"~"cable|minor_cable"](around:1000,{lat},{lon});
  node["amenity"~"fire_station|police|hospital"](around:5000,{lat},{lon});
  node["emergency"="ambulance_station"](around:5000,{lat},{lon});
  way["power"="substation"](around:3000,{lat},{lon});
  way["power"="generator"](around:2000,{lat},{lon});
  way["power"~"cable|minor_cable"](around:1000,{lat},{lon});
  way["amenity"~"fire_station|police|hospital"](around:5000,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: power=generator needs the solar-aware kinds_from_tags below (static
#: mapping alone cannot split rooftop PV from diesel backup), and buried
#: power features need the location=underground rule — so the central hook
#: must route power tags through kinds_from_tags, not this table alone.
GROUP10B_POI_KIND = [
    ("man_made", {"mast": "mast"}),
    ("power", {"substation": "substation", "generator": "generator",
               "cable": "ugutil", "minor_cable": "ugutil"}),
    ("amenity", {"fire_station": "emergency", "police": "emergency",
                 "hospital": "emergency"}),
    ("emergency", {"ambulance_station": "emergency"}),
]

#: OSM power values that are buried by definition (mapped as cable ways).
_CABLE_VALUES = {"cable", "minor_cable"}


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 10-batch-B kind matching the OSM tags, else None. Pure.

    Solar-aware: power=generator with generator:source=solar maps to
    "solargen" (p213); any other generator stays "generator" (unused by
    scorers, kept so the hook can tell PV apart from backup diesel).
    Burial-aware: any power feature tagged location=underground maps to
    "ugutil" (p476) even when it is not a cable way.
    """
    tags = tags or {}
    power_val = str(tags.get("power", "")).split(";")[0]
    if power_val == "generator":
        if str(tags.get("generator:source", "")).split(";")[0] == "solar":
            return "solargen"
        return "generator"
    if power_val in _CABLE_VALUES:
        return "ugutil"
    # Buried substations stay substations (p56 feeds); only other buried
    # power features count as underground utilities (p476).
    if (power_val and power_val != "substation"
            and str(tags.get("location", "")) == "underground"):
        return "ugutil"
    for tagkey, mapping in GROUP10B_POI_KIND:
        val = str(tags.get(tagkey, "")).split(";")[0]
        if val in mapping:
            return mapping[val]
    return None


# ---------------------------------------------------------------------------
# p56: power grid reliability (mapped-substation redundancy proxy).
# ---------------------------------------------------------------------------

#: Substation-count radius in metres (mid-density tier, matches p211).
GRID_RADIUS_M = 3000.0


def dim_grid_reliability(origin: Optional[Tuple[float, float]],
                         pois: Optional[List[dict]]) -> Score:
    """p56: mapped substations within 3 km (redundancy depth, not distance)."""
    if not origin or pois is None:
        return None, "Elektrivõrgu info puudub"
    n = _count_within_m(origin, pois, {"substation"}, GRID_RADIUS_M)
    if n == 0:
        return 35, ("Kaardistatud alajaamu 3 km raadiuses pole "
                    "(varustuskindluse hinnang, mitte mõõdetud katkestusstatistika)")
    s = _band(n, [(1, 60), (2, 80), (float("inf"), 100)])
    return s, ("Kaardistatud alajaamu 3 km raadiuses: %d "
               "(varustuskindluse hinnang, mitte mõõdetud katkestusstatistika)") % n


# ---------------------------------------------------------------------------
# p213: microgrid and community solar (mapped rooftop-PV uptake proxy).
# ---------------------------------------------------------------------------

#: Solar-generator count radius in metres (rooftop PV is dense in suburbs).
SOLAR_RADIUS_M = 2000.0


def dim_solar(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p213: mapped solar generators within 2 km (uptake proxy, not output)."""
    if not origin or pois is None:
        return None, "Päikeseenergia info puudub"
    n = _count_within_m(origin, pois, {"solargen"}, SOLAR_RADIUS_M)
    if n == 0:
        return 45, ("Kaardistatud päikesegeneraatoreid 2 km raadiuses pole "
                    "(naabruskonna PV-hinnang, mitte mõõdetud toodang)")
    s = _band(n, [(2, 65), (5, 80), (float("inf"), 100)])
    return s, ("Kaardistatud päikesegeneraatoreid 2 km raadiuses: %d "
               "(naabruskonna PV-hinnang, mitte mõõdetud toodang)") % n


# ---------------------------------------------------------------------------
# p216: cell tower shadow zones (mapped-mast coverage-gap proxy, inverted).
# ---------------------------------------------------------------------------

#: Mast-gap radius in metres (sparse tier, shared with sibling p52).
SHADOW_RADIUS_M = 5000.0


def dim_shadow(origin: Optional[Tuple[float, float]],
               pois: Optional[List[dict]]) -> Score:
    """p216: mapped masts within 5 km (gap = possible shadow zone)."""
    if not origin or pois is None:
        return None, "Mobiililevi katvuse info puudub"
    n = _count_within_m(origin, pois, {"mast"}, SHADOW_RADIUS_M)
    if n == 0:
        return 25, ("Võimalik leviauk: kaardistatud mobiilimasti 5 km "
                    "raadiuses pole (hinnang, mitte mõõdetud levi)")
    s = _band(n, [(1, 55), (3, 80), (float("inf"), 100)])
    return s, ("Kaardistatud mobiilimaste 5 km raadiuses: %d "
               "(katvuse hinnang, mitte mõõdetud levi)") % n


# ---------------------------------------------------------------------------
# p420: emergency services grid (mapped response-site proximity proxy).
# ---------------------------------------------------------------------------

#: Response-site search radius in metres (sparse tier).
EMERGENCY_RADIUS_M = 5000.0


def dim_emergency(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p420: nearest mapped response site (fire/police/hospital/ambulance)."""
    if not origin or pois is None:
        return None, "Päästeteenistuse info puudub"
    m = _nearest_m(origin, pois, {"emergency"})
    if m is None or m > EMERGENCY_RADIUS_M:
        return 30, ("Kaardistatud päästeteenistus (tuletõrje/politsei/haigla) "
                    "üle 5 km (reageerimisaja hinnang, mitte mõõdetud)")
    s = _band(m, [(800, 100), (1500, 85), (3000, 65)])
    return s, ("Lähim kaardistatud päästeteenistus %s "
               "(reageerimisaja hinnang, mitte mõõdetud)") % _fmt_m(m)


# ---------------------------------------------------------------------------
# p476: underground utility clustering (mapped buried-cable proxy).
# ---------------------------------------------------------------------------

#: Buried-cable count radius in metres (hyperlocal: burial clusters by street).
UG_RADIUS_M = 1000.0


def dim_underground(origin: Optional[Tuple[float, float]],
                    pois: Optional[List[dict]]) -> Score:
    """p476: mapped underground power features within 1 km (sparse tier)."""
    if not origin or pois is None:
        return None, "Maa-aluste kaablite info puudub"
    n = _count_within_m(origin, pois, {"ugutil"}, UG_RADIUS_M)
    if n == 0:
        return 55, ("Kaardistatud maa-aluseid kaableid läheduses pole "
                    "(harva kaardistatud; võib esineda kaardistamata)")
    s = _band(n, [(1, 75), (float("inf"), 90)])
    return s, ("Kaardistatud maa-aluseid kaableid 1 km raadiuses: %d "
               "(tormikindluse hinnang)") % n


#: Registry for the central weight-rebalance follow-up: (dims key, param id, fn).
GROUP10B_DIMS = (
    ("gridrel", "p56", dim_grid_reliability),
    ("solar", "p213", dim_solar),
    ("shadow", "p216", dim_shadow),
    ("emergency", "p420", dim_emergency),
    ("underground", "p476", dim_underground),
)


def score_group10b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """All five Group 10 batch-B dims for one listing (entry point for the
    weight-rebalance follow-up; keys match GROUP10B_DIMS)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP10B_DIMS}
