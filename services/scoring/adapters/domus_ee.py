"""domus.ee listings adapter (Domus Kinnisvara agency portal).

GitHub issue: #12 ([portal] Domus adapter).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live-markup note (2026-09-08, verified against the real hub):
GET https://domus.ee/kinnisvara 301-redirects to a 2015 blog post
(slug collision), so SEARCH_URL is the real listings hub
https://domus.ee/objektid/ ("Objektid" nav link, title "Kinnisvara müük",
785 results / 53 pages on 2026-09-08). Cards are server-rendered:

    <div class="col-md-4 object-col flex-col" data-id="...">
      <div class="object marker-wrapper">
        <a href="https://domus.ee/objektid/<oid>-<slug>/">...</a>
        <div class="content-box">
          <div class="row">
            <div class="col-xs-4 text-orange"><strong>35 000 €</strong></div>
            <div class="col-xs-4"><span class="toupper"><strong>2 tuba</strong></span></div>
          ...
          <div class="row small-text">
            <div class="col-xs-4">1.8 € / m<sup>2</sup></div>
            <div class="col-xs-4">43.2 m<sup>2</sup></div>
          ...
          <div class="link"><a href="...">Nõlvaku tn 17, Annelinn, ...</a></div>

Parsing the saved live hub page yields 15/15 cards (LIVE ROWS=15).
Rental cards quote monthly rent ("475 €/kuus"); canonical `price` keeps the
listed figure as-is. Land cards omit rooms (rooms=None).

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
    to_int_eur,
    to_int_rooms,
)

SOURCE = "domus.ee"
BASE_URL = "https://domus.ee"
# Real listings hub. NOTE: /kinnisvara 301s to a 2015 blog post — do not use.
SEARCH_URL = BASE_URL + "/objektid/"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # Card-opener hook of the live hub markup (server-rendered). Cards are
    # sliced between consecutive openers (nested divs defeat one regex).
    "card": r'<div class="col-md-4 object-col flex-col" data-id="(?P<dataid>\d+)">',
    "url": r'href="(?P<url>https?://domus\.ee/objektid/(?P<oid>\d+)-[^"]+/)"',
    "price": r'<div class="col-xs-4 text-orange"><strong>(?P<price>[^<]+)</strong></div>',
    "rooms": r'<span class="toupper"><strong>(?P<rooms>[^<]+)</strong></span>',
    # Area cell has no € (excludes the per-m2 "1 660.5 € / m<sup>2</sup>" cell);
    # total area uses dot decimals ("43.2", "20000").
    "area": r'<div class="col-xs-4">(?P<area>[\d\s.,]+)\s*m<sup>2</sup></div>',
    "address": r'<div class="link"><a[^>]*>(?P<a>[^<]+)</a></div>',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """First page of the domus.ee listings hub. Keep page_limit small; cron, don't hammer."""
    return fetch_html(SEARCH_URL, params={}, headers=HEADERS, timeout=timeout)


def _parse_card(body: str) -> Optional[dict]:
    um = re.search(SELECTORS["url"], body)
    if not um:
        return None
    card_id = um.group("oid")
    pm = re.search(SELECTORS["price"], body)
    rm = re.search(SELECTORS["rooms"], body)
    am = re.search(SELECTORS["area"], body)
    address_m = re.search(SELECTORS["address"], body)
    area = None
    if am:
        try:
            area = float(
                am.group("area").replace(" ", "").replace("\u00a0", "").replace(",", ".")
            )
        except ValueError:
            area = None
    return normalize_listing(
        {
            "id": "domus-%s" % card_id,
            "source": SOURCE,
            "source_url": um.group("url"),
            "address": address_m.group("a").strip() if address_m else "",
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": to_int_rooms(rm.group("rooms")) if rm else None,
            "area_m2": area,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """Parse search HTML into canonical records. Offline-safe (no network)."""
    out: List[dict] = []
    opens = list(re.finditer(SELECTORS["card"], html))
    for i, m in enumerate(opens):
        end = opens[i + 1].start() if i + 1 < len(opens) else len(html)
        row = _parse_card(html[m.start() : end])
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
        "domus_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
