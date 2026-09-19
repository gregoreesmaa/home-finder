"""Batch bus-mesh probe runner (issue #764): GTFS shape-crossing feasibility.

Offline, stdlib only, snapshot-only — no network. Reads a snapshot GTFS
zip, derives transfer-node candidates with services/scoring/
dims_p4_busmesh.py (single source of truth) and prints aggregates.

Reproduce the 2026-09-19 verdict (docs/p4_busmesh.md):
  python3 scripts/build/batch_busmesh_probe.py --zip PATH/TO/tallinn-gtfs-2026-09-11.zip
"""

import argparse
import csv
import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "services", "scoring"))
import dims_p4_busmesh as bm  # noqa: E402


def read_table(zf, name):
    with zf.open(name) as fh:
        return list(csv.DictReader(fh.read().decode("utf-8-sig").splitlines()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="Snapshot GTFS zip path")
    args = ap.parse_args()
    with zipfile.ZipFile(args.zip) as zf:
        stops = read_table(zf, "stops.txt")
        trips = read_table(zf, "trips.txt")
        routes = read_table(zf, "routes.txt")
        shapes = read_table(zf, "shapes.txt")
        calendar = read_table(zf, "calendar.txt")
    polys = bm.shape_polylines(shapes)
    shape_routes = bm.wed_shape_routes(trips, calendar)
    raw = bm.segment_crossings(polys, shape_routes)
    nodes = bm.cluster_nodes(raw)
    near_nodes, near_stops = bm.stop_overlap(nodes, stops)
    multi = sum(1 for n in nodes if len(n["routes"]) >= 3)
    print(f"stops={len(stops)} routes={len(routes)} trips={len(trips)}")
    print(f"shapes={len(polys)} wed_shapes={len(shape_routes)}")
    print(f"raw_crossings={len(raw)} nodes_60m={len(nodes)} "
          f"nodes_ge3routes={multi}")
    print(f"nodes_near_stop={near_nodes} stops_near_node={near_stops} "
          f"of {len(stops)} stops")


if __name__ == "__main__":
    main()
