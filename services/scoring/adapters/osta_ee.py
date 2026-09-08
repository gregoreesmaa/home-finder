"""osta.ee listings adapter (auction/classified portal).

GitHub issue: #10 ([portal] osta.ee adapter).
Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Probe note (2026-09-08, recon): GET /robots.txt on osta.ee -> HTTP 403
Forbidden, so NO listing-page probe was made (no retry per policy). The
fixture (tests/fixtures/osta_search.html) is hand-built from observed public
markup knowledge — auction cards exposing an item id, title link, and price —
never a scraped dump. Re-verify SELECTORS against live markup once robots
allows it; if parse yields 0 rows the selectors are stale.

Price semantics: osta.ee cards may show a current bid ("Pakkumine") and a
buy-now ("Osta kohe") price. The parser prefers the buy-now price when both
are present, else the single visible price, else None.

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

SOURCE = "osta.ee"
BASE_URL = "https://www.osta.ee"
SEARCH_URL = BASE_URL + "/kinnisvara"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # Auction-card hooks matching tests/fixtures/osta_search.html (hand-built
    # sample of public card markup); re-verify against live markup if parse
    # yields 0 rows.
    "card": r'<div[^>]*class="[^"]*offer[^"]*"[^>]*data-id="(?P<id>\d+)"[^>]*>(?P<body>.*?)</div>\s*(?=<div[^>]*class="[^"]*offer|$)',
    "url": r'href="(?P<url>/[^"]*?:(?P<id2>\d+)\.html)"',
    "buy_now": r'[Oo]sta\s*kohe[^€\d]*(?P<price>[\d\s\u00a0]+)\s*€',
    "price": r'(?P<price>[\d\s\u00a0]+)\s*€',
    "rooms": r'(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)',
    "area": r'(?P<area>[\d.,]+)\s*m[²2]',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of osta.ee kinnisvara search HTML. Keep page_limit small; cron, don't hammer."""
    params = {"page": 1}
    if query:
        params["q"] = query
    return fetch_html(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)


def _parse_card(card_id: str, body: str) -> dict:
    um = re.search(SELECTORS["url"], body)
    bm = re.search(SELECTORS["buy_now"], body)
    pm = bm or re.search(SELECTORS["price"], body)
    address_m = re.search(r"<h[23][^>]*>(?P<a>.*?)</h[23]>", body, re.S)
    if not address_m:
        address_m = re.search(
            r'class="[^"]*(?:title|heading)[^"]*"[^>]*>(?P<a>[^<]+)<', body, re.S | re.I
        )
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text, re.I)
    url = um.group("url") if um else "/"
    if not url.startswith("http"):
        url = BASE_URL + (url if url.startswith("/") else "/" + url)
    return normalize_listing(
        {
            "id": "osta-%s" % card_id,
            "source": SOURCE,
            "source_url": url,
            "address": address or ("osta.ee #%s" % card_id),
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
        "osta_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
