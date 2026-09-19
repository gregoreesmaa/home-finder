"""Seasonal groomed ski-track harvester (issue #692).

Pole-native per AGENTS.md section 9: the repo holds this code plus
hermetic tests; cadence, caches and the in-season status drop live
on the pole.

SOURCE VERDICT (2026-09-19, two polite GETs, UA
``home-finder-research/0.1``, ``--max-time`` 25, paced, raw in /tmp
only — full evidence in docs/p4_skis.md section 6): groomed-track
status is HUMAN-ONLY. ``piritaspordikeskus.ee`` 302-redirects to
``tallinn.ee/et/piritaspordikeskus`` (human HTML, 46 751 B), which
on 2026-09-19 says verbatim: "2025/26 suusahooaeg on selleks
korraks läbi. Kohtume järgmisel hooajal!" — off-season confirmed
live, status channel = the page + phone 600 8333. There is no
machine feed to poll, so --pull honestly refuses (exit 2).

SEASONAL MECHANISM: in season (roughly Nov-Mar) the operator reads
the human page and drops a verified ``status.json`` (shape: see
STATUS_EXAMPLE below) on the pole; the pole wrapper builds
``built/skis/table.json`` from that drop (absent drop = honest
off-season empty, never faked). Off-season the cron does not run
at all. Only groomed, coordinate-carrying tracks plot.

Usage:
  python3 scripts/build/batch_skis.py --build --cache-dir DIR \\
      [--status status.json]
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

#: Identifying user agent (used only if a machine feed ever
#: verifies; today --pull refuses without fetching anything).
UA = "home-finder-research/0.1"

#: Tracks whose status the operator reads in season (Tallinn
#: maintained tracks; entry-point coordinates are verified at the
#: first in-season drop, never hand-placed here).
KNOWN_TRACKS = (
    "pirita-velodroom",
    "nomme-harku",
    "harku",
    "hiiu",
)

STATUS_EXAMPLE = {
    "tracks": [
        {"track_id": "pirita-velodroom", "name": "Pirita Velodroomi ring",
         "lat": 59.4711, "lon": 24.8711, "groomed": True,
         "length_km": 3.8},
    ]
}


def parse_status(doc: Any) -> List[dict]:
    """Operator-verified status drop -> candidate rows. Pure.

    Keeps dicts with a known track_id; coordinates and the groomed
    flag are validated at build time (never faked, never assumed).
    """
    if not isinstance(doc, dict):
        return []
    tracks = doc.get("tracks")
    if not isinstance(tracks, list):
        return []
    rows = []
    for t in tracks:
        if not isinstance(t, dict):
            continue
        tid = t.get("track_id")
        if tid not in KNOWN_TRACKS:
            continue
        rows.append({
            "track_id": tid,
            "name": t.get("name") if isinstance(t.get("name"), str) else tid,
            "lat": t.get("lat"),
            "lon": t.get("lon"),
            "groomed": bool(t.get("groomed")),
            "length_km": t.get("length_km")
            if isinstance(t.get("length_km"), (int, float)) else None,
        })
    return rows


def build_table(rows: List[dict]) -> dict:
    """Candidate rows -> snapshot table. Pure.

    Only groomed tracks with finite coordinates plot; everything
    else yields the honest off-season empty (season "off", total 0
    — DATEX SRTI pattern, never faked).
    """
    points = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("groomed"):
            continue
        lat, lon = r.get("lat"), r.get("lon")
        if not isinstance(lat, (int, float)) \
                or not isinstance(lon, (int, float)):
            continue
        points.append({
            "track_id": r["track_id"],
            "name": r["name"],
            "lat": float(lat),
            "lon": float(lon),
            "length_km": r.get("length_km"),
        })
    points.sort(key=lambda p: p["track_id"])
    season = "on" if points else "off"
    return {"points": points, "season": season,
            "counts": {"total": len(points)}}


def _load(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Seasonal ski-track build.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--status", default=None,
                    help="Operator-verified status JSON (in-season drop).")
    ap.add_argument("--out", default=None,
                    help="Write built/skis/table.json here (pole wrapper).")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if args.pull:
        print("error: keeldun - hooldatud suusaradade masinvoogu pole "
              "(allikas on inimloetav tallinn.ee-leht + tel 600 8333, "
              "vt docs/p4_skis.md §6): hooajal loe leht ja anna --status "
              "verifitseeritud teavikuga; midagi ei päritud, midagi ei "
              "kirjutatud.", file=sys.stderr)
        return 2
    if args.build:
        rows = parse_status(_load(args.status)) if args.status else []
        table = build_table(rows)
        print(json.dumps({"total": table["counts"]["total"],
                          "season": table["season"]},
                         ensure_ascii=False))
        if args.out:
            payload = dict(table)
            payload["built_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00",
                                                time.gmtime())
            tmp = args.out + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp, args.out)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
