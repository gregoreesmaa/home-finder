"""Daily annateada report-pin harvest (issue #623, P4 fix-it pins).

Pulls the annateada pins API (one Tallinn-bbox POST per TTL window)
and builds the `fixit/fixit-points.json` snapshot sidecar the map
serves (apps/web/lib/layers_p4_fixit.ts). Parser + pin builder are
REUSED from services/scoring/dims_p4_fixit.py (never re-implemented
here — one tested implementation of the schema).

Maintainer decision (#623): the map shows the report PINS with
reporting-bias labeling — complaints measure reporting activity,
not place quality. Pins are ephemeral (server keeps a ~19-day
rolling window); NOTHING here scores them. The wire carries
lat/lon/handled/ts only — category/msg/photo/region never leave the
builder (report text can identify people; TAG_ALLOWLIST precedent).

Politeness (AGENTS.md section 7.4): one bbox POST per 24 h TTL with
a labelled UA, single attempt, HTTP 429/errors are a STOP signal
(never cached as data). The captcha-gated send endpoint is never
touched. Raw JSON lives in /tmp only — the only committed outputs
are this script, its tests, and the aggregate sidecar.

Expiry (load-bearing): pins expire 19 days after their own ts. The
route enforces it at serve time against Date.now(), so a stale
sidecar degrades to honestly-empty instead of rendering dead
complaints as current (pinned by test).
"""

import json
import os
import sys
import time
from typing import Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                               "services", "scoring"))
from dims_p4_fixit import (  # noqa: E402
    ANNATEADA_TTL_S,
    build_annateada_pins,
    parse_annateada_snapshot,
)

DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-623-fixit")

#: Rolling-window length in days (observed 2026-09-17: 2026-08-28 ->
#: 2026-09-17 = 19 days). Pins older than this at serve time are
#: expired (never rendered as current).
FIXIT_WINDOW_DAYS = 19


def build_sidecar(pins: List[dict], pulled_at: str,
                  vintage: str, out_dir: str) -> dict:
    """Write fixit/fixit-points.json; returns the doc.

    Wire shape per pin: lat/lon/handled/ts only (pure projection —
    category/msg/photo/region dropped here, never committed). Pins
    without a parseable ts are DROPPED and counted (fail closed: a
    timeless pin can never prove freshness, so it must never ship).
    """
    points = []
    handled = 0
    timeless = 0
    for pin in pins:
        ts = pin.get("ts")
        if not isinstance(ts, int):
            timeless += 1
            continue
        points.append({
            "lat": pin["lat"],
            "lon": pin["lon"],
            "handled": bool(pin.get("handled", False)),
            "ts": ts,
        })
        if pin.get("handled"):
            handled += 1
    doc = {
        "vintage": vintage,
        "pulled_at": pulled_at,
        "window_days": FIXIT_WINDOW_DAYS,
        "attribution": "annateada.ee report pins (rolling window)",
        "counts": {"total": len(points), "handled": handled,
                   "unhandled": len(points) - handled,
                   "dropped_timeless": timeless},
        "points": points,
    }
    fixit_dir = os.path.join(out_dir, "fixit")
    os.makedirs(fixit_dir, exist_ok=True)
    with open(os.path.join(fixit_dir, "fixit-points.json"), "w",
              encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return doc


def main() -> int:
    """Daily pins harvest (one POST per TTL, 429 = stop)."""
    import argparse
    from dims_p4_fixit import fetch_annateada_snapshot
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--out-dir", default=None,
                    help="snapshot dir receiving fixit/fixit-points.json "
                         "(default: <cache-dir>/snapshot)")
    ap.add_argument("--vintage", default="2026-09-17",
                    help="vintage label stamped on the sidecar")
    args = ap.parse_args()

    snap_path = fetch_annateada_snapshot(args.cache_dir, ANNATEADA_TTL_S)
    if snap_path is None:
        print("STOP: ask pull failed (transport refused or thin body) "
              "— no sidecar written")
        return 1
    records = parse_annateada_snapshot(snap_path)
    # All pull regions ride the sidecar (the bbox is Harjumaa-wide;
    # the scorer stays Tallinn-scoped, the map clips by view). Region
    # names come from the pull itself — never hardcoded here.
    regions = sorted({r.get("region") for r in records
                      if isinstance(r, dict) and r.get("region")})
    pins = []
    for region in regions:
        pins.extend(build_annateada_pins(records, region=region))
    pulled_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    doc = build_sidecar(pins, pulled_at, args.vintage,
                        args.out_dir
                        or os.path.join(args.cache_dir, "snapshot"))
    print("fixit extract: %d pins (%d handled, %d unhandled), "
          "pulled %s, window %d d" % (
              doc["counts"]["total"], doc["counts"]["handled"],
              doc["counts"]["unhandled"], pulled_at, FIXIT_WINDOW_DAYS))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
