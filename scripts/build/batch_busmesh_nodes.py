"""Batch bus-mesh nodes builder (issue #769): transfer-node sidecars.

Offline, stdlib only, snapshot-only — no network. Reads the snapshot
TLT-city GTFS vintage, derives transfer nodes per window (WD/SA/SU,
each from its OWN services — never copied across windows) and writes
``osm/derived-busmesh.json`` (+ ``-sat`` / ``-sun``) as bare LayerPoint
arrays the /app/api/layers/[layer] route serves generically. Pure
derivation lives in services/scoring/dims_p4_busmesh.py (single source
of truth, hermetic pytest suite); this script is I/O + calibration
printout.

Rebuild:
  python3 scripts/build/batch_busmesh_nodes.py --snap ~/hf-data/2026-09-12

What lands in the sidecars (per window):
* cluster crossings at 60 m -> collapse corridor chains (identical
  route sets within 300 m) -> snap to stops (100 m) -> drop stopless.
* One point per snapped stop {lon, lat, t = route count}; classless
  (no invented OSM tags, gtfsstops #483 precedent).

Deliberately NOT built: no walk raster, no metro master — the layers
ride the Euclidean fallback splat with the transfer spec (route-count
semantics, half 5). 429 off-node stops (1120 - 691 within 100 m of a
shipped E-R node, measured 2026-09-19) read honestly unknown instead
of borrowing a neighbour ("üksikteenus", never faked).
"""

import argparse
import csv
import io
import json
import math
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "services", "scoring"))
import dims_p4_busmesh as bm  # noqa: E402

#: Snapshot vintage path inside --snap (gtfsstops #483 precedent).
GTFS_VINTAGE = "gtfs/tallinn-gtfs-2026-09-11.zip"

#: Sidecar per served window (layer id == file stem).
OUT_NAMES = {"wd": "osm/derived-busmesh.json",
             "sat": "osm/derived-busmesh-sat.json",
             "sun": "osm/derived-busmesh-sun.json"}

#: Tallinn-window probes for the calibration printout (lon, lat, label).
PROBES = [
    (24.7369, 59.4405, "Balti jaam"),
    (24.7536, 59.4372, "Raekoja plats"),
    (24.6550, 59.4120, "Oismae"),
    (24.8316, 59.5120, "Viimsi"),
    (24.5000, 59.2000, "rural"),
]


def read_vintage(zip_path):
    """calendar/trips/stops/shapes/routes tables from the vintage zip."""
    out = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in ("calendar.txt", "trips.txt", "stops.txt",
                      "shapes.txt", "routes.txt"):
            with zf.open(name) as fh:
                out[name] = list(csv.DictReader(
                    io.TextIOWrapper(fh, encoding="utf-8-sig")))
    return out


def build_window(gtfs, days):
    """Full derivation for one window; returns (points, stats).

    Pure over the table dict (importable for hermetic tests): crossings
    -> 60 m clusters -> 300 m chain collapse -> 100 m stop snap.
    """
    polys = bm.shape_polylines(gtfs["shapes.txt"])
    shape_routes = bm.window_shape_routes(gtfs["trips.txt"],
                                          gtfs["calendar.txt"], days)
    raw = bm.segment_crossings(polys, shape_routes)
    nodes = bm.cluster_nodes(raw)
    kept, collapsed = bm.collapse_chains(nodes)
    snapped, dropped = bm.snap_to_stops(kept, gtfs["stops.txt"])
    stats = {"shapes": len(polys), "wed_shapes": len(shape_routes),
             "raw": len(raw), "nodes": len(nodes),
             "collapsed": collapsed, "kept": len(kept),
             "snapped": len(snapped), "dropped": dropped}
    return bm.busmesh_points(snapped), stats


def splat(points, lon, lat, sigma_km=0.2):
    """Gaussian route-count splat S at one cell (calibration printout).

    Mirrors client buildScoredField for kind trips with the transfer
    spec (half 5): score = 100*S/(S+5).
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
    ap.add_argument("--vintage", default=GTFS_VINTAGE)
    ap.add_argument("--out-dir", default=None,
                    help="sidecar dir override (default: <snap>/osm)")
    args = ap.parse_args()

    gtfs = read_vintage(os.path.join(args.snap, args.vintage))
    out_dir = args.out_dir or os.path.join(args.snap, "osm")
    os.makedirs(out_dir, exist_ok=True)
    for window, days in bm.WINDOWS.items():
        points, stats = build_window(gtfs, days)
        stem = os.path.basename(OUT_NAMES[window])
        out = os.path.join(out_dir, stem)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(points, fh)
        print("%s %s: shapes=%d raw=%d nodes=%d chains_collapsed=%d "
              "snapped=%d stopless_dropped=%d -> %s"
              % (window, days, stats["shapes"], stats["raw"],
                 stats["nodes"], stats["collapsed"], stats["snapped"],
                 stats["dropped"], out))
    # Calibration: transfer-spec scores against the Wednesday point set.
    points, _ = build_window(gtfs, bm.WINDOWS["wd"])
    scores = []
    for lon, lat, label in PROBES:
        s = splat(points, lon, lat)
        scores.append("%s=%d" % (label, round(100 * s / (s + 5))
                                 if s > 0 else -1))
    print("transfer half 5 (wd): %s" % " ".join(scores))


if __name__ == "__main__":
    main()
