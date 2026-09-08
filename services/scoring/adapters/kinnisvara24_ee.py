"""kinnisvara24.ee listings adapter.

GitHub issue: #7 ([portal] kinnisvara24.ee adapter).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live probe (2026-09-08, polite UA, single GET):
- GET https://kinnisvara24.ee/korter-muuk-tallinn/ -> HTTP 404, Vue SPA shell
  (assets on s1.kv24.ee, title "Kinnisvara24"). The guessed "muuk" search path
  does NOT exist; listing URLs observed publicly use the "myyk" spelling
  (/korter-myyk-tallinn/<id>), so SEARCH_URL uses that spelling. It still
  needs one re-verifying probe before enabling any cron poll.
- Site is JS-driven (SPA); if search results are client-rendered, parse will
  yield 0 rows and the adapter must stay fixture-only until SSR markup (or an
  approved data path) is confirmed. No retry, no scraped dumps — fixtures only.

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

SOURCE = "kinnisvara24.ee"
BASE_URL = "https://kinnisvara24.ee"
# "myyk" spelling per observed public listing URLs (/korter-myyk-tallinn/<id>);
# the "muuk" variant 404'd on probe (2026-09-08) — re-verify with one probe.
SEARCH_URL = BASE_URL + "/korter-myyk-tallinn/"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # Server-rendered card hooks (re-verify against live SSR markup: the site
    # is a Vue SPA, so if parse yields 0 rows the cards are client-rendered
    # and this adapter stays fixture-only). Fixture models this card shape.
    "card": r'<article[^>]*class="[^"]*listing-card[^"]*"[^>]*data-id="(?P<id>\d+)"[^>]*>(?P<body>.*?)</article>',
    "url": r'href="(?P<url>/[^"]*?-(?P<id2>\d+)(?:\.html|/?))"',
    "price": r'(?P<price>[\d\s ]+)\s*€',
    "rooms": r'(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)',
    "area": r'(?P<area>[\d.,]+)\s*m[²2]',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of kinnisvara24.ee search HTML. Keep page_limit small; cron, don't hammer."""
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
            "id": "kinnisvara24-%s" % card_id,
            "source": SOURCE,
            "source_url": url,
            "address": address or ("kinnisvara24.ee #%s" % card_id),
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
        "kinnisvara24_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
