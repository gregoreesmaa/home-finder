"""kinnisvaraweb.ee listings adapter.

GitHub issue: #8 ([portal] kinnisvaraweb.ee adapter).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live probe (2026-09-08, polite UA, single GET):
- GET https://www.kinnisvaraweb.ee/ -> 301 redirect to http://www.kv.ee/
  which served a kv.ee bot-check page (HTTP 403, "meie süsteem tuvastas
  võimaliku tõrke"). kinnisvaraweb.ee is therefore a kv.ee alias: it serves
  kv.ee search markup, so this adapter reuses the kv.ee card hooks. Kept as
  its own adapter (own SOURCE ids) rather than closed as a duplicate so
  listings keep their origin portal label.
- No retry: on any block, record it and stay fixture-only. Fixtures are
  hand-built (never scraped dumps).

Politeness / ToS: default page_limit=1, polite UA, 24h file cache, daily-cron
cadence. Check ROBOTS_URL before polling. Network isolated in
fetch_search_html() so tests run fully offline against tests/fixtures/.
"""

import re
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

SOURCE = "kinnisvaraweb.ee"
BASE_URL = "https://www.kinnisvaraweb.ee"
# kv.ee search path: the domain redirects to kv.ee (verified 2026-09-08).
SEARCH_URL = BASE_URL + "/kuulutused"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # kv.ee card hooks (kinnisvaraweb.ee serves kv.ee markup per probe);
    # re-verify if parse yields 0 rows.
    "card": r'<article[^>]*data-object-id="(?P<id>\d+)"[^>]*>(?P<body>.*?)</article>',
    "url": r'href="(?P<url>/[^"]*?-(?P<id2>\d+)\.html)"',
    "price": r'(?P<price>[\d\s ]+)\s*€',
    "rooms": r'(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)',
    "area": r'(?P<area>[\d.,]+)\s*m[²2]',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of kinnisvaraweb.ee search HTML. Keep page_limit small; cron, don't hammer."""
    params = {"page": 1}
    if query:
        params["q"] = query
    return fetch_html(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)


def _parse_card(card_id: str, body: str) -> dict:
    um = re.search(SELECTORS["url"], body)
    pm = re.search(SELECTORS["price"], body)
    address_m = re.search(r"<h[23][^>]*>(?P<a>.*?)</h[23]>", body, re.S)
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    text = re.sub(r"<[^>]+>", " ", body)
    text = re.sub(r"\s+", " ", text)
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text, re.I)
    return normalize_listing(
        {
            "id": "kinnisvaraweb-%s" % card_id,
            "source": SOURCE,
            "source_url": BASE_URL + um.group("url") if um else BASE_URL,
            "address": address or ("kinnisvaraweb.ee #%s" % card_id),
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": to_int_rooms(rm.group("rooms")) if rm else None,
            "area_m2": to_float_m2(am.group("area")) if am else None,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """Parse search HTML into canonical records. Offline-safe (no network)."""
    out: List[dict] = []
    for m in re.finditer(SELECTORS["card"], html, re.S):
        out.append(_parse_card(m.group("id"), m.group("body")))
    return out


def scrape(
    query: str = "",
    page_limit: int = 1,
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = 24 * 3600,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize."""
    html = cached_fetch(
        "kinnisvaraweb_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
