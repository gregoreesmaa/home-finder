"""Group 18 green-blue/street dimensions batch B (issue #126): p113/p411.

Params (this agent only — sibling batches own disjoint sets; Group 18 is
parameters3.md section 5.18, Maa-amet 3D/LiDAR + PVLib + Sentinel/Landsat
primaries re-derived here from OSM tags because the Group 18 primaries
carry no street-frontage or shade/cooling signal at listing scale; PR
#115 owns p82/p83/p166/p350/p441 in dims_group18.py):
* p113 extreme heat adaptation (green-blue cooling PROXY)
* p411 street-level visibility (road-frontage + enclosure PROXY)

HONESTY (AGENTS.md section 7.2): no thermal imagery, no 3D ray-tracing
and no measured temperatures are in the snapshot, so p113 is a
green-blue proximity proxy (closer cooling shade/evaporation -> higher),
and p411 is a mapped-street-frontage proxy (mapped street near + not
tree-enclosed -> higher). Every reason says "hinnang" (estimate);
p113 reasons additionally say "mitte mõõdetud temperatuur" (not measured
temperature). LAYER_META below carries the same labels for the future web
layer (title/legend/source).

p113 bands (nearest park|forest|water|beach, metres): <=150: 95,
<=300: 80, <=500: 65, <=1000: 50, else 30. No green-blue kind in range ->
30 (beyond the 1.5 km live fetch that is genuinely far, not unknown).
p411 base bands (nearest mapped street, metres): <=50: 90, <=150: 75,
<=300: 60, <=500: 45, else 25; dense wood within 150 m -> -10 (limited
sightlines, "puude varjus" note in the reason), floor 5. No street kind
in range -> 25. Judgment calls, documented here and in the PR notes:
* p113 reuses livability's existing kinds (park/forest/water/beach), so
  no new fetch is needed for it — same precedent as p88 reusing bus_stop
  in PR #101 and p441 reusing school in PR #115.
* p411 reads ONLY highway way-centers ("street" kind): a mapped corridor
  is the frontage signal. highway=bus_stop is excluded (a stop, not a
  street), as are proposed/construction (not yet streets).
* p411 ignores water adjacency: waterfront openness belongs to window
  views (p132, another batch's scope), not street visibility.

Style mirrors services/scoring/livability.py: pure scorers,
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
only in livability.fetch_pois; this module adds no network calls, only
the query fragment + tag mapping the live path needs.

Helpers are local copies (not imported from livability): a future central
hook may import this module from livability.py, and importing livability
here would turn that into a cycle (same precedent as PRs #100/#106/#115).

Tag verification (2026-09-12, done once by the author with osmium against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime):
* natural=water: 4645 ways + 170 relations; natural=wood: 4097 ways +
  106 relations; leisure=park: 7043 nodes + 310 ways + 12 relations;
  landuse=grass: 20833 ways, meadow: 1799 ways, village_green: 47 ways;
  leisure=garden: 2531 ways (all nwr/ — node-only extraction would drop
  thousands of cooling polygons, PR #118 rule).
* highway ways: 127777 (p411 corridor source); lit ways: 30878 (NOT
  used here — lit belongs to p350 in PR #115, kept disjoint).

Way geometries need centroid handling (extraction side, staged here as
documented convention): polygon bbox-center / LineString midpoint, the
same three cases as batch_b4_common.feature_point. Residual twin risk
(PR #118): large water/wood polygons export node+area duplicates; both
scorers below are nearest-only (p411's wood leg is a capped boolean
penalty, not a count), hence twin-immune — a future count/kernel builder
MUST dedupe first.

Delivery (stated per the task brief): scorer dims ONLY, no raster masters.
Why: (1) these dims are way-geometry (corridors/areas), not the
point-kernel shape the walk-raster pipeline stamps — corridor rasters
need a new length-weighted builder, not a reuse (same finding as PR
#115); (2) county+metro masters mean full-Harjumaa stamp runs plus hook
edits to layers.ts/snapshot.ts, which collide with open sibling PRs;
(3) the repo precedent (PRs #101/#106/#115) is scorer-first with one
central integration later. LAYER_META below stages the honest web labels.

Integration (deliberately NOT done here): extending
livability.OVERPASS_QUERY with GROUP18B_OVERPASS_FRAGMENT, routing
highway tags through kinds_from_tags in livability._POI_KIND (value-split
tags need kinds_from_tags — the static table alone cannot exclude
bus_stop/proposed/construction), and rebalancing livability.WEIGHTS must
be one joint change across all parameter batches — existing tests pin
set(WEIGHTS) exactly, so per-batch WEIGHTS edits would break every
sibling.
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


#: livability kinds reused as the green-blue cooling signal (no new fetch).
COOL_KINDS = {"park", "forest", "water", "beach"}

#: p113 bands: nearest cooling green-blue (higher = nearer).
COOL_BANDS = [(150, 95), (300, 80), (500, 65), (1000, 50), (float("inf"), 30)]

#: p411 bands: nearest mapped street (higher = nearer frontage).
STREET_BANDS = [(50, 90), (150, 75), (300, 60), (500, 45), (float("inf"), 25)]

#: Dense wood inside this radius limits sightlines (p411 penalty, metres).
ENCLOSE_M = 150.0
#: Sightline penalty points when tree-enclosed.
ENCLOSE_PENALTY = 10


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping.
# The p113 cool legs reuse livability's existing query; only the highway
# corridor fragment is new. highway=* is value-split (bus_stop, proposed
# and construction must NOT read as streets), so the central hook must
# route highway tags through kinds_from_tags below — the static
# _POI_KIND table alone cannot express the exclusions (same precedent as
# maxspeed tiers / lit variants in PR #115).
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP18B_OVERPASS_FRAGMENT = """
  way["highway"](around:1500,{lat},{lon});"""

#: Linear highway=* values that read as street corridors. Grounded in the
#: 2026-09-12 Nõmme window (footway 2355, service 1576, path 813,
#: residential 528, living_street 198, tertiary 193, secondary 183,
#: cycleway 175, track 110, steps 108, trunk 59, unclassified 51,
#: pedestrian 11, links, busway 2) plus the standard link/road/raceway set.
#: *_link values match via suffix so every graded link is covered.
STREET_HIGHWAY = frozenset({
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "living_street", "service",
    "pedestrian", "track", "footway", "bridleway", "steps", "path",
    "cycleway", "busway", "road", "raceway", "corridor", "via_ferrata",
})


def kinds_from_tags(tags: dict) -> Optional[str]:
    """First Group 18B kind matching the OSM tags, else None. Pure.

    Only linear corridor values read as "street": point furniture
    (crossing, traffic_signals, bus_stop ...), verticals (elevator) and
    not-yet streets (proposed, construction) never match, so a stray node
    POI cannot pose as a corridor. The live fragment fetches way["highway"]
    only, so way-centroid handling (see module docstring) feeds this.
    """
    if not isinstance(tags, dict):
        return None
    hw = tags.get("highway", "")
    hw = hw.split(";")[0].strip() if isinstance(hw, str) else ""
    if not hw:
        return None
    if hw in STREET_HIGHWAY or hw.endswith("_link"):
        return "street"
    return None


# ---------------------------------------------------------------------------
# p113: extreme heat adaptation — green-blue cooling PROXY.
# ---------------------------------------------------------------------------

def dim_heat(origin: Optional[Tuple[float, float]],
             pois: Optional[List[dict]]) -> Score:
    """p113: cooling green-blue near (high) vs heat-exposed (low).

    Honest proxy only: nearer park/forest/water reads as more shade and
    evaporative cooling. Never a temperature statement.
    """
    if not origin or pois is None:
        return None, "Kuumaleevenduse info puudub"
    m = _nearest_m(origin, pois, COOL_KINDS)
    if m is None:
        return 30, ("Jahutav rohe-/siniala kaugemal kui 1,5 km "
                    "(kuumaleevenduse hinnang, mitte mõõdetud temperatuur)")
    s = _band(m, COOL_BANDS)
    assert s is not None
    return s, ("Kuumaleevenduse hinnang (mitte mõõdetud temperatuur): "
               "lähim rohe-/siniala %s" % _fmt_m(m))


# ---------------------------------------------------------------------------
# p411: street-level visibility — road-frontage + enclosure PROXY.
# ---------------------------------------------------------------------------

def dim_visibility(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Score:
    """p411: legible open street frontage (high) vs remote/enclosed (low).

    Base reads the nearest mapped street; dense wood within ENCLOSE_M
    caps sightlines (-ENCLOSE_PENALTY, floored). Both legs are proxies.
    """
    if not origin or pois is None:
        return None, "Tänavavaate info puudub"
    m = _nearest_m(origin, pois, {"street"})
    if m is None:
        return 25, ("Kaardistatud tänav kaugemal kui 1,5 km "
                    "(nähtavuse hinnang)")
    s = _band(m, STREET_BANDS)
    assert s is not None
    wood = _nearest_m(origin, pois, {"forest"})
    if wood is not None and wood <= ENCLOSE_M:
        s = max(s - ENCLOSE_PENALTY, 5)
        return s, ("Tänavavaate nähtavus (hinnang): lähim tänav %s, "
                   "puude varjus (%s)" % (_fmt_m(m), _fmt_m(wood)))
    return s, ("Tänavavaate nähtavus (hinnang): lähim tänav %s"
               % _fmt_m(m))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP18B_DIMS = (
    ("heat", "p113", dim_heat),
    ("visibility", "p411", dim_visibility),
)


def score_group18b(origin: Optional[Tuple[float, float]],
                   pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Both Group 18B dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP18B_DIMS}


#: Honest Estonian web labels for the follow-up layers batch. Both titles
#: say "(hinnang)" — never bare "heat" or "visibility" that implies a
#: measured simulation.
LAYER_META = {
    "heat": {
        "param": 113,
        "title": "Kuumaleevendus (roheala hinnang)",
        "good": "roheline = jahutav rohe-/siniala lähedal (hinnang)",
        "bad": "punane = rohe-/siniala kaugel (hinnang, mitte mõõdetud temperatuur)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(park/mets/vesi; hinnang, mitte mõõdetud temperatuur)"),
    },
    "visibility": {
        "param": 411,
        "title": "Tänavavaate nähtavus (hinnang)",
        "good": "roheline = avatud kaardistatud tänavafront (hinnang)",
        "bad": "punane = tänav kaugel või puude varjus (hinnang)",
        "source": "kohalik hetktõmmis 2026-09-12 (highway + mets; hinnang)",
    },
}
