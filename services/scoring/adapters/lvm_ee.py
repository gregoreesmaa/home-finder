"""lvm.ee listings adapter (LVM Kinnisvara agency portal).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Politeness / ToS: default page_limit=1, polite UA, 24h file cache, daily-cron
cadence. Check ROBOTS_URL before polling. Network isolated in
fetch_search_html() so tests run fully offline against tests/fixtures/.

Live note (2026-09-08, offline re-read of saved search hub HTML,
https://lvm.ee/objektid/, no new live request): result cards are
<div class="realestate-object"> blocks (exact class; inner wrappers use
suffixed classes such as realestate-object-info), each with
<a href="/objektid/<id>">, an <h3> address, a
<span class="realestate-object-price"> ("520 €", "365 000 €") and a
<div class="realestate-object-stats"> span ("3 korrus | 2 tuba |
üldpind 34.70m²"). SELECTORS below match that live markup;
tests/fixtures/lvm_search.html holds 2 verbatim live cards (small excerpt,
not a dump). Full-page live parse yields 20 rows.
"""

import re
from html import unescape as _unescape
from typing import List, Optional

from adapters import (
    cached_fetch,
    fetch_html,
    normalize_listing,
    polite_headers,
    to_float_m2,
    to_int_eur,
    to_int_rooms,
)

SOURCE = "lvm.ee"
BASE_URL = "https://lvm.ee"
SEARCH_URL = BASE_URL + "/objektid/"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # Live card: outer <div class="realestate-object"> (exact class match so
    # inner -info/-description/-details wrappers don't open false cards).
    # Body runs from the main /objektid/<id> link through the stats div, so
    # the first url match in the body is always the canonical listing link
    # (not the trailing #objbroker broker anchor).
    "card": r'<div[^>]*class="realestate-object"[^>]*>(?P<body>\s*<a[^>]*href="/objektid/\d+"[^>]*>.*?</a>.*?<div[^>]*class="[^"]*realestate-object-stats[^"]*"[^>]*>.*?</div>\s*)</div>\s*</div>',
    "url": r'href="(?P<url>/objektid/(?P<id2>\d+)[^"]*)"',
    "price_scope": '<span[^>]*class="[^"]*realestate-object-price[^"]*"[^>]*>(?P<scope>.*?)</span>',
    "price": r'(?P<price>[\d\s\u00a0]+)\s*€',
    "rooms": r'(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)',
    "area": r'(?P<area>\d[\d.,]*)\s*m[²2]',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of lvm.ee search HTML. Keep page_limit small; cron, don't hammer."""
    params = {"page": 1}
    if query:
        params["q"] = query
    return fetch_html(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)


def _parse_card(card_id: str, body: str) -> dict:
    um = re.search(SELECTORS["url"], body)
    # Unescape first (live prices use &nbsp;, areas use m&#178;) and strip
    # tags before matching detail fields.
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _unescape(body)))
    scope_m = re.search(SELECTORS["price_scope"], _unescape(body), re.S)
    price_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", _unescape(scope_m.group("scope")))) if scope_m else text
    pm = re.search(SELECTORS["price"], price_text)
    address_m = re.search(r"<h3[^>]*>(?P<a>.*?)</h3>", _unescape(body), re.S)
    if not address_m:
        address_m = re.search(
            r'class="[^"]*(?:address|title)[^"]*"[^>]*>(?P<a>[^<]+)<', body, re.S | re.I
        )
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    address = re.sub(r"\s+", " ", _unescape(address)).strip()
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text, re.I)
    url = um.group("url") if um else "/"
    if not url.startswith("http"):
        url = BASE_URL + (url if url.startswith("/") else "/" + url)
    return normalize_listing(
        {
            "id": "lvm-%s" % card_id,
            "source": SOURCE,
            "source_url": url,
            "address": address or ("lvm.ee #%s" % card_id),
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": to_int_rooms(rm.group("rooms")) if rm else None,
            "area_m2": to_float_m2(am.group("area")) if am else None,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """Parse search HTML into canonical records. Offline-safe (no network)."""
    out: List[dict] = []
    for m in re.finditer(SELECTORS["card"], html, re.S):
        body = m.group("body")
        um = re.search(SELECTORS["url"], body)
        if not um:
            continue
        out.append(_parse_card(um.group("id2"), body))
    return out


def scrape(
    query: str = "",
    page_limit: int = 1,
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = 24 * 3600,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize."""
    html = cached_fetch(
        "lvm_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
