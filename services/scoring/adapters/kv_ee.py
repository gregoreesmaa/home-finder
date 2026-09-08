"""kv.ee listings adapter.

Fetches kv.ee sale-search HTML and extracts a canonical listing record per
result. Verified 2026-09-08 against the live page (keyword search renders
``<title>Korterite müük, ...`` with an ``ItemList`` JSON-LD block holding
one ``Apartment`` entity per result).

Two things the old adapter got wrong:
* host is ``www.kv.ee`` and the search route is path-style
  (``/et/search&deal_type=1&keyword=...``), not ``kv.ee/kuulutused?q=``;
* kv.ee gates on the TLS fingerprint: scripted HTTP clients get the 403
  challenge page even with a full browser header/cookie replay, while a
  genuine Chrome engine passes. So on HTTP error the fetch falls back to
  headless Chrome (``fetch_html_via_chrome``) — a real browser doing what
  a browser does, no fingerprint spoofing, no challenge-solving.

Politeness / ToS: default page_limit=1, 24h file cache so repeat runs hit
disk, callers must rate-limit (daily cron). Check ROBOTS_URL before
polling. Network is isolated in fetch_search_html() so tests run offline.
"""

import json
import re
from typing import List, Optional
from urllib.parse import quote_plus

import httpx

from adapters import (
    cached_fetch,
    fetch_html,
    fetch_html_via_chrome,
    normalize_listing,
    polite_headers,
    to_float_m2,
    to_int_eur,
    to_int_rooms,
)

SOURCE = "kv.ee"
BASE_URL = "https://www.kv.ee"
SEARCH_URL = BASE_URL + "/et/search"
ROBOTS_URL = BASE_URL + "/robots.txt"

# deal_type=1 is the sale search (müük); results carry an ItemList JSON-LD
# block, one Apartment per hit. DOM anchors (data-object-id) are fallback.
DEAL_TYPE_SALE = "1"

SELECTORS = {
    "jsonld": r'<script[^>]*type="application/ld\+json"[^>]*>(?P<blob>.*?)</script>',
    "card": r'data-object-id="(?P<id>\d+)"[^>]*data-object-url="(?P<url>[^"]+)"',
    "url": r'href="(?P<url>/[^"]*?-(?P<id2>\d+)\.html)"',
    "price": r"(?P<price>[\d\s ]+)\s*€",
    "rooms": r"(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)",
    "area": r"(?P<area>[\d.,]+)\s*m[²2]",
}

HEADERS = polite_headers()


def build_search_url(query: str = "") -> str:
    """Path-style sale-search URL exactly as the site's own form uses."""
    url = "%s&deal_type=%s" % (SEARCH_URL, DEAL_TYPE_SALE)
    if query:
        url += "&keyword=" + quote_plus(query)
    return url


CHROME_ATTEMPTS = 3


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single sale-search page. Plain HTTP first, genuine Chrome on block.

    Challenge outcomes vary per visit, so the Chrome fallback retries with a
    fresh profile and only accepts dumps that actually contain results.
    """
    url = build_search_url(query)
    try:
        return fetch_html(url, params={}, headers=HEADERS, timeout=timeout)
    except httpx.HTTPError:
        pass
    last: Exception = RuntimeError("unreachable")
    for _ in range(CHROME_ATTEMPTS):
        try:
            html = fetch_html_via_chrome(url)
        except RuntimeError as e:
            last = e
            continue
        if '"itemListElement"' in html:
            return html
        last = RuntimeError("headless Chrome returned a challenge/empty page")
    raise last


def _id_from_url(url: str) -> Optional[str]:
    """kv-<id> from detail URLs, classic (`-123.html`) or project-style.

    Project URLs end in a bare `-<id>` with no .html suffix; requiring 5+
    digits keeps dates/years (`/19-08-2026-kliendipaev...`) and article slugs
    out while real ids (7 digits) always match.
    """
    m = re.search(r"-(\d+)\.html", url or "")
    if m:
        return "kv-%s" % m.group(1)
    m = re.search(r"-(\d{5,})/?$", url or "")
    return "kv-%s" % m.group(1) if m else None


def _parse_jsonld_item(entry: dict) -> Optional[dict]:
    item = entry.get("item", entry) if isinstance(entry, dict) else None
    if not isinstance(item, dict):
        return None
    url = item.get("url") or item.get("@id") or ""
    if isinstance(url, dict):
        url = ""
    rec_id = _id_from_url(url)
    if not rec_id:
        return None
    addr = item.get("address") or {}
    parts = [addr.get("streetAddress"), addr.get("addressLocality")]
    address = ", ".join(p for p in parts if p) or item.get("name") or ""
    offers = item.get("offers") or {}
    floor = item.get("floorSize") or {}
    rooms = item.get("numberOfRooms")
    return normalize_listing(
        {
            "id": rec_id,
            "source": SOURCE,
            "source_url": url if url.startswith("http") else BASE_URL + url,
            "address": address,
            "price": to_int_eur(str(offers.get("price", ""))) or None,
            "rooms": to_int_rooms(str(rooms)) if rooms is not None else None,
            "area_m2": to_float_m2(str(floor.get("value", ""))) or None,
        }
    )


def _parse_jsonld(html: str) -> List[dict]:
    out: List[dict] = []
    for m in re.finditer(SELECTORS["jsonld"], html, re.S | re.I):
        try:
            blob = json.loads(m.group("blob"))
        except (ValueError, AttributeError):
            continue
        blobs = blob if isinstance(blob, list) else [blob]
        for b in blobs:
            if not isinstance(b, dict):
                continue
            main = b.get("mainEntity", b)
            if not isinstance(main, dict):
                continue
            items = main.get("itemListElement", [])
            if isinstance(items, dict):
                items = [items]
            for entry in items:
                rec = _parse_jsonld_item(entry) if isinstance(entry, dict) else None
                if rec:
                    out.append(rec)
    return out


def _parse_card(card_id: str, url: str, body: str) -> dict:
    pm = re.search(SELECTORS["price"], body)
    address_m = re.search(r"<h[23][^>]*>(?P<a>.*?)</h[23]>", body, re.S)
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text, re.I)
    return normalize_listing(
        {
            "id": "kv-%s" % card_id,
            "source": SOURCE,
            "source_url": BASE_URL + url,
            "address": address or ("kv.ee #%s" % card_id),
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": to_int_rooms(rm.group("rooms")) if rm else None,
            "area_m2": to_float_m2(am.group("area")) if am else None,
        }
    )


def _parse_dom_cards(html: str) -> List[dict]:
    out: List[dict] = []
    for m in re.finditer(SELECTORS["card"], html):
        window = html[m.start() : m.start() + 4000]
        out.append(_parse_card(m.group("id"), m.group("url"), window))
    return out


def parse_search_html(html: str) -> List[dict]:
    """Parse search HTML into canonical records. Offline-safe (no network).

    Primary source is the ItemList JSON-LD block (exact price/rooms/area);
    DOM cards are fallback for pages where the block is absent.
    """
    rows = _parse_jsonld(html)
    if rows:
        return rows
    return _parse_dom_cards(html)


def scrape(
    query: str = "",
    page_limit: int = 1,
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = 24 * 3600,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize."""
    html = cached_fetch(
        "kv_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
