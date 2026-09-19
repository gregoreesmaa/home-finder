"""P4 TomTom geocode repair for coord-less listings (issue #675).

Buyer question: listings that arrive WITHOUT coordinates drop out of
area scoring - Structured Geocode gives them coordinates so they can
join instead of dropping out. Trickle volume (only coord-less
listings, cached by address hash - never re-geocode a known address).

ToS verdict (step zero, #669): SHORT-TERM CACHE ONLY (TomTom Portal
Terms 11.4 + 11.6 - pasted in docs/p4_tomtom_matrix.md section 0,
repeated in docs/p4_tomtom_geocode.md section 0). NOTE: geocodes are
explicitly named as "Results" in the agreement ("geocodes and reverse
geocodes"), so the address-hash cache is TTL-BOUNDED (30 d), not
permanent: zero re-calls within TTL, re-verify after. NO committed
sidecars, NO stored tables: the cache lives in a git-ignored operator
cache dir, max-age honored when present.

Quota math: trickle - at most GEOCODE_MAX_CALLS = 100 keyed calls per
30 d window (only coord-less listings miss the cache); 429 = stop.

Unresolvable addresses are LOGGED, the listing is KEPT (NULL coords,
surfaced in QA) - never dropped silently. Pinned by test.

Ingestion (stdlib only, mirrors dims_tomtom_parking.py): fetch_geocode
does the polite keyed GET (key from TOMTOM_API_KEY env only, quota
cap, TTL, single attempt, 429 = stop; transport errors and short
bodies are never cached; max-age honored when present). Scorers and
unit tests never touch the network.
"""

import hashlib
import json
import math
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

#: Structured Geocode endpoint (key-gated; never called without
#: TOMTOM_API_KEY).
GEOCODE_URL = "https://api.tomtom.com/search/2/structuredGeocode/.json"

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
TOMTOM_KEY_ENV = "TOMTOM_API_KEY"

#: Trickle budget: only coord-less listings cost calls.
GEOCODE_MAX_CALLS = 100

#: Address-hash cache entries live 30 d (ToS 11.4: geocodes are named
#: Results, so the cache is TTL-bounded, not permanent).
GEOCODE_TTL_S = 30 * 24 * 3600

#: Identifying user agent for the polite pull.
GEOCODE_UA = "home-finder geocode-repair (keyed, quota-capped)"

#: Minimum plausible geocode body.
GEOCODE_MIN_BYTES = 64

#: Default municipality when the address names none (operator
#: overrides per listing via the address text itself).
DEFAULT_MUNICIPALITY = "Tallinn"


def normalize_address(address: str) -> str:
    """Canonical address form for hashing. Pure.

    Lowercases, strips punctuation, collapses whitespace - "Tartu mnt
    25, Tallinn" and "tartu mnt 25 tallinn" hash identically, so a
    known address is never re-geocoded under a spelling variant.
    """
    if not isinstance(address, str):
        return ""
    s = address.lower()
    s = re.sub(r"[^a-zõäöü0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def address_hash(address: str) -> str:
    """sha256 over the normalized address (cache key). Pure."""
    return hashlib.sha256(normalize_address(address).encode("utf-8")
                          ).hexdigest()


def split_street(address: str) -> Tuple[str, str]:
    """Light street split for structuredGeocode. Pure.

    Returns (streetName, municipality): the municipality is the text
    after the last comma when present (else DEFAULT_MUNICIPALITY);
    the street is the remainder. Best-effort - a wrong split costs
    one trickle call and lands in the unresolvable log, never a guess.
    """
    text = address if isinstance(address, str) else ""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) >= 2 and parts[-1]:
        return ", ".join(parts[:-1]).strip() or text.strip(), parts[-1]
    return text.strip(), DEFAULT_MUNICIPALITY


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_geocode_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > GEOCODE_TTL_S:
            return 0
        return max(0, int(rec.get("used", 0)))
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def _quota_spend(cache_dir: str) -> None:
    """Record one spent keyed call (best-effort; quota is a cap)."""
    try:
        os.makedirs(cache_dir, exist_ok=True)
        start = time.time()
        used = 0
        try:
            with open(_quota_path(cache_dir), encoding="utf-8") as fh:
                rec = json.load(fh)
            if time.time() - float(rec.get("window_start", 0)) <= GEOCODE_TTL_S:
                start = float(rec["window_start"])
                used = max(0, int(rec.get("used", 0)))
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            pass
        with open(_quota_path(cache_dir), "w", encoding="utf-8") as fh:
            json.dump({"window_start": start, "used": used + 1}, fh)
    except OSError:
        pass


def _cache_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_geocode_cache.json")


def _cache_load(cache_dir: str) -> dict:
    try:
        with open(_cache_path(cache_dir), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def _cache_save(cache_dir: str, cache: dict) -> None:
    try:
        os.makedirs(cache_dir, exist_ok=True)
        with open(_cache_path(cache_dir), "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
    except OSError:
        pass


def _max_age_s(resp) -> Optional[int]:
    """Cache-control max-age of a response, if present. Pure."""
    try:
        cc = resp.headers.get("Cache-Control", "")
    except (AttributeError, OSError):
        return None
    for part in str(cc).split(","):
        part = part.strip().lower()
        if part.startswith("max-age="):
            try:
                return max(0, int(part.split("=", 1)[1]))
            except ValueError:
                return None
    return None


def fetch_geocode(address: str, cache_dir: str,
                  api_key: Optional[str] = None,
                  ttl_s: int = GEOCODE_TTL_S
                  ) -> Optional[Tuple[float, float]]:
    """Polite keyed Structured Geocode with address-hash cache.

    Known addresses (hash hit within TTL) return with ZERO requests -
    pinned by test. Otherwise one GET; the result is cached only on
    HTTP 200 with a usable position, else None (transport errors never
    cached, 429 is a stop signal, no retries; max-age honored - ToS
    11.4). Unresolvable addresses return None (caller logs + keeps).
    Scorers never call this.
    """
    key = api_key or os.environ.get(TOMTOM_KEY_ENV)
    if not key or not normalize_address(address):
        return None
    os.makedirs(cache_dir, exist_ok=True)
    h = address_hash(address)
    cache = _cache_load(cache_dir)
    hit = cache.get(h) if isinstance(cache, dict) else None
    if isinstance(hit, dict):
        try:
            if time.time() - float(hit.get("fetched_at", 0)) < ttl_s:
                lat, lon = float(hit["lat"]), float(hit["lon"])
                if math.isfinite(lat) and math.isfinite(lon):
                    return lat, lon
        except (TypeError, ValueError, KeyError):
            pass
    if _quota_used(cache_dir) >= GEOCODE_MAX_CALLS:
        return None
    street, municipality = split_street(address)
    qs = urllib.parse.urlencode({
        "key": key, "countryCode": "EE", "streetName": street,
        "municipality": municipality, "limit": 1,
    })
    try:
        req = urllib.request.Request(GEOCODE_URL + "?" + qs, method="GET",
                                     headers={"User-Agent": GEOCODE_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
            max_age = _max_age_s(resp)
        if len(body) < GEOCODE_MIN_BYTES:
            return None
        data = json.loads(body.decode("utf-8"))
        results = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(results, list) or not results:
            return None
        pos = results[0].get("position", {}) \
            if isinstance(results[0], dict) else {}
        lat, lon = float(pos["lat"]), float(pos["lon"])
        if not (math.isfinite(lat) and math.isfinite(lon)):
            return None
        fetched_at = time.time()
        if max_age is not None and max_age < ttl_s:
            # ToS 11.4: never keep Results longer than max-age -
            # backdate fetched_at so the TTL expires on time.
            fetched_at -= ttl_s - max_age
        cache[h] = {"lat": lat, "lon": lon, "fetched_at": fetched_at}
        _cache_save(cache_dir, cache)
        _quota_spend(cache_dir)
        return lat, lon
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline repair over listing dicts (pure except via fetch_geocode).
# ---------------------------------------------------------------------------

def has_coords(listing: dict) -> bool:
    """A listing has usable coordinates. Pure."""
    try:
        lat = float(listing["lat"])
        lon = float(listing["lon"])
    except (TypeError, ValueError, KeyError, AttributeError):
        return False
    if isinstance(listing.get("lat"), bool) \
            or isinstance(listing.get("lon"), bool):
        return False
    return math.isfinite(lat) and math.isfinite(lon)


def repair_listings(listings: List[dict], cache_dir: str,
                    api_key: Optional[str] = None) -> dict:
    """Geocode-repair coord-less listings. Returns report. Pure I/O.

    Returns ``{"listings": [...], "counts": {coord_less_before,
    repaired, coord_less_after, unresolvable}}``. Repaired listings
    gain ``lat``/``lon`` (+ ``geocoded_by: "tomtom"``); unresolvable
    ones are KEPT with NULL coords and listed under
    ``"unresolvable"`` (surfaced in QA, never dropped silently).
    """
    out = []
    repaired = 0
    unresolvable = []
    before = 0
    for listing in listings:
        if not isinstance(listing, dict):
            continue
        row = dict(listing)
        if has_coords(row):
            out.append(row)
            continue
        before += 1
        addr = row.get("address", "")
        hit = fetch_geocode(addr if isinstance(addr, str) else "",
                            cache_dir, api_key=api_key)
        if hit is not None:
            row["lat"], row["lon"] = hit
            row["geocoded_by"] = "tomtom"
            repaired += 1
        else:
            row["lat"], row["lon"] = None, None
            unresolvable.append(row.get("id", addr))
        out.append(row)
    after = sum(1 for r in out if not has_coords(r))
    return {"listings": out,
            "unresolvable": unresolvable,
            "counts": {"coord_less_before": before, "repaired": repaired,
                       "coord_less_after": after,
                       "unresolvable": len(unresolvable)}}
