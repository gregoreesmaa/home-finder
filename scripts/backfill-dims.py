"""One-off backfill: dims/score/reasons for rows imported before those columns.

Default reads ONLY from the ingest file cache (no network): rows whose
geocode/POI answers are cached get the current-registry recompute, the rest
stay for the daily cron. With --live, cache misses resolve live through the
same polite pipeline the cron uses (Photon ~1/s, Overpass mirrors+backoff),
so a small remainder (#81) converges now. Preserves deal/type warnings.

Usage: DATABASE_URL=... HF_CACHE_DIR=/tmp/hf-import python3 scripts/backfill-dims.py [--live]
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "services", "scoring"))

import ingest
import livability
from adapters import _cache_path, read_cache

CACHE_DIR = os.environ.get("HF_CACHE_DIR", "/tmp/hf-import")
TYPE_WARNINGS = set(ingest.TYPE_REASON.values())
PHOTON_GAP_S = 1.1  # Photon usage policy: max 1 req/s


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
    ap = argparse.ArgumentParser(description="backfill dims/score/reasons")
    ap.add_argument("--live", action="store_true",
                    help="resolve cache misses live (polite, cron pipeline)")
    args = ap.parse_args()
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
        if geo is None and args.live and address:
            time.sleep(PHOTON_GAP_S)  # Photon: max 1 req/s
            geo = livability.resolve(address, CACHE_DIR)
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
