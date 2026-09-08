"""Facebook Marketplace/groups listings adapter — MANUAL PASTE-IN (v1).

GitHub issue: #11 ([portal] Facebook Marketplace/groups adapter).

There is no public search API and automated scraping would violate the
Facebook Terms of Service and require a logged-in session, so by design
there is NO automated fetching here: fetch_search_html() always raises
NotImplementedError and parse_search_html() always returns []. Instead the
user pastes a listing's URL + visible text and parse_pasted() normalizes it
to the canonical kv.ee record shape
{id, source, source_url, address, price, rooms, area_m2}.

parse_pasted() is pure and offline-safe (no network). Validation: a pasted
listing MUST include a non-empty address/title line and a price in euros;
otherwise ValueError is raised so bad pastes fail loudly at import time.
"""

import hashlib
import re
from typing import List, Optional

from adapters import (
    normalize_listing,
    polite_headers,
    to_float_m2,
    to_int_eur,
    to_int_rooms,
)

SOURCE = "facebook"
BASE_URL = "https://www.facebook.com/marketplace"
# Documented but never fetched (see module docstring): kept so the shared
# adapter contract (adapter_contract_check) stays green.
SEARCH_URL = BASE_URL
ROBOTS_URL = "https://www.facebook.com/robots.txt"

# No scraper SELECTORS: nothing is fetched automatically (see docstring).
SELECTORS = {}

HEADERS = polite_headers()


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """Always raises: automated Facebook fetching is out of scope (ToS/login)."""
    raise NotImplementedError(
        "Facebook has no public search API; v1 is manual paste-in, do not automate."
    )


def parse_pasted(text: str, source_url: Optional[str] = None) -> dict:
    """Parse user-pasted listing text into a canonical record.

    Expected paste: the listing title/address line plus its price, e.g.
    "Kotzebue 12, Tallinn\\n285 000 €" or with a marketplace URL passed
    separately via source_url. Raises ValueError when the address/title or
    the price cannot be found.
    """
    raw = text or ""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("pasted Facebook listing is empty")
    text_flat = re.sub(r"\s+", " ", raw)

    pm = re.search(r"([\d\s\u00a0]+)\s*€", text_flat)
    if not pm:
        raise ValueError("pasted Facebook listing has no price in euros: %r" % raw[:80])
    price = to_int_eur(pm.group(1))
    if price is None:
        raise ValueError("pasted Facebook listing has no parseable price: %r" % raw[:80])

    # Address/title = first non-price line (the headline the user copied).
    address = ""
    for ln in lines:
        candidate = re.sub(r"[\d\s\u00a0]+\s*€", "", ln).strip(" -–—|•\t")
        if candidate and not re.fullmatch(r"[\d\s\u00a0.,€-]+", ln):
            address = candidate
            break
    if not address:
        raise ValueError("pasted Facebook listing has no address/title line: %r" % raw[:80])

    rm = re.search(r"(\d+)\s*(?:tuba|tubal|rooms?|tk|bedrooms?)", text_flat, re.I)
    am = re.search(r"([\d.,]+)\s*m[²2]", text_flat, re.I)

    url = source_url or BASE_URL
    digest = hashlib.sha256(("%s|%s" % (address.lower(), price)).encode()).hexdigest()[:12]
    return normalize_listing(
        {
            "id": "facebook-%s" % digest,
            "source": SOURCE,
            "source_url": url,
            "address": address,
            "price": price,
            "rooms": to_int_rooms(rm.group(1)) if rm else None,
            "area_m2": to_float_m2(am.group(1)) if am else None,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """No automated parsing (see module docstring); always empty."""
    return []


def scrape(query: str = "", page_limit: int = 1) -> List[dict]:
    return parse_search_html(fetch_search_html(query, page_limit))
