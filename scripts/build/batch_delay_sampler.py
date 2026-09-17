"""Tallinn GPS typical-delay sampler + table builder (issue #629).

Cron step (`pull`): ONE polite gps.txt snapshot per invocation into a
timestamped cache file (the 60 s cadence guard lives in
fetch_gps_snapshot -- faster re-invocations are no-ops). Build step
(`build`): all cached snapshots -> vehicle-tracked segment speeds ->
corridor x hour typical/free-flow table -> delay/delay-corridors.json.

Free-flow baseline per corridor = its off-peak ("muu") median from
the SAME samples (GTFS static carries schedules, never speeds, so the
vintage validates corridor service -- weekday stops + lines nearby --
instead of pretending to supply speeds). No school-holiday split
(documented limitation); thin cells (<20 samples) stay NULL.

Sampler host (recorded decision, #629): scheduled GitHub workflow is
REJECTED (artefact round-trip for a 60 s+ cadence pull is the wrong
tool); production host = container cron sidecar (compose follow-up),
research pulls = maintainer machine. The committed automation surface
stays unchanged by this issue.

Usage:
  python3 scripts/build/batch_delay_sampler.py --pull --cache-dir /tmp/hf-delay
  python3 scripts/build/batch_delay_sampler.py --build --cache-dir /tmp/hf-delay \\
      --snap ~/hf-data/2026-09-17 [--vintage gtfs/tallinn-gtfs-2026-09-11.zip]
"""

import argparse
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "services", "scoring"))
from dims_p4_gtfsstops import read_gtfs_tables  # noqa: E402
from dims_p4_typical_delay import (  # noqa: E402
    CORRIDORS,
    MAP_BANDS,
    WORST_BAND,
    build_delay_table,
    corridor_midpoint,
    corridor_of,
    fetch_gps_snapshot,
    muu_baselines,
    parse_gps_txt,
    table_to_pois,
    tallinn_hour,
    track_segments,
)

SNAP_PREFIX = "gps-"
SNAP_SUFFIX = ".txt"

#: Strip half-width (m) around a corridor segment for the map band.
MAP_HALF_WIDTH_M = 250.0


def pull(cache_dir):
    """One cron pull -> timestamped snapshot path (or cached no-op)."""
    os.makedirs(cache_dir, exist_ok=True)
    name = "%s%d%s" % (SNAP_PREFIX, int(time.time()), SNAP_SUFFIX)
    dest = fetch_gps_snapshot(cache_dir, name)
    print("pull -> %s" % dest, flush=True)
    return dest


def _fixes_from_cache(cache_dir):
    """Cached snapshots -> timestamped road-vehicle fixes."""
    fixes = []
    for path in sorted(glob.glob(os.path.join(cache_dir,
                                               SNAP_PREFIX + "*" +
                                               SNAP_SUFFIX))):
        try:
            stamp = int(os.path.basename(path)[len(SNAP_PREFIX):-len(
                SNAP_SUFFIX)])
        except ValueError:
            stamp = int(os.path.getmtime(path))
        for rec in parse_gps_txt(path):
            if rec.get("vtype") not in (1, 2, 7):
                continue  # trams run on rails, not in jams
            fixes.append({"vehicle": rec["vehicle"], "t": float(stamp),
                          "lat": rec["lat"], "lon": rec["lon"]})
    return fixes


def _gtfs_validation(snap, vintage):
    """Weekday bus stops + lines near each corridor (service proof)."""
    out = {}
    if not snap or not vintage:
        return out
    path = os.path.join(snap, vintage)
    if not os.path.exists(path):
        print("WARNING: GTFS vintage missing %s -- validation skipped"
              % path, flush=True)
        return out
    gtfs = read_gtfs_tables(path)
    stops = []
    for row in gtfs.get("stops.txt", []):
        try:
            stops.append((float(row["stop_lat"]), float(row["stop_lon"]),
                          row.get("stop_id", "")))
        except (TypeError, ValueError, KeyError):
            continue
    # Lines NOT mapped: route-to-corridor needs GTFS shapes.txt, absent
    # from the vintage -- stops-nearby is the validation, honestly thin.
    for name, _a, _b, _label in CORRIDORS:
        near = [s for s in stops if corridor_of(s[0], s[1]) == name]
        out[name] = {"weekday_stops_nearby": len(near)}
    return out


def _strip_polygon(a, b, half_m=MAP_HALF_WIDTH_M):
    """Corridor segment -> narrow map band quad (display only).

    Equirectangular degrees (documented approx): the band shows the
    500 m join window, never a surveyed road polygon.
    """
    import math
    (x0, y0), (x1, y1) = a, b
    mx = math.cos(math.radians((y0 + y1) / 2))
    dx, dy = (x1 - x0) * mx, y1 - y0
    leng = math.hypot(dx, dy) or 1e-9
    dlat = half_m / 6371000.0 * 180.0 / math.pi
    # Perpendicular offset in degrees (lon scaled by cos latitude).
    ox = -dy / leng * dlat / max(mx, 0.2)
    oy = dx / leng * dlat
    quad = [[x0 + ox, y0 + oy], [x1 + ox, y1 + oy],
            [x1 - ox, y1 - oy], [x0 - ox, y0 - oy],
            [x0 + ox, y0 + oy]]
    return [quad]


def build(cache_dir, snap, vintage=None):
    """Samples -> corridor x hour table + map sidecar."""
    fixes = _fixes_from_cache(cache_dir)
    # Host-local hours: cron hosts run TZ=Europe/Tallinn (host
    # requirement -- hour bands are Tallinn wall-clock).
    segments = track_segments(fixes, hour_of=tallinn_hour)
    table = build_delay_table(segments)
    baselines = muu_baselines(segments)
    validation = _gtfs_validation(snap, vintage)
    by_corridor = {}
    for (c, band), cell in table.items():
        by_corridor.setdefault(c, {})[band] = cell
    areas = []
    for name, a, b, _label in CORRIDORS:
        mid = corridor_midpoint(name)
        cells = by_corridor.get(name, {})
        factors = {}
        ns = {}
        for band in MAP_BANDS:
            if band == "muu":
                base = baselines.get(name)
                # Off-peak IS the free-flow anchor: factor 1.0 where
                # measured (n >= 20), else NULL (never assumed).
                factors[band] = 1.0 if base else None
                ns[band] = base["n"] if base else 0
            else:
                cell = cells.get(band)
                factors[band] = cell["factor"] if cell else None
                ns[band] = cell["n"] if cell else 0
        peaks = [factors[band] for band in MAP_BANDS
                 if band != "muu" and factors[band] is not None]
        factors[WORST_BAND] = max(peaks) if peaks else None
        ns[WORST_BAND] = max([ns[band] for band in MAP_BANDS
                              if band != "muu"] or [0])
        xs = [a[0], b[0]]
        ys = [a[1], b[1]]
        areas.append({"corridor": name,
                      "factors": factors, "ns": ns,
                      "gtfs": validation.get(name, {}),
                      "rep": {"lon": mid[0], "lat": mid[1]} if mid else None,
                      "b": [min(xs), min(ys), max(xs), max(ys)],
                      "r": _strip_polygon(a, b)})
    doc = {"vintage": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "cells": [{"corridor": c, "hour_band": band,
                      "factor": cell["factor"], "n": cell["n"]}
                     for (c, band), cell in sorted(table.items())],
           "pois": table_to_pois(table),
           "areas": areas,
           "stats": {"fixes": len(fixes), "segments": len(segments),
                     "cells": len(table),
                     "corridors": len(CORRIDORS),
                     "attribution": ("Tallinna Linnavalitsus GPS "
                                     "(keyless gps.txt) + TLT GTFS "
                                     "vintage (schedules, validation)")}}
    out = os.path.join(snap, "delay", "delay-corridors.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    print("fixes=%d segments=%d cells=%d -> %s"
          % (len(fixes), len(segments), len(table), out), flush=True)
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", default="/tmp/hf-delay")
    ap.add_argument("--snap", default=None)
    ap.add_argument("--vintage", default=None)
    args = ap.parse_args(argv)
    if args.pull:
        pull(args.cache_dir)
    if args.build:
        if not args.snap:
            ap.error("--snap is required for --build")
        build(args.cache_dir, args.snap, args.vintage)
    if not args.pull and not args.build:
        ap.error("nothing to do: pass --pull and/or --build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
