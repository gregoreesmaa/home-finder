"""P4 TomTom parking / P&R POI layer (issue #674): keyed, short-lived cache.

Buyer question (car-commute segment): "kuhu auto jätta enne viimast
ühistranspordilõiku" - parking / park-and-ride POIs via the Search
API ``categorySet``, tiled over Tallinn, refreshed monthly. Amenity
score; pairs with the car-commute layers (#669/#670).

Same harvest mechanism as the EV-POI issue (#673): this ships as a
SIBLING script (``batch_tomtom_parking.py`` + ``dims_tomtom_parking``
- the issue allows "or sibling script"). The branches are parallel
(one issue per worktree/PR from main), so literal flag-sharing would
couple them; convergence to one ``--category`` script is flagged as a
follow-up once both land. The plumbing is identical by construction
(same quota/TTL/refusal/max-age shape).

STATIC LOCATIONS ONLY (load-bearing, mirrors #673): real-time
occupancy is out of reach - the layer must NEVER imply live free
spaces. Every user-facing string says "staatiline"; a live-looking
label is a bug. Pinned by test.

ToS verdict (step zero, #669): SHORT-TERM CACHE ONLY (TomTom Portal
Terms 11.4 + 11.6 - pasted in docs/p4_tomtom_matrix.md section 0,
repeated in docs/p4_tomtom_parking.md section 0). NO committed
sidecars, NO stored POI lists: --pull fills a git-ignored operator
cache dir (30 d TTL cap, cache-control max-age honored), --build
reads that cache (or fixture files) and prints counts to stdout.

Quota math (pinned from the issue body): ~10 txn per monthly
refresh. Coded as PARKING_MAX_CALLS = 10 per 30 d window; 429 = stop.

Category ID (judgment call, for the reviewer): PARKING_CATEGORY =
7311 is the widely-used TomTom Search categorySet value for parking,
but the category docs page is login-walled, so this is
SPIKE-UNVERIFIED - the first keyed operator run must resolve it via
one POI-Categories call and correct it if wrong (documented in the
harvester --category help and docs/p4_tomtom_parking.md). The
plumbing is pinned by test; the numeric value is not asserted.

Ingestion (stdlib only, mirrors dims_tomtom_evpois.py): fetch_parking
does the polite keyed GET (key from TOMTOM_API_KEY env only, quota
cap, TTL, single attempt, 429 = stop; transport errors and short
bodies are never cached; max-age honored when present). Scorers and
unit tests never touch the network.
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Search API Nearby Search endpoint (key-gated; never called without
#: TOMTOM_API_KEY).
PARKING_SEARCH_URL = "https://api.tomtom.com/search/2/nearbySearch/.json"

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
TOMTOM_KEY_ENV = "TOMTOM_API_KEY"

#: Parking categorySet value. SPIKE-UNVERIFIED (see module docstring):
#: re-check via one POI-Categories call before the first keyed pull.
#: Overridable per-run with --category.
PARKING_CATEGORY = 7311
PARKING_CATEGORY_VERIFIED = False

#: Harvest budget: ~10 txn per monthly refresh (tiled over Tallinn).
PARKING_MAX_CALLS = 10

#: Short-lived cache only (ToS 11.4): monthly refresh -> 30 d TTL cap;
#: a response cache-control max-age below this wins (never exceeded).
PARKING_TTL_S = 30 * 24 * 3600

#: Identifying user agent for the polite pull.
PARKING_UA = "home-finder parking-poi harvest (keyed, quota-capped)"

#: Minimum plausible search body.
PARKING_MIN_BYTES = 64

#: Static-only label (load-bearing: never imply live free spaces).
STATIC_LABEL = ("staatiline parkla (vabade kohtade arv teadmata, "
                "mitte reaalajas)")

#: P&R name markers (Estonian + English): a POI whose name matches any
#: of these counts as park-and-ride in the amenity reason.
PR_MARKERS = ("p&r", "park and ride", "ümberistumisparkla",
              "ümberistumine")

#: No-key NULL reason (buyer check, never a guess).
NO_KEY_NULL = ("Parklate info puudub (EI OLE võtmeta parklaliidestust: "
               "TomTom Search vajab võtit - lisa võti, staatilist "
               "vabade kohtade arvu ära eelda)")


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_parking_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > PARKING_TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= PARKING_TTL_S:
                start = float(rec["window_start"])
                used = max(0, int(rec.get("used", 0)))
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            pass
        with open(_quota_path(cache_dir), "w", encoding="utf-8") as fh:
            json.dump({"window_start": start, "used": used + 1}, fh)
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


def fetch_parking(lat: float, lon: float, radius_m: int, cache_dir: str,
                  filename: str, category: int = PARKING_CATEGORY,
                  api_key: Optional[str] = None,
                  ttl_s: int = PARKING_TTL_S) -> Optional[str]:
    """Polite keyed POI pull for one tile. Path or None.

    Key from the TOMTOM_API_KEY env (or the explicit arg - tests only,
    never a committed secret). No key, spent quota, or fresh cache: NO
    request. Otherwise one GET; the body is stored only on HTTP 200
    over PARKING_MIN_BYTES, else None (transport errors never cached,
    429 is a stop signal, no retries; max-age honored - ToS 11.4).
    Scorers never call this.
    """
    key = api_key or os.environ.get(TOMTOM_KEY_ENV)
    if not key:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    dest_path = os.path.join(cache_dir, filename)
    try:
        if os.path.exists(dest_path):
            age = time.time() - os.path.getmtime(dest_path)
            if age < ttl_s:
                return dest_path
    except OSError:
        return None
    if _quota_used(cache_dir) >= PARKING_MAX_CALLS:
        return None
    qs = urllib.parse.urlencode({
        "key": key, "lat": lat, "lon": lon, "radius": radius_m,
        "categorySet": category, "limit": 100,
    })
    try:
        req = urllib.request.Request(PARKING_SEARCH_URL + "?" + qs,
                                     method="GET",
                                     headers={"User-Agent": PARKING_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
            max_age = _max_age_s(resp)
        if len(body) < PARKING_MIN_BYTES:
            return None
        with open(dest_path, "wb") as fh:
            fh.write(body)
        if max_age is not None and max_age < ttl_s:
            try:
                now = time.time()
                os.utime(dest_path, (now, now - (ttl_s - max_age)))
            except OSError:
                pass
        _quota_spend(cache_dir)
        return dest_path
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offline readers over the cached search JSON (pure).
# ---------------------------------------------------------------------------

def is_park_and_ride(name) -> bool:
    """P&R name match (Estonian + English markers). Pure."""
    if not isinstance(name, str):
        return False
    lowered = name.lower()
    return any(m in lowered for m in PR_MARKERS)


def parse_parking_response(path: str) -> List[dict]:
    """Parse a cached Nearby Search body. Offline.

    Returns per-POI dicts: ``poi_id``, ``name``, ``lat``/``lon``,
    ``park_and_ride`` (bool, name-marker based). Garbage rows keep
    honest Nones; nothing is guessed.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    results = data.get("results", []) if isinstance(data, dict) else []
    if not isinstance(results, list):
        return []
    out = []
    for res in results:
        if not isinstance(res, dict):
            continue
        poi = res.get("poi") if isinstance(res.get("poi"), dict) else {}
        pos = res.get("position") if isinstance(res.get("position"),
                                                dict) else {}
        try:
            lat = float(pos["lat"])
            lon = float(pos["lon"])
        except (TypeError, ValueError, KeyError):
            lat, lon = None, None
        if isinstance(pos.get("lat"), bool) or isinstance(pos.get("lon"),
                                                           bool):
            lat, lon = None, None
        if lat is not None and not math.isfinite(lat):
            lat = None
        if lon is not None and not math.isfinite(lon):
            lon = None
        name = poi.get("name") if isinstance(poi, dict) else None
        out.append({"poi_id": res.get("id"), "name": name,
                    "lat": lat, "lon": lon,
                    "park_and_ride": is_park_and_ride(name)})
    return out


def build_table(rows: List[dict]) -> dict:
    """Parking POI rows -> snapshot table. Pure.

    Returns ``{"pois": [...], "counts"}`` with a ``park_and_ride``
    sub-count; coord-less rows keep NULL coords (never faked, never
    dropped silently).
    """
    pois = [r for r in rows if isinstance(r, dict)]
    geo = sum(1 for p in pois if isinstance(p.get("lat"), float)
              and isinstance(p.get("lon"), float))
    pr = sum(1 for p in pois if p.get("park_and_ride") is True)
    return {"pois": pois,
            "counts": {"total": len(pois), "geocoded": geo,
                       "coord_less": len(pois) - geo,
                       "park_and_ride": pr}}


# ---------------------------------------------------------------------------
# Scorer dims (over the short-lived cache table, never stored).
# ---------------------------------------------------------------------------

def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _fmt_m(m: float) -> str:
    return "%d m" % int(round(m)) if m < 1000 else "~%.1f km" % (m / 1000.0)


def dim_parking_amenity(origin: Optional[Tuple[float, float]],
                        table: Optional[dict]) -> Score:
    """Parking amenity: nearest STATIC parking within 1 km.

    <=300 m -> 75, <=600 m -> 65, <=1 km -> 55, none -> 40. A
    park-and-ride within 2 km adds a named bonus note (the car+PT
    pair the issue asks for) without changing the score scale. The
    reason ALWAYS carries the static label - live free spaces are
    never implied.
    """
    if table is None:
        return None, NO_KEY_NULL
    pois = table.get("pois") if isinstance(table, dict) else None
    if not origin or not pois:
        return None, ("Parklate mõõtmist pole (lühiajaline TomTom "
                      "puhver, mõõtmata pole halb)")
    near = []
    pr_near = []
    for p in pois:
        if not isinstance(p, dict):
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
        if d <= 1000:
            near.append((d, p))
        if d <= 2000 and p.get("park_and_ride") is True:
            pr_near.append((d, p))
    if not near:
        return 40, ("1 km raadiuses pole staatilist parklat "
                    "(lühiajaline TomTom-mõõtmik; parkla puudumine "
                    "pole halb elamine)")
    nearest_m = min(d for d, _ in near)
    score = 75 if nearest_m <= 300 else 65 if nearest_m <= 600 else 55
    name = near[0][1].get("name") or "nimetu parkla"
    extra = ("; ümberistumisparkla %s kaugusel - auto + ühistransport "
             "paar" % _fmt_m(pr_near[0][0])) if pr_near else ""
    return score, ("Lähim %s: %s %s kaugusel%s (%d parklat 1 km "
                   "puhvris) -> skoor %d" % (STATIC_LABEL, name,
                                             _fmt_m(nearest_m), extra,
                                             len(near), score))


#: Registry for the central weight-rebalance follow-up: (dim key, param).
TOMTOM_PARKING_DIMS = (
    ("parking_amenity", "P4-tomtom-parking", dim_parking_amenity),
)


def score_tomtom_parking(origin: Optional[Tuple[float, float]],
                         table: Optional[dict]) -> Dict[str, Optional[int]]:
    """TomTom parking legs for one listing (entry point for follow-up)."""
    return {key: fn(origin, table)[0] for key, _, fn in TOMTOM_PARKING_DIMS}
