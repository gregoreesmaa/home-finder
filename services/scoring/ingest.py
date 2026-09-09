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
import math
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
    ("adapters.kinnisvaraekspert_ee", True, "agency index; mixes sale+rent like domus"),
    ("adapters.lahekinnisvara_ee", False, "HTTP 403 on robots.txt; no listing probe"),
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

# Default deal type per hub. domus and kinnisvaraekspert provably mix
# sale+rent on marker-free detail URLs, so markers (or unknown) decide
# there; the other enabled hubs are sale-listing pages, so unmarked rows
# default to sale. Rent markers override everywhere.
PORTAL_DEFAULT_TYPE = {
    "adapters.domus_ee": None,
    "adapters.kinnisvaraekspert_ee": None,
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
        geo = (resolver or (lambda a: livability.resolve(a, cache_dir)))(
            r.get("address", "")
        )
        if geo:
            r["lat"], r["lon"] = geo.get("lat"), geo.get("lon")
        liv, liv_reasons = livability.enrich_row(
            r.get("address", ""), r.get("county", ""), cache_dir,
            resolver=resolver, geo=geo,
        )
        r["score_livability"] = liv
        r["reasons"].extend(liv_reasons)
    return rows


def enrich(rows: List[dict], modname: str = "", cache_dir: Optional[str] = None, resolver=None) -> List[dict]:
    """classify + score in one pass (single-portal convenience)."""
    return score(classify(rows, modname), cache_dir, resolver=resolver)


SCHEMA_SQL = """
ALTER TABLE listings ADD COLUMN IF NOT EXISTS image_url TEXT
"""


def ensure_schema(conn) -> None:
    """Idempotent schema evolution for long-lived volumes (#76).

    db/init.sql only runs on first volume creation; existing databases gain
    new columns here instead of a migration framework.
    """
    cur = conn.cursor()
    cur.execute(SCHEMA_SQL, {})
    conn.commit()


UPSERT_SQL = """
INSERT INTO listings
  (id, source, source_url, address, county, price, price_per_m2,
   rooms, area_m2, lat, lon, score_livability, discount_pct, reasons,
   image_url)
VALUES
  (%(id)s, %(source)s, %(source_url)s, %(address)s, %(county)s, %(price)s,
   %(price_per_m2)s, %(rooms)s, %(area_m2)s, %(lat)s, %(lon)s,
   %(score_livability)s, %(discount_pct)s, %(reasons)s::jsonb,
   %(image_url)s)
ON CONFLICT (id) DO UPDATE SET
  source_url = EXCLUDED.source_url, address = EXCLUDED.address,
  county = EXCLUDED.county, price = EXCLUDED.price,
  price_per_m2 = EXCLUDED.price_per_m2, rooms = EXCLUDED.rooms,
  area_m2 = EXCLUDED.area_m2, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
  score_livability = EXCLUDED.score_livability,
  discount_pct = EXCLUDED.discount_pct, reasons = EXCLUDED.reasons,
  image_url = EXCLUDED.image_url,
  scraped_at = now()
"""


def upsert(conn, rows: List[dict]) -> int:
    ensure_schema(conn)
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
                "image_url": r.get("image_url"),
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


CELL_DEGREES = 0.25  # mirrors web binListingsToHexes default


def heat_level(score: float) -> str:
    if score >= 70:
        return "good"
    if score >= 40:
        return "mid"
    return "bad"


def build_cells(rows: List[dict]) -> List[dict]:
    """Aggregate geocoded rows into grid cells (avg livability + count)."""
    acc: Dict[str, dict] = {}
    for r in rows:
        lon, lat = r.get("lon"), r.get("lat")
        liv = r.get("score_livability")
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            continue
        if not isinstance(liv, (int, float)):
            continue
        ix, iy = math.floor(lon / CELL_DEGREES), math.floor(lat / CELL_DEGREES)
        key = "cell-%d:%d" % (ix, iy)
        cell = acc.setdefault(key, {"sum": 0.0, "n": 0, "ix": ix, "iy": iy})
        cell["sum"] += liv
        cell["n"] += 1
    out = []
    for key, c in acc.items():
        avg = round(c["sum"] / c["n"], 1)
        out.append(
            {
                "h3": key,
                "score_goodness": int(round(avg)),
                "level": heat_level(avg),
                "lon": (c["ix"] + 0.5) * CELL_DEGREES,
                "lat": (c["iy"] + 0.5) * CELL_DEGREES,
                "count": c["n"],
            }
        )
    return out


UPSERT_CELL_SQL = """
INSERT INTO area_scores (h3, score_goodness, level, geom)
VALUES (%(h3)s, %(score_goodness)s, %(level)s,
  ST_MakeEnvelope(%(minlon)s, %(minlat)s, %(maxlon)s, %(maxlat)s, 4326))
ON CONFLICT (h3) DO UPDATE SET
  score_goodness = EXCLUDED.score_goodness, level = EXCLUDED.level,
  geom = EXCLUDED.geom
"""


def upsert_cells(conn, cells: List[dict]) -> int:
    cur = conn.cursor()
    for c in cells:
        cur.execute(
            UPSERT_CELL_SQL,
            {
                "h3": c["h3"],
                "score_goodness": c["score_goodness"],
                "level": c["level"],
                "minlon": c["lon"] - CELL_DEGREES / 2,
                "minlat": c["lat"] - CELL_DEGREES / 2,
                "maxlon": c["lon"] + CELL_DEGREES / 2,
                "maxlat": c["lat"] + CELL_DEGREES / 2,
            },
        )
    conn.commit()
    return len(cells)


CACHE_DIR_ENV_VAR = "HF_CACHE_DIR"


PAGE_LIMIT_ENV_VAR = "HF_PAGE_LIMIT"
DEFAULT_PAGE_LIMIT = 2


def run(cache_dir: Optional[str] = None, page_limit: Optional[int] = None) -> dict:
    """Scrape enabled portals, dedup, enrich, upsert. Returns a report."""
    if cache_dir is None:
        # Container cron sets HF_CACHE_DIR at a persisted volume (#78);
        # explicit --cache-dir still wins for host runs.
        cache_dir = os.environ.get(CACHE_DIR_ENV_VAR)
    if page_limit is None:
        # (#67) more than the first results page per portal; adapters that
        # ignore paging are unaffected. Explicit arg still wins.
        try:
            page_limit = int(os.environ.get(PAGE_LIMIT_ENV_VAR, DEFAULT_PAGE_LIMIT))
        except ValueError:
            page_limit = DEFAULT_PAGE_LIMIT
        page_limit = max(1, page_limit)
    report: Dict[str, dict] = {}
    fetched: List[dict] = []
    for modname, enabled, note in PORTALS:
        if not enabled:
            report[modname] = {"status": "skipped", "reason": note, "count": 0}
            continue
        try:
            mod = importlib.import_module(modname)
            rows = mod.scrape("", page_limit, cache_dir)
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
    cells = build_cells(priced)
    ncells = upsert_cells(conn, cells) if conn is not None else 0
    if conn is not None:
        conn.close()
    report["_total"] = {
        "fetched": len(fetched),
        "unique": len(merged),
        "skipped_no_price": len(enriched) - len(priced),
        "stored": stored,
        "cells": ncells,
        "db": conn is not None,
    }
    return report


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="home-finder live ingestion")
    ap.add_argument("--cache-dir", default=None)
    ap.add_argument("--page-limit", type=int, default=None)
    args = ap.parse_args()
    print(json.dumps(run(args.cache_dir, args.page_limit), indent=2, ensure_ascii=False))
