"""Keyed TomTom geocode-repair harvester (issue #675).

Runs ONLY on a user-supplied env key (TOMTOM_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --repair and --report
paths) having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test).

Trickle design: only coord-less listings cost keyed calls, and the
address-hash cache (sha256 over the normalized address) gives ZERO
re-calls for known addresses within TTL - pinned by test. Geocodes
are named "Results" in the TomTom Portal Terms, so the cache is
TTL-bounded (30 d, re-verify after), never permanent (ToS 11.4;
verdict pasted in docs/p4_tomtom_geocode.md section 0). No sidecars
are committed and no tables are stored: the cache lives in a
git-ignored operator cache dir.

Unresolvable addresses are LOGGED to stderr, the listing is KEPT
(NULL coords, surfaced in QA) - never dropped silently.

Delegates to services/scoring/dims_tomtom_geocode (quota cap
GEOCODE_MAX_CALLS = 100 per 30 d window, 429 = stop, transport never
cached), so quota/TTL semantics agree by construction.

Usage:
  TOMTOM_API_KEY=... python3 scripts/build/batch_tomtom_geocode.py \\
      --repair --listings-file listings.json --cache-dir DIR
Key placement: export the variable in the operator shell only (see
docs/p4_tomtom_geocode.md section 7); never commit it, never put it
in repo files.
"""

import argparse
import json
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_tomtom_geocode import (  # noqa: E402
    GEOCODE_MAX_CALLS,
    TOMTOM_KEY_ENV,
    _quota_used,
    has_coords,
    repair_listings,
)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed TomTom geocode repair.")
    ap.add_argument("--repair", action="store_true")
    ap.add_argument("--report", action="store_true",
                    help="Count coord-less listings without repairing.")
    ap.add_argument("--listings-file", default=None)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--out-file", default=None,
                    help="Where to write repaired listings (operator path).")
    args = ap.parse_args(argv)
    if not args.repair and not args.report:
        args.repair = args.report = True

    if not os.environ.get(TOMTOM_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TomTom võti selles terminalis (vt "
              "docs/p4_tomtom_geocode.md §7); midagi ei päritud, "
              "midagi ei kirjutatud." % TOMTOM_KEY_ENV, file=sys.stderr)
        return 2
    if args.repair and _quota_used(args.cache_dir) >= GEOCODE_MAX_CALLS:
        print("error: keeldun - TomTom geokodeerimise kvoot on täis "
              "(100 päringut / 30 ööpäeva); midagi ei päritud.",
              file=sys.stderr)
        return 2

    if not args.listings_file:
        print("error: --repair/--report vajab --listings-file "
              "(operaatori kuulutuste fail, mitte repositoorium).",
              file=sys.stderr)
        return 2
    with open(args.listings_file, encoding="utf-8") as fh:
        data = json.load(fh)
    listings = data.get("listings", data) if isinstance(data, dict) else data
    if not isinstance(listings, list):
        print("error: --listings-file on vigane; midagi ei päritud.",
              file=sys.stderr)
        return 1

    before = sum(1 for r in listings
                 if isinstance(r, dict) and not has_coords(r))
    if args.repair:
        report = repair_listings(listings, args.cache_dir)
    else:
        report = {"listings": listings,
                  "unresolvable": [],
                  "counts": {"coord_less_before": before, "repaired": 0,
                             "coord_less_after": before,
                             "unresolvable": 0}}
    counts = report["counts"]
    print(json.dumps({"coord_less_before": counts["coord_less_before"],
                      "repaired": counts["repaired"],
                      "coord_less_after": counts["coord_less_after"]},
                     ensure_ascii=False))
    for uid in report.get("unresolvable", []):
        print("qa: geokodeerimata aadress, kuulutus alles: %s" % uid,
              file=sys.stderr)
    if args.repair and args.out_file:
        with open(args.out_file, "w", encoding="utf-8") as fh:
            json.dump({"listings": report["listings"]}, fh,
                      ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
