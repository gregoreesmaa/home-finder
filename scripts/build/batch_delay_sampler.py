"""Tallinn GPS typical-delay sampler + table builder (issues #629/#667).

Cron step (`pull`): ONE polite gps.txt snapshot per invocation into a
timestamped cache file (the 60 s cadence guard lives in
fetch_gps_snapshot -- faster re-invocations are no-ops). Build step
(`build`): all cached snapshots -> vehicle-tracked segment speeds ->
corridor x hour typical/free-flow table -> delay/delay-corridors.json.

Corridor web (#667): every GTFS trip shape is a corridor (name
"short · headsign", road-following ribbon strips on the map); legacy
8 street corridors survive ONLY as the GTFS-less fallback (and the
hermetic-test default). Free-flow baseline per corridor = its
off-peak ("muu") median from the SAME samples (GTFS static carries
schedules, never speeds, so the vintage validates corridor service --
weekday stops nearby -- instead of pretending to supply speeds). No
school-holiday split (documented limitation); thin cells (<20
samples) stay NULL.

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
from typing import Dict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "services", "scoring"))
from dims_p4_gtfsstops import read_gtfs_tables  # noqa: E402
from dims_p4_typical_delay import (  # noqa: E402
    CORRIDORS,
    MAP_BANDS,
    WORST_BAND,
    build_corridor_index,
    build_delay_table,
    corridor_midpoint,
    corridor_of,
    fetch_gps_snapshot,
    load_shape_corridors,
    muu_baselines,
    parse_gps_txt,
    strip_ribbon,
    table_to_pois,
    tallinn_hour,
    track_segments,
)

SNAP_PREFIX = "gps-"
SNAP_SUFFIX = ".txt"


def _resolve_corridors(snap, vintage):
    """Shape web from the GTFS vintage, else legacy CORRIDORS (pure-ish).

    Missing/unreadable vintage keeps the legacy 8 (offline fallback,
    never a failed build): the web fills in once the vintage lands.
    """
    if snap and vintage:
        path = os.path.join(snap, vintage)
        if os.path.exists(path):
            try:
                shapes = load_shape_corridors(path)
            except Exception as exc:  # noqa: BLE001 -- corrupt zip, fall back
                print("WARNING: shape web unreadable (%s) -- legacy 8"
                      % exc, flush=True)
            else:
                if shapes:
                    print("corridor web: %d GTFS shapes" % len(shapes),
                          flush=True)
                    return shapes
    print("corridor web: legacy 8 (no GTFS vintage)", flush=True)
    return CORRIDORS


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


def _gtfs_validation(snap, vintage, corridors):
    """Weekday bus stops near each corridor (service proof)."""
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
    # ONE join per stop (never corridors x stops: the 196-shape web
    # turns the naive nesting into 220k distance calls).
    counts: Dict[str, int] = {}
    for s in stops:
        name = corridor_of(s[0], s[1], corridors)
        if name:
            counts[name] = counts.get(name, 0) + 1
    for name, _poly, _bbox, _label in corridors:
        out[name] = {"weekday_stops_nearby": counts.get(name, 0)}
    return out


def _poly_bbox(poly):
    lons = [p[0] for p in poly]
    lats = [p[1] for p in poly]
    return [min(lons), min(lats), max(lons), max(lats)]


def build(cache_dir, snap, vintage=None):
    """Samples -> corridor x hour table + map sidecar."""
    corridors = _resolve_corridors(snap, vintage)
    # One prebuilt bbox index for the whole build: corridor_of scans
    # bboxes per query, and recomputing them per query stalled the
    # 196-shape web (~1 s/stop in validation).
    index = build_corridor_index(corridors)
    fixes = _fixes_from_cache(cache_dir)
    # Host-local hours: cron hosts run TZ=Europe/Tallinn (host
    # requirement -- hour bands are Tallinn wall-clock).
    segments = track_segments(fixes, hour_of=tallinn_hour,
                              corridors=index)
    table = build_delay_table(segments)
    baselines = muu_baselines(segments)
    validation = _gtfs_validation(snap, vintage, index)
    by_corridor = {}
    for (c, band), cell in table.items():
        by_corridor.setdefault(c, {})[band] = cell
    areas = []
    for name, poly, _bbox, _label in index:
        mid = corridor_midpoint(name, index)
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
        ring = strip_ribbon(poly)
        areas.append({"corridor": name,
                      "factors": factors, "ns": ns,
                      "gtfs": validation.get(name, {}),
                      "rep": {"lon": mid[0], "lat": mid[1]} if mid else None,
                      "b": _poly_bbox(poly),
                      "r": [ring] if ring else []})
    doc = {"vintage": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "cells": [{"corridor": c, "hour_band": band,
                      "factor": cell["factor"], "n": cell["n"]}
                     for (c, band), cell in sorted(table.items())],
           "pois": table_to_pois(table, index),
           "areas": areas,
           "stats": {"fixes": len(fixes), "segments": len(segments),
                     "cells": len(table),
                     "corridors": len(corridors),
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
