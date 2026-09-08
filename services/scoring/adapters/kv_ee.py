"""kv.ee listings adapter.

Fetches kv.ee search HTML and extracts a canonical listing record per card.
No public API exists, so this parses server-rendered markup; selectors are
kept in one place (SELECTORS) so breakage is a one-spot fix.

Politeness / ToS: default page_limit=1, polite UA, 24h file cache so repeat
runs hit disk, callers must rate-limit (daily cron). Check ROBOTS_URL before
polling. Network is isolated in fetch_search_html() so tests run offline.
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

SOURCE = "kv.ee"
BASE_URL = "https://kv.ee"
SEARCH_URL = BASE_URL + "/kuulutused"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # data-* hooks observed on kv.ee search cards; re-verify if parse yields 0 rows
    "card": r'<article[^>]*data-object-id="(?P<id>\d+)"[^>]*>(?P<body>.*?)</article>',
    "url": r'href="(?P<url>/[^"]*?-(?P<id2>\d+)\.html)"',
    "price": r'(?P<price>[\d\s\u00a0]+)\s*€',
    "rooms": r'(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)',
    "area": r'(?P<area>[\d.,]+)\s*m[²2]',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of kv.ee search HTML. Keep page_limit small; cron, don't hammer."""
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
            "id": "kv-%s" % card_id,
            "source": SOURCE,
            "source_url": BASE_URL + um.group("url") if um else BASE_URL,
            "address": address or ("kv.ee #%s" % card_id),
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
        "kv_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
