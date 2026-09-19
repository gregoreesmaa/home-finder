"""Keyed TomTom commute-shed harvester (issue #670).

Runs ONLY on a user-supplied env key (TOMTOM_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test).

ToS step-zero verdict (docs/p4_tomtom_matrix.md section 0, repeated in
docs/p4_tomtom_isochrones.md section 0): SHORT-TERM CACHE ONLY
(TomTom Portal Terms 11.4 + 11.6). No sidecars are committed and no
tables are stored: --pull fills a git-ignored operator cache dir
(TTL-capped, cache-control max-age honored), --build reads that cache
(or a fixture file) and prints counts to stdout.

Delegates the pull to services/scoring/dims_tomtom_isochrones.
fetch_shed (quota cap SHED_MAX_CALLS = 20 per 7 d window = 5 hubs x 2
budgets x 2 bands, 429 = stop, transport never cached), so quota/TTL
semantics agree with the scorer by construction.

Usage:
  TOMTOM_API_KEY=... python3 scripts/build/batch_tomtom_isochrones.py \\
      --pull --build --cache-dir DIR
Key placement: export the variable in the operator shell only (see
docs/p4_tomtom_isochrones.md section 7); never commit it, never put
it in repo files.
"""

import argparse
import json
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_tomtom_isochrones import (  # noqa: E402
    DEPART_OFFPEAK,
    DEPART_RUSH,
    SHED_BUDGETS_S,
    SHED_MAX_CALLS,
    SHED_TTL_S,
    TOMTOM_KEY_ENV,
    _quota_used,
    build_table,
    fetch_shed,
    parse_shed_response,
)

#: Same 5 job hubs as the matrix issue (approximate public
#: coordinates; override with --hubs-file).
DEFAULT_HUBS = (
    {"id": "city-center", "name": "Kesklinn", "lat": 59.4370, "lon": 24.7535},
    {"id": "ulemiste", "name": "Ülemiste", "lat": 59.4215, "lon": 24.7996},
    {"id": "mustamae", "name": "Mustamäe", "lat": 59.4050, "lon": 24.6850},
    {"id": "port", "name": "Sadam", "lat": 59.4431, "lon": 24.7672},
    {"id": "airport", "name": "Lennujaam", "lat": 59.4133, "lon": 24.8328},
)


def _load_hubs(path: Optional[str]) -> List[dict]:
    if not path:
        return list(DEFAULT_HUBS)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    hubs = data.get("hubs", data) if isinstance(data, dict) else data
    return [h for h in hubs if isinstance(h, dict)]


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed TomTom shed pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--hubs-file", default=None)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--fixture", default=None,
                    help="Fixture shed JSON for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if not os.environ.get(TOMTOM_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TomTom võti selles terminalis (vt "
              "docs/p4_tomtom_isochrones.md §7); midagi ei päritud, "
              "midagi ei kirjutatud." % TOMTOM_KEY_ENV, file=sys.stderr)
        return 2

    hubs = _load_hubs(args.hubs_file)
    bands = (("rush", DEPART_RUSH), ("offpeak", DEPART_OFFPEAK))
    if args.pull:
        expected = ["tomtom_shed_%s_%d_%s.json" % (h["id"], b, band)
                    for h in hubs for b in SHED_BUDGETS_S
                    for band, _ in bands]
        try:
            if expected and all(
                    os.path.exists(os.path.join(args.cache_dir, f))
                    and time.time() - os.path.getmtime(
                        os.path.join(args.cache_dir, f)) < SHED_TTL_S
                    for f in expected):
                print("ok: värske puhver, uusi päringuid ei tehtud (%s)"
                      % args.cache_dir)
                if not args.build:
                    return 0
                args.pull = False
        except OSError:
            pass
    if args.pull and _quota_used(args.cache_dir) >= SHED_MAX_CALLS:
        print("error: keeldun - TomTom ulatuse kvoot on täis (20 "
              "päringut / 7 ööpäeva); midagi ei päritud.",
              file=sys.stderr)
        return 2
    if args.pull:
        pulled = 0
        for hub in hubs:
            for budget in SHED_BUDGETS_S:
                for band, depart in bands:
                    dest = fetch_shed(
                        hub["lat"], hub["lon"], budget, depart,
                        args.cache_dir,
                        "tomtom_shed_%s_%d_%s.json"
                        % (hub["id"], budget, band))
                    if dest is not None:
                        pulled += 1
        if pulled == 0:
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver, täis kvoot või transport/429) - midagi uut "
                  "ei puhvritatud.", file=sys.stderr)
            return 1
        print("ok: %d ulatuspäringut puhvritatud (%s)" % (pulled,
                                                         args.cache_dir))
    if args.build:
        rows: List[dict] = []
        if args.fixture:
            ring = parse_shed_response(args.fixture)
            hub0 = hubs[0]["id"] if hubs else "city-center"
            rows = [{"hub": hub0, "budget_s": 1800, "band": "rush",
                     "ring": ring}]
        else:
            for hub in hubs:
                for budget in SHED_BUDGETS_S:
                    for band, _ in bands:
                        p = os.path.join(
                            args.cache_dir,
                            "tomtom_shed_%s_%d_%s.json"
                            % (hub["id"], budget, band))
                        if not os.path.exists(p):
                            continue
                        rows.append({"hub": hub["id"], "budget_s": budget,
                                     "band": band,
                                     "ring": parse_shed_response(p)})
        table = build_table(rows)
        print(json.dumps(table["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
