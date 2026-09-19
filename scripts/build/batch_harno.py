"""Static annual school-quality snapshot builder (issue #687).

NO polling by default (the issue's own shape): per-school
riigieksamite averages arrive ONCE A YEAR as an operator-verified
snapshot file — never scraped, never polled. The repo holds this
code plus hermetic tests; the yearly drop lives with the operator
(and, once real, as a vintage-stamped derived table — never raw
dumps, never personal data).

SOURCE VERDICT (2026-09-19, polite single GETs, UA
``home-finder-research/0.1``, ``--max-time`` 25, paced, raw in /tmp
only — full evidence in docs/p4_harno.md section 6): NO bulk
machine-readable per-school exam export exists —
* Haridussilm (haridussilm.ee) is a JS SPA over a PowerBI backend
  (41 kB app shell, ``/v1/comparison-view/`` serves strategic-plan
  docs, not per-school scores; no CSV/XLS/API/download surface);
* EIS exam records sit behind school accounts; the yearly
  per-school averages reach the public as media ranking graphics,
  not tables.
So --build honestly refuses (exit 2) without an operator-verified
--snapshot, and the layer/dims ship NULL/empty until the first
verified annual drop (re-open path in docs/p4_harno.md).

PER-SCHOOL LINKAGE (for the first real drop): EHIS registry id
(``ehis_id``) is the join key; coordinates are verified at snapshot
time against the held OSM extract (amenity=school name match
checked against the EHIS street address — never hand-geocoded,
paaste #493 rule); thin cohorts (n < MIN_N) never plot.

Usage:
  python3 scripts/build/batch_harno.py --build --cache-dir DIR \\
      [--snapshot snapshot.json]
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

#: Minimum graduating cohort: thinner slices never plot (a 4-pupil
#: mean is noise, not quality — never a faked school score).
MIN_N = 10

#: Required snapshot fields (vintage + per-school linkage).
REQUIRED_TOP = ("vintage", "schools")
REQUIRED_SCHOOL = ("ehis_id", "name", "lat", "lon",
                   "avg_estonian", "avg_math", "avg_foreign",
                   "n_graduates")


def quality_band(mean: Optional[float]) -> Optional[int]:
    """Mean of subject averages -> coarse quality band. Pure.

    Cap 80 — an exam mean is never a whole school (same honesty cap
    as the bathing-water bands). None in, None out (never a faked
    middle).
    """
    if not isinstance(mean, (int, float)) or not 0 <= mean <= 100:
        return None
    if mean >= 80:
        return 80
    if mean >= 70:
        return 70
    if mean >= 60:
        return 60
    if mean >= 50:
        return 45
    return 30


def _mean_avgs(row: dict) -> Optional[float]:
    vals = [row.get(k) for k in ("avg_estonian", "avg_math",
                                 "avg_foreign")]
    if not all(isinstance(v, (int, float)) and 0 <= v <= 100
               for v in vals):
        return None
    return sum(vals) / 3.0


def validate_snapshot(doc: Any) -> Tuple[bool, List[str]]:
    """Check an annual snapshot's shape. Pure (no network, no files)."""
    errs: List[str] = []
    if not isinstance(doc, dict):
        return False, ["snapshot pole sõnastik"]
    for key in REQUIRED_TOP:
        if key not in doc:
            errs.append("puudub väli: %s" % key)
    schools = doc.get("schools")
    if not isinstance(schools, list):
        errs.append("schools pole loend")
        return False, errs
    for i, s in enumerate(schools):
        if not isinstance(s, dict):
            errs.append("kool #%d pole sõnastik" % i)
            continue
        for key in REQUIRED_SCHOOL:
            if key not in s:
                errs.append("kool #%d: puudub väli %s" % (i, key))
    return (len(errs) == 0), errs


def build_table(rows: List[dict], vintage: str) -> dict:
    """Validated snapshot rows -> snapshot table. Pure.

    Only coordinate-carrying schools with MIN_N graduates and
    complete subject means plot; everything else yields the honest
    empty (never faked quality).
    """
    points = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        lat, lon = r.get("lat"), r.get("lon")
        n = r.get("n_graduates")
        if not isinstance(lat, (int, float)) \
                or not isinstance(lon, (int, float)):
            continue
        if not isinstance(n, int) or n < MIN_N:
            continue
        q = quality_band(_mean_avgs(r))
        if q is None:
            continue
        points.append({
            "ehis_id": str(r.get("ehis_id")),
            "name": r.get("name"),
            "lat": float(lat),
            "lon": float(lon),
            "q": q,
            "n": n,
        })
    points.sort(key=lambda p: p["ehis_id"])
    return {"points": points, "vintage": vintage,
            "counts": {"total": len(points)}}


def _load(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


#: Band ladder (pinned by test; the TS side mirrors it).
QUALITY_BANDS = (80, 70, 60, 45, 30)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Annual school-quality build.")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--snapshot", default=None,
                    help="Operator-verified annual snapshot JSON.")
    args = ap.parse_args(argv)

    if not args.snapshot:
        print("error: keeldun - verifitseeritud aastasnapshot puudub "
              "(per-kooli masin-eksporti pole, vt docs/p4_harno.md §6): "
              "anna --snapshot operaatori kontrollitud teavikuga; "
              "midagi ei päritud, midagi ei kirjutatud.",
              file=sys.stderr)
        return 2
    doc = _load(args.snapshot)
    ok, errs = validate_snapshot(doc)
    if not ok:
        print("error: snapshot ei valideeru: %s" % "; ".join(errs[:5]),
              file=sys.stderr)
        return 1
    table = build_table(doc["schools"], str(doc["vintage"]))
    print(json.dumps({"total": table["counts"]["total"],
                      "vintage": table["vintage"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
