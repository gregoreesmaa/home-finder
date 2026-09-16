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

ADDENDUM 2026-09-16 (issue #522): the transform step is ported, not
pending — lest97_to_wgs84 below is the batch_tervise.py (#511) inverse
Lambert Conformal Conic, same constants, same ~1 m datum label, and
projected_records() joins per-point WGS84 + vintage labels while
pre-2019 blank-coordinate rows stay NULL (skipped, counted via
split_coords). Dated probe, same day: ONE polite bytes 0-2500 range
peek (UA home-finder-522-accblack-probe/1.0) -> HTTP 206 text/csv,
byte-identical size 12342189 B, same ``;``-delimited header — no
re-pull, no dumps committed, zero 429. Wiring the projected extract
into the route/sidecar is the follow-up; measured_records() keeps its
raw shape for back-compat.
"""

import argparse
import csv
import math
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
# L-EST97 (EPSG:3301) -> WGS84, labelled approximate (~1 m). Ported
# 2026-09-16 from scripts/build/batch_tervise.py::lest97_to_wgs84
# (issue #511, verified <1 mm vs pyproj there) for issue #522 — same
# register family (X = northing ~6.4-6.6M, Y = easting ~0.37-0.74M),
# same math, same datum label. Copied, not imported: scripts/build
# files ship per-issue and stay rebase-safe against unmerged siblings.
# ---------------------------------------------------------------------------

#: GRS80 ellipsoid (L-EST97 datum; ETRS89, drifts ~1 m from WGS84 Gxxx).
_LEST_A = 6378137.0
_LEST_F = 1 / 298.257222101
_LEST_E2 = 2 * _LEST_F - _LEST_F * _LEST_F
_LEST_E = math.sqrt(_LEST_E2)

#: L-EST97 projection constants (Maa-amet / EPSG:3301 registry).
_LEST_PHI0 = math.radians(57.5175539305556)
_LEST_LAM0 = math.radians(24.0)
_LEST_PHI1 = math.radians(59.3333333333333)
_LEST_PHI2 = math.radians(58.0)
_LEST_E0 = 500000.0
_LEST_N0 = 6375000.0


def _lest_m(phi: float) -> float:
    return math.cos(phi) / math.sqrt(1 - _LEST_E2 * math.sin(phi) ** 2)


def _lest_t(phi: float) -> float:
    s = _LEST_E * math.sin(phi)
    return math.tan(math.pi / 4 - phi / 2) / ((1 - s) / (1 + s)) ** (_LEST_E / 2)


_LEST_M1, _LEST_M2 = _lest_m(_LEST_PHI1), _lest_m(_LEST_PHI2)
_LEST_T1, _LEST_T2 = _lest_t(_LEST_PHI1), _lest_t(_LEST_PHI2)
_LEST_T0 = _lest_t(_LEST_PHI0)
_LEST_N = ((math.log(_LEST_M1) - math.log(_LEST_M2))
           / (math.log(_LEST_T1) - math.log(_LEST_T2)))
_LEST_FF = _LEST_M1 / (_LEST_N * _LEST_T1 ** _LEST_N)
_LEST_RHO0 = _LEST_A * _LEST_FF * _LEST_T0 ** _LEST_N

#: Accuracy label stamped on every projected point (reviewable, never
#: hidden) — byte-identical wording to batch_tervise.py.
LEST97_ACCURACY_LABEL = (
    "L-EST97 (EPSG:3301) inverse-LCC poordumine, GRS80~WGS84 "
    "daatumi vahe ~1 m — punktid on ausad ~1 m tapsusega"
)


def lest97_to_wgs84(northing: float, easting: float):
    """Project L-EST97 metres to (lat, lon). Labelled ~1 m (see above).

    CSV convention: ``X koordinaat`` is the northing (~6.4-6.6M),
    ``Y koordinaat`` the easting (~0.37-0.74M). Raises ValueError on
    non-finite input (callers drop such rows, never fake them).
    """
    if not (math.isfinite(northing) and math.isfinite(easting)):
        raise ValueError("non-finite L-EST97 coordinate")
    rho = math.copysign(
        math.hypot(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0)),
        _LEST_N)
    theta = math.atan2(easting - _LEST_E0, _LEST_RHO0 - (northing - _LEST_N0))
    t = (rho / (_LEST_A * _LEST_FF)) ** (1 / _LEST_N)
    lam = theta / _LEST_N + _LEST_LAM0
    phi = math.pi / 2 - 2 * math.atan(t)
    for _ in range(20):
        s = _LEST_E * math.sin(phi)
        phi = math.pi / 2 - 2 * math.atan(t * ((1 - s) / (1 + s)) ** (_LEST_E / 2))
    return math.degrees(phi), math.degrees(lam)


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


def projected_records(rows):
    """Coordinated rows -> projected WGS84 records (issue #522). Pure.

    Each record carries the raw L-EST97 x/y, the projected ``lat``/``lon``
    (labelled ~1 m via ``transform``), the severity weight, and the
    per-point vintage (``year`` from ``Toimumisaeg``, ``vintage`` date
    prefix). Rows without coordinates (pre-2019 blanks) are SKIPPED —
    they stay NULL: callers count them via split_coords, never plot
    them, never zero-fill them.
    """
    out = []
    for r in rows:
        if not has_lest97(r):
            continue
        x = float(str(r["X koordinaat"]).strip())
        y = float(str(r["Y koordinaat"]).strip())
        lat, lon = lest97_to_wgs84(x, y)
        out.append({
            "lat": lat,
            "lon": lon,
            "x_lest": x,
            "y_lest": y,
            "dead": r.get("Hukkunuid"),
            "injured": r.get("Vigastatuid"),
            "sev": severity(r),
            "year": (r.get("Toimumisaeg") or "")[:4],
            "vintage": (r.get("Toimumisaeg") or "")[:10],
            "commune": r.get("Omavalitsus"),
            "projected": True,
            "transform": LEST97_ACCURACY_LABEL,
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
