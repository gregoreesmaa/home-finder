"""P4 TomTom daily incident overlay (issue #672): keyed, short-lived cache.

Buyer question: "kas mu marsruudil on täna ummik, sulgus või
teetööd" - daily incident snapshot (jams, closures, roadworks, with
geometry) from one Tallinn bbox poll with
``timeValidityFilter=present``. Freshness-dated overlay in the
teeolud family: stale incidents expire, never presented as live when
old.

ToS verdict (step zero, #669): SHORT-TERM CACHE ONLY (TomTom Portal
Terms 11.4 + 11.6 - pasted in docs/p4_tomtom_matrix.md section 0,
repeated in docs/p4_tomtom_incidents.md section 0). NO committed
sidecars, NO stored tables: --pull fills a git-ignored operator
cache dir (6 h TTL cap, cache-control max-age honored), --build reads
that cache (or a fixture) and prints counts to stdout.

Quota math (pinned from the issue body): 1-2 txn/day. Coded as
INCIDENTS_MAX_CALLS = 2 per 6 h window; 429 = stop.

Expiry (documented, load-bearing): a snapshot older than
INCIDENTS_TTL_S is STALE - the scorer returns NULL ("aegunud", never
a live claim) and the overlay must show the freshness timestamp, not
the geometry. Transport errors and short bodies are never cached.

Ingestion (stdlib only, mirrors dims_tomtom_flow.py): fetch_incidents
does the polite keyed GET (key from TOMTOM_API_KEY env only, quota
cap, TTL, single attempt, 429 = stop; transport never cached;
max-age honored when present). Scorers and unit tests never touch
the network.
"""

import json
import math
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Incident-details endpoint (key-gated; never called without
#: TOMTOM_API_KEY).
INCIDENTS_URL = ("https://api.tomtom.com/traffic/services/5/"
                 "incidentDetails")

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
TOMTOM_KEY_ENV = "TOMTOM_API_KEY"

#: Harvest budget: 1-2 txn/day (one Tallinn bbox poll, one spare).
INCIDENTS_MAX_CALLS = 2

#: Tallinn bbox for the daily poll (lon0,lat0,lon1,lat1).
TALLINN_BBOX = "24.55,59.35,24.95,59.49"

#: Short-lived cache only (ToS 11.4): incidents go stale fast -> 6 h
#: TTL cap; a response cache-control max-age below this wins (never
#: exceeded). Older than this = STALE (NULL, never live).
INCIDENTS_TTL_S = 6 * 3600

#: Identifying user agent for the polite pull.
INCIDENTS_UA = "home-finder incident harvest (keyed, quota-capped)"

#: Minimum plausible incident body.
INCIDENTS_MIN_BYTES = 64

#: Magnitude -> Estonian label (TomTom magnitudeOfDelay 0..4).
MAGNITUDE_ET = {0: "teadmata", 1: "väike", 2: "keskmine",
                3: "suur", 4: "väga suur"}

#: No-key NULL reason (buyer check, never a guess).
NO_KEY_NULL = ("Teeolude info puudub (EI OLE võtmeta intsidentide "
               "liidestust: TomTom Incidents vajab võtit - ummikuid, "
               "sulgusi ja teetöid ära eelda)")


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_incidents_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > INCIDENTS_TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= INCIDENTS_TTL_S:
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


def fetch_incidents(cache_dir: str, filename: str,
                    bbox: str = TALLINN_BBOX,
                    api_key: Optional[str] = None,
                    ttl_s: int = INCIDENTS_TTL_S) -> Optional[str]:
    """Polite keyed incident bbox pull. Path or None.

    Key from the TOMTOM_API_KEY env (or the explicit arg - tests only,
    never a committed secret). No key, spent quota, or fresh cache: NO
    request. Otherwise one GET with timeValidityFilter=present; the
    body is stored only on HTTP 200 over INCIDENTS_MIN_BYTES, else
    None (transport errors never cached, 429 is a stop signal, no
    retries; max-age honored - ToS 11.4). Scorers never call this.
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
    if _quota_used(cache_dir) >= INCIDENTS_MAX_CALLS:
        return None
    qs = urllib.parse.urlencode({
        "bbox": bbox, "timeValidityFilter": "present",
        "language": "et-EE", "key": key,
    })
    try:
        req = urllib.request.Request(INCIDENTS_URL + "?" + qs, method="GET",
                                     headers={"User-Agent": INCIDENTS_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
            max_age = _max_age_s(resp)
        if len(body) < INCIDENTS_MIN_BYTES:
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
# Offline readers over the cached incident JSON (pure).
# ---------------------------------------------------------------------------

def parse_incidents_response(path: str) -> List[dict]:
    """Parse a cached incidentDetails body. Offline.

    Returns per-incident dicts: ``incident_id``, ``category``
    (iconCategory int|None), ``magnitude`` (0..4 int|None),
    ``description`` (str|None), ``points`` ([(lat, lon), ...]).
    Garbage rows keep honest Nones; nothing is guessed.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    incidents = data.get("incidents", []) if isinstance(data, dict) else []
    if not isinstance(incidents, list):
        return []
    out = []
    for inc in incidents:
        if not isinstance(inc, dict):
            continue
        props = inc.get("properties") if isinstance(inc.get("properties"),
                                                    dict) else {}
        geom = inc.get("geometry") if isinstance(inc.get("geometry"),
                                                 dict) else {}
        cat = props.get("iconCategory")
        try:
            cat = int(cat)
            if cat < 0:
                cat = None
        except (TypeError, ValueError):
            cat = None
        mag = props.get("magnitudeOfDelay")
        try:
            mag = int(mag)
            if mag not in (0, 1, 2, 3, 4):
                mag = None
        except (TypeError, ValueError):
            mag = None
        desc = props.get("freeText")
        if not isinstance(desc, str):
            events = props.get("events")
            desc = ", ".join(str(e) for e in events) \
                if isinstance(events, list) else None
        pts = []
        coords = geom.get("coordinates") if isinstance(geom, dict) else []
        if isinstance(coords, list):
            for c in coords:
                if not isinstance(c, (list, tuple)) or len(c) < 2:
                    continue
                try:
                    lon, lat = float(c[0]), float(c[1])
                except (TypeError, ValueError):
                    continue
                if isinstance(c[0], bool) or isinstance(c[1], bool):
                    continue
                if math.isfinite(lat) and math.isfinite(lon):
                    pts.append((lat, lon))
        out.append({"incident_id": inc.get("id", props.get("id")),
                    "category": cat, "magnitude": mag,
                    "description": desc, "points": pts})
    return out


def build_table(rows: List[dict], fetched_at: Optional[float] = None) -> dict:
    """Incident rows -> freshness-dated snapshot table. Pure.

    Returns ``{"incidents": [...], "fetched_at": ts, "counts"}``.
    The freshness timestamp is the contract the overlay renders;
    staleness is decided against INCIDENTS_TTL_S by `is_fresh`.
    """
    incidents = [r for r in rows if isinstance(r, dict)]
    by_mag: Dict[str, int] = {}
    for r in incidents:
        by_mag[str(r.get("magnitude"))] = \
            by_mag.get(str(r.get("magnitude")), 0) + 1
    return {"incidents": incidents,
            "fetched_at": fetched_at if fetched_at is not None else 0,
            "counts": {"total": len(incidents), "by_magnitude": by_mag}}


def is_fresh(table: Optional[dict], now: Optional[float] = None) -> bool:
    """Snapshot freshness: fetched within INCIDENTS_TTL_S. Pure."""
    if not isinstance(table, dict):
        return False
    try:
        age = (time.time() if now is None else now) - float(
            table.get("fetched_at", 0))
    except (TypeError, ValueError):
        return False
    return 0 <= age < INCIDENTS_TTL_S


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


def dim_teeolud(origin: Optional[Tuple[float, float]],
                table: Optional[dict],
                now: Optional[float] = None) -> Score:
    """Teeolud: nearby incidents at pull time (freshness-dated).

    Counts incidents with any geometry point within 1 km: 0 -> 75
    (vaba), 1-2 -> 60, 3+ -> 40. STALE snapshots (older than 6 h) and
    missing tables return NULL - never presented as live when old.
    """
    if table is None:
        return None, NO_KEY_NULL
    if not is_fresh(table, now):
        return None, ("Intsidentide mõõtmik on aegunud (üle 6 h vana) - "
                      "teeolusid ei hinnata, värsket mõõtmikut oodatakse; "
                      "aegunut reaalajas pähe ei määrida")
    if not origin:
        return None, NO_KEY_NULL
    incidents = table.get("incidents") if isinstance(table, dict) else None
    if not incidents:
        return 75, ("Teetöid/ummikuid 1 km raadiuses pole värskes "
                    "mõõtmikus (vaba; lühiajaline TomTom-mõõtmik, mitte "
                    "reaalajas)")
    near = 0
    worst = 0
    for inc in incidents:
        if not isinstance(inc, dict):
            continue
        pts = inc.get("points") if isinstance(inc.get("points"), list) else []
        if any(isinstance(p, (list, tuple)) and len(p) == 2
               and _haversine_m(origin, float(p[0]), float(p[1])) <= 1000
               for p in pts):
            near += 1
            mag = inc.get("magnitude")
            if isinstance(mag, int) and not isinstance(mag, bool):
                worst = max(worst, mag)
    score = 75 if near == 0 else 60 if near <= 2 else 40
    return score, ("%d intsidenti 1 km raadiuses värskes mõõtmikus "
                   "(suurim viivitus %s; lühiajaline TomTom-mõõtmik, "
                   "mitte reaalajas) -> skoor %d"
                   % (near, MAGNITUDE_ET.get(worst, "teadmata"), score))


#: Registry for the central weight-rebalance follow-up: (dim key, param).
TOMTOM_INCIDENTS_DIMS = (
    ("teeolud", "P4-tomtom-incidents", dim_teeolud),
)


def score_tomtom_incidents(origin: Optional[Tuple[float, float]],
                           table: Optional[dict],
                           now: Optional[float] = None
                           ) -> Dict[str, Optional[int]]:
    """TomTom incident legs for one listing (entry point for follow-up)."""
    return {key: fn(origin, table, now)[0]
            for key, _, fn in TOMTOM_INCIDENTS_DIMS}
