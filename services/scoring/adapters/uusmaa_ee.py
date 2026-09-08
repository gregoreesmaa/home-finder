"""uusmaa.ee listings adapter (Uus Maa Kinnisvarabüroo).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live verification (2026-09-08, polite UA "home-finder/0.1", 1 probe + robots):
- GET https://uusmaa.ee/robots.txt -> 200; only /emailsig/, /uus/, /uus1/
  disallowed, so the property search below is allowed.
- GET https://uusmaa.ee/ (apex) -> 200 (~194KB, WordPress). Observed live:
  search/filter links of the form
  https://uusmaa.ee/?post_type=property&...&s=&... (property post type),
  and listing containers carrying a "property" CSS class. SEARCH_URL reuses
  the observed post_type=property base; fetch maps `query` onto the observed
  WP `s` search var. Card regexes target <article class="*property*"> blocks;
  id comes from data-id with a fallback to trailing digits in the card URL.

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

SOURCE = "uusmaa.ee"
BASE_URL = "https://uusmaa.ee"
SEARCH_URL = BASE_URL + "/?post_type=property"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # <article class="...property..."> teasers observed on the live front page;
    # re-verify against live markup if parse yields 0 rows.
    "card": r'<article[^>]*class="[^"]*property[^"]*"[^>]*>.*?</article>',
    "id": r'data-id="(?P<id>\d+)"',
    "url": r'href="(?P<url>(?:https://uusmaa\.ee)?/[^"]*)"',
    "price": r'(?P<price>[\d\s\u00a0]+)\s*€',
    "rooms": r'(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)',
    "area": r'(?P<area>[\d.,]+)\s*m[²2]',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of uusmaa.ee property search HTML. Keep page_limit small; cron, don't hammer."""
    params = {}
    if query:
        params["s"] = query  # WP search var, observed in the live filter URL (s=)
    return fetch_html(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)


def _parse_card(card_html: str) -> Optional[dict]:
    im = re.search(SELECTORS["id"], card_html)
    um = re.search(SELECTORS["url"], card_html)
    pm = re.search(SELECTORS["price"], card_html)
    address_m = re.search(r"<h[23][^>]*>(?P<a>.*?)</h[23]>", card_html, re.S)
    if not address_m:
        address_m = re.search(
            r'class="[^"]*(?:address|title)[^"]*"[^>]*>(?P<a>[^<]+)<', card_html, re.S | re.I
        )
    url = um.group("url") if um else "/"
    card_id = im.group("id") if im else None
    if not card_id and um:
        dm = re.search(r"(\d+)(?:/?(?:\?.*)?)$", url)
        card_id = dm.group(1) if dm else None
    if not card_id:
        return None
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", card_html))
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text, re.I)
    if not url.startswith("http"):
        url = BASE_URL + (url if url.startswith("/") else "/" + url)
    return normalize_listing(
        {
            "id": "uusmaa-%s" % card_id,
            "source": SOURCE,
            "source_url": url,
            "address": address or ("uusmaa.ee #%s" % card_id),
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": to_int_rooms(rm.group("rooms")) if rm else None,
            "area_m2": to_float_m2(am.group("area")) if am else None,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """Parse search HTML into canonical records. Offline-safe (no network)."""
    out: List[dict] = []
    for m in re.finditer(SELECTORS["card"], html, re.S):
        row = _parse_card(m.group(0))
        if row is not None:
            out.append(row)
    return out


def scrape(
    query: str = "",
    page_limit: int = 1,
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = 24 * 3600,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize."""
    html = cached_fetch(
        "uusmaa_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
