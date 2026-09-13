"""Transpordiamet accident-blackspot offline reader (issue #490).

Stdlib only. Offline, snapshot-only (NO network): rows come from a
LOCAL cached copy of lo_2011_2026.csv (the monthly Transpordiamet
casualty-accident distribution), never from a live service. Pure logic
at module top so unit tests stay hermetic; the full-month pull runs
only via the documented reopen commands.

COORD VERDICT (checked 2026-09-13, 2 tiny range peeks, custom UA —
see apps/web/lib/layers_accblack.ts ACCBLACK_PROBE): the CSV header
is 54 ``;``-delimited columns ending in ``X koordinaat;Y koordinaat``;
newer rows carry finite L-EST97 metres there, older rows (2011/2016
samples) have EMPTY X/Y. L-EST97 is NOT WGS84, and no projection
toolchain (GDAL/pyproj) is vendored here — so this reader keeps the
RAW x/y, flags every record ``projected: False``, and counts (never
hides) the rows without coordinates. Plotting raw L-EST97 as WGS84
would be fake precision (AGENTS.md 7.2); the web overlay stays empty
until the reopen PR projects (see the checklist in layers_accblack.ts).
"""

import argparse
import csv
import os
import sys

# ---------------------------------------------------------------------------
# Verdict constants (drift-guarded: test_batch_accblack.py parses
# apps/web/lib/layers_accblack.ts and fails on disagreement).
# ---------------------------------------------------------------------------

#: Dated probe this verdict rests on (YYYY-MM-DD).
PROBE_DATE = "2026-09-13"
#: Full live CSV size in bytes on the probe date.
PROBE_CSV_BYTES = 12342189
#: Live header column count (``;``-delimited, ends X/Y koordinaat).
PROBE_HEADER_COLS = 54

#: P4-012 blackspot window in metres — byte parity with
#: BLACKSPOT_WINDOW_M in services/scoring/dims_p4_trans.py and
#: ACCBLACK_WINDOW_M in layers_accblack.ts.
ACCBLACK_WINDOW_M = 300

#: Municipality value marking Tallinn rows (``Omavalitsus``).
TALLINN_COMMUNE = "Tallinn"

#: L-EST97 plausibility gate (metres, padded): Estonian northings run
#: ~6.37M (south border) to ~6.64M (north coast), eastings ~340k (west
#: islands) to ~730k (east border). This gate REJECTS WGS84-scale
#: values (lat ~59, lon ~24) and garbage — it never validates truth.
LEST97_X_MIN, LEST97_X_MAX = 6360000.0, 6655000.0
LEST97_Y_MIN, LEST97_Y_MAX = 330000.0, 740000.0


# ---------------------------------------------------------------------------
# Pure offline readers (same CSV shape as dims_p4_trans.parse_accidents_csv).
# ---------------------------------------------------------------------------

def parse_csv(path):
    """Parse a cached lo_2011_2026.csv copy. Offline; no filtering."""
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def _finite(value):
    try:
        return value is not None and str(value).strip() != "" \
            and float(str(value).strip()) == float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return False


def has_lest97(row):
    """True when X/Y koordinaat are finite L-EST97-plausible metres."""
    try:
        x = float(str(row.get("X koordinaat")).strip())
        y = float(str(row.get("Y koordinaat")).strip())
    except (TypeError, ValueError, AttributeError):
        return False
    return (LEST97_X_MIN <= x <= LEST97_X_MAX
            and LEST97_Y_MIN <= y <= LEST97_Y_MAX)


def split_coords(rows):
    """Split rows into (with_xy, without_xy). Counts, never hides."""
    with_xy, without_xy = [], []
    for r in rows:
        (with_xy if has_lest97(r) else without_xy).append(r)
    return with_xy, without_xy


def tallinn_rows(rows):
    """Keep Tallinn-municipality rows (Omavalitsus == Tallinn). Pure."""
    return [r for r in rows if r.get("Omavalitsus") == TALLINN_COMMUNE]


def severity(row):
    """Severity weight: 3 per death + 1 per injured; garbage -> 0. Pure."""
    def _num(key):
        v = row.get(key)
        if isinstance(v, bool):
            return 0
        try:
            n = int(str(v).strip())
        except (TypeError, ValueError, AttributeError):
            return 0
        return n if n > 0 else 0
    return 3 * _num("Hukkunuid") + _num("Vigastatuid")


def measured_records(rows):
    """Coordinated rows -> measured-only records. Pure.

    Records keep RAW L-EST97 x/y with ``projected: False`` — no WGS84
    lat/lon is emitted (never faked). Rows without coordinates are the
    caller's job to count via split_coords, not silently dropped here.
    """
    out = []
    for r in rows:
        if not has_lest97(r):
            continue
        out.append({
            "x_lest": float(str(r["X koordinaat"]).strip()),
            "y_lest": float(str(r["Y koordinaat"]).strip()),
            "dead": r.get("Hukkunuid"),
            "injured": r.get("Vigastatuid"),
            "sev": severity(r),
            "year": (r.get("Toimumisaeg") or "")[:4],
            "commune": r.get("Omavalitsus"),
            "projected": False,
        })
    return out


def summarize(rows):
    """Honest counts for a cached CSV: total / with-xy / empty-xy / Tallinn."""
    with_xy, without_xy = split_coords(rows)
    tall = tallinn_rows(rows)
    tall_xy, _ = split_coords(tall)
    return {
        "rows": len(rows),
        "with_xy": len(with_xy),
        "empty_xy": len(without_xy),
        "tallinn": len(tall),
        "tallinn_xy": len(tall_xy),
    }


def main(argv=None):
    """CLI: summarize a locally cached CSV (the pull itself is manual)."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True, help="cached lo_2011_2026.csv path")
    args = ap.parse_args(argv)
    if not os.path.exists(args.csv):
        print("missing cache file: %s" % args.csv, file=sys.stderr)
        return 2
    rows = parse_csv(args.csv)
    s = summarize(rows)
    print("rows=%d with_xy=%d empty_xy=%d tallinn=%d tallinn_xy=%d window_m=%d" % (
        s["rows"], s["with_xy"], s["empty_xy"], s["tallinn"],
        s["tallinn_xy"], ACCBLACK_WINDOW_M))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
