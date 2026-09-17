"""Keyed Places-ratings harvester (issue #630): one Nearby Search pull.

Runs ONLY on a user-supplied env key (GOOGLE_PLACES_API_KEY) — without
it the command hard-refuses (exit 2, tested) having touched nothing:
no request, no files. Never scrape reviews (refused class, AGENTS.md
§5/§7); scores/tiers only, no review text ingested.

Delegates the pull to services/scoring/dims_p4_ratings.fetch_places
(30 d TTL, monthly quota cap, 429 = stop, transport never cached), so
quota/TTL semantics agree with the scorer by construction. The key is
never printed, never written to any file (pinned by test).

Usage:
  GOOGLE_PLACES_API_KEY=... python3 scripts/build/batch_places.py \\
      --lat 59.437 --lon 24.753 [--radius-m 500] [--cache-dir DIR]
Key placement: export the variable in the operator shell only (see
docs/p4_ratings.md §7); never commit it, never put it in repo files.
"""

import argparse
import os
import sys
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_p4_ratings import (  # noqa: E402
    PLACES_KEY_ENV,
    PLACES_MONTHLY_MAX_CALLS,
    _quota_used,
    fetch_places,
    parse_places_response,
)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed Places ratings pull.")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--radius-m", type=int, default=500)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--filename", default=None)
    args = ap.parse_args(argv)

    if not os.environ.get(PLACES_KEY_ENV):
        print("error: refusing — %s is not set. Export your own "
              "Google Places API key in this shell (see "
              "docs/p4_ratings.md §7); nothing was fetched, nothing "
              "was written." % PLACES_KEY_ENV, file=sys.stderr)
        return 2
    if _quota_used(args.cache_dir) >= PLACES_MONTHLY_MAX_CALLS:
        print("error: refusing — monthly Places quota is spent; "
              "nothing was fetched.", file=sys.stderr)
        return 2
    filename = args.filename or ("places_%.5f_%.5f_%dm.json"
                                  % (args.lat, args.lon, args.radius_m))
    dest = fetch_places(args.lat, args.lon, args.radius_m,
                        args.cache_dir, filename)
    if dest is None:
        print("error: pull failed or was skipped (unfresh cache, "
              "spent quota, or transport/429) — nothing new cached.",
              file=sys.stderr)
        return 1
    places = parse_places_response(dest)
    rated = sum(1 for p in places if p.get("rating") is not None)
    print("ok: %s (%d places, %d rated)" % (dest, len(places), rated))
    return 0


if __name__ == "__main__":
    sys.exit(main())
