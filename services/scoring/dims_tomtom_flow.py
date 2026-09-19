"""P4 TomTom flow-segment car speeds (issue #671): keyed, short-lived cache.

Buyer question (indirect): are the GPS bus-delay corridors telling the
truth about car traffic? Independent car-speed truth via
``GET /traffic/services/4/flowSegmentData/absolute/10``
(``currentSpeed`` vs ``freeFlowSpeed``) at ~40 arterial probe points,
morning/evening bands. Where TomTom car speeds and bus delays
disagree is itself a signal (bus lanes working vs general jam).

ToS verdict (step zero, #669): SHORT-TERM CACHE ONLY (TomTom Portal
Terms 11.4 + 11.6 - pasted in docs/p4_tomtom_matrix.md section 0,
repeated in docs/p4_tomtom_flow.md section 0). NO committed sidecars,
NO stored tables: --pull fills a git-ignored operator cache dir (1 d
TTL cap, cache-control max-age honored), --build reads that cache (or
a fixture) and prints counts + calibration stats to stdout.

Quota math (pinned from the issue body): 1 txn per call -> ~40 probe
points x 2 bands = ~80 txn/day, well inside budget. Coded as
FLOW_MAX_CALLS = 80 per 1 d window; 429 = stop.

Ingestion (stdlib only, mirrors dims_tomtom_matrix.py): fetch_flow
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

#: Flow-segment endpoint (key-gated; never called without
#: TOMTOM_API_KEY).
FLOW_URL = ("https://api.tomtom.com/traffic/services/4/"
            "flowSegmentData/absolute/10/json")

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
TOMTOM_KEY_ENV = "TOMTOM_API_KEY"

#: Harvest budget: ~40 arterial probes x morning/evening bands =
#: ~80 txn/day (1 txn per call), well inside budget.
FLOW_PROBES = 40
FLOW_MAX_CALLS = 80

#: Short-lived cache only (ToS 11.4): daily samples -> 1 d TTL cap; a
#: response cache-control max-age below this wins (never exceeded).
FLOW_TTL_S = 24 * 3600

#: Identifying user agent for the polite pull.
FLOW_UA = "home-finder flow-speed harvest (keyed, quota-capped)"

#: Minimum plausible flow body.
FLOW_MIN_BYTES = 64

#: Morning/evening band pins (probe time is pull time; bands label
#: which daily pull a sample belongs to).
FLOW_BANDS = ("morning", "evening")

#: Speed-ratio bands (current/freeFlow): >=0.9 free, >=0.75 steady,
#: >=0.5 slow, else jammed. Scores mirror the delay-corridor bands so
#: the calibration comparison is apples-to-apples.
FLOW_SCORE = {"free": 75, "steady": 60, "slow": 45, "jammed": 30}

#: No-key NULL reason (buyer check, never a guess).
NO_KEY_NULL = ("Autokiiruse võrdlusinfo puudub (EI OLE võtmeta "
               "kiirusliidestust: TomTom Flow vajab võtit - bussi-"
               "viivituse kiht jääb kalibreerimata, autoummikut ära "
               "eelda)")


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "tomtom_flow_quota.json")


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > FLOW_TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= FLOW_TTL_S:
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


def fetch_flow(lat: float, lon: float, cache_dir: str, filename: str,
               api_key: Optional[str] = None,
               ttl_s: int = FLOW_TTL_S) -> Optional[str]:
    """Polite keyed flow-segment pull for one probe point. Path or None.

    Key from the TOMTOM_API_KEY env (or the explicit arg - tests only,
    never a committed secret). No key, spent quota, or fresh cache: NO
    request. Otherwise one GET; the body is stored only on HTTP 200
    over FLOW_MIN_BYTES, else None (transport errors never cached, 429
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
    if _quota_used(cache_dir) >= FLOW_MAX_CALLS:
        return None
    qs = urllib.parse.urlencode({"point": "%s,%s" % (lat, lon), "key": key})
    try:
        req = urllib.request.Request(FLOW_URL + "?" + qs, method="GET",
                                     headers={"User-Agent": FLOW_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
            max_age = _max_age_s(resp)
        if len(body) < FLOW_MIN_BYTES:
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
# Offline readers over the cached flow JSON (pure).
# ---------------------------------------------------------------------------

def parse_flow_response(path: str) -> dict:
    """Parse a cached flow-segment body. Offline.

    Returns ``{"current": int|None, "freeflow": int|None}`` (km/h).
    Garbage keeps honest Nones; nothing is guessed.
    """
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    seg = data.get("flowSegmentData", {}) if isinstance(data, dict) else {}
    if not isinstance(seg, dict):
        return {"current": None, "freeflow": None}
    out = {}
    for key, name in (("currentSpeed", "current"),
                      ("freeFlowSpeed", "freeflow")):
        try:
            v: Optional[int] = int(seg[key])
            if v is not None and (v < 0 or v > 250):
                v = None
        except (TypeError, ValueError, KeyError):
            v = None
        out[name] = v
    return out


def speed_band(current: Optional[int],
               freeflow: Optional[int]) -> Optional[str]:
    """Speed ratio -> band (free/steady/slow/jammed). Pure."""
    if (not isinstance(current, int) or isinstance(current, bool)
            or not isinstance(freeflow, int) or isinstance(freeflow, bool)
            or freeflow <= 0 or current < 0):
        return None
    ratio = current / freeflow
    if not math.isfinite(ratio):
        return None
    if ratio >= 0.9:
        return "free"
    if ratio >= 0.75:
        return "steady"
    if ratio >= 0.5:
        return "slow"
    return "jammed"


def build_table(rows: List[dict]) -> dict:
    """Per-probe x band speed rows -> daily table. Pure.

    Each row: ``probe_id``, ``band`` (morning|evening), ``current``,
    ``freeflow``. Returns ``{"rows": [...], "counts"}`` with per-row
    ``ratio`` and ``speed_band``. Unmeasured rows keep NULLs.
    """
    out_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        cur, free = r.get("current"), r.get("freeflow")
        band = speed_band(cur, free)
        ratio = (cur / free if isinstance(cur, int)
                 and not isinstance(cur, bool) and isinstance(free, int)
                 and not isinstance(free, bool) and free > 0
                 and cur >= 0 else None)
        out_rows.append({"probe_id": r.get("probe_id"), "band": r.get("band"),
                         "current": cur, "freeflow": free, "ratio": ratio,
                         "speed_band": band})
    measured = sum(1 for x in out_rows if x["speed_band"] is not None)
    return {"rows": out_rows,
            "counts": {"total": len(out_rows), "measured": measured,
                       "unmeasured": len(out_rows) - measured}}


def calibrate_vs_delay(flow_rows: List[dict],
                       delay_factors: Dict[str, float]) -> dict:
    """Agree/disagree stats vs bus-delay corridor factors. Pure.

    Maps each flow row's speed band to the delay-corridor band scale
    (free/steady/slow/jammed, same thresholds by construction) and
    compares with the delay factor band for the same probe_id:
    ``{"agree": n, "disagree": n, "details": [...]}``. A disagree
    means bus lanes working (bus fast, cars jammed) or the reverse -
    the signal the issue body asks for. Unknowns on either side are
    skipped, never forced.
    """
    agree = disagree = 0
    details = []
    for r in flow_rows:
        if not isinstance(r, dict):
            continue
        pid = r.get("probe_id")
        fband = r.get("speed_band") or speed_band(r.get("current"),
                                                  r.get("freeflow"))
        factor = delay_factors.get(pid) if isinstance(pid, str) else None
        if fband is None or not isinstance(factor, (int, float)) \
                or isinstance(factor, bool) \
                or not math.isfinite(factor) or factor < 1:
            continue
        dband = ("free" if factor <= 1.1 else "steady" if factor <= 1.3
                 else "slow" if factor <= 1.6 else "jammed")
        verdict = "agree" if dband == fband else "disagree"
        if verdict == "agree":
            agree += 1
        else:
            disagree += 1
        details.append({"probe_id": pid, "flow_band": fband,
                        "delay_band": dband, "verdict": verdict})
    return {"agree": agree, "disagree": disagree, "details": details}


# ---------------------------------------------------------------------------
# Scorer dims (over the short-lived cache table, never stored).
# ---------------------------------------------------------------------------

def dim_car_speed(origin: Optional[Tuple[float, float]],
                  table: Optional[dict],
                  probe_id: Optional[str] = None,
                  band: str = "morning") -> Score:
    """Car speed at the nearest measured probe (calibrator, not ranker).

    Reports the probe's speed band as context for the bus-delay layer;
    the disagreement flag (bus vs car) is the calibration signal and is
    surfaced in docs, not scored here.
    """
    if table is None:
        return None, NO_KEY_NULL
    rows = table.get("rows") if isinstance(table, dict) else None
    if not rows:
        return None, ("Autokiiruse mõõtmist pole (lühiajaline TomTom "
                      "puhver, mõõtmata pole halb)")
    cands = [r for r in rows if isinstance(r, dict)
             and r.get("band", "morning") == band
             and r.get("speed_band") is not None]
    if probe_id is not None:
        cands = [r for r in cands if r.get("probe_id") == probe_id]
    if not cands:
        return None, ("Selle punkti autokiiruse mõõtmist pole "
                      "(lühiajaline TomTom puhver)")
    best = cands[0]
    score = FLOW_SCORE.get(best["speed_band"], 45)
    return score, ("Autokiirus %s: %s km/h (vaba %s, %s; lühiajaline "
                   "TomTom Flow-mõõtmik, mitte reaalajas) -> skoor %d"
                   % (best.get("probe_id"), best.get("current"),
                      best.get("freeflow"), best.get("speed_band"), score))


#: Registry for the central weight-rebalance follow-up: (dim key, param).
TOMTOM_FLOW_DIMS = (
    ("car_speed", "P4-tomtom-flow", dim_car_speed),
)


def score_tomtom_flow(origin: Optional[Tuple[float, float]],
                      table: Optional[dict],
                      probe_id: Optional[str] = None) -> Dict[str, Optional[int]]:
    """TomTom flow legs for one listing (entry point for follow-up)."""
    return {key: fn(origin, table, probe_id)[0]
            for key, _, fn in TOMTOM_FLOW_DIMS}
