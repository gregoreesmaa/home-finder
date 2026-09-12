"""Batch 4 Group 13 builder: p342 rideshare availability & wait (PROKSI).

Honest minutes proxy -- NOT measured Bolt ETA data (no such feed exists
offline). Model, documented in code, legend and reviewer notes:

  Tn = S_t / (S_t + 1500)      transit supply: kernel-weighted Wednesday
                               GTFS departures nearby (sigma=0.3 km).
                               Proxy logic: frequent transit corridors are
                               where drivers idle and demand pools.
  Rn = D / (D + 800)           road supply: kernel-weighted car-graph nodes
                               nearby (sigma=0.3 km). Proxy logic: dense
                               drivable streets = short pickup detours.
  wait = 2 + 13 * (1 - 0.5*Tn - 0.5*Rn)   minutes, clamped to [2, 15].
  score = 100 * (15 - wait) / 13          2 min -> 100, 15 min -> 0, linear.

Calibrated 2026-09-12: Balti ~4.9 min (78), Oismae ~6.9 (62), Lasnamae
~7.9 (55), Viimsi ~10.2 (37), deep rural ~14.6 (3). Cells with neither
signal (S_t == 0 and D == 0) stay 255 = unknown (renders red, honest);
score 0 is known-bad (mirrors the schools far-field=0 precedent).

Compute is Dijkstra-free by design: euclidean kernel stamps over a
spatial bucket index (stops) + a 300 m coarse road-density grid sampled
nearest. "No new full-Harjumaa Dijkstra per layer" holds trivially --
there are none at all here. The walk graph is not even loaded.
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_b4_common import (  # noqa: E402
    COUNTY_BBOX,
    kernel,
)

KX = 111.32 * math.cos(math.radians(59.0))
KY = 110.57
COARSE_M = 300.0


def transit_norm(s, half=1500.0):
    return s / (s + half) if s > 0 else 0.0


def road_norm(d, half=800.0):
    return d / (d + half) if d > 0 else 0.0


def wait_from_norms(tn, rn, wait_min=2.0, wait_max=15.0):
    """Estimated pickup wait in REAL minutes (proxy -- see module docstring)."""
    w = wait_min + (wait_max - wait_min) * (1.0 - 0.5 * tn - 0.5 * rn)
    return min(wait_max, max(wait_min, w))


def score_from_wait(w, wait_min=2.0, wait_max=15.0):
    """Absolute 0-100 score: linear, wait_min -> 100, wait_max -> 0."""
    return 100.0 * (wait_max - w) / (wait_max - wait_min)


def grid_shape(bbox, step_m):
    minlon, minlat, maxlon, maxlat = bbox
    cols = int(round((maxlon - minlon) * KX * 1000 / step_m))
    rows = int(round((maxlat - minlat) * KY * 1000 / step_m))
    return cols, rows


def cell_of(bbox, step_m, cols, rows, lon, lat):
    ix = int((lon - bbox[0]) * KX * 1000 / step_m)
    iy = int((lat - bbox[1]) * KY * 1000 / step_m)
    if 0 <= ix < cols and 0 <= iy < rows:
        return iy * cols + ix
    return None


def center_of(bbox, step_m, cols, k):
    ix, iy = k % cols, k // cols
    return (bbox[0] + (ix + 0.5) * step_m / 1000 / KX,
            bbox[1] + (iy + 0.5) * step_m / 1000 / KY)


def stamp_euclid(acc, bbox, step_m, cols, rows, lon, lat, weight, sigma, cutoff):
    """Add weight*K(d) to cells within cutoff km of (lon, lat)."""
    x0 = (lon - bbox[0]) * KX
    y0 = (lat - bbox[1]) * KY
    r = cutoff
    ix0 = max(0, int((x0 - r) * 1000 / step_m))
    ix1 = min(cols - 1, int((x0 + r) * 1000 / step_m))
    iy0 = max(0, int((y0 - r) * 1000 / step_m))
    iy1 = min(rows - 1, int((y0 + r) * 1000 / step_m))
    touched = 0
    for iy in range(iy0, iy1 + 1):
        clat = bbox[1] + (iy + 0.5) * step_m / 1000 / KY
        for ix in range(ix0, ix1 + 1):
            clon = bbox[0] + (ix + 0.5) * step_m / 1000 / KX
            d = math.hypot((clon - lon) * KX, (clat - lat) * KY)
            if d > cutoff:
                continue
            k = iy * cols + ix
            acc[k] = acc.get(k, 0.0) + weight * kernel(d, sigma)
            touched += 1
    return touched


def build_scores(bbox, step_m, stops, car_nodes, sigma=0.3,
                 transit_half=1500.0, road_half=800.0,
                 wait_min=2.0, wait_max=15.0):
    """County/metro score field. Pure function -- hermetically unit-tested.

    stops: [(lon, lat, wed_trips)]; car_nodes: [(lon, lat)].
    Returns (scores, stats) with scores = {cell: 0..100 int}.
    """
    cols, rows = grid_shape(bbox, step_m)
    cutoff = 4 * sigma
    s_transit = {}
    for lon, lat, trips in stops:
        if trips > 0:
            stamp_euclid(s_transit, bbox, step_m, cols, rows,
                         lon, lat, trips, sigma, cutoff)
    # Road density on a coarse grid (300 m is plenty for a wait proxy),
    # then sampled nearest at the target resolution.
    ccols, crows = grid_shape(bbox, COARSE_M)
    coarse = {}
    for lon, lat in car_nodes:
        k = cell_of(bbox, COARSE_M, ccols, crows, lon, lat)
        if k is not None:
            coarse[k] = coarse.get(k, 0) + 1
    road = {}
    for k, n in coarse.items():
        clon, clat = center_of(bbox, COARSE_M, ccols, k)
        stamp_euclid(road, bbox, COARSE_M, ccols, crows,
                     clon, clat, n, sigma, cutoff)

    def road_at(lon, lat):
        k = cell_of(bbox, COARSE_M, ccols, crows, lon, lat)
        return road.get(k, 0.0) if k is not None else 0.0

    scores = {}
    for k, s in s_transit.items():
        lon, lat = center_of(bbox, step_m, cols, k)
        w = wait_from_norms(transit_norm(s, transit_half),
                            road_norm(road_at(lon, lat), road_half),
                            wait_min, wait_max)
        scores[k] = int(round(score_from_wait(w, wait_min, wait_max)))
    # Road-only cells (no transit at all): known-bad, not unknown --
    # unless there is no road signal either.
    for k in range(cols * rows):
        if k in scores:
            continue
        lon, lat = center_of(bbox, step_m, cols, k)
        d = road_at(lon, lat)
        if d <= 0:
            continue  # 255 = unknown
        w = wait_from_norms(0.0, road_norm(d, road_half), wait_min, wait_max)
        scores[k] = int(round(score_from_wait(w, wait_min, wait_max)))
    stats = {"cols": cols, "rows": rows, "cells": len(scores),
             "transit_cells": len(s_transit), "road_cells": len(road)}
    return scores, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--derived", default=None)
    ap.add_argument("--step-m", type=float, default=75.0)
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    args = ap.parse_args()

    from batch_b4_common import CAL, read_gtfs, service_ids_for, departures_per_stop
    cal = CAL["rideshare"]
    gtfs = read_gtfs(os.path.join(args.snap, "gtfs", "tallinn-gtfs-2026-09-11.zip"))
    wed = service_ids_for(gtfs["calendar.txt"], "wednesday")
    cnt, _ = departures_per_stop(gtfs, wed)
    stops = [(float(s["stop_lon"]), float(s["stop_lat"]), cnt[s["stop_id"]])
             for s in gtfs["stops.txt"] if s["stop_id"] in cnt]
    car = json.load(open(os.path.join(args.snap, "osm", "harju-car-graph.json")))
    car_nodes = [(float(lo), float(la)) for lo, la in car["nodes"]]
    print("rideshare: %d gtfs stops, %d car nodes" % (len(stops), len(car_nodes)))

    if args.derived:
        with open(args.derived, "w", encoding="utf-8") as f:
            # Transit-only fallback points: the TS Euclidean path estimates
            # wait from trips alone at MEAN road density (documented in
            # layers_batch4.ts); the raster below is the full two-signal map.
            json.dump([{"lon": lo, "lat": la, "t": t} for lo, la, t in stops], f)
        print("rideshare: wrote %d fallback points to %s" % (len(stops), args.derived))

    scores, stats = build_scores(
        args.bbox, args.step_m, stops, car_nodes, cal["sigma"],
        cal["transit_half"], cal["road_half"], cal["wait_min"], cal["wait_max"])
    print("rideshare: %s" % (stats,))

    cols, rows = stats["cols"], stats["rows"]
    vals = bytearray(255 for _ in range(cols * rows))
    for k, v in scores.items():
        vals[k] = v
    meta = {"bbox": {"minlon": args.bbox[0], "minlat": args.bbox[1],
                     "maxlon": args.bbox[2], "maxlat": args.bbox[3]},
            "step_m": args.step_m, "cols": cols, "rows": rows,
            "half": None, "sigma": cal["sigma"], "per": 0, "cap": 0,
            "waitMin": cal["wait_min"], "waitMax": cal["wait_max"],
            "unknown": 255, "dtype": "uint8"}
    if args.format == "split":
        prefix = os.path.join(args.out, "rideshare-metro")
        with open(prefix + ".json", "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in meta.items()}, f)
        with open(prefix + ".u8", "wb") as f:
            f.write(bytes(vals))
        print("wrote %s.json + .u8" % prefix)
    else:
        import base64
        meta["data"] = base64.b64encode(bytes(vals)).decode("ascii")
        with open(os.path.join(args.out, "rideshare-walk-raster.json"), "w",
                  encoding="utf-8") as f:
            json.dump(meta, f)
        print("wrote rideshare-walk-raster.json")


if __name__ == "__main__":
    main()
