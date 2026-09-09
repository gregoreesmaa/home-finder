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
import time
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


PAGE_SIZE = 50  # kv.ee serves 50 results per search page (start=0,50,...)
PAGE_DELAY_S = 3.0  # politeness gap between page fetches (0 in tests)

# (#67) the legacy /et/search view is one unpaged apartment list; the
# category indexes paginate via ?start=N. (#69) the default search only
# ever showed apartments (korterid) — houses (majad) need their own index.
CATEGORIES = (
    ("korterid", "/korterid-muuk"),
    ("majad", "/majad-muuk"),
)


def build_search_url(query: str = "", category: str = "", page: int = 0) -> str:
    """Category index (+start pagination) by default.

    With a category path, returns that index at the given page; otherwise
    the legacy path-style sale-search URL exactly as the site's own form
    uses (apartments default view, single page).
    """
    if category:
        return "%s%s?start=%d" % (BASE_URL, category, page * PAGE_SIZE)
    url = "%s&deal_type=%s" % (SEARCH_URL, DEAL_TYPE_SALE)
    if query:
        url += "&keyword=" + quote_plus(query)
    return url


CHROME_ATTEMPTS = 3


def _fetch_url(url: str, timeout: float = 20.0) -> str:
    """One search URL. Plain HTTP first, genuine Chrome on block.

    Challenge outcomes vary per visit, so the Chrome fallback retries with a
    fresh profile and only accepts dumps that actually contain results.
    """
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


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Legacy single-URL sale search (apartments default view).

    The daily-cron path is scrape() with an empty query, which walks both
    category indexes page by page instead.
    """
    return _fetch_url(build_search_url(query), timeout)


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
    image = item.get("image") or None
    if not isinstance(image, str) or not image.startswith("http"):
        image = None
    return normalize_listing(
        {
            "id": rec_id,
            "source": SOURCE,
            "source_url": url if url.startswith("http") else BASE_URL + url,
            "address": address,
            "price": to_int_eur(str(offers.get("price", ""))) or None,
            "rooms": to_int_rooms(str(rooms)) if rooms is not None else None,
            "area_m2": to_float_m2(str(floor.get("value", ""))) or None,
            "image_url": image,
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
    delay_s: float = PAGE_DELAY_S,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize.

    Empty query (the cron path): walk both category indexes (#69) page by
    page (#67), one cached fetch per (category, page) with a politeness gap
    between fetches. Query mode keeps the legacy single-search behavior.
    """
    if query:
        html = cached_fetch(
            "kv_ee", query, page_limit,
            lambda: fetch_search_html(query, page_limit),
            cache_dir, cache_ttl_s,
        )
        return parse_search_html(html)
    out: List[dict] = []
    targets = [
        (path, page)
        for _name, path in CATEGORIES
        for page in range(max(1, page_limit))
    ]
    for i, (path, page) in enumerate(targets):
        url = build_search_url("", path, page)
        html = cached_fetch(
            "kv_ee", "%s:p%d" % (path, page),
            1, lambda u=url: _fetch_url(u),
            cache_dir, cache_ttl_s,
        )
        out.extend(parse_search_html(html))
        if delay_s and i < len(targets) - 1:
            time.sleep(delay_s)
    return out
