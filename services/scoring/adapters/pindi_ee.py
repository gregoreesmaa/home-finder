"""pindi.ee listings adapter — STUB.

GitHub issue: #14 ([portal] Pindi adapter).
Status: skeleton anchor only. Owning builder: implement the fetch/parse
TODOs below (verify search path + selectors against live markup, add
tests/fixtures/pindi_search.html + regression test), keeping the kv.ee
record shape: [{id, source, source_url, address, price}].

Politeness: default page_limit=1, desktop UA, callers must rate-limit
(daily cron). Never commit scraped listing dumps — fixtures only.
"""

from typing import List

import httpx

SOURCE = "pindi.ee"
BASE_URL = "https://www.pindi.ee"
# TODO(#14): confirm the real search path/query params on pindi.ee.
SEARCH_URL = BASE_URL

# TODO(#14): verify selectors against live search markup; keep them here.
SELECTORS = {
    "card": "",
    "url": "",
    "price": "",
}

HEADERS = {"User-Agent": "home-finder/0.1 (+research scaffold; daily poll)"}


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """TODO(#14): confirm query params/pagination, then return one page of search HTML."""
    resp = httpx.get(SEARCH_URL, params={"q": query} if query else None, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def parse_search_html(html: str) -> List[dict]:
    """TODO(#14): extract [{id, source, source_url, address, price}] like adapters.kv_ee."""
    return []


def scrape(query: str = "", page_limit: int = 1) -> List[dict]:
    return parse_search_html(fetch_search_html(query, page_limit))
