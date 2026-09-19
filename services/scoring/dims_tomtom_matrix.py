"""P4 TomTom car-commute matrix dims (issue #669): keyed, short-lived cache.

Buyer question: "autoga toole: N min (+M ummikulisand)" per area -
rush-hour vs off-peak drive times from each area centroid to the 5 job
hubs (City Center, Ulemiste, Mustamae, Port, Airport) via
``POST /routing/matrix/2`` with ``traffic=true``.

ToS VERDICT (step zero, gates all TomTom work - pasted in
docs/p4_tomtom_matrix.md section 0): TomTom Portal Terms & Conditions
clause 11.4 PROHIBITS caching/storing Results except a short
client-side cache bounded by the response cache-control max-age, and
clause 11.6.1/11.6.2 forbids derivative/secondary databases.
Consequence: NO committed sidecars, NO stored tables - the harvester
keeps a short-lived operator cache (git-ignored cache dir, TTL-capped)
and the repo holds fixtures + code only. Route results count as
"Results" under the agreement, so this covers all seven TomTom
harvesters (#669-#675).

Quota math (pinned from the issue body, verified vs current docs):
196 area centroids x 5 hubs, sync cap 200 cells/call -> one call per
hub (196x1 = 196 txn); ~980 txn per refresh, 3x/week inside the
2500/day free budget. Coded as MATRIX_MAX_CALLS = 5 per 2 d window.

Ingestion (stdlib only, mirrors dims_p4_ratings.py): fetch_matrix does
the polite keyed pull (key from TOMTOM_API_KEY env only, quota cap,
TTL, single attempt, 429 = stop; transport errors and short bodies are
never cached; cache-control max-age is honored when present and never
exceeded). Scorers and unit tests never touch the network.
"""

import json
import math
import os
import time
import urllib.request
from typing import Dict, List, Optional, Tuple

Score = Tuple[Optional[int], str]  # (score 0..100 | None, Estonian reason)

#: Routing Matrix endpoint (key-gated; never called without
#: TOMTOM_API_KEY).
MATRIX_URL = "https://api.tomtom.com/routing/matrix/2"

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
TOMTOM_KEY_ENV = "TOMTOM_API_KEY"

#: Harvest budget: 196 centroids x 5 hubs at <=200 cells/call = one
#: call per hub x band, i.e. 10 calls per full refresh (5 hubs x rush +
#: off-peak). One band = ~980 txn (the issue-body number); a full
#: refresh ~= 1960 txn, refreshed 3x/week ~= 840 txn/day average,
#: inside the 2500/day free budget.
MATRIX_ORIGINS = 196
MATRIX_MAX_CALLS = 10
MATRIX_TXN_PER_REFRESH = 1960
MATRIX_TXN_PER_BAND = 980
MATRIX_DAILY_BUDGET = 2500

#: Short-lived cache only (ToS 11.4): refresh 3x/week -> 2 d TTL cap;
#: a response cache-control max-age below this wins (never exceeded).
MATRIX_TTL_S = 2 * 24 * 3600

#: Identifying user agent for the polite pull.
MATRIX_UA = "home-finder commute-matrix harvest (keyed, quota-capped)"

#: Minimum plausible matrix body.
MATRIX_MIN_BYTES = 64

#: The 5 job hubs (approximate public coordinates; override with
#: --hubs-file when exact hub pins are wanted).
HUBS = (
    {"id": "city-center", "name": "Kesklinn", "lat": 59.4370, "lon": 24.7535},
    {"id": "ulemiste", "name": "Ülemiste", "lat": 59.4215, "lon": 24.7996},
    {"id": "mustamae", "name": "Mustamäe", "lat": 59.4050, "lon": 24.6850},
    {"id": "port", "name": "Sadam", "lat": 59.4431, "lon": 24.7672},
    {"id": "airport", "name": "Lennujaam", "lat": 59.4133, "lon": 24.8328},
)

#: Rush-hour vs off-peak departAt pins (Europe/Tallinn local).
DEPART_RUSH = "2026-09-22T08:00:00+03:00"
DEPART_OFFPEAK = "2026-09-22T12:00:00+03:00"

#: Commute bands (rush minutes one-way): <=20 kiire, <=35 ok, <=50
#: veniv, else ummikune. Scores: fast surroundings delight (75),
#: slow surroundings drag (30).
COMMUTE_SCORE = {"kiire": 75, "ok": 65, "veniv": 45, "ummikune": 30}

#: No-key NULL reason (buyer check, never a guess).
NO_KEY_NULL = ("Autoga-toole info puudub (EI OLE võtmeta automarsruudi-"
               "liidestust: TomTom Matrix vajab võtit - lisa võti või "
               "hinda ühistransporti GPS-viivituse kihilt, autoaega ära "
               "eelda)")


def _haversine_m(origin: Tuple[float, float], lat: float, lon: float) -> float:
    """Great-circle distance in metres."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (origin[0], origin[1], lat, lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_matrix_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > MATRIX_TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= MATRIX_TTL_S:
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


def fetch_matrix(origins: List[dict], dest: dict, depart_at: str,
                 cache_dir: str, filename: str,
                 api_key: Optional[str] = None,
                 ttl_s: int = MATRIX_TTL_S) -> Optional[str]:
    """Polite keyed matrix pull for one hub x one band. Path or None.

    Key from the TOMTOM_API_KEY env (or the explicit arg - tests only,
    never a committed secret). No key, spent quota, or fresh cache: NO
    request. Otherwise one POST; the body is stored only on HTTP 200
    over MATRIX_MIN_BYTES, else None (transport errors never cached,
    429 is a stop signal, no retries; a response max-age below ttl_s
    shortens freshness - ToS 11.4, never exceeded). Scorers never call
    this.
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
    if _quota_used(cache_dir) >= MATRIX_MAX_CALLS:
        return None
    payload = json.dumps({
        "origins": [{"point": {"latitude": o["lat"], "longitude": o["lon"]}}
                    for o in origins],
        "destinations": [{"point": {"latitude": dest["lat"],
                                    "longitude": dest["lon"]}}],
        "options": {"traffic": True, "departAt": depart_at,
                    "travelMode": "car"},
    }).encode("utf-8")
    try:
        req = urllib.request.Request(
            MATRIX_URL + "?key=" + key, data=payload, method="POST",
            headers={"User-Agent": MATRIX_UA,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
            max_age = _max_age_s(resp)
        if len(body) < MATRIX_MIN_BYTES:
            return None
        with open(dest_path, "wb") as fh:
            fh.write(body)
        if max_age is not None and max_age < ttl_s:
            # ToS 11.4: never keep Results longer than max-age -
            # backdate the mtime so freshness expires on time.
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
# Offline readers over the cached matrix JSON (pure).
# ---------------------------------------------------------------------------

def parse_matrix_response(path: str) -> List[dict]:
    """Parse a cached matrix body. Offline.

    Returns per-cell dicts: ``origin_idx``, ``travel_s`` (int|None),
    ``delay_s`` (int, 0 when absent). Short/traffic-free cells keep
    honest Nones; nothing is guessed.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    cells = data.get("results", data.get("data", []))
    if not isinstance(cells, list):
        return []
    out = []
    for i, cell in enumerate(cells):
        if not isinstance(cell, dict):
            continue
        summary = cell.get("summary") if isinstance(cell.get("summary"),
                                                     dict) else {}
        travel = summary.get("travelTimeInSeconds",
                             cell.get("travelTimeInSeconds"))
        delay = summary.get("trafficDelayInSeconds",
                            cell.get("trafficDelayInSeconds", 0))
        try:
            travel_s: Optional[int] = int(travel)
            if travel_s < 0:
                travel_s = None
        except (TypeError, ValueError):
            travel_s = None
        try:
            delay_s = int(delay)
            if delay_s < 0:
                delay_s = 0
        except (TypeError, ValueError):
            delay_s = 0
        out.append({"origin_idx": cell.get("originIndex", i),
                    "travel_s": travel_s, "delay_s": delay_s})
    return out


def build_table(rows: List[dict]) -> dict:
    """Per-area x hub commute rows -> snapshot table. Pure.

    Each row: ``area_id``, ``hub``, ``rush_s`` (int|None),
    ``offpeak_s`` (int|None). Returns ``{"rows": [...], "counts"}``
    with per-row ``delay_s`` (rush minus off-peak, floor 0) and
    ``band`` (kiire/ok/veniv/ummikune/None). Unmeasured rows keep
    NULLs, never guesses.
    """
    out_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        rush = r.get("rush_s")
        off = r.get("offpeak_s")
        try:
            rush = int(rush) if rush is not None else None
            if rush is not None and rush < 0:
                rush = None
        except (TypeError, ValueError):
            rush = None
        try:
            off = int(off) if off is not None else None
            if off is not None and off < 0:
                off = None
        except (TypeError, ValueError):
            off = None
        if rush is None:
            delay, band = None, None
        else:
            delay = max(0, rush - (off if off is not None else rush))
            mins = rush / 60.0
            band = ("kiire" if mins <= 20 else "ok" if mins <= 35
                    else "veniv" if mins <= 50 else "ummikune")
        out_rows.append({"area_id": r.get("area_id"), "hub": r.get("hub"),
                         "rush_s": rush, "offpeak_s": off,
                         "delay_s": delay, "band": band})
    measured = sum(1 for x in out_rows if x["rush_s"] is not None)
    return {"rows": out_rows,
            "counts": {"total": len(out_rows), "measured": measured,
                       "unmeasured": len(out_rows) - measured}}


# ---------------------------------------------------------------------------
# Scorer dims (over the short-lived cache table, never stored).
# ---------------------------------------------------------------------------

def dim_car_commute(origin: Optional[Tuple[float, float]],
                    table: Optional[dict],
                    area_id: Optional[str] = None) -> Score:
    """Car commute: rush minutes to the best hub + jam surcharge.

    Scores the area's best (lowest) rush time across hubs: kiire 75,
    ok 65, veniv 45, ummikune 30. The reason always carries the
    off-peak comparison (+M ummikulisand).
    """
    if table is None:
        return None, NO_KEY_NULL
    rows = table.get("rows") if isinstance(table, dict) else None
    if not rows or area_id is None:
        return None, NO_KEY_NULL if table is None else (
            "Selle piirkonna autoga-toole mõõtmist pole (lühiajaline "
            "TomTom puhver, mõõtmata pole halb - hinda ühistransporti)")
    cands = [r for r in rows
             if isinstance(r, dict) and r.get("area_id") == area_id
             and isinstance(r.get("rush_s"), int)]
    if not cands:
        return None, ("Selle piirkonna autoga-toole mõõtmist pole "
                      "(lühiajaline TomTom puhver, mõõtmata pole halb - "
                      "hinda ühistransporti)")
    best = min(cands, key=lambda r: r["rush_s"])
    band = best.get("band") or "veniv"
    score = COMMUTE_SCORE.get(band, 45)
    rush_m = best["rush_s"] / 60.0
    delay_m = (best.get("delay_s") or 0) / 60.0
    return score, ("Autoga tööle: %.0f min tipptunnil (+%.0f ummikulisand, "
                   "%s, %s; lühiajaline TomTom Matrix-mõõtmik, mitte "
                   "reaalajas) -> skoor %d"
                   % (rush_m, delay_m, best.get("hub"),
                      {"kiire": "kiire", "ok": "sobiv",
                       "veniv": "veniv", "ummikune": "ummikune"}.get(
                           band, band), score))


#: Registry for the central weight-rebalance follow-up: (dim key, param).
TOMTOM_MATRIX_DIMS = (
    ("car_commute", "P4-tomtom-matrix", dim_car_commute),
)


def score_tomtom_matrix(origin: Optional[Tuple[float, float]],
                        table: Optional[dict],
                        area_id: Optional[str] = None
                        ) -> Dict[str, Optional[int]]:
    """TomTom matrix legs for one listing (entry point for follow-up)."""
    return {key: fn(origin, table, area_id)[0]
            for key, _, fn in TOMTOM_MATRIX_DIMS}
