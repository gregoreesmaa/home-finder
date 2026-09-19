"""Keyed TomTom EV-charging POI harvester (issue #673).

Runs ONLY on a user-supplied env key (TOMTOM_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test).

ToS step-zero verdict (docs/p4_tomtom_matrix.md section 0, repeated in
docs/p4_tomtom_ev.md section 0): SHORT-TERM CACHE ONLY (TomTom Portal
Terms 11.4 + 11.6). No sidecars are committed and no POI lists are
stored: --pull fills a git-ignored operator cache dir (TTL-capped,
cache-control max-age honored), --build reads that cache (or fixture
files) and prints counts to stdout.

STATIC LOCATIONS ONLY: real-time per-plug availability is an
enterprise product - the harvester ingests locations + connector
types, never availability; UI labels them static (pinned by test).

Delegates the pull to services/scoring/dims_tomtom_evpois.fetch_evpois
(quota cap EV_MAX_CALLS = 20 per 30 d window = ~20 txn/monthly
refresh, 429 = stop, transport never cached), so quota/TTL semantics
agree with the scorer by construction.

Usage:
  TOMTOM_API_KEY=... python3 scripts/build/batch_tomtom_evpois.py \\
      --pull --build --cache-dir DIR
Key placement: export the variable in the operator shell only (see
docs/p4_tomtom_ev.md section 7); never commit it, never put it in
repo files.
"""

import argparse
import glob
import json
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_tomtom_evpois import (  # noqa: E402
    EV_CATEGORY,
    EV_CATEGORY_VERIFIED,
    EV_MAX_CALLS,
    EV_TTL_S,
    TOMTOM_KEY_ENV,
    _quota_used,
    build_table,
    fetch_evpois,
    parse_evpois_response,
)

#: Static tile centers over Tallinn (public district facts, ToS-clean
#: to commit; the operator refines via --tiles-file). Radius covers
#: tile gaps with overlap.
DEFAULT_TILES = (
    {"tile_id": "kesklinn", "lat": 59.4370, "lon": 24.7535},
    {"tile_id": "lasnamae", "lat": 59.4400, "lon": 24.8300},
    {"tile_id": "mustamae", "lat": 59.4050, "lon": 24.6900},
    {"tile_id": "nomme", "lat": 59.3800, "lon": 24.6800},
    {"tile_id": "pirita", "lat": 59.4650, "lon": 24.8200},
    {"tile_id": "haabersti", "lat": 59.4300, "lon": 24.6500},
)
TILE_RADIUS_M = 4000


def _load_tiles(path: Optional[str]) -> List[dict]:
    if not path:
        return list(DEFAULT_TILES)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    tiles = data.get("tiles", data) if isinstance(data, dict) else data
    out = []
    for t in tiles:
        if not isinstance(t, dict):
            continue
        try:
            out.append({"tile_id": t.get("tile_id", t.get("id")),
                        "lat": float(t["lat"]), "lon": float(t["lon"])})
        except (TypeError, ValueError, KeyError):
            continue
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed TomTom EV-POI pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--category", type=int, default=EV_CATEGORY,
                    help="Search categorySet value (default 7309, "
                         "SPIKE-UNVERIFIED: resolve via one POI-Categories "
                         "call before the first keyed pull).")
    ap.add_argument("--tiles-file", default=None)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--fixture-dir", default=None,
                    help="Fixture search JSONs for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if not os.environ.get(TOMTOM_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TomTom võti selles terminalis (vt "
              "docs/p4_tomtom_ev.md §7); midagi ei päritud, midagi "
              "ei kirjutatud." % TOMTOM_KEY_ENV, file=sys.stderr)
        return 2
    if not EV_CATEGORY_VERIFIED:
        print("warning: kategooria %d on kinnitamata (vt "
              "docs/p4_tomtom_ev.md §0); enne esimest võtmega päringut "
              "kontrolli POI-Categories päringuga." % args.category,
              file=sys.stderr)

    tiles = _load_tiles(args.tiles_file)
    if args.pull:
        expected = ["tomtom_ev_%s.json" % t["tile_id"] for t in tiles]
        try:
            if expected and all(
                    os.path.exists(os.path.join(args.cache_dir, f))
                    and time.time() - os.path.getmtime(
                        os.path.join(args.cache_dir, f)) < EV_TTL_S
                    for f in expected):
                print("ok: värske puhver, uusi päringuid ei tehtud (%s)"
                      % args.cache_dir)
                if not args.build:
                    return 0
                args.pull = False
        except OSError:
            pass
    if args.pull and _quota_used(args.cache_dir) >= EV_MAX_CALLS:
        print("error: keeldun - TomTom EV-kvoot on täis (20 päringut "
              "/ 30 ööpäeva); midagi ei päritud.", file=sys.stderr)
        return 2
    if args.pull:
        if not tiles:
            print("error: ruudustik on tühi; midagi ei päritud.",
                  file=sys.stderr)
            return 1
        pulled = 0
        for t in tiles:
            dest = fetch_evpois(t["lat"], t["lon"], TILE_RADIUS_M,
                                args.cache_dir,
                                "tomtom_ev_%s.json" % t["tile_id"],
                                category=args.category)
            if dest is not None:
                pulled += 1
        if pulled == 0:
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver, täis kvoot või transport/429) - midagi uut "
                  "ei puhvritatud.", file=sys.stderr)
            return 1
        print("ok: %d EV-päringut puhvritatud (%s)" % (pulled,
                                                      args.cache_dir))
    if args.build:
        rows: List[dict] = []
        seen = set()
        paths = (sorted(glob.glob(os.path.join(args.fixture_dir, "*.json")))
                 if args.fixture_dir else
                 [os.path.join(args.cache_dir, "tomtom_ev_%s.json"
                               % t["tile_id"]) for t in tiles])
        for p in paths:
            if not os.path.exists(p):
                continue
            for poi in parse_evpois_response(p):
                pid = poi.get("poi_id") or (poi.get("name"), poi.get("lat"),
                                            poi.get("lon"))
                if pid in seen:
                    continue
                seen.add(pid)
                rows.append(poi)
        table = build_table(rows)
        print(json.dumps(table["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
