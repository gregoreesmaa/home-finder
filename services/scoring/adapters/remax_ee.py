"""remax.ee listings adapter (RE/MAX Estonia agency portal).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Politeness / ToS: default page_limit=1, polite UA, 24h file cache, daily-cron
cadence. Check ROBOTS_URL before polling. Network isolated in
fetch_search_html() so tests run fully offline against tests/fixtures/.

Probe note (2026-09-08, 1 polite probe, no retry): GET
https://www.remax.ee/robots.txt -> HTTP 200, WordPress/Yoast rules with an
empty `Disallow:` (listing paths allowed) + sitemap_index.xml. Search markup
was NOT fetched (1-probe budget spent on robots.txt). The site is
WordPress-based and listing grids may be JS-rendered: if live parse yields 0
rows, check whether cards need JS rendering (record, do not hammer) before
touching selectors. SELECTORS below are hand-built from observed public
markup knowledge and tests/fixtures/remax_search.html is a synthetic offline
sample (not a scraped dump). Re-verify SEARCH_URL + selectors with one polite
probe before enabling cron.
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

SOURCE = "remax.ee"
BASE_URL = "https://www.remax.ee"
# Candidate search path — re-verify with 1 polite probe before enabling cron.
SEARCH_URL = BASE_URL + "/kinnisvara"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # property-tile hooks matching tests/fixtures/remax_search.html;
    # re-verify against live markup if parse yields 0 rows (may be JS-rendered).
    "card": r'<div[^>]*class="[^"]*property-tile[^"]*"[^>]*data-id="(?P<id>\d+)"[^>]*>(?P<body>.*?)</div>\s*(?=<div[^>]*class="[^"]*property-tile|$)',
    "url": r'href="(?P<url>/[^\"]*?-(?P<id2>\d+)(?:\.html|/?))"',
    "price": r'(?P<price>[\d\s\u00a0]+)\s*€',
    "rooms": r'(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)',
    "area": r'(?P<area>[\d.,]+)\s*m[²2]',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of remax.ee search HTML. Keep page_limit small; cron, don't hammer."""
    params = {"page": 1}
    if query:
        params["q"] = query
    return fetch_html(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)


def _parse_card(card_id: str, body: str) -> dict:
    um = re.search(SELECTORS["url"], body)
    pm = re.search(SELECTORS["price"], body)
    address_m = re.search(r"<h[23][^>]*>(?P<a>.*?)</h[23]>", body, re.S)
    if not address_m:
        address_m = re.search(
            r'class="[^"]*(?:address|title)[^"]*"[^>]*>(?P<a>[^<]+)<', body, re.S | re.I
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
            "id": "remax-%s" % card_id,
            "source": SOURCE,
            "source_url": url,
            "address": address or ("remax.ee #%s" % card_id),
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
        "remax_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
