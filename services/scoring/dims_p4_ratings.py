"""P4 ratings + price tiers dims (issue #556): probe-first, no scraping.

Buyer question: not just "is there food nearby" (owned: OSM amenity
counts, #549 toitlustus) but "is it any good, and what does it
cost" - rating + price tier for restaurants, cafes, shops near the
listing.

HONESTY FRAMING (read before estimating): there is NO open keyless
ratings/costs feed. What exists and its status:
* OSM (cuisine/shop/price tags): counts only - no ratings,
  virtually no prices. Owned as proximity legs; counts != quality.
* Review platforms / delivery apps (review scraping, Tripadvisor,
  Wolt/Bolt internals): scraping or app-internal - REFUSED class
  (AGENTS.md sections 5/7), not re-litigated here. No scraped stars
  from any surface, ever. No review-text ingestion (scores/tiers
  only - never quote reviews).
* Google Places API (New) ``rating`` / ``userRatingCount`` /
  ``priceLevel``: the only structured source - but KEY-GATED
  (billing account). Probe 2026-09-16 (docs pages only, no
  scraping): the usage-and-billing page confirms the FieldMask tier
  model - rating/price fields are Atmosphere-tier data billed on top
  of the base SKU (Nearby Search / Text Search / Place Details, each
  with Essentials/Pro/Enterprise tiers); exact per-SKU dollars live
  on the pricing page and are NOT pinned here (re-check before
  keying). ToS retention clause likewise re-checked live before the
  first keyed pull - the harvester below defaults to a 30 d TTL
  (re-pull, don't hoard) and a quota cap. Precedent for
  user-supplied keys: Mapillary/OpenCellID tokens from env at pull
  time, NEVER committed (public repo, no secrets).
* Huvipunktid toitlustus (#549): register locations without ratings
  - the join keys if a ratings leg ever lands.

OUTCOME: documented gated verdict + the exact join shape below,
fixtures only. The key model is workable (env key, TTL, quotas in
code, transport/429 never cached), so the harvester ships behind
it; production stays NULL until a key is supplied.

JOIN PATH (place <-> huvipunkt/OSM linkage + mismatch handling):
Nearby Search results link to register/OSM records by distance
(<= 50 m) AND name agreement (normalised containment either way);
a place matching nothing, or two places claiming one record, is
left UNMATCHED (ignored, never force-joined - a wrong star is
worse than none). Mismatches are therefore silent NULLs on the
unmatched side, never guesses.

RULES (pinned by tests): rating floor ``userRatingCount >= 10``
(load-bearing - fake ratings are worse than none); price_level
bands 0-4 (Free->Inexpensive->Moderate->Expensive->Very Expensive);
no-key NULL path: with no keyed pull (pois None) every leg returns
None with the buyer check, never a guess; unrated != bad (a place
below the floor is ignored, never scored 0).

Ingestion (stdlib only, offline-first, mirrors dims_p4_trans.py):
fetch_places does the polite keyed pull (key from env
GOOGLE_PLACES_API_KEY only, monthly quota cap
PLACES_MONTHLY_MAX_CALLS, 30 d TTL, single attempt, 429 = stop;
transport errors and short bodies are never cached). Scorers and
tests never touch the network.

Integration (deliberately NOT done here): WEIGHTS splice is one
joint change across batches. No shared files touched: 3 new files
only.
"""

import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Places API (New) Nearby Search endpoint (key-gated; never called
#: without GOOGLE_PLACES_API_KEY).
PLACES_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

#: Field mask: location + the Atmosphere-tier rating/price fields.
PLACES_FIELD_MASK = (
    "places.id,places.displayName,places.location,"
    "places.rating,places.userRatingCount,places.priceLevel"
)

#: Env var carrying the user-supplied key (never committed).
PLACES_KEY_ENV = "GOOGLE_PLACES_API_KEY"

#: Harvest budget: at most this many keyed calls per 30 d window per
#: cache dir (quota enforced in code; sized for small monthly use -
#: re-check the live pricing page before keying).
PLACES_MONTHLY_MAX_CALLS = 500

#: Re-pull, don't hoard: cached place data refreshes monthly.
PLACES_TTL_S = 30 * 24 * 3600

#: Identifying user agent for the polite pull.
PLACES_UA = "home-finder ratings harvest (keyed, quota-capped, no scrape)"

#: Minimum plausible Nearby Search body.
PLACES_MIN_BYTES = 64

#: Rating floor: review-count floor is load-bearing (fake ratings
#: are worse than none).
RATING_MIN_N = 10

#: Delight threshold: rating >= 4.3 with enough reviews nearby.
DINING_DELIGHT_RATING = 4.3
DINING_DELIGHT_SCORE = 70

#: Price-level bands (0..4) -> cost-character score (high = cheaper).
PRICE_BANDS = {0: 75, 1: 65, 2: 55, 3: 40, 4: 30}

#: Join window: place <-> register record linkage distance.
JOIN_WINDOW_M = 50.0

#: Scorer window: rated places counted near the listing.
RATED_WINDOW_M = 500.0

#: No-key NULL reason (buyer check, never a guess).
NO_KEY_NULL = ("Hinnangute info puudub (EI OLE võtmeta hinnanguliidestust: "
               "Google Places vajab arveldusvõtit - lisa võti või loe "
               "lähedust OSM-toitlustusloendist, hinnangut ära eelda)")


def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "places_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current 30 d window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > PLACES_TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= PLACES_TTL_S:
                start = float(rec["window_start"])
                used = max(0, int(rec.get("used", 0)))
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            pass
        with open(_quota_path(cache_dir), "w", encoding="utf-8") as fh:
            json.dump({"window_start": start, "used": used + 1}, fh)
    except OSError:
        pass


def fetch_places(lat: float, lon: float, radius_m: int, cache_dir: str,
                 filename: str, api_key: Optional[str] = None,
                 ttl_s: int = PLACES_TTL_S) -> Optional[str]:
    """Polite keyed Nearby Search pull. Returns path or None.

    Key from the GOOGLE_PLACES_API_KEY env (or the explicit arg -
    tests only, never a committed secret). No key, spent quota, or
    fresh cache: NO request. Otherwise one POST with the rating/price
    field mask; the body is stored only on HTTP 200 over
    PLACES_MIN_BYTES, else None (transport errors never cached, 429
    is a stop signal, no retries). Scorers never call this.
    """
    key = api_key or os.environ.get(PLACES_KEY_ENV)
    if not key:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < ttl_s):
            return dest
    except OSError:
        return None
    if _quota_used(cache_dir) >= PLACES_MONTHLY_MAX_CALLS:
        return None
    payload = json.dumps({
        "locationRestriction": {
            "circle": {"center": {"latitude": lat, "longitude": lon},
                       "radius": float(radius_m)}},
        "rankPreference": "DISTANCE",
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            PLACES_NEARBY_URL, data=payload, method="POST",
            headers={"User-Agent": PLACES_UA,
                     "Content-Type": "application/json",
                     "X-Goog-Api-Key": key,
                     "X-Goog-FieldMask": PLACES_FIELD_MASK})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < PLACES_MIN_BYTES:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        _quota_spend(cache_dir)
        return dest
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached Nearby Search JSON (pure).
# ---------------------------------------------------------------------------

def parse_places_response(path: str) -> List[dict]:
    """Parse the cached Nearby Search body. Offline.

    Returns per-place dicts: ``place_id``, ``name``, ``rating``
    (float|None), ``n`` (userRatingCount int, 0 when absent),
    ``price_level`` (0..4 int|None), ``lat``/``lon``. Garbage rows
    keep honest Nones; nothing is guessed.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    places = data.get("places")
    if not isinstance(places, list):
        return []
    out = []
    for pl in places:
        if not isinstance(pl, dict):
            continue
        loc = pl.get("location") if isinstance(pl.get("location"), dict) else {}
        try:
            lat = float(loc.get("latitude"))
            lon = float(loc.get("longitude"))
        except (TypeError, ValueError):
            lat, lon = None, None
        rating = pl.get("rating")
        try:
            rating = float(rating)
            if not (math.isfinite(rating) and 0.0 <= rating <= 5.0):
                rating = None
        except (TypeError, ValueError):
            rating = None
        n = pl.get("userRatingCount", 0)
        if isinstance(n, bool):
            n = 0
        try:
            n = int(n)
            if n < 0:
                n = 0
        except (TypeError, ValueError):
            n = 0
        price = pl.get("priceLevel")
        price_map = {"PRICE_LEVEL_FREE": 0, "PRICE_LEVEL_INEXPENSIVE": 1,
                     "PRICE_LEVEL_MODERATE": 2, "PRICE_LEVEL_EXPENSIVE": 3,
                     "PRICE_LEVEL_VERY_EXPENSIVE": 4}
        if isinstance(price, int) and not isinstance(price, bool) \
                and 0 <= price <= 4:
            price_level: Optional[int] = price
        elif isinstance(price, str):
            price_level = price_map.get(price)
        else:
            price_level = None
        name = pl.get("displayName")
        if isinstance(name, dict):
            name = name.get("text")
        out.append({"place_id": pl.get("id"), "name": name,
                    "rating": rating, "n": n, "price_level": price_level,
                    "lat": lat, "lon": lon})
    return out


def _norm_name(name) -> str:
    if not isinstance(name, str):
        return ""
    return "".join(ch for ch in name.lower() if ch.isalnum())


def link_places_to_records(places: List[dict],
                           records: List[dict]) -> Dict[str, Optional[dict]]:
    """Link keyed places to register/OSM records. Pure.

    A place links to a record within JOIN_WINDOW_M whose normalised
    name contains (or is contained in) the record's name. Unmatched
    places and double-claimed records stay unmatched (returned None)
    - a wrong star is worse than none. Returns
    {place_id: record|None}.
    """
    links: Dict[str, Optional[dict]] = {}
    claimed = set()
    for pl in places:
        pid = pl.get("place_id")
        if not isinstance(pid, str) or not pid:
            continue
        pname = _norm_name(pl.get("name"))
        plat, plon = pl.get("lat"), pl.get("lon")
        cands = []
        if pname and isinstance(plat, float) and isinstance(plon, float):
            for ri, rec in enumerate(records):
                if not isinstance(rec, dict) or ri in claimed:
                    continue
                rname = _norm_name(rec.get("name"))
                if not rname or (pname not in rname and rname not in pname):
                    continue
                try:
                    rlat = float(rec["lat"])
                    rlon = float(rec["lon"])
                except (TypeError, ValueError, KeyError):
                    continue
                if isinstance(rec.get("lat"), bool) \
                        or isinstance(rec.get("lon"), bool):
                    continue
                if not (math.isfinite(rlat) and math.isfinite(rlon)):
                    continue
                if _haversine_m((plat, plon), rlat, rlon) <= JOIN_WINDOW_M:
                    cands.append((ri, rec))
        if len(cands) == 1:
            links[pid] = cands[0][1]
            claimed.add(cands[0][0])
        else:
            links[pid] = None  # unmatched or ambiguous: never force-joined
    return links


def rating_pois_from_places(places: List[dict]) -> List[dict]:
    """Keyed places -> scorer POIs. Pure.

    Only places AT or ABOVE the review-count floor become POIs;
    below-floor places are ignored (unrated != bad, never scored 0).
    Malformed coordinates are skipped, never faked.
    """
    pois = []
    for pl in places:
        if not isinstance(pl, dict):
            continue
        n = pl.get("n", 0)
        if not isinstance(n, int) or isinstance(n, bool) or n < RATING_MIN_N:
            continue
        rating = pl.get("rating")
        if not isinstance(rating, (int, float)) or isinstance(rating, bool):
            continue
        rating = float(rating)
        if not (math.isfinite(rating) and 0.0 <= rating <= 5.0):
            continue
        try:
            lat = float(pl["lat"])
            lon = float(pl["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(pl.get("lat"), bool) or isinstance(pl.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        price = pl.get("price_level")
        if isinstance(price, bool) or not isinstance(price, int) \
                or not 0 <= price <= 4:
            price = None
        pois.append({"kind": "place_rating_p4", "lat": lat, "lon": lon,
                     "rating": rating, "n": n, "price_level": price,
                     "place_id": pl.get("place_id")})
    return pois


# ---------------------------------------------------------------------------
# Scorer dims (never a raster - ratings are per-place facts).
# ---------------------------------------------------------------------------

def _rated_nearby(origin: Tuple[float, float],
                  pois: List[dict]) -> List[Tuple[float, dict]]:
    out = []
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") != "place_rating_p4":
            continue
        # Review-count floor enforced at scoring time too (load-bearing:
        # POIs may arrive from other paths than rating_pois_from_places).
        n = p.get("n", 0)
        if not isinstance(n, int) or isinstance(n, bool) or n < RATING_MIN_N:
            continue
        try:
            lat = float(p["lat"])
            lon = float(p["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(p.get("lat"), bool) or isinstance(p.get("lon"), bool):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        d = _haversine_m(origin, lat, lon)
        if d <= RATED_WINDOW_M:
            out.append((d, p))
    return out


def dim_dining_delight(origin: Optional[Tuple[float, float]],
                       pois: Optional[List[dict]]) -> Score:
    """Dining delight: rating >= 4.3 with enough reviews nearby.

    Capped taste-match (70): a well-rated place within 500 m delights,
    but taste stays buyer-side (no "best restaurants" editorial).
    """
    if not origin or pois is None:
        return None, NO_KEY_NULL
    hits = [(d, p) for d, p in _rated_nearby(origin, pois)
            if isinstance(p.get("rating"), (int, float))
            and not isinstance(p.get("rating"), bool)
            and math.isfinite(float(p["rating"]))
            and 0.0 <= float(p["rating"]) <= 5.0
            and float(p["rating"]) >= DINING_DELIGHT_RATING]
    if not hits:
        return None, ("Läheduses pole piisavalt hinnatud heade kohtade "
                      "kirjet - hinnangut pole (EI OLE võtmega "
                      "hinnanguliidestust või ükski koht ei ületa "
                      "%.1f/lei %d arvustusega; hinnanguta pole halb)"
                      % (DINING_DELIGHT_RATING, RATING_MIN_N))
    nearest_m = min(d for d, _ in hits)
    best = max(float(p["rating"]) for _, p in hits)
    return DINING_DELIGHT_SCORE, (
        "Söögikoha-maitse hinnang: %d hästihinnatud kohta 500 m "
        "puhvris (parim %.1f/5, lähim %s) -> skoor %d (maitse, mitte "
        "edetabel)" % (len(hits), best, _fmt_m(nearest_m),
                       DINING_DELIGHT_SCORE))


def dim_price_character(origin: Optional[Tuple[float, float]],
                        pois: Optional[List[dict]]) -> Score:
    """Price-tier character: price_level mix near the listing.

    Cost character, not quality: the cheapest tiered place within
    500 m sets the tone (high = cheaper surroundings).
    """
    if not origin or pois is None:
        return None, NO_KEY_NULL
    tiered = [(d, p) for d, p in _rated_nearby(origin, pois)
              if isinstance(p.get("price_level"), int)
              and not isinstance(p.get("price_level"), bool)
              and 0 <= p["price_level"] <= 4]
    if not tiered:
        return None, ("Läheduses pole hinnatasemega kohtade kirjet - "
                      "hinnangut pole (EI OLE võtmega hinnatasemete "
                      "liidestust; hinnatase pole ostukorv)")
    nearest_m = min(d for d, _ in tiered)
    cheapest = min(p["price_level"] for _, p in tiered)
    s = PRICE_BANDS[cheapest]
    return s, ("Hinnataseme hinnang: odavaim tier %d/4 läheduses %s "
               "(%d tier-kirjet 500 m puhvris) -> skoor %d "
               "(kulukarakter, mitte kvaliteet; hinnatase pole ostukorv)"
               % (cheapest, _fmt_m(nearest_m), len(tiered), s))


#: Registry for the central weight-rebalance follow-up: (dim key, param id).
P4_RATINGS_DIMS = (
    ("dining_delight", "P4-ratings", dim_dining_delight),
    ("price_character", "P4-ratings", dim_price_character),
)


def score_p4_ratings(origin: Optional[Tuple[float, float]],
                     pois: Optional[List[dict]]) -> Dict[str, Optional[int]]:
    """P4 ratings legs for one listing (entry point for the follow-up)."""
    return {key: fn(origin, pois)[0] for key, _, fn in P4_RATINGS_DIMS}
