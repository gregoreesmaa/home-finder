"""city24.ee listings adapter (City24 Baltics portal).

Backend: the public City24 search JSON API (the same endpoint their own
JS frontend queries -- no key, no login). The /en/for-sale page is a JS
shell with no server-rendered cards, so HTML scraping yields nothing.

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2} plus API-native county + lat/lon. The "html" crossing the
fetch/parse boundary is the JSON payload text (kept under the inherited
names so the shared contract and cached_fetch keep working unchanged).

Politeness / ToS: default page_limit=1 fetches page 1 of apartments +
page 1 of houses (2 requests), 24h file cache, daily-cron cadence, polite
UA + Accept: application/json. Check ROBOTS_URL before polling. Network
isolated in fetch_search_html() so tests run fully offline against
tests/fixtures/ (PII-free excerpts: broker/office/image blobs stripped).
"""

import json
from typing import List, Optional

from adapters import (
    cached_fetch,
    fetch_html,
    normalize_listing,
    polite_headers,
)

SOURCE = "city24.ee"
BASE_URL = "https://www.city24.ee"
SEARCH_URL = BASE_URL + "/en/for-sale"
ROBOTS_URL = BASE_URL + "/robots.txt"
API_URL = "https://api.city24.ee/et_EE/search/realties"

SELECTORS = {
    # API query description (one-spot fixes live here, not CSS hooks):
    # country 1 = Estonia, deal_types 1 = sale; object_types 1/2 = apt/house.
    "api": API_URL,
    "country": 1,
    "deal": "sale",
    "apartments": 1,
    "houses": 2,
}

HEADERS = dict(polite_headers())
HEADERS["Accept"] = "application/json"

# Canonical detail-page pattern (mirrors the site's own links).
DETAIL_URL = BASE_URL + "/et_EE/kinnisvara-otsing/objekt/%s"


def _api_params(object_type: int, page: int) -> dict:
    return {
        "address[cc]": 1,
        "deal_types[]": 1,
        "object_types[]": object_type,
        "page": page,
        "limit": 50,
    }


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """First page(s) of sale listings as a JSON array payload (text).

    One polite request per object type per page (default: 2 requests).
    `query` is accepted for interface compat and ignored (server-side text
    search is out of scope for the daily import).
    """
    _ = query
    items: List[dict] = []
    for object_type in (SELECTORS["apartments"], SELECTORS["houses"]):
        for page in range(1, max(1, page_limit) + 1):
            payload = fetch_html(
                API_URL,
                params=_api_params(object_type, page),
                headers=HEADERS,
                timeout=timeout,
            )
            try:
                batch = json.loads(payload)
            except ValueError:
                batch = []
            if isinstance(batch, list):
                items.extend(batch)
    return json.dumps(items)


def _address_of(item: dict) -> str:
    addr = item.get("address") or {}
    street = (addr.get("street_name") or "").strip()
    house = (addr.get("house_number") or "").strip()
    line = (street + (" " + house if house else "")).strip()
    tail = [
        addr.get("district_name") or addr.get("city_name") or "",
        addr.get("parish_name") or "",
        addr.get("county_name") or "",
    ]
    parts = ([line] if line else []) + [t for t in tail if t]
    return ", ".join(parts)


def _parse_item(item: dict) -> Optional[dict]:
    if not isinstance(item, dict) or not item.get("id"):
        return None
    try:
        price = int(float(item.get("price") or 0)) or None
    except (TypeError, ValueError):
        price = None
    rooms = item.get("room_count")
    rooms = int(rooms) if isinstance(rooms, (int, float)) else None
    area = item.get("property_size")
    area = float(area) if isinstance(area, (int, float)) else None
    lat = item.get("latitude")
    lat = float(lat) if isinstance(lat, (int, float)) else None
    lon = item.get("longitude")
    lon = float(lon) if isinstance(lon, (int, float)) else None
    addr = item.get("address") or {}
    rec = normalize_listing(
        {
            "id": "city24-%s" % item["id"],
            "source": SOURCE,
            "source_url": DETAIL_URL % item["id"],
            "address": _address_of(item) or ("city24.ee #%s" % item["id"]),
            "price": price,
            "rooms": rooms,
            "area_m2": area,
        }
    )
    rec["county"] = addr.get("county_name") or ""
    rec["lat"] = lat
    rec["lon"] = lon
    return rec


def parse_search_html(html: str) -> List[dict]:
    """Parse the JSON payload text into canonical records. Offline-safe."""
    try:
        payload = json.loads(html)
    except ValueError:
        return []
    if not isinstance(payload, list):
        return []
    out: List[dict] = []
    for item in payload:
        rec = _parse_item(item)
        if rec is not None:
            out.append(rec)
    return out


def scrape(
    query: str = "",
    page_limit: int = 1,
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = 24 * 3600,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize."""
    payload = cached_fetch(
        "city24_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(payload)
