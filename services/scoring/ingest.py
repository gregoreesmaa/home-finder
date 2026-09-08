"""Live ingestion: portal adapters -> normalized records -> PostGIS `listings`.

Enabled portals are the ones reachable with polite plain-HTTP fetches
(probed 2026-09-08: domus, uusmaa, pindi, 1partner, arcovara, lvm, remax
all serve server-rendered cards; selectors verified against live markup).
kv.ee gates scripted HTTP on TLS fingerprint, so it fetches via genuine
headless Chrome instead (verified 2026-09-08: real ItemList JSON-LD).
Blocked/JS-only portals stay listed with their reason and are skipped
gracefully -- never retried aggressively.

Scoring of live rows: livability comes from the dimension registry in
livability.py (Photon geocode + OSM POIs, cached, graceful nulls), so rows
get varied per-listing scores with Estonian reasons; discount_pct is
measured against the county median EUR/m2 *within the fetched batch*,
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
import livability  # noqa: E402

# (adapter module, enabled, note when disabled)
PORTALS: List[Tuple[str, bool, str]] = [
    ("adapters.domus_ee", True, ""),
    ("adapters.uusmaa_ee", True, ""),
    ("adapters.pindi_ee", True, ""),
    ("adapters.one_partner_ee", True, ""),
    ("adapters.arcovara_ee", True, ""),
    ("adapters.lvm_ee", True, ""),
    ("adapters.remax_ee", True, ""),
    ("adapters.kv_ee", True, "headless-Chrome fetch (genuine browser TLS); daily cron"),
    ("adapters.city24_ee", True, "public search JSON API (no key, no login)"),
    ("adapters.kinnisvara24_ee", False, "HTTP 403 bot protection"),
    ("adapters.kinnisvaraweb_ee", False, "HTTP 403 bot protection"),
    ("adapters.okidoki_ee", False, "HTTP 403 bot protection"),
    ("adapters.osta_ee", False, "HTTP 403 on robots.txt; no listing probe"),
    ("adapters.oberhaus_ee", False, "connection timeouts"),
    ("adapters.facebook", False, "paste-in only by design, never scraped"),
]

NEUTRAL_LIVABILITY = 50

# Deal typing from URL slugs (lowercase substring match). Sale/rent markers
# were read off real imported URLs (domus mixes both: 'muua-*' vs
# 'uurile-anda-*'); remax URLs carry the property type (korter/maja/...).
RENT_MARKERS = ("uurile", "üürile", "for-rent", "to-rent", "rent", "vuokra", "miete")
SALE_MARKERS = ("muua", "muugi", "müü", "myy", "sale", "for-sale", "osta", "ostu")
LAND_MARKERS = ("-maa", "/maa", "maatükk", "maatykk", "land", "plot", "grund", "kinnistu")

# Default deal type per hub. domus provably mixes sale+rent, so markers (or
# unknown) decide there; the other enabled hubs are sale-listing pages, so
# unmarked rows default to sale. Rent markers override everywhere.
PORTAL_DEFAULT_TYPE = {
    "adapters.domus_ee": None,
}


def deal_type(source_url: str, modname: str) -> str:
    """rent | sale | land | unknown — drives median pooling, never hidden."""
    slug = (source_url or "").lower()
    if any(m in slug for m in RENT_MARKERS) and not any(
        m in slug for m in SALE_MARKERS
    ):
        return "rent"
    if any(m in slug for m in SALE_MARKERS):
        if any(m in slug for m in LAND_MARKERS):
            return "land"
        return "sale"
    default = PORTAL_DEFAULT_TYPE.get(modname, "sale")
    return default or "unknown"


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


COUNTY_NAMES = {
    "harju maakond": "Harju maakond",
    "tartu maakond": "Tartu maakond",
    "pärnu maakond": "Pärnu maakond",
    "ida-viru maakond": "Ida-Viru maakond",
    "viljandi maakond": "Viljandi maakond",
    "lääne-viru maakond": "Lääne-Viru maakond",
    "saare maakond": "Saare maakond",
    "lääne maakond": "Lääne maakond",
    "järva maakond": "Järva maakond",
    "valga maakond": "Valga maakond",
    "võru maakond": "Võru maakond",
    "põlva maakond": "Põlva maakond",
    "rapla maakond": "Rapla maakond",
    "jõgeva maakond": "Jõgeva maakond",
    "hiiu maakond": "Hiiu maakond",
    # Colloquial short forms seen in live addresses ("Harjumaa", ...).
    "harjumaa": "Harju maakond",
    "tartumaa": "Tartu maakond",
    "pärnumaa": "Pärnu maakond",
    "idavirumaa": "Ida-Viru maakond",
    "ida-virumaa": "Ida-Viru maakond",
    "viljandimaa": "Viljandi maakond",
    "lääne-virumaa": "Lääne-Viru maakond",
    "saaremaa": "Saare maakond",
    "läänemaa": "Lääne maakond",
    "järvamaa": "Järva maakond",
    "valgamaa": "Valga maakond",
    "võrumaa": "Võru maakond",
    "põlvamaa": "Põlva maakond",
    "raplamaa": "Rapla maakond",
    "jõgevamaa": "Jõgeva maakond",
    "hiiumaa": "Hiiu maakond",
}


def county_for(address: str) -> str:
    """Map an address to its county.

    Live addresses carry the full hierarchy
    ('Nõlvaku tn 17, Annelinn, Tartu linn, Tartu maakond'), so segments are
    scanned last-first: the city almost always sits at the end, while street
    names may borrow another city's name ('Rakvere tn 87, Narva' is Narva,
    not Rakvere). Falls back to explicit county names, then 'Eesti'.
    """
    segments = (address or "").split(",")
    for seg in reversed(segments):
        seg = seg.strip().lower()
        for city in sorted(CITY_COUNTY, key=len, reverse=True):
            if city in seg:
                return CITY_COUNTY[city]
    text = (address or "").lower()
    for name in sorted(COUNTY_NAMES, key=len, reverse=True):
        if name in text:
            return COUNTY_NAMES[name]
    return "Eesti"


TYPE_REASON = {
    "rent": "Üürikuulutus – tehingu skoorimata",
    "land": "Maatükk – €/m² ei võrrelda hoonetega",
    "unknown": "Kuulutuse tüüp teadmata – tehingu skoorimata",
}


def classify(rows: List[dict], modname: str = "") -> List[dict]:
    """Add price_per_m2, county, deal type. Typing needs the portal default."""
    for r in rows:
        price, area = r.get("price"), r.get("area_m2")
        r["price_per_m2"] = round(price / area) if price and area else None
        r["county"] = county_for(r.get("address", ""))
        r["deal_type"] = deal_type(r.get("source_url", ""), modname)
    return rows


SALE_PPM_FLOOR = 100.0


def score(rows: List[dict], cache_dir: Optional[str] = None, resolver=None) -> List[dict]:
    """Batch-median discount over SALE rows per county + livability dims.

    Rents (EUR/month) and land (EUR/m2 of soil) are excluded from the sale
    medians and keep discount 0.0 with an honest typed reason. As a backstop
    against mislabeled rows, sub-floor sale prices (EUR/m2 < 100 — far below
    any Estonian sale market) do not enter the median pool either, though
    they are still scored against it.

    Livability comes from livability.enrich_row (Photon geocode + OSM POIs,
    30d file cache under cache_dir, graceful nulls); all-dims-missing keeps
    the neutral 50 with an explicit no-data reason.
    """
    buckets: Dict[str, List[float]] = {}
    for r in rows:
        ppm = r["price_per_m2"]
        if (
            r.get("deal_type", "sale") == "sale"
            and ppm is not None
            and ppm >= SALE_PPM_FLOOR
        ):
            buckets.setdefault(r["county"], []).append(ppm)
    medians = {c: statistics.median(v) for c, v in buckets.items()}
    for r in rows:
        # Source attribution renders from the `source` field in the UI.
        # Livability reasons are computed per listing below; deal/type
        # warnings stay first in the list.
        r["reasons"] = []
        if r.get("deal_type", "sale") == "sale":
            ppm, med = r["price_per_m2"], medians.get(r["county"])
            r["discount_pct"] = (
                round((med - ppm) / med * 100, 1) if ppm and med else 0.0
            )
            if ppm is not None and ppm < SALE_PPM_FLOOR:
                # Sub-floor "sale" (likely a rent slipped through the
                # markers): do not present a fantasy steal, flag for check.
                r["discount_pct"] = 0.0
                r["reasons"].insert(
                    0, "Hind ebatavaline (€/m²) – kontrolli, kas on müük",
                )
        else:
            r["discount_pct"] = 0.0
            r["reasons"].insert(
                0, TYPE_REASON.get(r["deal_type"], TYPE_REASON["unknown"])
            )
        liv, liv_reasons = livability.enrich_row(
            r.get("address", ""), r.get("county", ""), cache_dir,
            resolver=resolver,
        )
        r["score_livability"] = liv
        r["reasons"].extend(liv_reasons)
    return rows


def enrich(rows: List[dict], modname: str = "", cache_dir: Optional[str] = None, resolver=None) -> List[dict]:
    """classify + score in one pass (single-portal convenience)."""
    return score(classify(rows, modname), cache_dir, resolver=resolver)


UPSERT_SQL = """
INSERT INTO listings
  (id, source, source_url, address, county, price, price_per_m2,
   rooms, area_m2, lat, lon, score_livability, discount_pct, reasons)
VALUES
  (%(id)s, %(source)s, %(source_url)s, %(address)s, %(county)s, %(price)s,
   %(price_per_m2)s, %(rooms)s, %(area_m2)s, %(lat)s, %(lon)s,
   %(score_livability)s, %(discount_pct)s, %(reasons)s::jsonb)
ON CONFLICT (id) DO UPDATE SET
  source_url = EXCLUDED.source_url, address = EXCLUDED.address,
  county = EXCLUDED.county, price = EXCLUDED.price,
  price_per_m2 = EXCLUDED.price_per_m2, rooms = EXCLUDED.rooms,
  area_m2 = EXCLUDED.area_m2, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
  score_livability = EXCLUDED.score_livability,
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
                "lat": r.get("lat"),
                "lon": r.get("lon"),
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
            fetched.extend(classify(rows, modname))
        except Exception as e:  # polite: record, never crash the run
            report[modname] = {
                "status": "error",
                "reason": "%s: %s" % (type(e).__name__, e),
                "count": 0,
            }
    # Typing is per-portal, but discount medians pool across all portals,
    # so classify first, dedup, then score the merged set.
    merged = dedup_listings(*[fetched]) if fetched else []
    enriched = score(merged, cache_dir)
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
