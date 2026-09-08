"""uusmaa.ee listings adapter (Uus Maa Kinnisvarabüroo).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live verification (2026-09-08, polite UA "home-finder/0.1"):
- GET https://uusmaa.ee/ (front page, ~194KB) carries NO listing cards with
  prices (only /arendus/ development teasers + market stats), so it parses
  to 0 rows by design.
- One polite probe GET https://uusmaa.ee/pakkumised/ -> 200 (~429KB,
  "Kõik pakkumised (3556)"). Real card markup observed there:
  <div class="col property property-type-default"> wrapping
  <a href="https://uusmaa.ee/pakkumine/<id>-<slug>"> with
  <div class="value">95 000 €</div>,
  <div class="small-address">Viljandi linn, Männimäe, Riia mnt 71</div>,
  <span>3 tuba</span>, <span>62.40 m<sup>2</sup></span>.
  SEARCH_URL is that observed index (the old /?post_type=property base
  matched nothing live). Cards are sliced between consecutive card starts
  because each card embeds a multi-image gallery + a hidden infowindow
  duplicate; field regexes take the first match (the main block).
- GET https://uusmaa.ee/robots.txt -> 200; the clean /pakkumised/ index is
  fetched without params by default (`query` maps onto the observed WP `s`
  search var, also seen in live filter URLs).

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
SEARCH_URL = BASE_URL + "/pakkumised/"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # Card START tag on the live /pakkumised/ index (2026-09-08); parse slices
    # between consecutive starts (gallery + infowindow markup is nested).
    "card": r'<div class="col property property-type-default"[^>]*>',
    "id": r"/pakkumine/(?P<id>\d+)-",
    "url": r'href="(?P<url>https://uusmaa\.ee/pakkumine/[^"]+)"',
    "address": r'small-address">(?P<a>[^<]+)<',
    "address_fallback": r"<h4[^>]*>(?P<a>.*?)</h4>",
    "price": r"(?P<price>[\d\s\u00a0.,]+)\s*€",
    "rooms": r"(?P<rooms>\d+)\s*(?:-toaline|tuba|tubade|rooms?|tk)",
    # Stripped text turns 62.40 m<sup>2</sup> into "62.40 m 2".
    "area": r"(?P<area>\d[\d.,]*)\s*m\s*(?:²|2(?!\d))",
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of uusmaa.ee /pakkumised/ HTML. Keep page_limit small; cron, don't hammer."""
    params = {}
    if query:
        params["s"] = query  # WP search var, observed in the live filter URLs (s=)
    return fetch_html(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)


def _parse_card(card_html: str) -> Optional[dict]:
    im = re.search(SELECTORS["id"], card_html)
    um = re.search(SELECTORS["url"], card_html)
    pm = re.search(SELECTORS["price"], card_html)
    address_m = re.search(SELECTORS["address"], card_html)
    if not address_m:
        address_m = re.search(SELECTORS["address_fallback"], card_html, re.S)
    if not um or not im:
        return None
    url = um.group("url")
    card_id = im.group("id")
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", card_html))
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text)
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
    starts = [m.start() for m in re.finditer(SELECTORS["card"], html)]
    out: List[dict] = []
    for i, pos in enumerate(starts):
        chunk = html[pos : starts[i + 1] if i + 1 < len(starts) else pos + 60000]
        row = _parse_card(chunk)
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
