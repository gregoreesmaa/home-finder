"""remax.ee listings adapter (RE/MAX Estonia agency portal).

Same interface as adapters/kv_ee.py: fetch_search_html / parse_search_html /
scrape, returning canonical records {id, source, source_url, address, price,
rooms, area_m2}. Selectors live in SELECTORS for one-spot fixes.

Live-markup note (2026-09-08, verified with 1 polite request each):
the human search hub is https://www.remax.ee/muugiobjektid/ (title
"Soovin osta"; the old /kinnisvara SEARCH_URL never existed there), but its
static HTML contains ZERO server-rendered cards — listings load client-side
as JSON from DATA_URL below (see the page's getListings/outputListing JS;
55 hits on 2026-09-08) and render into `a.apartment-list-items` cards
pointing at /objekt/<town>/<district>/<type>/<identifier>/.
parse_search_html therefore accepts BOTH payloads:

  * JSON array text from DATA_URL (the live poll path) — fields identifier,
    town, district, street_address, listingType/localized, price/rent,
    living_area/lot_area_in_sqm, rooms;
  * rendered `a.apartment-list-items` card HTML (post-JS DOM), with the
    €-bearing .item-price cell as price and the m²-bearing one as area.

Parsing the live JSON first page yields 21/21 objects (LIVE ROWS=21).
Quirks mirrored from the site's own JS: living_area uses comma decimals
("72,8") and space thousands ("1 200"); `rooms` is usually ad copy or empty,
so canonical rooms is set ONLY for pure-numeric values (else None rather
than a bogus number scraped from prose); card URLs fold diacritics exactly
like outputListing (first space dropped, first comma -> dash, lowercase).

Politeness / ToS: default page_limit=1, polite UA, 24h file cache, daily-cron
cadence. Check ROBOTS_URL before polling (200, empty Disallow on 2026-09-08).
Network isolated in fetch_search_html() so tests run fully offline against
tests/fixtures/.
"""

import json
import re
from typing import List, Optional

from adapters import (
    cached_fetch,
    fetch_html,
    normalize_listing,
    polite_headers,
    to_float_m2,
    to_int_eur,
)

SOURCE = "remax.ee"
BASE_URL = "https://www.remax.ee"
# Human search hub (server-rendered shell; cards arrive via DATA_URL JSON).
SEARCH_URL = BASE_URL + "/muugiobjektid/"
ROBOTS_URL = BASE_URL + "/robots.txt"
# Polite single-page data endpoint behind the hub's own search frontend.
DATA_URL = BASE_URL + "/wp-content/themes/blocksy-child/property_search_LINEAR.php"
DATA_PARAMS = {"property-type": "asunnot", "sales-method": "myynti"}

SELECTORS = {
    # Rendered-card hook from the hub's outputListing JS template.
    "card": r'<a class="apartment-list-items" href="(?P<url>/objekt/[^"]+/)">(?P<body>.*?)</a>',
    "url": r"/objekt/(?:[^/]+/){0,3}(?P<id>\d+)/$",
    "price": r'<div class="item-price">(?P<price>[^<]*€[^<]*)</div>',
    "rooms": r'<div class="item-text">(?P<rooms>[^<]*)</div>',
    "area": r'<div class="item-price">(?P<area>[^<]*m²[^<]*)</div>',
    # JSON payload field names (DATA_URL path).
    "json_id": "identifier",
    "json_price": "price",
    "json_rent": "rent",
    "json_area": "living_area",
    "json_lot_area": "lot_area_in_sqm",
}

HEADERS = polite_headers()

# Diacritic folding copied from the hub's outputListing JS (exact list).
_FOLD = str.maketrans(
    {
        "á": "a", "à": "a", "â": "a", "ä": "a", "å": "a",
        "ó": "o", "ò": "o", "ô": "o", "ö": "o", "õ": "o",
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "ú": "u", "ù": "u", "û": "u", "ü": "u",
        "ć": "c", "š": "s", "ž": "z",
    }
)


def _fold(s: str) -> str:
    return (s or "").translate(_FOLD)


def _listing_url(obj: dict) -> str:
    """Rebuild the /objekt/... card URL exactly like the hub's JS does."""
    url = (obj.get("town") or "").lower() + "/"
    if obj.get("district"):
        url += obj["district"].replace(" ", "", 1).replace(",", "-", 1).lower() + "/"
    listing_type = obj.get("listingTypeLocalized") or obj.get("listingType") or ""
    if listing_type:
        url += listing_type.lower() + "/"
    url += (obj.get("identifier") or "") + "/"
    return BASE_URL + "/objekt/" + _fold(url)


def _location(obj: dict) -> tuple:
    """(location, short_location) exactly like the hub's JS builds them."""
    town = obj.get("town") or ""
    location, short = town, town
    if obj.get("district"):
        location = obj["district"] + ", " + location
        short = obj["district"].split(",")[0].strip() + ", " + short
    return location, short


def _num_or_none(raw) -> Optional[int]:
    """Canonical rooms: pure-numeric strings only (rooms is often ad copy)."""
    if raw is None:
        return None
    s = str(raw).strip()
    return int(s) if re.fullmatch(r"\d+", s) else None


def _area_or_none(raw) -> Optional[float]:
    """Space-thousands ("1 200") and comma-decimal ("72,8") aware float."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(re.sub(r"\s+", "", str(raw)).replace("\u00a0", "").replace(",", "."))
    except ValueError:
        return to_float_m2(str(raw))


def _parse_json_obj(obj: dict) -> Optional[dict]:
    identifier = str(obj.get(SELECTORS["json_id"]) or "").strip()
    if not identifier:
        return None
    price_raw = obj.get(SELECTORS["json_price"]) or ""
    rent_raw = obj.get(SELECTORS["json_rent"]) or ""
    price = to_int_eur(str(price_raw)) if str(price_raw).strip() else None
    if price is None and str(rent_raw).strip():
        price = to_int_eur(str(rent_raw))  # rental-only card: monthly rent figure
    area = _area_or_none(obj.get(SELECTORS["json_area"]))
    if area is None:
        area = _area_or_none(obj.get(SELECTORS["json_lot_area"]))
    _location_full, short = _location(obj)
    street = (obj.get("street_address") or "").strip()
    address = ("%s, %s" % (street, short)).strip(", ") if street else short
    return normalize_listing(
        {
            "id": "remax-%s" % identifier,
            "source": SOURCE,
            "source_url": _listing_url(obj),
            "address": address or ("remax.ee #%s" % identifier),
            "price": price,
            "rooms": _num_or_none(obj.get("rooms")),
            "area_m2": area,
        }
    )


def _parse_card(url: str, body: str) -> Optional[dict]:
    um = re.search(SELECTORS["url"], url)
    if not um:
        return None
    card_id = um.group("id")
    pm = re.search(SELECTORS["price"], body)
    am = re.search(SELECTORS["area"], body)
    rm = re.search(SELECTORS["rooms"], body, re.S)
    title_m = re.search(r'<div class="item-title">(?P<t>.*?)</div>', body, re.S)
    subtitle_m = re.search(r'<div class="item-title-text">(?P<t>.*?)</div>', body, re.S)
    title = re.sub(r"<[^>]+>", "", title_m.group("t")).strip() if title_m else ""
    subtitle = (
        re.sub(r"<[^>]+>", "", subtitle_m.group("t")).strip() if subtitle_m else ""
    )
    address = ("%s, %s" % (title, subtitle)).strip(", ") if title else subtitle
    full_url = url if url.startswith("http") else BASE_URL + url
    return normalize_listing(
        {
            "id": "remax-%s" % card_id,
            "source": SOURCE,
            "source_url": full_url,
            "address": address or ("remax.ee #%s" % card_id),
            "price": to_int_eur(pm.group("price")) if pm else None,
            "rooms": _num_or_none(rm.group("rooms")) if rm else None,
            "area_m2": _area_or_none(am.group("area")) if am else None,
        }
    )


def parse_search_html(html: str) -> List[dict]:
    """Parse DATA_URL JSON text or rendered-card HTML. Offline-safe."""
    out: List[dict] = []
    text = (html or "").strip()
    if text.startswith("["):
        try:
            payload = json.loads(text)
        except ValueError:
            return []
        if isinstance(payload, list):
            for obj in payload:
                if isinstance(obj, dict):
                    row = _parse_json_obj(obj)
                    if row is not None:
                        out.append(row)
        return out
    for m in re.finditer(SELECTORS["card"], html, re.S):
        row = _parse_card(m.group("url"), m.group("body"))
        if row is not None:
            out.append(row)
    return out


def fetch_search_html(query: str = "", page_limit: int = 1, timeout: float = 20.0) -> str:
    """First page of remax.ee sale listings via the hub's data endpoint."""
    headers = dict(HEADERS)
    headers["Referer"] = SEARCH_URL
    return fetch_html(DATA_URL, params=dict(DATA_PARAMS), headers=headers, timeout=timeout)


def scrape(
    query: str = "",
    page_limit: int = 1,
    cache_dir: Optional[str] = None,
    cache_ttl_s: float = 24 * 3600,
) -> List[dict]:
    """Fetch (via 24h file cache when cache_dir is set) + parse + normalize."""
    html = cached_fetch(
        "remax_ee", query, page_limit, lambda: fetch_search_html(query, page_limit),
        cache_dir, cache_ttl_s,
    )
    return parse_search_html(html)
