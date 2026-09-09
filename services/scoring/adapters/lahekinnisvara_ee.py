"""lahekinnisvara.ee listings adapter (Lahe Kinnisvara) — disabled stub.

GitHub issue: #68 (mirror more portals from the reference project).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live probe (2026-09-09, polite UA, single GET):
- GET https://lahekinnisvara.ee/robots.txt -> HTTP 403 bot protection.
  Per the no-probe-past-a-block rule (cf. osta.ee), no listing probe was
  attempted. This adapter stays disabled until an approved data path is
  confirmed. No retry, no scraped dumps — stub only.

SEARCH_URL below is reference-derived (~/projects/real-estate-search lists
https://lahekinnisvara.ee/kinnisvara/ as the offers index) and UNVERIFIED
against live markup; re-verify with one probe before enabling any cron poll.

Politeness / ToS: default page_limit=1, polite UA, 24h file cache, daily-cron
cadence. Check ROBOTS_URL before polling. Network isolated in
fetch_search_html() so tests run fully offline.
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

SOURCE = "lahekinnisvara.ee"
BASE_URL = "https://lahekinnisvara.ee"
# Reference-derived, UNVERIFIED (see module docstring): re-probe before use.
SEARCH_URL = BASE_URL + "/kinnisvara/"
ROBOTS_URL = BASE_URL + "/robots.txt"

SELECTORS = {
    # No verified card markup yet (blocked at robots.txt): parse matches
    # nothing until selectors are confirmed against a live/approved page.
    "card": r'<article[^>]*data-listing-id="(?P<id>\d+)"[^>]*>(?P<body>.*?)</article>',
    "url": r'href="(?P<url>/[^\"]*?-(?P<id2>\d+)(?:\.html|/?))\"',
    "price": r"(?P<price>[\d\s ]+)\s*€",
    "rooms": r"(?P<rooms>\d+)\s*(?:tuba|tubal|rooms?|tk)",
    "area": r"(?P<area>[\d.,]+)\s*m[²2]",
}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Blocked at robots.txt (HTTP 403): refuse the automated fetch."""
    raise RuntimeError(
        "lahekinnisvara.ee gates robots.txt (HTTP 403 bot protection); "
        "no listing probe attempted"
    )


def _parse_card(card_id: str, body: str) -> Optional[dict]:
    um = re.search(SELECTORS["url"], body)
    pm = re.search(SELECTORS["price"], body)
    if not um:
        return None
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
    rm = re.search(SELECTORS["rooms"], text, re.I)
    am = re.search(SELECTORS["area"], text, re.I)
    return normalize_listing(
        {
            "id": "lahe-%s" % card_id,
            "source": SOURCE,
            "source_url": BASE_URL + um.group("url"),
            "address": "",
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": to_int_rooms(rm.group("rooms")) if rm else None,
            "area_m2": to_float_m2(am.group("area")) if am else None,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """Parse search HTML into canonical records. Offline-safe (no network)."""
    out: List[dict] = []
    for m in re.finditer(SELECTORS["card"], html or "", re.S):
        rec = _parse_card(m.group("id"), m.group("body"))
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
        "lahekinnisvara_ee", query, page_limit,
        lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
