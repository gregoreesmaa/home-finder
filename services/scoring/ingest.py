"""Live ingestion: portal adapters -> normalized records -> PostGIS `listings`.

Enabled portals are the ones reachable with polite plain-HTTP fetches
(probed 2026-09-08: domus, uusmaa, pindi, 1partner, arcovara, lvm, remax
all serve server-rendered cards; selectors verified against live markup).
Blocked/JS-only portals stay listed with their reason and are skipped
gracefully -- never retried aggressively.

Scoring of live rows (honest v1): livability signals are not scraped, so
every live row gets the neutral 50 with a reason saying so; discount_pct
is measured against the county median EUR/m2 *within the fetched batch*,
so "steal vs overpriced" stays meaningful and sort modes keep working.

Usage (daily cron cadence, polite: page_limit=1 per portal):
    DATABASE_URL=postgresql://homefinder:homefinder@localhost:5432/homefinder \\
        python3 ingest.py [--cache-dir /tmp/hf-cache]
"""

import importlib
import json
import os
import statistics
import sys
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters import dedup_listings  # noqa: E402

# (adapter module, enabled, note when disabled)
PORTALS: List[Tuple[str, bool, str]] = [
    ("adapters.domus_ee", True, ""),
    ("adapters.uusmaa_ee", True, ""),
    ("adapters.pindi_ee", True, ""),
    ("adapters.one_partner_ee", True, ""),
    ("adapters.arcovara_ee", True, ""),
    ("adapters.lvm_ee", True, ""),
    ("adapters.remax_ee", True, ""),
    ("adapters.kv_ee", False, "HTTP 403 bot protection on search pages"),
    ("adapters.city24_ee", False, "JS SPA shell -- no server-rendered cards"),
    ("adapters.kinnisvara24_ee", False, "HTTP 403 bot protection"),
    ("adapters.kinnisvaraweb_ee", False, "HTTP 403 bot protection"),
    ("adapters.okidoki_ee", False, "HTTP 403 bot protection"),
    ("adapters.osta_ee", False, "HTTP 403 on robots.txt; no listing probe"),
    ("adapters.oberhaus_ee", False, "connection timeouts"),
    ("adapters.facebook", False, "paste-in only by design, never scraped"),
]

NEUTRAL_LIVABILITY = 50

CITY_COUNTY = {
    "tallinn": "Harju maakond",
    "tartu": "Tartu maakond",
    "pärnu": "Pärnu maakond",
    "narva": "Ida-Viru maakond",
    "kohtla-järve": "Ida-Viru maakond",
    "sillamäe": "Ida-Viru maakond",
    "jõhvi": "Ida-Viru maakond",
    "viljandi": "Viljandi maakond",
    "rakvere": "Lääne-Viru maakond",
    "kuressaare": "Saare maakond",
    "haapsalu": "Lääne maakond",
    "paide": "Järva maakond",
    "valga": "Valga maakond",
    "võru": "Võru maakond",
    "põlva": "Põlva maakond",
    "rapla": "Rapla maakond",
    "jõgeva": "Jõgeva maakond",
    "kärdla": "Hiiu maakond",
    "keila": "Harju maakond",
    "maardu": "Harju maakond",
    "saue": "Harju maakond",
    "elva": "Tartu maakond",
    "tapa": "Lääne-Viru maakond",
}


def county_for(address: str) -> str:
    """Map 'Street 12, Tallinn' -> county via the city after the last comma."""
    city = (address or "").split(",")[-1].strip().lower()
    return CITY_COUNTY.get(city, "Eesti")


def enrich(rows: List[dict]) -> List[dict]:
    """Add price_per_m2, county, batch-median discount, neutral livability."""
    for r in rows:
        price, area = r.get("price"), r.get("area_m2")
        r["price_per_m2"] = round(price / area) if price and area else None
        r["county"] = county_for(r.get("address", ""))
    medians: Dict[str, float] = {}
    buckets: Dict[str, List[float]] = {}
    for r in rows:
        if r["price_per_m2"] is not None:
            buckets.setdefault(r["county"], []).append(r["price_per_m2"])
    medians = {c: statistics.median(v) for c, v in buckets.items()}
    for r in rows:
        ppm, med = r["price_per_m2"], medians.get(r["county"])
        r["discount_pct"] = (
            round((med - ppm) / med * 100, 1) if ppm and med else 0.0
        )
        r["score_livability"] = NEUTRAL_LIVABILITY
        # Source attribution renders from the `source` field in the UI.
        r["reasons"] = ["Elamiskvaliteet arvutamata (automaatimport)"]
    return rows


UPSERT_SQL = """
INSERT INTO listings
  (id, source, source_url, address, county, price, price_per_m2,
   rooms, area_m2, score_livability, discount_pct, reasons)
VALUES
  (%(id)s, %(source)s, %(source_url)s, %(address)s, %(county)s, %(price)s,
   %(price_per_m2)s, %(rooms)s, %(area_m2)s, %(score_livability)s,
   %(discount_pct)s, %(reasons)s::jsonb)
ON CONFLICT (id) DO UPDATE SET
  source_url = EXCLUDED.source_url, address = EXCLUDED.address,
  county = EXCLUDED.county, price = EXCLUDED.price,
  price_per_m2 = EXCLUDED.price_per_m2, rooms = EXCLUDED.rooms,
  area_m2 = EXCLUDED.area_m2, score_livability = EXCLUDED.score_livability,
  discount_pct = EXCLUDED.discount_pct, reasons = EXCLUDED.reasons,
  scraped_at = now()
"""


def upsert(conn, rows: List[dict]) -> int:
    cur = conn.cursor()
    for r in rows:
        cur.execute(
            UPSERT_SQL,
            {
                "id": r["id"],
                "source": r.get("source", "?"),
                "source_url": r.get("source_url", ""),
                "address": r.get("address", ""),
                "county": r.get("county", "Eesti"),
                "price": r["price"],
                "price_per_m2": r.get("price_per_m2"),
                "rooms": r.get("rooms"),
                "area_m2": r.get("area_m2"),
                "score_livability": r.get("score_livability", NEUTRAL_LIVABILITY),
                "discount_pct": r.get("discount_pct", 0.0),
                "reasons": json.dumps(list(r.get("reasons", []))),
            },
        )
    conn.commit()
    return len(rows)


def connect():
    """DB handle or None (no DATABASE_URL / no driver / unreachable)."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        import psycopg  # type: ignore
    except ImportError:
        return None
    try:
        return psycopg.connect(url, connect_timeout=5)  # type: ignore[attr-defined]
    except Exception:
        return None


def run(cache_dir: Optional[str] = None) -> dict:
    """Scrape enabled portals, dedup, enrich, upsert. Returns a report."""
    report: Dict[str, dict] = {}
    fetched: List[dict] = []
    for modname, enabled, note in PORTALS:
        if not enabled:
            report[modname] = {"status": "skipped", "reason": note, "count": 0}
            continue
        try:
            mod = importlib.import_module(modname)
            rows = mod.scrape("", 1, cache_dir)
            report[modname] = {"status": "ok", "count": len(rows)}
            fetched.extend(rows)
        except Exception as e:  # polite: record, never crash the run
            report[modname] = {
                "status": "error",
                "reason": "%s: %s" % (type(e).__name__, e),
                "count": 0,
            }
    merged = dedup_listings(*[fetched]) if fetched else []
    enriched = enrich(merged)
    priced = [r for r in enriched if r.get("price")]
    conn = connect()
    stored = upsert(conn, priced) if conn is not None else 0
    if conn is not None:
        conn.close()
    report["_total"] = {
        "fetched": len(fetched),
        "unique": len(merged),
        "skipped_no_price": len(enriched) - len(priced),
        "stored": stored,
        "db": conn is not None,
    }
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="home-finder live ingestion")
    ap.add_argument("--cache-dir", default=None)
    args = ap.parse_args()
    print(json.dumps(run(args.cache_dir), indent=2, ensure_ascii=False))
