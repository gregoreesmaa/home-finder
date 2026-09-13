"""Batch GTFS-stops builder (issue #483): GTFS stops as points, overlay only.

Offline, stdlib only, snapshot-only — no network. Reads the snapshot
TLT-city vintage + the snapshot OSM transit extract, writes
``osm/derived-gtfsstops.json`` (bare LayerPoint array the
/app/api/layers/[layer] route serves generically). Pure derivation lives
in services/scoring/dims_p4_gtfsstops.py (single source of truth,
hermetic pytest suite); this script is I/O + calibration printout.

Rebuild:
  python3 scripts/build/batch_gtfs_stops.py --snap ~/hf-data/2026-09-12

What lands in the sidecar:
* GTFS leg: one point per stop_id in the vintage (1120 on 2026-09-11),
  {lon, lat, t = scheduled Wednesday departures}; stops with no
  Wednesday service keep no t (unknown, never 0). NO OSM tags on GTFS
  points (per-stop tag mapping is unverified — not claimed).
* Elron leg: OSM railway=station/halt/stop points from the snapshot
  derived-transit.json (mapped position + real railway tags only, no t —
  Elron publishes no machine timetable to join; tram_stop/platform
  excluded, the tram/bus networks ride the GTFS leg).

Deliberately NOT built (overlay-only AC): no walk raster, no metro
master — the layer rides the Euclidean fallback splat with the trips
spec (same scheduled-departures semantics as the transit layer, but a
measured-only point set: no default-100 fills, so beyond-vintage reads
honestly unknown instead of mid-ramp). Evening ridership is not derived
anywhere: GTFS static has no occupancy column (P4-032 stays NULL).
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "services", "scoring"))
import dims_p4_gtfsstops as gs  # noqa: E402

DERIVED_TRANSIT = os.path.join("osm", "derived-transit.json")
OUT_NAME = os.path.join("osm", "derived-gtfsstops.json")

#: Tallinn-window probes for the calibration printout (lon, lat, label).
PROBES = [
    (24.7369, 59.4405, "Balti jaam"),
    (24.7536, 59.4372, "Raekoja plats"),
    (24.6550, 59.4120, "Oismae"),
    (24.8316, 59.5120, "Viimsi"),
    (24.5000, 59.2000, "rural"),
]


def load_elron_rows(snap):
    """OSM rail points (Elron leg) from the snapshot transit extract."""
    with open(os.path.join(snap, DERIVED_TRANSIT), encoding="utf-8") as fh:
        rows = json.load(fh)
    out = []
    for p in rows:
        tags = p.get("tags") or {}
        if tags.get("railway") in gs.ELRON_RAILWAY_VALUES:
            out.append({"lon": p["lon"], "lat": p["lat"], "tags": tags})
    return out


def splat(points, lon, lat, sigma_km=0.2):
    """Gaussian trips splat S at one cell (mirrors client buildScoredField).

    Client: splatValues weight (p.t ?? 0), 5-sigma cutoff, score =
    100*S/(S+half). Pure helper for the calibration printout only.
    """
    s = 0.0
    for p in points:
        t = p.get("t") or 0
        if t <= 0:
            continue
        dlon = (p["lon"] - lon) * 111.32 * math.cos(math.radians(lat))
        dlat = (p["lat"] - lat) * 110.57
        d2 = dlon * dlon + dlat * dlat
        if d2 > (5 * sigma_km) ** 2:
            continue
        s += t * math.exp(-d2 / (2 * sigma_km * sigma_km))
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", required=True, help="snapshot dir")
    ap.add_argument("--vintage", default=gs.GTFS_VINTAGE)
    ap.add_argument("--out", default=None, help="sidecar path override")
    args = ap.parse_args()

    gtfs = gs.read_gtfs_tables(os.path.join(args.snap, args.vintage))
    wed = gs.services_for(gtfs["calendar.txt"], "wednesday")
    sat = gs.services_for(gtfs["calendar.txt"], "saturday")
    cnt_wed = gs.window_counts(gtfs, wed)
    cnt_eve = gs.window_counts(gtfs, wed, after=gs.EVENING_FROM)
    cnt_sat = gs.window_counts(gtfs, sat)
    modes = gs.stop_modes(gtfs)
    coords = gs.stop_coords(gtfs["stops.txt"])
    elron = load_elron_rows(args.snap)
    points, stats = gs.overlay_points(coords, cnt_wed, modes, elron)

    out = args.out or os.path.join(args.snap, OUT_NAME)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(points, fh)
    print("gtfs stops: %d (vintage %s)" % (stats["gtfs_stops"],
                                           args.vintage))
    print("with Wednesday service: %d; with evening: %d; with Saturday: %d"
          % (stats["gtfs_with_wed"], len(cnt_eve), len(cnt_sat)))
    print("mode split: %s" % (stats["mode_split"],))
    print("elron mapped-only: %d" % stats["elron_mapped"])
    print("total points -> %s" % out)

    vals = sorted(cnt_wed.values())
    print("wed deps/stop: n=%d median=%d p10=%d max=%d"
          % (len(vals), vals[len(vals) // 2],
             vals[len(vals) // 10], vals[-1]))
    eve_vals = sorted(cnt_eve.values())
    print("eve deps/stop: n=%d median=%d max=%d (SCHEDULED, not ridership)"
          % (len(eve_vals), eve_vals[len(eve_vals) // 2], eve_vals[-1]))
    # Calibration: trips-spec halves against the measured point set.
    for half in (800, 1500, 2500):
        scores = []
        for lon, lat, label in PROBES:
            s = splat(points, lon, lat)
            scores.append("%s=%d" % (label, round(100 * s / (s + half))
                                     if s > 0 else -1))
        print("half %d: %s" % (half, " ".join(scores)))


if __name__ == "__main__":
    main()
