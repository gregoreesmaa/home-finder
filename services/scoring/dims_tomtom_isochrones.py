"""P4 TomTom commute-shed isochrones (issue #670): keyed, short-lived cache.

Buyer question: "mitu töökohta jääb 30 min autosõidu kaugusele" -
reachable-range polygons (timeBudgetInSec 900/1800) from each of the
5 job hubs (same hubs as #669), traffic=true, peak vs off-peak via
departAt. Cheapest layer per unit of wow: ~20 calls, weekly refresh.

ToS verdict (step zero, #669): SHORT-TERM CACHE ONLY (TomTom Portal
Terms 11.4 + 11.6 - pasted in docs/p4_tomtom_matrix.md section 0,
repeated in docs/p4_tomtom_isochrones.md section 0). NO committed
sidecars, NO stored tables: --pull fills a git-ignored operator
cache dir (7 d TTL cap, cache-control max-age honored), --build reads
that cache (or a fixture) and prints counts to stdout.

Quota math (pinned from the issue body): 5 hubs x 2 budgets
(900/1800 s) x 2 bands (peak/off-peak) = 20 txn per refresh, weekly.
Coded as SHED_MAX_CALLS = 20 per 7 d window; 429 = stop.

Ingestion (stdlib only, mirrors dims_tomtom_matrix.py): fetch_shed
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

#: Reachable-range endpoint (key-gated; never called without
#: TOMTOM_API_KEY). {lat},{lon} are interpolated into the path.
SHED_URL_TMPL = ("https://api.tomtom.com/routing/1/calculateReachableRange"
                 "/{lat},{lon}/json")

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
TOMTOM_KEY_ENV = "TOMTOM_API_KEY"

#: Harvest budget: 5 hubs x 2 budgets x 2 bands = 20 txn per weekly
#: refresh.
SHED_HUBS = 5
SHED_BUDGETS_S = (900, 1800)
SHED_MAX_CALLS = 20

#: Short-lived cache only (ToS 11.4): weekly refresh -> 7 d TTL cap;
#: a response cache-control max-age below this wins (never exceeded).
SHED_TTL_S = 7 * 24 * 3600

#: Identifying user agent for the polite pull.
SHED_UA = "home-finder commute-shed harvest (keyed, quota-capped)"

#: Minimum plausible reachable-range body.
SHED_MIN_BYTES = 64

#: Rush-hour vs off-peak departAt pins (Europe/Tallinn local).
DEPART_RUSH = "2026-09-22T08:00:00+03:00"
DEPART_OFFPEAK = "2026-09-22T12:00:00+03:00"

#: No-key NULL reason (buyer check, never a guess).
NO_KEY_NULL = ("Tööulatuse info puudub (EI OLE võtmeta ulatusliidestust: "
               "TomTom Reachable Range vajab võtit - lisa võti või "
               "hinda autoteekonda Matrix-mõõtmiku kihilt, ulatust ära "
               "eelda)")


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_sheds_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > SHED_TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= SHED_TTL_S:
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


def fetch_shed(lat: float, lon: float, budget_s: int, depart_at: str,
               cache_dir: str, filename: str,
               api_key: Optional[str] = None,
               ttl_s: int = SHED_TTL_S) -> Optional[str]:
    """Polite keyed reachable-range pull for one hub x budget x band.

    Key from the TOMTOM_API_KEY env (or the explicit arg - tests only,
    never a committed secret). No key, spent quota, or fresh cache: NO
    request. Otherwise one GET; the body is stored only on HTTP 200
    over SHED_MIN_BYTES, else None (transport errors never cached, 429
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
    if _quota_used(cache_dir) >= SHED_MAX_CALLS:
        return None
    qs = urllib.parse.urlencode({
        "key": key, "timeBudgetInSec": budget_s, "traffic": "true",
        "departAt": depart_at,
    })
    url = SHED_URL_TMPL.format(lat=lat, lon=lon) + "?" + qs
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": SHED_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
            max_age = _max_age_s(resp)
        if len(body) < SHED_MIN_BYTES:
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
# Offline readers over the cached reachable-range JSON (pure).
# ---------------------------------------------------------------------------

def parse_shed_response(path: str) -> List[Tuple[float, float]]:
    """Parse a cached reachable-range body. Offline.

    Returns the boundary ring as [(lat, lon), ...]. Garbage rows are
    skipped, never faked; an empty ring means unmeasured.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    ring = data.get("reachableRange", {}).get("boundary", []) \
        if isinstance(data, dict) else []
    if not isinstance(ring, list):
        return []
    out = []
    for pt in ring:
        if not isinstance(pt, dict):
            continue
        try:
            lat = float(pt["latitude"])
            lon = float(pt["longitude"])
        except (TypeError, ValueError, KeyError):
            continue
        if isinstance(pt.get("latitude"), bool) \
                or isinstance(pt.get("longitude"), bool):
            continue
        if math.isfinite(lat) and math.isfinite(lon):
            out.append((lat, lon))
    return out


def build_table(rows: List[dict]) -> dict:
    """Per-hub x budget x band shed rows -> snapshot table. Pure.

    Each row: ``hub``, ``budget_s`` (900|1800), ``band``
    (rush|offpeak), ``ring`` ([(lat, lon), ...]). Returns
    ``{"polygons": [...], "counts"}``; empty rings stay listed with
    ``n_points: 0`` (unmeasured, never dropped silently).
    """
    polys = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        ring = r.get("ring") if isinstance(r.get("ring"), list) else []
        polys.append({"hub": r.get("hub"), "budget_s": r.get("budget_s"),
                      "band": r.get("band"), "n_points": len(ring),
                      "ring": ring})
    measured = sum(1 for p in polys if p["n_points"] >= 3)
    return {"polygons": polys,
            "counts": {"total": len(polys), "measured": measured,
                       "unmeasured": len(polys) - measured}}


def point_in_ring(lat: float, lon: float,
                  ring: List[Tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon over a shed ring. Pure."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if ((yi > lat) != (yj > lat)) and \
                (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------------
# Scorer dims (over the short-lived cache table, never stored).
# ---------------------------------------------------------------------------

def dim_jobs_within_30min(origin: Optional[Tuple[float, float]],
                          table: Optional[dict]) -> Score:
    """Jobs-within-30-min: how many hub sheds cover the listing.

    Each of the 5 hubs' 30-min (1800 s) rush shed covering the listing
    counts one: 5/5 -> 80, 3-4 -> 65, 1-2 -> 50, 0 -> 35 (far from all
    hubs, not bad housing). Off-peak-only coverage is ignored (rush is
    the binding constraint).
    """
    if table is None:
        return None, NO_KEY_NULL
    polys = table.get("polygons") if isinstance(table, dict) else None
    if not origin or not polys:
        return None, ("Tööulatuse mõõtmist pole (lühiajaline TomTom "
                      "puhver, mõõtmata pole halb)")
    hits = set()
    for p in polys:
        if not isinstance(p, dict) or p.get("budget_s") != 1800 \
                or p.get("band") != "rush":
            continue
        if point_in_ring(origin[0], origin[1], p.get("ring", [])):
            hits.add(p.get("hub"))
    n = len(hits)
    score = 80 if n >= 5 else 65 if n >= 3 else 50 if n >= 1 else 35
    return score, ("%d/5 tööhubi 30 min autosõiduulatuses tipptunnil "
                   "(%s; lühiajaline TomTom Reachable-Range-mõõtmik, "
                   "mitte reaalajas) -> skoor %d"
                   % (n, ", ".join(sorted(str(h) for h in hits)) or "üks",
                      score))


#: Registry for the central weight-rebalance follow-up: (dim key, param).
TOMTOM_SHED_DIMS = (
    ("jobs_within_30min", "P4-tomtom-sheds", dim_jobs_within_30min),
)


def score_tomtom_sheds(origin: Optional[Tuple[float, float]],
                       table: Optional[dict]) -> Dict[str, Optional[int]]:
    """TomTom shed legs for one listing (entry point for follow-up)."""
    return {key: fn(origin, table)[0] for key, _, fn in TOMTOM_SHED_DIMS}
