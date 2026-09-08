"""kv.ee listings adapter (scaffold v0.1).

Fetches kv.ee search HTML and extracts a minimal listing record per card.
No public API exists, so this parses server-rendered markup; selectors are
kept in one place (SELECTORS) so breakage is a one-spot fix. Respects ToS:
default page_limit=1, ships a desktop UA, callers must rate-limit/cron-daily.
Network is isolated in fetch_search_html() so tests run fully offline.
"""

import re
from typing import List, Optional

import httpx

SOURCE = "kv.ee"
BASE_URL = "https://kv.ee"
SEARCH_URL = BASE_URL + "/kuulutused"

SELECTORS = {
    # data-* hooks observed on kv.ee search cards; re-verify if parse yields 0 rows
    "card": r'<article[^>]*data-object-id="(?P<id>\d+)"[^>]*>(?P<body>.*?)</article>',
    "url": r'href="(?P<url>/[^"]*?-(?P<id2>\d+)\.html)"',
    "price": r'(?P<price>[\d\s\u00a0]+)\s*€',
}

HEADERS = {"User-Agent": "home-finder/0.1 (+research scaffold; daily poll)"}


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Single page of kv.ee search HTML. Keep page_limit small; cron, don't hammer."""
    params = {"page": 1}
    if query:
        params["q"] = query
    resp = httpx.get(SEARCH_URL, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _to_int_eur(raw: str) -> Optional[int]:
    digits = re.sub(r"\D", "", raw or "")
    return int(digits) if digits else None


def parse_search_html(html: str) -> List[dict]:
    """Parse search HTML into [{id, source, source_url, address, price}]. Offline-safe."""
    out: List[dict] = []
    for m in re.finditer(SELECTORS["card"], html, re.S):
        body = m.group("body")
        um = re.search(SELECTORS["url"], body)
        pm = re.search(SELECTORS["price"], body)
        price = _to_int_eur(pm.group("price")) if pm else None
        address_m = re.search(r"<h[23][^>]*>(?P<a>.*?)</h[23]>", body, re.S)
        address = re.sub(r"<[^>]+>", "", address_m.group("a")).strip() if address_m else ""
        out.append(
            {
                "id": "kv-%s" % m.group("id"),
                "source": SOURCE,
                "source_url": BASE_URL + um.group("url") if um else BASE_URL,
                "address": address or ("kv.ee #%s" % m.group("id")),
                "price": price,
            }
        )
    return out


def scrape(query: str = "", page_limit: int = 1) -> List[dict]:
    return parse_search_html(fetch_search_html(query, page_limit))
