"""kinnisvaraekspert.ee listings adapter (Kinnisvaraekspert).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live verification (2026-09-09, polite UA "home-finder/0.1"):
- GET https://kinnisvaraekspert.ee/robots.txt -> 200, "Disallow:" empty
  (full allow, Yoast block only).
- GET https://kinnisvaraekspert.ee/objektid/ -> 200, ~148KB server-rendered
  index with 20 <article class="post object ..."> cards (15 sale / 5 rent).
  Real card markup observed:
  <article class="post object  object-large ">
    <h2 class="price-right" > 86&nbsp;000 <span class="currency">€</span></h2>
    <h2 class="entry-title"><a href="/objektid/156286">
      <span class="transaction">Müüa </span>
      <span class="objecttype">korter </span>
      <span class="objectname">Oja 118</span></a></h2>
    <p class="entry-sub-title">...<span class="Level1">Pärnu maakond, </span>
      <span class="Level2">Pärnu linn, </span><span class="Level3">Pärnu linn</span></p>
    ...<div class="param NumberOfRooms"><div class="param-value">1</div>...
    ...<div class="param AreaSize"><div class="param-value"><strong>25</strong>...
  Prices use &nbsp; thousand separators (unescaped before parsing).
- The index mixes sale (Müüa) and rent (Üürida) rows like domus.ee, and
  detail URLs carry no deal markers (/objektid/<id>), so the adapter keeps
  all rows and ingest.PORTAL_DEFAULT_TYPE maps this hub to None (unmarked
  rows type as unknown, rent markers still override) — same model as domus.

Politeness / ToS: default page_limit=1, polite UA, 24h file cache, daily-cron
cadence. Check ROBOTS_URL before polling. Network isolated in
fetch_search_html() so tests run fully offline against tests/fixtures/.
"""

import html as _html
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

SOURCE = "kinnisvaraekspert.ee"
BASE_URL = "https://kinnisvaraekspert.ee"
SEARCH_URL = BASE_URL + "/objektid/"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # One server-rendered <article> per object on the live index.
    "card": r'<article class="post object.*?</article>',
    "url": r'href="(?P<url>/objektid/(?P<id>\d+)/?)"',
    "price": r'class="price-right"[^>]*>(?P<price>[\d\s\xa0;&]+?)\s*<span class="currency">',
    "objectname": r'<span class="objectname">(?P<name>[^<]*)</span>',
    "level": r'<span class="Level\d">(?P<lvl>[^<]*)</span>',
    "rooms": r'param NumberOfRooms"><div class="param-value">(?P<rooms>\d+)',
    "area": r'param AreaSize"><div class="param-value"><strong>(?P<area>[\d.,]+)',
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of the objektid index. Keep page_limit small; cron, don't hammer."""
    _ = (query, page_limit)  # server-side search/paging out of scope for import
    return fetch_html(SEARCH_URL, params={}, headers=HEADERS, timeout=timeout)


def _parse_card(card_html: str) -> Optional[dict]:
    um = re.search(SELECTORS["url"], card_html)
    if not um:
        return None
    card = _html.unescape(card_html)
    pm = re.search(SELECTORS["price"], card)
    nm = re.search(SELECTORS["objectname"], card)
    levels = [lv.strip(" ,") for lv in re.findall(SELECTORS["level"], card)]
    name = nm.group("name").strip() if nm else ""
    parts = []
    for p in [name] + levels:
        if p and (not parts or parts[-1] != p):
            parts.append(p)
    address = ", ".join(parts)
    rm = re.search(SELECTORS["rooms"], card)
    am = re.search(SELECTORS["area"], card)
    return normalize_listing(
        {
            "id": "ekspert-%s" % um.group("id"),
            "source": SOURCE,
            "source_url": BASE_URL + um.group("url"),
            "address": address,
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": to_int_rooms(rm.group("rooms")) if rm else None,
            "area_m2": to_float_m2(am.group("area")) if am else None,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """Parse index HTML into canonical records. Offline-safe (no network)."""
    out: List[dict] = []
    for m in re.finditer(SELECTORS["card"], html or "", re.S):
        rec = _parse_card(m.group(0))
        if rec:
            out.append(rec)
    return out


def scrape(
    query: str = "",
    page_limit: int = 1,
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = 24 * 3600,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize."""
    html = cached_fetch(
        "kinnisvaraekspert_ee", query, page_limit,
        lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
