"""One-off backfill: dims/score/reasons for rows imported before those columns.

Reads ONLY from the ingest file cache (no network): rows whose geocode/POI
answers are cached get the current-registry recompute; everything else is
left untouched for the daily cron to converge. Preserves deal/type warning
reasons at index 0.

Usage: DATABASE_URL=... HF_CACHE_DIR=/tmp/hf-import python3 scripts/backfill-dims.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "scoring"))

import ingest
import livability
from adapters import _cache_path, read_cache

CACHE_DIR = os.environ.get("HF_CACHE_DIR", "/tmp/hf-import")
TYPE_WARNINGS = set(ingest.TYPE_REASON.values())


def cached_geo(address):
    """Cache-only geo lookup: None on any miss (never fetches)."""
    raw = read_cache(
        _cache_path(CACHE_DIR, "liv_geocode6", address, 1), livability.GEOCODE_TTL_S
    )
    if not raw:
        return None
    lat, lon = livability._load_loc(raw)
    if lat is None:
        return None
    praw = read_cache(
        _cache_path(CACHE_DIR, "liv_pois3", "%.4f,%.4f" % (lat, lon), 1),
        livability.OVERPASS_TTL_S,
    )
    return {"lat": lat, "lon": lon,
            "pois": livability._load_pois(praw) if praw else None}


def main():
    conn = ingest.connect()
    if conn is None:
        print("no DATABASE_URL / unreachable DB")
        return 1
    ingest.ensure_schema(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, address, county, reasons FROM listings"
        " WHERE dims IS NULL"
    )
    rows = cur.fetchall()
    updated, skipped = 0, 0
    for rid, address, county, reasons in rows:
        geo = cached_geo(address or "")
        if geo is None:
            skipped += 1
            continue
        liv, liv_reasons, dims = livability.enrich_row(
            address or "", county or "", geo=geo
        )
        old = reasons if isinstance(reasons, list) else []
        keep = old[:1] if old and old[0] in TYPE_WARNINGS else []
        cur.execute(
            "UPDATE listings SET score_livability=%s, reasons=%s::jsonb,"
            " dims=%s::jsonb WHERE id=%s",
            (liv, json.dumps(keep + liv_reasons), json.dumps(dims), rid),
        )
        updated += 1
    conn.commit()
    conn.close()
    print("backfilled=%d skipped=%d (left for cron)" % (updated, skipped))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
