"""Group 17 municipal-services per-listing dimensions, batch A (issue #177).

Params (this agent only — sibling batches own disjoint sets):
* p60 municipal service schedules (ALWAYS None — per-district schedule fact)
* p187 municipal composting infrastructure (mapped compost-station count hinnang)
* p311 snow plowing priority (mapped grit-bin winter-service count hinnang)
* p312 leaf collection and yard waste (mapped green-waste drop-off count hinnang)
* p347 garbage can storage concealment (ALWAYS None — per-parcel courtyard fact)

HONESTY (AGENTS.md section 7.2): the Tallinna Linnavalitsus / KOV service
registers — waste-collection calendars, street plow-priority classes
(hooldusklassid), courtyard bin-enclosure records — are NOT in the
2026-09-12 snapshot, so p60/p347 stay NULL with a buyer-check reason,
and p187/p311/p312 are coarse OSM-derived PROXIES. Reasons say
"hinnang" (estimate) and name what is missing — never a municipal
capacity ruling, a plow-route register entry, or a collection calendar.

Style mirrors services/scoring/livability.py and sibling batch
dims_group05c.py (#163): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #163).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
jäätmejaam areas, PR #118):
* compost predicate (green/garden-waste recycling centre or bio/food-waste
  recycling): 44 objects county-wide (35 in the Tallinn window:
  Pääsküla, Rahumäe, Pärnamäe, Paljassaare jäätmejaamad + bio/food
  containers). Plain paper/glass/plastic containers stay p54's.
* grit predicate (amenity=grit_bin): 30 objects county-wide (25 in the
  Tallinn window). Deliberately NOT a road-class field: road class
  already scores INVERTED as p446 plow-berm burden
  (services/scoring/dims_group18veg.py) — a second road-class gradient
  would duplicate it with the arrow flipped. winter_service tags: zero
  in the snapshot; Tallinna hooldusklassid: not in the snapshot.
* leaf predicate (any green/garden-waste recycling + green-accepting
  household waste_disposal): 131 objects county-wide (122 in the
  Tallinn window). 555 untagged waste_disposal litter/dog bins drop out
  BY DESIGN (a litter bin is not yard-waste collection).
* service schedules: zero schedule/calendar keys anywhere in the PBF —
  a per-district calendar has no area signal to calibrate.
* bin concealment: zero enclosure/screening keys anywhere in the PBF —
  a per-parcel courtyard attribute has no area signal to calibrate.

Overlap (documented, ehitus/buildout G05A+G05B precedent): the 18 green
centres and the food+green containers sit in BOTH the compost and the
leafdrop source sets (a jäätmejaam both composts and takes yard waste).
kinds_from_tags maps centres and bio/food points to "compostsite"
first, other green points to "leafdrop".

Judgment calls (reviewable per AGENTS.md section 7.5):
* p187/p311/p312 count mapped service points within 800 m (viewshed-style
  saturating reading): >=3 scores 80 (serviced pocket), >=1 scores 65,
  else 45 with an unknown-service reason. Green sits NEAR the service,
  never a municipal register ruling.
* p60/p311-absence and p347 return None / the unknown band for EVERY
  input including missing origin: inventing a gradient from zero signal
  would be fake precision (OTA PR #131 precedent). The reasons point at
  the operator-schedule / viewing check the buyer must do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP17A_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP17A_POI_KIND, centroiding way
geometries to points (jäätmejaamad are ways/relations; raw way
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


def _count_within_m(origin: Tuple[float, float], pois: List[dict], kinds: set,
                    radius_m: float) -> int:
    n = 0
    for p in pois:
        if p.get("kind") in kinds and p.get("lat") is not None:
            if _haversine_m(origin, p["lat"], p["lon"]) <= radius_m:
                n += 1
    return n


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# Radii are judgment calls: service points are neighbourhood-scale, so all
# three dims search 800 m (viewshed precedent). Both node[...] and
# way[...] lines are required (nwr/ parity): jäätmejaamad are
# ways/relations; node-only drops them (PR #118).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP17A_OVERPASS_FRAGMENT = """
  node["amenity"="recycling"](around:800,{lat},{lon});
  node["amenity"="waste_disposal"](around:800,{lat},{lon});
  node["amenity"="grit_bin"](around:800,{lat},{lon});
  way["amenity"="recycling"](around:800,{lat},{lon});
  way["amenity"="waste_disposal"](around:800,{lat},{lon});
  way["amenity"="grit_bin"](around:800,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "compostsite" = green/garden-waste recycling centre or bio/food-waste
#: recycling point (plain paper/glass/plastic containers map to None —
#: they stay p54's); "leafdrop" = other green-waste recycling points +
#: green-accepting household waste_disposal (untagged litter bins map to
#: None — a litter bin is not yard-waste collection); "gritbin" = mapped
#: grit bin (road class is p446's, never re-scored here).
GROUP17A_POI_KIND = [
    ("amenity", {"recycling": "leafdrop", "waste_disposal": "leafdrop",
                 "grit_bin": "gritbin"}),
]


def _first_value(value) -> str:
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 17-batch-A kind matching the OSM tags, else None. Pure.

    amenity=grit_bin maps to "gritbin"; amenity=recycling maps by
    recycling_type + material — green/garden centres and bio/food-waste
    points map to "compostsite", other green/garden points to "leafdrop";
    amenity=waste_disposal maps to "leafdrop" only when it accepts green
    waste (untagged litter bins map to None).
    """
    tags = tags or {}
    if _first_value(tags.get("amenity")) == "grit_bin":
        return "gritbin"
    if _first_value(tags.get("amenity")) == "recycling":
        green = _first_value(tags.get("recycling:green_waste")) == "yes" or \
            _first_value(tags.get("recycling:garden_waste")) == "yes"
        bio = _first_value(tags.get("recycling:food_waste")) == "yes" or \
            _first_value(tags.get("recycling:organic")) == "yes"
        if bio:
            return "compostsite"
        if tags.get("recycling_type") == "centre" and green:
            return "compostsite"
        if green:
            return "leafdrop"
        return None
    if _first_value(tags.get("amenity")) == "waste_disposal":
        if _first_value(tags.get("recycling:green_waste")) == "yes":
            return "leafdrop"
        return None
    return None


# ---------------------------------------------------------------------------
# p187/p311/p312: mapped service-point count hinnangs (viewshed-shaped).
# ---------------------------------------------------------------------------

#: Search radius for the service counts (neighbourhood pocket reading).
SERVICE_RADIUS_M = 800.0


def _service_reading(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]], kinds: set,
                     missing: str, name: str) -> Score:
    """Count mapped service points within 800 m: >=3 -> 80, >=1 -> 65."""
    if not origin or pois is None:
        return None, missing
    n = _count_within_m(origin, pois, kinds, SERVICE_RADIUS_M)
    if n >= 3:
        return 80, "%s (hinnang): %d punkti 800 m raadiuses — teenus lähedal" % (name, n)
    if n >= 1:
        return 65, "%s (hinnang): %d punkt 800 m raadiuses" % (name, n)
    return 45, "%s teadmata (hinnang): 800 m raadiuses kaardistatud punkt puudub" % name


def dim_compost(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p187: composting-service reading from mapped stations/bio points."""
    return _service_reading(
        origin, pois, {"compostsite"},
        "Kompostitaristu info puudub (jäätmejaamade hetktõmmis)",
        "Kompostimine")


def dim_gritbin(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p311: winter-service reading from mapped grit bins."""
    return _service_reading(
        origin, pois, {"gritbin"},
        "Talvise teehoolduse info puudub (hoolduspunktide hetktõmmis)",
        "Talvine teehooldus")


def dim_leafdrop(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p312: yard-waste collection reading from mapped green-waste points."""
    return _service_reading(
        origin, pois, {"leafdrop"},
        "Aiajäätmete kogumise info puudub (kogumispunktide hetktõmmis)",
        "Haljasjäätmete kogumine")


# ---------------------------------------------------------------------------
# p60/p347: documented no-map registry NULLs (OTA PR #131 precedent).
# A district calendar and a courtyard attribute have no honest area
# signal; the scorer reports the gap with a concrete buyer check
# instead of a faked number.
# ---------------------------------------------------------------------------

def dim_sched(origin: Optional[Tuple[float, float]],
              pois: Optional[List[dict]]) -> Score:
    """p60: NULL — service schedules are a per-district calendar (no map)."""
    return None, "Teenuste graafik teadmata (vedaja kogumiskalender; hetktõmmises pole graafikuandmeid — kontrolli vedaja kalendrist)"


def dim_binconceal(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p347: NULL — bin concealment is a per-parcel courtyard fact (no map)."""
    return None, "Prügikastide varjatus teadmata (hoovi varjesein; hetktõmmises pole varjatusandmeid — kontrolli kohapealsel vaatlusel)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP17A_DIMS: Dict[str, Tuple[str, object]] = {
    "sched": ("Teenuste graafik (kontroll)", dim_sched),
    "compost": ("Kompostimine (proksi)", dim_compost),
    "gritbin": ("Talvine teehooldus (proksi)", dim_gritbin),
    "leafdrop": ("Haljasjäätmed (proksi)", dim_leafdrop),
    "binconceal": ("Prügikastide varjatus (kontroll)", dim_binconceal),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP17A_PARAM_IDS = {
    "sched": 60,
    "compost": 187,
    "gritbin": 311,
    "leafdrop": 312,
    "binconceal": 347,
}


def score_group17a(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 17-batch-A dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP17A_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
