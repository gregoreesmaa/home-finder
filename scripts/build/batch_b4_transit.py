"""Batch 4 Group 12 builders: p125 teenager independence, p343 airport transit.

p125 (Noorte iseseisvus): teenagers travel alone off-peak, so the honest
GTFS signal is WEEKEND service (sat+sun departures per stop from the
snapshot GTFS zip), not the Wednesday commuter peak the p15 transit layer
uses. Walk-kernel saturating sum, half=800 (locked §CAL): Balti ~80,
Oismae ~60, Viimsi ~11, rural unknown. Judgment call, documented here
and in the PR reviewer notes.

p343 (Lennujaama uhistranspordiuhendus): routes serving the Lennujaam
GTFS stops on Wednesday (bus 2/47/49/65, tram T2/T4 in this feed) carry
the airport connection; per-stop Wednesday departures ON THOSE ROUTES
only, walk-kernel saturating sum, half=150: corridor ~70+, off-corridor
unknown. A stop is "airport-served" iff its route calls at Lennujaam --
no invented transfers, no OSRM routing (offline snapshot has no router).

Both reuse the walk-graph kernel (stamp_sum, min-distance-per-cell) via
lazy imports so unit tests stay hermetic. Rebuild (offline, snapshot-only):
  python3 scripts/build/batch_b4_transit.py --which teens --snap HF_SNAP --out DIR
  python3 scripts/build/batch_b4_transit.py --which airport --snap HF_SNAP --out DIR
with --graph/--step-m/--bbox/--format flags mirroring build-walk-raster.py.
 masters land next to the base rasters as
  teens-walk-raster.json / teens-metro.{json,u8} (same for airport).
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_b4_common import (  # noqa: E402
    COUNTY_BBOX,
    SCORE_FLOOR,
    departures_per_stop,
    read_gtfs,
    saturate,
    service_ids_for,
)

# Lennujaam GTFS stop_ids in tallinn-gtfs-2026-09-11.zip (verified).
AIRPORT_STOP_IDS = ("138901", "138215", "138869")

JOIN_KM = 0.1
DEFAULT_TRIPS = 100


def weekend_counts(gtfs):
    """stop_id -> sat+sun departures (p125 signal)."""
    satsun = service_ids_for(
        gtfs["calendar.txt"], "saturday") | service_ids_for(
        gtfs["calendar.txt"], "sunday")
    # Union, not intersection: saturday-only and sunday-only services both
    # run weekends; service_ids_for(day) alone already means "runs that day".
    cnt, _ = departures_per_stop(gtfs, satsun)
    return cnt


def airport_counts(gtfs, airport_stop_ids=AIRPORT_STOP_IDS):
    """(routes, stop_id -> Wednesday departures on airport-serving routes)."""
    wed = service_ids_for(gtfs["calendar.txt"], "wednesday")
    cnt_wed, trip_route = departures_per_stop(gtfs, wed)
    del cnt_wed
    aproutes = set()
    for row in gtfs["stop_times.txt"]:
        if row["stop_id"] in airport_stop_ids and row["trip_id"] in trip_route:
            aproutes.add(trip_route[row["trip_id"]])
    ap_trips = {t for t, r in trip_route.items() if r in aproutes}
    cnt = {}
    for row in gtfs["stop_times.txt"]:
        if row["trip_id"] in ap_trips:
            cnt[row["stop_id"]] = cnt.get(row["stop_id"], 0) + 1
    return sorted(aproutes), cnt


def stop_coords(gtfs):
    return {s["stop_id"]: (float(s["stop_lon"]), float(s["stop_lat"]))
            for s in gtfs["stops.txt"]}


def write_frequency_sidecar(path, as_of, coords, counts, extra=None):
    stops = [{"lon": lon, "lat": lat, "trips": counts[sid]}
             for sid, (lon, lat) in coords.items() if sid in counts]
    doc = {"asOf": as_of, "stops": stops}
    if extra:
        doc.update(extra)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    vals = sorted(counts.values())
    print("stops: %d median/d: %d max/d: %d -> %s"
          % (len(stops), vals[len(vals) // 2], vals[-1], path))
    return doc


def join_trips(stops, freq, default=DEFAULT_TRIPS):
    """Winner-takes-all OSM<->count join (mirrors walk_raster.join_trips).

    stops: [{lon,lat}...]; freq: [{lon,lat,trips}...]. Unmatched stops get
    `default`: DEFAULT_TRIPS (unknown, not bad) for teens/weekend, but 0
    for airport -- a stop no airport route serves contributes no airport
    departures (defaulting it to 100 would paint airport access county-wide).
    Co-claimants read 0 so the SUM stays honest. Pure: unit-tested.
    """
    from batch_b4_common import hav_km
    claim = [-1] * len(stops)
    dist = [float("inf")] * len(stops)
    for i, p in enumerate(stops):
        for j, f in enumerate(freq):
            if abs(f["lon"] - p["lon"]) > 0.002 or abs(f["lat"] - p["lat"]) > 0.001:
                continue
            d = hav_km(p["lon"], p["lat"], f["lon"], f["lat"])
            if d < dist[i]:
                dist[i] = d
                claim[i] = j
    won = {}
    for i in range(len(stops)):
        if claim[i] < 0 or dist[i] > JOIN_KM:
            continue
        if claim[i] not in won or dist[i] < dist[won[claim[i]]]:
            won[claim[i]] = i
    out = []
    for i in range(len(stops)):
        if claim[i] < 0 or dist[i] > JOIN_KM:
            out.append(default)
        elif won[claim[i]] == i:
            out.append(freq[claim[i]]["trips"])
        else:
            out.append(0)
    return out


def _build_trips_layer(graph, snap, grid, half, sigma, sidecar, default):
    """Shared walk-kernel stamp for a departures-weighted stop layer."""
    import walk_raster as wr  # lazy: hermetic unit tests never reach here
    stops = json.load(open(os.path.join(snap, "osm", "derived-transit.json")))
    freq = json.load(open(os.path.join(snap, "osm", sidecar)))["stops"]
    trips = join_trips(stops, freq, default)
    feats = [(p["lon"], p["lat"], t, (p.get("tags") or {}))
             for p, t in zip(stops, trips) if t > 0]

    def bit_of(tags):
        return wr.MODE_BIT.get(wr.stop_mode(tags) or "", 0)

    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma,
                                   bit_of, wr.KICKER_KM)

    # No mode kicker (unlike p15): weekend/airport corridors are thin and
    # single-mode by nature; a kicker would reward the city center for
    # geometry, not for off-peak or airport service. Documented divergence.
    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = saturate(s, half)
        return sc if sc >= SCORE_FLOOR else None

    return score_of, snapped, euclid


def build_teens(graph, snap, grid, half, sigma):
    score_of, snapped, euclid = _build_trips_layer(
        graph, snap, grid, half, sigma, "transit-weekend-frequency.json",
        DEFAULT_TRIPS)
    print("teens: snapped=%d euclid=%d" % (snapped, euclid))
    return score_of, {"half": half, "sigma": sigma}


def build_airport(graph, snap, grid, half, sigma):
    score_of, snapped, euclid = _build_trips_layer(
        graph, snap, grid, half, sigma, "transit-airport-frequency.json", 0)
    print("airport: snapped=%d euclid=%d" % (snapped, euclid))
    return score_of, {"half": half, "sigma": sigma}


BUILDERS = {"teens": build_teens, "airport": build_airport}
SIDECAR = {"teens": "transit-weekend-frequency.json",
           "airport": "transit-airport-frequency.json"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True, choices=sorted(BUILDERS),
                    help="teens = p125 weekend departures; airport = p343")
    ap.add_argument("--snap", required=True)
    ap.add_argument("--out", required=True, help="output dir for sidecars+rasters")
    ap.add_argument("--feed-date", default="2026-09-11")
    ap.add_argument("--freq-only", action="store_true",
                    help="only (re)write the frequency sidecar, no raster")
    ap.add_argument("--graph", default=None)
    ap.add_argument("--step-m", type=float, default=75.0)
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--half", type=float, default=None)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    args = ap.parse_args()

    from batch_b4_common import CAL
    half = args.half if args.half is not None else CAL[args.which]["half"]
    sigma = args.sigma if args.sigma is not None else CAL[args.which]["sigma"]

    gtfs = read_gtfs(os.path.join(args.snap, "gtfs", "tallinn-gtfs-2026-09-11.zip"))
    coords = stop_coords(gtfs)
    if args.which == "teens":
        counts = weekend_counts(gtfs)
        extra = None
    else:
        routes, counts = airport_counts(gtfs)
        print("airport routes: %s" % ", ".join(routes))
        extra = {"routes": routes}
    os.makedirs(os.path.join(args.snap, "osm"), exist_ok=True)
    write_frequency_sidecar(os.path.join(args.snap, "osm", SIDECAR[args.which]),
                            args.feed_date, coords, counts, extra)
    if args.freq_only:
        return

    if not args.graph:
        ap.error("--graph is required for raster builds")
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import walk_raster as wr
    from walk_graph import load_graph
    graph = load_graph(args.graph)
    grid = wr.Grid(args.bbox, args.step_m)
    score_of, contract = BUILDERS[args.which](graph, args.snap, grid, half, sigma)
    name = {"teens": "teens", "airport": "airport"}[args.which]
    if args.format == "split":
        prefix = os.path.join(args.out, name + "-metro")
        wr.save_master(prefix, grid, score_of, contract["half"], contract["sigma"])
    else:
        doc = wr.encode_raster(grid, score_of, half=contract["half"],
                               sigma=contract["sigma"])
        with open(os.path.join(args.out, name + "-walk-raster.json"), "w",
                  encoding="utf-8") as f:
            json.dump(doc, f)
    print("wrote %s raster half=%s sigma=%s" % (name, half, sigma))


if __name__ == "__main__":
    main()
