"""Facebook Marketplace/groups listings adapter — STUB (paste-in v1).

GitHub issue: #11 ([portal] Facebook Marketplace/groups adapter).
Status: skeleton anchor only. There is no public search API and automated
scraping would violate ToS + require login, so v1 is MANUAL PASTE-IN:
the user pastes a listing URL/price/address and the app normalizes it to
the kv.ee record shape. Do NOT implement automated fetching here.

Owning builder: implement parse_pasted() + validation + regression test
with a pasted-text fixture; keep fetch_search_html() raising.
"""

from typing import List, Optional

SOURCE = "facebook"
BASE_URL = "https://www.facebook.com/marketplace"

# No SELECTORS: nothing is scraped automatically (see module docstring).
SELECTORS = {}


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Always raises: automated Facebook fetching is out of scope (ToS/login)."""
    raise NotImplementedError(
        "TODO(#11): Facebook has no public search API; v1 is manual paste-in, do not automate."
    )


def parse_pasted(text: str, source_url: Optional[str] = None) -> dict:
    """TODO(#11): parse user-pasted listing text into {id, source, source_url, address, price}."""
    raise NotImplementedError("TODO(#11): implement paste-in parsing + validation.")


def parse_search_html(html: str) -> List[dict]:
    """No automated parsing (see module docstring); always empty."""
    return []


def scrape(query: str = "", page_limit: int = 1) -> List[dict]:
    return parse_search_html(fetch_search_html(query, page_limit))
