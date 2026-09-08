"""1partner.ee listings adapter (1Partner Kinnisvara).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live verification (2026-09-08, polite UA "home-finder/0.1"):
- GET https://www.1partner.ee/robots.txt -> 200 with
  "Disallow: /*?*=*" (no query-string URLs may be polled) and "Disallow: /fi/".
  fetch_search_html therefore NEVER sends query params; `query` is accepted
  for interface compatibility and intentionally ignored.
- Saved live page /tmp/live_partner.html is the broker front page (no € prices,
  only blog teasers), so it parses to 0 rows by design.
- One polite probe GET https://www.1partner.ee/pakkumised -> 200 (~174KB,
  title "Pakkumised - 1Partner") with 18 real cards (clean URL, robots-safe).
  Real card markup observed:
  <div class="catalog-list-item"><a href="/pakkumised/<slug>-p.<id>"> with
  <div class="location"><strong>Müüa</strong>E. Vilde tee 65, ...</div>,
  attribute rows Hind: 120 000 € / Üldpind: 47 m<sup>2</sup> /
  Tubade arv: 2. SEARCH_URL is that observed index (the old apex base matched
  nothing live). Cards are sliced between consecutive card starts because each
  card nests carousel-control anchors; `query` stays ignored per robots.

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

SOURCE = "1partner.ee"
BASE_URL = "https://www.1partner.ee"
SEARCH_URL = BASE_URL + "/pakkumised"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # Card START tag on the live /pakkumised index (2026-09-08); parse slices
    # between consecutive starts (carousel-control anchors are nested).
    "card": r'<div class="catalog-list-item">',
    "id": r"-p\.(?P<id>\d+)",
    "id_fallback": r"\.(?P<id>\d+)(?:[/?#]|$)",
    "url": r'href="(?P<url>/pakkumised/[^"#]+)"',
    "address": r'class="location">\s*(?:<strong[^>]*>.*?</strong>)?\s*(?P<a>[^<]+?)\s*</div>',
    "price": r"(?P<price>[\d\s\u00a0.,]+)\s*€",
    # Room count is a bare number after its label ("Tubade arv 2").
    "rooms_label": r"(?:Tubade arv|tubade arv)\s*(?P<rooms>\d+)",
    "rooms": r"(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)",
    # Stripped text turns 47 m<sup>2</sup> into "47 m 2".
    "area": r"(?P<area>\d[\d.,]*)\s*m\s*(?:²|2(?!\d))",
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of 1partner.ee /pakkumised offers. Keeps page_limit small; cron, don't hammer.

    `query` is intentionally ignored: robots.txt disallows query-string URLs
    (Disallow: /*?*=*), so only the clean SEARCH_URL is ever fetched.
    """
    return fetch_html(SEARCH_URL, params={}, headers=HEADERS, timeout=timeout)


def _parse_card(card_html: str) -> Optional[dict]:
    um = re.search(SELECTORS["url"], card_html)
    pm = re.search(SELECTORS["price"], card_html)
    if not um or not pm:
        return None  # nav/blog teaser, not an offer
    im = re.search(SELECTORS["id"], um.group("url"))
    if not im:
        im = re.search(SELECTORS["id_fallback"], um.group("url"))
    if not im:
        return None
    card_id = im.group("id")
    address_m = re.search(SELECTORS["address"], card_html, re.S)
    url = um.group("url")
    address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
    address = re.sub(r"^(?:Müüa|Üürile anda|Müük|Üür)\s+", "", address)
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", card_html))
    rm = re.search(SELECTORS["rooms_label"], text)
    if not rm:
        rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text)
    if not url.startswith("http"):
        url = BASE_URL + (url if url.startswith("/") else "/" + url)
    return normalize_listing(
        {
            "id": "1partner-%s" % card_id,
            "source": SOURCE,
            "source_url": url,
            "address": address or ("1partner.ee #%s" % card_id),
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
        chunk = html[pos : starts[i + 1] if i + 1 < len(starts) else pos + 15000]
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
        "one_partner_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
