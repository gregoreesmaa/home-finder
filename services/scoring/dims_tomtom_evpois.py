"""P4 TomTom EV-charging POI layer (issue #673): keyed, short-lived cache.

Buyer question (EV-driving segment): "kus on lähim laadija" -
EV-station POIs via the Search API ``categorySet`` + connector-type
filter, tiled over Tallinn, refreshed monthly. Amenity score + map
points.

STATIC LOCATIONS ONLY (load-bearing): real-time per-plug
availability is an enterprise product and out of reach - the layer
must NEVER imply live availability. Every user-facing string says
"staatiline" (static); a live-looking label is a bug. Pinned by test.

ToS verdict (step zero, #669): SHORT-TERM CACHE ONLY (TomTom Portal
Terms 11.4 + 11.6 - pasted in docs/p4_tomtom_matrix.md section 0,
repeated in docs/p4_tomtom_ev.md section 0). NO committed sidecars,
NO stored tables: --pull fills a git-ignored operator cache dir
(30 d TTL cap, cache-control max-age honored), --build reads that
cache (or fixture files) and prints counts to stdout.

Quota math (pinned from the issue body): ~20 txn per monthly
refresh. Coded as EV_MAX_CALLS = 20 per 30 d window; 429 = stop.

Category ID (judgment call, for the reviewer): EV_CATEGORY = 7309 is
the widely-used TomTom Search categorySet value for EV charging
stations, but the category docs page is login-walled, so this is
SPIKE-UNVERIFIED - the first keyed operator run must resolve it via
one POI-Categories call and correct it if wrong (documented in the
harvester --category help and docs/p4_tomtom_ev.md). The plumbing
(category param -> request -> POI parse) is pinned by test; the
numeric value is not asserted as truth.

Ingestion (stdlib only, mirrors dims_tomtom_flow.py): fetch_evpois
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
EV_SEARCH_URL = "https://api.tomtom.com/search/2/nearbySearch/.json"

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
TOMTOM_KEY_ENV = "TOMTOM_API_KEY"

#: EV-charging-station categorySet value. SPIKE-UNVERIFIED (see module
#: docstring): re-check via one POI-Categories call before the first
#: keyed pull. Overridable per-run with --category.
EV_CATEGORY = 7309
EV_CATEGORY_VERIFIED = False

#: Harvest budget: ~20 txn per monthly refresh (tiled over Tallinn).
EV_MAX_CALLS = 20

#: Short-lived cache only (ToS 11.4): monthly refresh -> 30 d TTL cap;
#: a response cache-control max-age below this wins (never exceeded).
EV_TTL_S = 30 * 24 * 3600

#: Identifying user agent for the polite pull.
EV_UA = "home-finder ev-poi harvest (keyed, quota-capped)"

#: Minimum plausible search body.
EV_MIN_BYTES = 64

#: Static-only label (load-bearing: never imply live availability).
STATIC_LABEL = "staatiline laadimiskoht (saadavus teadmata, mitte reaalajas)"

#: No-key NULL reason (buyer check, never a guess).
NO_KEY_NULL = ("Laadijate info puudub (EI OLE võtmeta laadijaliidestust: "
               "TomTom Search vajab võtit - lisa võti, staatilist "
               "saadavust ära eelda)")


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_evpois_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > EV_TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= EV_TTL_S:
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


def fetch_evpois(lat: float, lon: float, radius_m: int, cache_dir: str,
                 filename: str, category: int = EV_CATEGORY,
                 api_key: Optional[str] = None,
                 ttl_s: int = EV_TTL_S) -> Optional[str]:
    """Polite keyed POI pull for one tile. Path or None.

    Key from the TOMTOM_API_KEY env (or the explicit arg - tests only,
    never a committed secret). No key, spent quota, or fresh cache: NO
    request. Otherwise one GET; the body is stored only on HTTP 200
    over EV_MIN_BYTES, else None (transport errors never cached, 429
    is a stop signal, no retries; max-age honored - ToS 11.4).
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
    if _quota_used(cache_dir) >= EV_MAX_CALLS:
        return None
    qs = urllib.parse.urlencode({
        "key": key, "lat": lat, "lon": lon, "radius": radius_m,
        "categorySet": category, "limit": 100,
    })
    try:
        req = urllib.request.Request(EV_SEARCH_URL + "?" + qs, method="GET",
                                     headers={"User-Agent": EV_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
            max_age = _max_age_s(resp)
        if len(body) < EV_MIN_BYTES:
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

def parse_evpois_response(path: str) -> List[dict]:
    """Parse a cached Nearby Search body. Offline.

    Returns per-POI dicts: ``poi_id``, ``name``, ``lat``/``lon``,
    ``connectors`` (list of str|None - static info only, never live
    availability). Garbage rows keep honest Nones; nothing is guessed.
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
        connectors = None
        charge = poi.get("chargingInformation") if isinstance(poi, dict) \
            else None
        if isinstance(charge, dict):
            conns = charge.get("connectors")
            if isinstance(conns, list):
                connectors = [c.get("connectorType") for c in conns
                              if isinstance(c, dict)]
        out.append({"poi_id": res.get("id"), "name": poi.get("name"),
                    "lat": lat, "lon": lon, "connectors": connectors})
    return out


def build_table(rows: List[dict]) -> dict:
    """EV POI rows -> snapshot table. Pure.

    Returns ``{"pois": [...], "counts"}``; coord-less rows are listed
    with NULL coords (unmeasured, never faked, never dropped
    silently).
    """
    pois = [r for r in rows if isinstance(r, dict)]
    geo = sum(1 for p in pois if isinstance(p.get("lat"), float)
              and isinstance(p.get("lon"), float))
    return {"pois": pois,
            "counts": {"total": len(pois), "geocoded": geo,
                       "coord_less": len(pois) - geo}}


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


def dim_ev_amenity(origin: Optional[Tuple[float, float]],
                   table: Optional[dict]) -> Score:
    """EV amenity: nearest STATIC charging POI within 2 km.

    <=500 m -> 75, <=1 km -> 60, <=2 km -> 50, none -> 35 (no charger
    nearby, not bad housing). The reason ALWAYS carries the static
    label - live availability is never implied.
    """
    if table is None:
        return None, NO_KEY_NULL
    pois = table.get("pois") if isinstance(table, dict) else None
    if not origin or not pois:
        return None, ("Laadijate mõõtmist pole (lühiajaline TomTom "
                      "puhver, mõõtmata pole halb)")
    near = []
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
        if d <= 2000:
            near.append((d, p))
    if not near:
        return 35, ("2 km raadiuses pole staatilist laadijat "
                    "(lühiajaline TomTom-mõõtmik; laadija puudumine "
                    "pole halb elamine)")
    nearest_m = min(d for d, _ in near)
    score = 75 if nearest_m <= 500 else 60 if nearest_m <= 1000 else 50
    name = near[0][1].get("name") or "nimetu jaam"
    return score, ("Lähim %s: %s %s kaugusel (%d jaama 2 km puhvris) "
                   "-> skoor %d" % (STATIC_LABEL, name,
                                    _fmt_m(nearest_m), len(near), score))


#: Registry for the central weight-rebalance follow-up: (dim key, param).
TOMTOM_EV_DIMS = (
    ("ev_amenity", "P4-tomtom-ev", dim_ev_amenity),
)


def score_tomtom_ev(origin: Optional[Tuple[float, float]],
                    table: Optional[dict]) -> Dict[str, Optional[int]]:
    """TomTom EV legs for one listing (entry point for follow-up)."""
    return {key: fn(origin, table)[0] for key, _, fn in TOMTOM_EV_DIMS}
