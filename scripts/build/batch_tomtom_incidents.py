"""Keyed TomTom daily incident harvester (issue #672).

Runs ONLY on a user-supplied env key (TOMTOM_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test).

ToS step-zero verdict (docs/p4_tomtom_matrix.md section 0, repeated in
docs/p4_tomtom_incidents.md section 0): SHORT-TERM CACHE ONLY
(TomTom Portal Terms 11.4 + 11.6). No sidecars are committed and no
tables are stored: --pull fills a git-ignored operator cache dir
(TTL-capped, cache-control max-age honored), --build reads that cache
(or a fixture file) and prints counts to stdout. Stale snapshots
expire (see dims_tomtom_incidents.is_fresh), never presented as live.

Delegates the pull to services/scoring/dims_tomtom_incidents.
fetch_incidents (quota cap INCIDENTS_MAX_CALLS = 2 per 6 h window =
1-2 txn/day, 429 = stop, transport never cached), so quota/TTL
semantics agree with the scorer by construction.

Usage:
  TOMTOM_API_KEY=... python3 scripts/build/batch_tomtom_incidents.py \\
      --pull --build --cache-dir DIR
Key placement: export the variable in the operator shell only (see
docs/p4_tomtom_incidents.md section 7); never commit it, never put it
in repo files.
"""

import argparse
import json
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_tomtom_incidents import (  # noqa: E402
    INCIDENTS_MAX_CALLS,
    INCIDENTS_TTL_S,
    TALLINN_BBOX,
    TOMTOM_KEY_ENV,
    _quota_used,
    build_table,
    fetch_incidents,
    parse_incidents_response,
)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed TomTom incident pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--bbox", default=TALLINN_BBOX)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--fixture", default=None,
                    help="Fixture incident JSON for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if not os.environ.get(TOMTOM_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TomTom võti selles terminalis (vt "
              "docs/p4_tomtom_incidents.md §7); midagi ei päritud, "
              "midagi ei kirjutatud." % TOMTOM_KEY_ENV, file=sys.stderr)
        return 2

    dest_name = "tomtom_incidents.json"
    if args.pull:
        try:
            p = os.path.join(args.cache_dir, dest_name)
            if os.path.exists(p) and time.time() - os.path.getmtime(p) \
                    < INCIDENTS_TTL_S:
                # STDOUT CONTRACT (#776/#782): stdout is the servable
                # table only (the pole wrapper redirects it into
                # built/tomtom-incidents/table.json); human status rides
                # stderr, never stdout.
                print("ok: värske puhver, uusi päringuid ei tehtud (%s)"
                      % args.cache_dir, file=sys.stderr)
                if not args.build:
                    return 0
                args.pull = False
        except OSError:
            pass
    if args.pull and _quota_used(args.cache_dir) >= INCIDENTS_MAX_CALLS:
        print("error: keeldun - TomTom intsidentide kvoot on täis (2 "
              "päringut / 6 tundi); midagi ei päritud.",
              file=sys.stderr)
        return 2
    if args.pull:
        dest = fetch_incidents(args.cache_dir, dest_name, bbox=args.bbox)
        if dest is None:
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver, täis kvoot või transport/429) - midagi uut "
                  "ei puhvritatud.", file=sys.stderr)
            return 1
        print("ok: intsidentide päring puhvritatud (%s)" % dest,
              file=sys.stderr)
    if args.build:
        rows: List[dict] = []
        fetched_at: Optional[float] = None
        if args.fixture:
            rows = parse_incidents_response(args.fixture)
            fetched_at = time.time()
        else:
            p = os.path.join(args.cache_dir, dest_name)
            if os.path.exists(p):
                rows = parse_incidents_response(p)
                try:
                    fetched_at = os.path.getmtime(p)
                except OSError:
                    fetched_at = None
        table = build_table(rows, fetched_at)
        # STDOUT CONTRACT (#776/#782): exactly one JSON doc, the full
        # table — the pole wrapper redirects stdout into
        # built/tomtom-incidents/table.json and the web route parses it
        # (incidents + fetched_at + counts). Human status rides stderr.
        print(json.dumps(table, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
