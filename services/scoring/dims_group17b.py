"""Group 17 municipal-services per-listing dimensions, batch B (issue #178).

Params (this agent only — sibling batches own disjoint sets):
* p463 sidewalk maintenance laws (ALWAYS None — per-parcel legal fact + pedinfra duplication)
* p464 street sweeping ticketing (ALWAYS None — schedule/enforcement fact, zero keys)
* p465 snow shoveling mandates (ALWAYS None — per-parcel legal fact + gritbin/pedinfra duplication)
* p469 weed and lawn ordinances (mapped mown-lawn count hinnang)

HONESTY (AGENTS.md section 7.2): the Tallinna Linnavalitsus / KOV upkeep
registers — sidewalk-duty records, sweeping calendars and ticketing logs,
shoveling-duty enforcement, lawn-height inspections — are NOT in the
2026-09-12 snapshot, so p463/p464/p465 stay NULL with a buyer-check
reason, and p469 is a coarse OSM-derived PROXY. Reasons say "hinnang"
(estimate) and name what is missing — never a duty record, a sweeping
calendar, or a mowing-inspection ruling.

Style mirrors services/scoring/livability.py and sibling batch
dims_group17a.py (#177): every scorer is pure and offline-tested —
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network
lives only in livability.fetch_pois; this module adds no network
calls, only the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability or sibling
batches): a future central hook may import this module alongside
them, and importing any of them here would turn that into a cycle
(same precedent as batch B3, PR #100, and sibling #177).

Tag verification (2026-09-12, done once by the author with osmium
tags-filter/export against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime;
nwr/ filters throughout — node-only would silently drop way-mapped
lawn polygons, PR #118):
* lawn predicate (landuse=grass, first value): 40499 objects
  county-wide (33524 in the Tallinn window: Mustamäe/Õismäe/Lasnamäe
  panel lawns, Kadriorg verges). 890 untagged relation members drop
  out. landuse=meadow (1799 ways + 79 relations) is OUT by design: a
  meadow is unmown by definition, not a mowing-duty lawn — and it
  stays livability's "park" kind. leisure=garden stays the parks
  layer's amenity side.
* sidewalk duties: zero heakorra-duty keys anywhere in the PBF — and
  mapped footway density (30360 highway=footway ways) already scores
  as pedinfra, so a second footway gradient would duplicate it.
* sweeping/ticketing: sweeping, street_cleaning, cleaning and
  snow_removal keys are ALL zero (nodes + ways) anywhere in the PBF —
  a schedule-plus-enforcement fact has no area signal to calibrate.
* shoveling mandates: winter_service tags are zero in the snapshot
  (G17A corroboration); winter-service proximity already scores via
  gritbin p311 and footway density via pedinfra — a third winter
  gradient would duplicate them.

Overlap (documented, ehitus/buildout G05A+G05B precedent): landuse=grass
also feeds livability's nearest-"park" scorer kind (nature amenity,
p270 yard leg, cooling). Those ask how far green relief is; the lawncare
dim asks how much mown grass surrounds the listing (upkeep-pressure
count, viewshed-shaped). kinds_from_tags maps grass to the NEW "lawn"
kind (never "park"), so the live path stays disjoint.

Judgment calls (reviewable per AGENTS.md section 7.5):
* p469 counts mapped lawns within 800 m (density bands that loosely
  track the half=20 map): >=500 scores 85 (Mustamäe/Õismäe/Lasnamäe
  read 86-92 on the map), >=200 scores 70 (Balti/Viru/Kadriorg read
  81-86), >=1 scores 55 (Pirita n800=158, map reads 50), else 45
  with an unknown-enforcement reason (Nõmme/rural: n800=0, map 0/255).
  Viewshed/G17A bands (>=3/>=1) would saturate: every Tallinn listing
  has hundreds of lawns within 800 m (verified 2026-09-12 probe).
  Green sits NEAR the lawns (maintained streetscape), never a
  mowing-inspection ruling.
* p463/p464/p465 return None for EVERY input including missing
  origin: inventing a gradient from zero signal (or duplicating
  pedinfra/gritbin) would be fake precision (OTA PR #131 precedent).
  The reasons point at the heakorra/operator/KOV check the buyer must
  do instead.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP17B_OVERPASS_FRAGMENT,
livability._POI_KIND with GROUP17B_POI_KIND, centroiding way
geometries to points (lawns are ways/relations; raw way nodes would
multi-count — residual twin risk per PR #118 must be noted by the
hook author), and rebalancing livability.WEIGHTS must be one joint
change across all parameter batches — existing tests pin set(WEIGHTS)
exactly, so per-batch WEIGHTS edits would break every sibling.
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
# Radius is a judgment call: lawns are neighbourhood-scale, so the dim
# searches 800 m (viewshed/G17A precedent). Both node[...] and way[...]
# lines are required (nwr/ parity): lawns are ways/relations; node-only
# drops them (PR #118). No highway/footway source: footway density
# already scores as pedinfra — never re-scored here.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP17B_OVERPASS_FRAGMENT = """
  node["landuse"="grass"](around:800,{lat},{lon});
  way["landuse"="grass"](around:800,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND.
#: "lawn" = mapped mown grass (landuse=grass first value). Meadows map
#: to None (unmown by design — and livability's "park" kind, not ours);
#: footways map to None (pedinfra's, never re-scored here).
GROUP17B_POI_KIND = [
    ("landuse", {"grass": "lawn"}),
]


def _first_value(value) -> str:
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 17-batch-B kind matching the OSM tags, else None. Pure.

    landuse=grass maps to "lawn"; landuse=meadow maps to None (a meadow
    is not a mowing-duty lawn); footway/highway tags map to None
    (pedinfra's). Everything else maps to None.
    """
    tags = tags or {}
    if _first_value(tags.get("landuse")) == "grass":
        return "lawn"
    return None


# ---------------------------------------------------------------------------
# p469: weed and lawn ordinances (mapped-lawn count hinnang).
# ---------------------------------------------------------------------------

#: Search radius for the lawn count (neighbourhood pocket reading).
LAWN_RADIUS_M = 800.0


def dim_lawncare(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p469: upkeep-visibility reading from mapped mown lawns within 800 m."""
    if not origin or pois is None:
        return None, "Murualade info puudub (haljasalade hetktõmmis)"
    n = _count_within_m(origin, pois, {"lawn"}, LAWN_RADIUS_M)
    if n >= 500:
        return 85, "Niitmisnõuete nähtavus (hinnang): %d muruala 800 m raadiuses — hooldus selgelt nähtav" % n
    if n >= 200:
        return 70, "Niitmisnõuete nähtavus (hinnang): %d muruala 800 m raadiuses — hooldus nähtav" % n
    if n >= 1:
        return 55, "Niitmisnõuete nähtavus (hinnang): %d muruala 800 m raadiuses" % n
    return 45, "Niitmisnõuete jõustamine teadmata (hinnang): 800 m raadiuses kaardistatud muruala puudub"


# ---------------------------------------------------------------------------
# p463/p464/p465: documented no-map registry NULLs (OTA PR #131 precedent).
# Legal duties and schedule/enforcement facts have no honest area signal
# (or would duplicate pedinfra/gritbin); the scorer reports the gap with
# a concrete buyer check instead of a faked number.
# ---------------------------------------------------------------------------

def dim_sidewalk(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p463: NULL — sidewalk upkeep is a per-parcel legal duty (no map)."""
    return None, "Kõnnitee hoolduskohustus teadmata (heakorraeeskiri: hooldab piirnev omanik; hetktõmmises pole kohustusandmeid, kõnniteede tihedus on juba pedinfra — kontrolli KOVist)"


def dim_sweeping(origin: Optional[Tuple[float, float]],
                 pois: Optional[List[dict]]) -> Score:
    """p464: NULL — sweeping tickets are a schedule/enforcement fact (no map)."""
    return None, "Tänavapuhastuse trahvirisk kaardil pole (vedaja puhastuskalender + munitsipaalpolitsei; hetktõmmises pole kalendri- ega trahviandmeid — kontrolli vedajalt)"


def dim_shoveling(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Score:
    """p465: NULL — shoveling duty is a per-parcel legal fact (no map)."""
    return None, "Lumekoristuskohustus teadmata (heakorraeeskiri: hooldab piirnev omanik; talihoolduse lähedus on juba gritbin p311 — kontrolli KOVist)"


#: Registry for UI/API wiring on integration: param -> (Estonian title, fn).
GROUP17B_DIMS: Dict[str, Tuple[str, object]] = {
    "sidewalk": ("Kõnnitee hooldus (kontroll)", dim_sidewalk),
    "sweeping": ("Puhastustrahv (kontroll)", dim_sweeping),
    "shoveling": ("Lumekoristus (kontroll)", dim_shoveling),
    "lawncare": ("Murualade hooldus (proksi)", dim_lawncare),
}

#: Param-id wiring for the central weight-rebalance follow-up.
GROUP17B_PARAM_IDS = {
    "sidewalk": 463,
    "sweeping": 464,
    "shoveling": 465,
    "lawncare": 469,
}


def score_group17b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Tuple[Dict[str, Optional[int]], List[str]]:
    """All Group 17-batch-B dims at once: ({param: score}, [reasons])."""
    dims: Dict[str, Optional[int]] = {}
    reasons: List[str] = []
    for param, (_, fn) in GROUP17B_DIMS.items():
        v, reason = fn(origin, pois)  # type: ignore[operator]
        dims[param] = v
        if v is not None:
            reasons.append(reason)
    return dims, reasons
