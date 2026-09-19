"""Keyed TomTom car-commute-matrix harvester (issue #669).

Runs ONLY on a user-supplied env key (TOMTOM_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test).

ToS step-zero verdict (docs/p4_tomtom_matrix.md section 0): SHORT-TERM
CACHE ONLY (TomTom Portal Terms 11.4 + 11.6). No sidecars are committed
and no tables are stored: --pull fills a git-ignored operator cache
dir (TTL-capped, cache-control max-age honored), --build reads that
cache (or a fixture file) and prints the table to stdout.

Delegates the pull to services/scoring/dims_tomtom_matrix.fetch_matrix
(quota cap MATRIX_MAX_CALLS = 10 per 2 d window ~= 1960 txn/refresh,
429 = stop, transport never cached), so quota/TTL semantics agree with
the scorer by construction.

Usage:
  TOMTOM_API_KEY=... python3 scripts/build/batch_tomtom_matrix.py \\
      --pull --build --areas-file areas.json --cache-dir DIR
Key placement: export the variable in the operator shell only (see
docs/p4_tomtom_matrix.md section 7); never commit it, never put it in
repo files.
"""

import argparse
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_tomtom_matrix import (  # noqa: E402
    DEPART_OFFPEAK,
    DEPART_RUSH,
    HUBS,
    TOMTOM_KEY_ENV,
    _quota_used,
    build_table,
    fetch_matrix,
    parse_matrix_response,
    MATRIX_MAX_CALLS,
    MATRIX_TTL_S,
)


def _load_areas(path: str) -> List[dict]:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    areas = data.get("areas", data) if isinstance(data, dict) else data
    out = []
    for a in areas:
        if not isinstance(a, dict):
            continue
        try:
            out.append({"area_id": a.get("area_id", a.get("id")),
                        "lat": float(a["lat"]), "lon": float(a["lon"])})
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _load_hubs(path: Optional[str]) -> List[dict]:
    if not path:
        return list(HUBS)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    hubs = data.get("hubs", data) if isinstance(data, dict) else data
    return [h for h in hubs if isinstance(h, dict)]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed TomTom matrix pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--areas-file", default=None)
    ap.add_argument("--hubs-file", default=None)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--fixture", default=None,
                    help="Fixture matrix JSON for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if not os.environ.get(TOMTOM_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TomTom võti selles terminalis (vt "
              "docs/p4_tomtom_matrix.md §7); midagi ei päritud, midagi "
              "ei kirjutatud." % TOMTOM_KEY_ENV, file=sys.stderr)
        return 2
    hubs = _load_hubs(args.hubs_file)
    rows: List[dict] = []
    if args.pull:
        import time
        expected = ["tomtom_matrix_%s_%s.json" % (h["id"], b)
                    for h in hubs for b in ("rush", "offpeak")]
        try:
            if expected and all(
                    os.path.exists(os.path.join(args.cache_dir, f))
                    and time.time() - os.path.getmtime(
                        os.path.join(args.cache_dir, f)) < MATRIX_TTL_S
                    for f in expected):
                print("ok: värske puhver, uusi päringuid ei tehtud (%s)"
                      % args.cache_dir)
                if not args.build:
                    return 0
                args.pull = False
        except OSError:
            pass
    if args.pull and _quota_used(args.cache_dir) >= MATRIX_MAX_CALLS:
        print("error: keeldun - TomTom Matrix kvoot on täis (10 "
              "päringut / 2 ööpäeva); midagi ei päritud.",
              file=sys.stderr)
        return 2
    if args.pull:
        if not args.areas_file:
            print("error: --pull vajab --areas-file (196 GTFS-ala "
                  "tsentroidi, operaatori fail, mitte repositoorium).",
                  file=sys.stderr)
            return 2
        areas = _load_areas(args.areas_file)
        if not areas:
            print("error: --areas-file on tühi või vigane; midagi ei "
                  "päritud.", file=sys.stderr)
            return 1
        pulled = 0
        for hub in hubs:
            for band, depart in (("rush", DEPART_RUSH),
                                 ("offpeak", DEPART_OFFPEAK)):
                dest = fetch_matrix(
                    areas, hub, depart, args.cache_dir,
                    "tomtom_matrix_%s_%s.json" % (hub["id"], band))
                if dest is not None:
                    pulled += 1
        if pulled == 0:
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver, täis kvoot või transport/429) - midagi uut "
                  "ei puhvritatud.", file=sys.stderr)
            return 1
        print("ok: %d Matrix-päringut puhvritatud (%s)" % (pulled,
                                                          args.cache_dir))
    if args.build:
        cells: List[dict] = []
        if args.fixture:
            cells = parse_matrix_response(args.fixture)
            rows = [{"area_id": "fixture-%d" % c["origin_idx"],
                     "hub": hubs[0]["id"] if hubs else "city-center",
                     "rush_s": c["travel_s"], "offpeak_s": c["travel_s"]}
                    for c in cells]
        else:
            import glob
            for hub in hubs:
                rush_p = os.path.join(
                    args.cache_dir,
                    "tomtom_matrix_%s_rush.json" % hub["id"])
                off_p = os.path.join(
                    args.cache_dir,
                    "tomtom_matrix_%s_offpeak.json" % hub["id"])
                if not (os.path.exists(rush_p) and os.path.exists(off_p)):
                    continue
                rush = {c["origin_idx"]: c["travel_s"]
                        for c in parse_matrix_response(rush_p)}
                off = {c["origin_idx"]: c["travel_s"]
                       for c in parse_matrix_response(off_p)}
                for idx, travel in rush.items():
                    rows.append({"area_id": str(idx), "hub": hub["id"],
                                 "rush_s": travel,
                                 "offpeak_s": off.get(idx)})
        table = build_table(rows)
        print(json.dumps(table["counts"], ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
