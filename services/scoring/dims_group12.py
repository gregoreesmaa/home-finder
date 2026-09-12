"""Group 12 commute-time dimension (issue #126): p11 scorer + GTFS wiring.

Param (this agent only — sibling batches own disjoint sets; Group 12 is
parameters3.md section 5.12, Peatus.ee GTFS + OSRM/OTP):
* p11 commute time (GTFS-frequency style estimated minutes -> 0..100)

HONESTY (AGENTS.md section 7.2): the 2026-09-12 snapshot has NO routing
engine (no OSRM/OTP/Valhalla) and no origin-destination matrix, so p11
CANNOT measure a real commute. It estimates one-way minutes as
walk-to-stop + expected-wait-from-Wednesday-frequency + a fixed ride leg,
and every reason says "hinnang" (estimate). The minutes-to-score mapping
is documented explicitly below (no hidden curve).

Minutes model (GTFS-frequency style, Dijkstra-free):
  M = walk_min + wait_min + RIDE_MIN, where
  * walk_min = dist_to_nearest_stop_m / 75  (4.5 km/h = livability
    SPEED_WALK_KMH, so 75 m/min; bird-flight, no routing — stated).
  * wait_min = min(540 / D, 40), D = Wednesday departures at that stop.
    540 = half of an 18 h service span (06-24) in minutes: headway =
    1080 / D, expected wait = headway / 2. Cap 40 avoids absurd waits
    when D is tiny but nonzero. D missing (OSM-only stop, no GTFS join)
    -> DFLT_DEPS = 30 (hourly-ish suburban default, reason flags
    "sõiduplaanita peatuse hinnang").
  * RIDE_MIN = 20: fixed city-mean in-vehicle leg. Judgment call: the
    snapshot cannot route, so ordering comes from walk+wait (real GTFS
    signal) and the ride leg only anchors the scale. The reason prints
    all three components so the constant is reviewable, never hidden.
  M -> score bands: <=25: 100, <=35: 85, <=45: 70, <=55: 55, <=70: 40,
  else 25 (worst scored case ~80 min; beyond 1500 m the dim is unknown).

Calibration (2026-09-12, author probes against
~/hf-data/2026-09-12/gtfs/tallinn-gtfs-2026-09-11.zip, NOT at runtime):
* Wednesday services: 73; stops with Wed departures: 1114/1120.
* Wednesday departures/stop/day: median 138, p10 42, max 974.
* Sample M: Balti jaam (118 m, D=530) -> ~23 min -> 100;
  Õismäe/Nurmenuku (202 m, D=665) -> ~24 -> 100;
  Lasnamäe/Kumu (215 m, D=44) -> ~35 -> 70;
  Viimsi vallamaja (109 m, D=71) -> ~29 -> 85;
  rural Kuusalu (nearest stop 27 km) -> unknown.
* calendar_dates.txt carries 2310 exception rows (holidays/diversions)
  the base-Wednesday model ignores — same precedent as batch B4
  (batch_b4_transit.py); a live path should prefer the GTFS-RT TripUpdate
  feed per parameters3.md §5.12, which is also absent from the snapshot.

Style mirrors services/scoring/livability.py: pure scorers,
(origin, pois) -> (Optional[int 0..100], Estonian reason). Network lives
only in livability.fetch_pois; this module adds no network calls, only
the query fragment + tag mapping + GTFS sidecar join the live path needs.

Helpers are local copies (not imported from livability): a future central
hook may import this module from livability.py, and importing livability
here would turn that into a cycle (same precedent as PRs #100/#106/#115).

Tag/feed verification (2026-09-12, osmium against
~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf, NOT at runtime):
* highway=bus_stop nodes: 4240 (+1 way); public_transport=platform:
  5385 nodes + 245 ways + 1 relation — the Overpass fragment below
  fetches nodes+ways (relation stop_areas: 1 in the county, negligible —
  documented, not fetched).
* GTFS stops: 1120 (feed tallinn-gtfs-2026-09-11.zip).

Delivery (stated per the task brief): scorer dims ONLY, no raster masters.
Why: (1) p11 is a per-listing minutes estimate, not a kernel-density
surface — the walk-raster stamp pipeline fits corridor layers, not an
OD-free commute proxy; (2) a county raster run plus hook edits to
layers.ts/snapshot.ts would collide with open sibling PRs; (3) the repo
precedent (PRs #101/#106/#115) is scorer-first with one central
integration later. LAYER_META below stages the honest web labels.

Integration (deliberately NOT done here): GTFS sidecar join
(stop_pois_from_counts over the Wednesday frequency sidecar, mirrors
batch_b4_transit.join_trips), extending livability.OVERPASS_QUERY with
GROUP12_OVERPASS_FRAGMENT, livability._POI_KIND with GROUP12_POI_KIND,
and rebalancing livability.WEIGHTS must be one joint change across all
parameter batches — existing tests pin set(WEIGHTS) exactly, so per-batch
WEIGHTS edits would break every sibling.
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


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


# ---------------------------------------------------------------------------
# p11 minutes model constants (all documented in the module docstring).
# ---------------------------------------------------------------------------

#: Walk speed 4.5 km/h = livability SPEED_WALK_KMH, as metres per minute.
WALK_M_PER_MIN = 75.0
#: Fixed in-vehicle leg (minutes). Ordering comes from walk+wait; see above.
RIDE_MIN = 20.0
#: Half of the assumed 18 h (06-24) service span, in minutes (wait = span/D).
WAIT_HALF_SPAN_MIN = 540.0
#: Wait cap (minutes) for tiny-but-nonzero departure counts.
WAIT_CAP_MIN = 40.0
#: Conservative departures/day for an OSM-only stop with no GTFS join.
DFLT_DEPS = 30
#: A stop further than this is not a commute option (unknown, not bad).
STOP_WINDOW_M = 1500.0

#: Explicit minutes -> score mapping (the load-bearing table for p11).
#: Reachable M spans ~21 (adjacent frequent stop) to ~80 (1500 m walk +
#: capped wait + ride leg), so the last band's fallback covers the worst
#: scored case — no dead branch above the window (beyond 1500 m the dim
#: is unknown, not worse).
MINUTES_BANDS = [(25, 100), (35, 85), (45, 70), (55, 55), (70, 40),
                 (float("inf"), 25)]


# ---------------------------------------------------------------------------
# Live-path wiring: Overpass fragment + tag mapping + GTFS sidecar join.
# ---------------------------------------------------------------------------

#: Lines to splice into livability.OVERPASS_QUERY's (...) union on integration.
GROUP12_OVERPASS_FRAGMENT = """
  node["highway"="bus_stop"](around:1500,{lat},{lon});
  node["public_transport"="platform"](around:1500,{lat},{lon});
  way["public_transport"="platform"](around:1500,{lat},{lon});"""

#: Extra (tagkey, {value: kind}) rows for livability._POI_KIND. Wednesday
#: departure counts ("deps") are attached later by stop_pois_from_counts
#: from the GTFS frequency sidecar; OSM-only stops keep deps=None and the
#: scorer falls back to DFLT_DEPS with a flagged reason.
GROUP12_POI_KIND = [
    ("highway", {"bus_stop": "stop_wday"}),
    ("public_transport", {"platform": "stop_wday",
                          "stop_position": "stop_wday"}),
]


def kinds_from_tags(tags: dict) -> Optional[str]:
    """Group 12 kind for OSM tags (stop positions only), else None. Pure."""
    if not isinstance(tags, dict):
        return None
    if tags.get("highway") == "bus_stop":
        return "stop_wday"
    if tags.get("public_transport") in ("platform", "stop_position"):
        return "stop_wday"
    return None


def stop_pois_from_counts(coords: Dict[str, Tuple[float, float]],
                          counts: Dict[str, int]) -> List[dict]:
    """GTFS stops -> scorer POIs with Wednesday departures attached. Pure.

    coords: stop_id -> (lon, lat); counts: stop_id -> Wednesday departures
    (batch_b4_transit sidecar shape). Stops without a count keep deps=None
    (OSM-only position, conservative default at score time). Hermetic and
    unit-tested; the snapshot zip is read by the caller (same split as
    batch_b4_common.read_gtfs + sidecar writers).
    """
    pois = []
    for sid, (lon, lat) in coords.items():
        pois.append({"kind": "stop_wday", "lat": lat, "lon": lon,
                     "deps": counts.get(sid)})
    return pois


def _nearest_stop(origin: Tuple[float, float],
                  pois: List[dict]) -> Optional[Tuple[float, Optional[int]]]:
    """(distance_m, deps) of the nearest stop_wday, else None. Pure."""
    best = None
    for p in pois:
        if p.get("kind") != "stop_wday" or p.get("lat") is None:
            continue
        d = _haversine_m(origin, p["lat"], p["lon"])
        deps = p.get("deps")
        if isinstance(deps, bool):
            deps = None
        if deps is not None:
            try:
                deps = int(deps)
            except (TypeError, ValueError):
                deps = None
        if best is None or d < best[0]:
            best = (d, deps)
    return best


def estimate_minutes(dist_m: float, deps: Optional[int]) -> Tuple[float, float, float]:
    """(walk_min, wait_min, total_M) for the p11 minutes model. Pure.

    Total M includes RIDE_MIN (documented constant); the reason printer
    reports all three components.
    """
    walk = dist_m / WALK_M_PER_MIN
    d = deps if (deps is not None and deps > 0) else DFLT_DEPS
    wait = min(WAIT_HALF_SPAN_MIN / d, WAIT_CAP_MIN)
    return walk, wait, walk + wait + RIDE_MIN


# ---------------------------------------------------------------------------
# p11: commute time — GTFS-frequency minutes estimate, higher score = shorter.
# ---------------------------------------------------------------------------

def dim_commute(origin: Optional[Tuple[float, float]],
                pois: Optional[List[dict]]) -> Score:
    """p11: estimated one-way commute minutes -> 0..100 (high = short).

    Unknown (None) when inputs are missing OR no stop lies within
    STOP_WINDOW_M — a stop-less listing has no GTFS commute to score, and
    scoring it 0 would present missing service as a measured bad commute.
    """
    if not origin or pois is None:
        return None, "Sõiduaja info puudub"
    hit = _nearest_stop(origin, pois)
    if hit is None or hit[0] > STOP_WINDOW_M:
        return None, ("Peatus kaugemal kui 1,5 km – sõiduaja hinnangut pole "
                      "(GTFS-ühendus puudub, mitte mõõdetud halb ühendus)")
    dist_m, deps = hit
    walk, wait, total = estimate_minutes(dist_m, deps)
    s = _band(total, MINUTES_BANDS)
    assert s is not None
    if deps is None or deps <= 0:
        return s, ("Töölesõit (hinnang, sõiduplaanita peatus ~%d väljumist/päev): "
                   "peatus %s + ooteaeg ~%d min + sõit ~%d min → kokku ~%d min"
                   % (DFLT_DEPS, _fmt_m(dist_m), int(round(wait)),
                      int(RIDE_MIN), int(round(total))))
    return s, ("Töölesõit (hinnang): peatus %s, %d väljumist/kolmapäev, "
               "ooteaeg ~%d min + sõit ~%d min → kokku ~%d min"
               % (_fmt_m(dist_m), deps, int(round(wait)), int(RIDE_MIN),
                  int(round(total))))


#: Registry for the central weight-rebalance follow-up: (dims key, param id).
GROUP12_DIMS = (
    ("commute", "p11", dim_commute),
)


def score_group12(origin: Optional[Tuple[float, float]],
                  pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """Group 12 dims for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in GROUP12_DIMS}


#: Honest Estonian web labels for the follow-up layers batch. The title says
#: "hinnang" — never a bare "commute time" that implies a routed measurement.
LAYER_META = {
    "commute": {
        "param": 11,
        "title": "Töölesõit (sageduse hinnang)",
        "good": "roheline = sagedane ühendus lähedal (hinnang)",
        "bad": "punane = harv/kauge ühendus (hinnang, mitte mõõdetud sõit)",
        "source": ("kohalik hetktõmmis 2026-09-12 "
                   "(GTFS kolmapäeva sagedus + jalgsikäik; hinnang, marsruutimata)"),
    },
}
