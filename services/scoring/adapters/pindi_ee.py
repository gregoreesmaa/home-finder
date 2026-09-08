"""pindi.ee listings adapter (Pindi Kinnisvara).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live verification (2026-09-08, polite UA "home-finder/0.1"):
- GET https://www.pindi.ee/robots.txt -> 200, "Disallow:" empty (full allow).
- Saved live page /tmp/live_pindi.html is the listing index itself
  (title "Kinnisvarapakkumised", ~233KB) with 10 real cards; no extra probe
  was needed. Real card markup observed:
  <div class="offer"><a class="offer-link"
  href="https://www.pindi.ee/kinnisvarapakkumised/<slug>/?offset=N"> with
  <div class="offer-name ...">Ida-Viru maakond, Narva linn, Rakvere tn 87</div>,
  <li class="offer-details-item">3 tuba</li> / 61.5 m² / 5/5 korrus,
  <div class="offer-price-amount ...">47 500 € (+ per-m² extra)</div> and
  <div class="... js-offer-price-favorite" item-id="17102">.
  The card URL slug carries NO numeric id, so the stable id comes from the
  item-id attribute (the old data-id / trailing-URL-digits fallbacks matched
  nothing live and are gone). Exactly one <a> per card, so the card regex
  spans <div class="offer">..</a></div>.

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

SOURCE = "pindi.ee"
BASE_URL = "https://www.pindi.ee"
SEARCH_URL = BASE_URL + "/kinnisvara-pakkumised/"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # One <a class="offer-link"> per card on the live index (2026-09-08).
    "card": r'<div class="offer">\s*<a[^>]*class="offer-link"[^>]*>.*?</a>\s*</div>',
    "id": r'item-id="(?P<id>\d+)"',
    "url": r'href="(?P<url>(?:https://www\.pindi\.ee)?/[^"]*)"',
    "address": r'offer-name[^>]*>(?P<a>[^<]+)<',
    "price": r"(?P<price>[\d\s\u00a0.,]+)\s*€",
    "rooms": r"(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)",
    "area": r"(?P<area>\d[\d.,]*)\s*m\s*(?:²|2(?!\d))",
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of pindi.ee offers HTML. Keep page_limit small; cron, don't hammer."""
    params = {}
    if query:
        params["s"] = query  # site runs WordPress; WP search var
    return fetch_html(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)


def _parse_card(card_html: str) -> Optional[dict]:
    im = re.search(SELECTORS["id"], card_html)
    um = re.search(SELECTORS["url"], card_html)
    pm = re.search(SELECTORS["price"], card_html)
    address_m = re.search(SELECTORS["address"], card_html, re.S)
    if not address_m:
        address_m = re.search(r"<h[23][^>]*>(?P<a>.*?)</h[23]>", card_html, re.S)
    if not um or not im:
        return None
    url = um.group("url")
    card_id = im.group("id")
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", card_html))
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text)
    price_raw = pm.group("price") if pm else None
    if price_raw:
        # Live rents can carry decimals ("2 011.1 €"); euros are integers,
        # so drop a trailing fraction instead of gluing it onto the price.
        price_raw = re.sub(r"[.,]\d+\s*$", "", price_raw)
    if not url.startswith("http"):
        url = BASE_URL + (url if url.startswith("/") else "/" + url)
    return normalize_listing(
        {
            "id": "pindi-%s" % card_id,
            "source": SOURCE,
            "source_url": url,
            "address": address or ("pindi.ee #%s" % card_id),
            "price": to_int_eur(price_raw) if price_raw else None,
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
        "pindi_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
