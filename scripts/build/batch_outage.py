"""Live-outage harvester (issue #729): GetApplicationData -> sidecar.

Pole/operator pull ONLY (5-min cadence per the issue; live data goes
stale in minutes — never CI, never unit tests). The repo holds this
code plus hermetic tests; the sidecar lives in cache//tmp and on the
pole as ``built/outage/table.json`` (served at ``GET /v1/outage``,
honest 503 until the first pull).

SOURCE (verified 2026-09-19, UA ``home-finder-research/0.1``,
``--max-time`` 30, 429 = stop): keyless
``geoserver-api/GetApplicationData`` -> 200, ~130 KB double-encoded
JSON ``scopes.p.{areas,dynareas,outages}``. Field semantics pinned
from ``geoserver-api/content/configuration.js`` (see
services/scoring/dims_p4_outage.py + docs/p4_outage.md §1):
fc/fcc = active faults + affected customers, pc/pcc = active
planned, uc/ucc = upcoming planned.

Usage:
  python3 scripts/build/batch_outage.py --pull --cache-dir DIR \
      --out sidecar.json
  python3 scripts/build/batch_outage.py --build-reliability \
      --log DIR/observations.jsonl --out reliability.json

Issue #780: --pull also appends one compact record per successful pull
to <cache-dir>/observations.jsonl (rolling 90-day log, city rollup);
--build-reliability aggregates the log into the servable 28-day
reliability table (pole built/outage/reliability.json, honest 503
until the first build).
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

#: Live JSON endpoint (keyless, verified 2026-09-19).
OUTAGE_URL = ("https://rikkekaart.elektrilevi.ee/"
              "geoserver-api/GetApplicationData")

#: Freshness ceiling in seconds (live data, issue constraint).
TTL_S = 300

#: Observation-log filename inside the cache dir (issue #780: every
#: 5-min pull appends one compact line — pole ``cache/`` convention,
#: rolling raw, NOT served; the aggregation below reads it).
OBSERVATIONS_NAME = "observations.jsonl"

#: Log retention in days (rolling log, 288 pulls/day; ~300 B/line ->
#: ~8 MB at full retention — prune policy, documented).
RETAIN_DAYS = 90

#: Reliability window in days (documented metric window, issue #780).
RELIABILITY_WINDOW_DAYS = 28

#: Expected pulls per day at the 5-min cadence (coverage denominator).
EXPECTED_PULLS_PER_DAY = 288

#: Logged grain: city rollup first (Tallinn row + Harju fallback row
#: only — the 99-area verbatim sidecar would be ~37 MB/day; open
#: design question "grain" decided for this slice, documented).
LOG_LABELS = ("Tallinn", "Harju maakond")

#: Observed-reliability metric (open design question "metric" decided
#: for this slice: fault/planned observation counts + affected-
#: customer sums over the window — SAIDI-like thinking, never SAIDI).
RELIABILITY_METRIC = (
    "vaadeldud töökindlus: aktiivsete rikete (fc/fcc>0) ja plaaniliste "
    "(pc/pcc>0) vaatlusarv + mõjutatud klientide (fcc/pcc) summa aknas "
    "(SAIDI-sarnane mõtlemine, MITTE SAIDI-garantii)"
)

#: Identifying user agent for the polite pull.
OUTAGE_UA = ("home-finder outage ingest (polite 5-min pulls, single GET, "
             "file cache; contact via GitHub home-finder)")

#: Double-encoded envelope keys (outer JSON string -> scopes.p.*).
ENVELOPE_TABLES = ("areas", "dynareas", "outages")


def decode_application_data(body: str) -> Optional[Dict[str, Any]]:
    """Parse the double-encoded GetApplicationData body (pure).

    Returns ``{"areas": [...], "dynareas": [...], "outages": [...]}``
    with list tables, or None when the envelope is missing or
    malformed (transport garbage is never a record).
    """
    try:
        outer = json.loads(body)
    except ValueError:
        return None
    if isinstance(outer, str):
        try:
            outer = json.loads(outer)
        except ValueError:
            return None
    if not isinstance(outer, dict):
        return None
    scopes = outer.get("scopes")
    if not isinstance(scopes, dict):
        return None
    inner = scopes.get("p")
    if not isinstance(inner, dict):
        return None
    out: Dict[str, Any] = {}
    for table in ENVELOPE_TABLES:
        rows = inner.get(table)
        out[table] = [r for r in rows if isinstance(r, dict)] \
            if isinstance(rows, list) else []
    return out


def build_sidecar(decoded: Dict[str, Any],
                  now: Optional[datetime] = None) -> Dict[str, Any]:
    """Decoded tables -> timestamped sidecar (pure).

    Keeps every area row verbatim (dims pick Tallinn/Harju — no
    pre-scored selection) plus outage-type tallies for the doc
    record. Raises ValueError on a table-less payload.
    """
    if not isinstance(decoded, dict) or not decoded.get("areas"):
        raise ValueError("tühjendatud väljavõte (areas-tabel puudub)")
    at = now or datetime.now(tz=timezone.utc)
    tallies: Dict[str, int] = {}
    for row in decoded.get("outages", []):
        t = row.get("t")
        if isinstance(t, str):
            tallies[t] = tallies.get(t, 0) + 1
    return {
        "pulled_at": at.isoformat(),
        "ttl_s": TTL_S,
        "source": OUTAGE_URL,
        "areas": decoded["areas"],
        "n_dynareas": len(decoded.get("dynareas", [])),
        "outage_tallies": tallies,
    }


def fetch_application_data(cache_dir: str, timeout_s: int = 30) -> str:
    """Single polite GET of the live JSON (never cached as data on error).

    Transport errors RAISE (never written as data); HTTP 429 raises
    immediately (stop signal, no retry). Returns the raw body text
    (callers decode + timestamp it — the cache file is the sidecar,
    rewritten on every pull).
    """
    req = urllib.request.Request(OUTAGE_URL,
                                 headers={"User-Agent": OUTAGE_UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            status = getattr(resp, "status", 200)
            if status == 429:
                raise RuntimeError("HTTP 429 — stop, do not retry: "
                                   + OUTAGE_URL)
            if status != 200:
                raise RuntimeError("HTTP %s: %s" % (status, OUTAGE_URL))
            raw = resp.read()
    except Exception:
        raise
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("vastus ei ole UTF-8: %s" % exc)


def _int_or_none(v) -> Optional[int]:
    """Finite non-bool number as int, else None (never faked from junk)."""
    if isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):
        return None
    return int(f)


def observation_from_sidecar(sidecar: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Built sidecar -> one compact log record (pure, issue #780).

    Keeps the city-rollup counters (LOG_LABELS) + outage tallies with
    the pull timestamp. Returns None when no logged label is present
    (nothing scoreable — never logged as data).
    """
    if not isinstance(sidecar, dict):
        return None
    ts = sidecar.get("pulled_at")
    if not isinstance(ts, str):
        return None
    areas: Dict[str, Any] = {}
    for row in sidecar.get("areas", []):
        if not isinstance(row, dict):
            continue
        label = row.get("label")
        if label not in LOG_LABELS:
            continue
        areas[str(label)] = {
            k: _int_or_none(row.get(k))
            for k in ("fc", "fcc", "pc", "pcc", "uc", "ucc")
        }
    if not areas:
        return None
    tallies = sidecar.get("outage_tallies")
    return {
        "ts": ts,
        "areas": areas,
        "tallies": {k: v for k, v in tallies.items()
                    if isinstance(k, str) and isinstance(v, int)}
        if isinstance(tallies, dict) else {},
    }


def append_observation(log_path: str, obs: Dict[str, Any]) -> None:
    """Append one observation line (creates parent dirs; atomic line)."""
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obs, ensure_ascii=False) + "\n")


def read_observations(log_path: str) -> List[Dict[str, Any]]:
    """Read the log, skipping malformed lines (corrupt lines are gaps,
    never data — mirrors the sidecar honesty contract)."""
    out: List[Dict[str, Any]] = []
    try:
        with open(log_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and isinstance(rec.get("ts"), str) \
                and isinstance(rec.get("areas"), dict):
            out.append(rec)
    return out


def prune_observations(log_path: str, retain_days: int = RETAIN_DAYS,
                       now: Optional[datetime] = None) -> int:
    """Drop log lines older than retain_days (rolling log, issue #780).

    Malformed lines are dropped too (never data). Returns surviving
    count. A missing log is a no-op returning 0.
    """
    at = now or datetime.now(tz=timezone.utc)
    try:
        with open(log_path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return 0
    cutoff = at.timestamp() - retain_days * 86400
    kept: List[str] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
            ts = datetime.fromisoformat(str(rec.get("ts", "")))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, AttributeError):
            continue
        if ts.timestamp() >= cutoff:
            kept.append(line)
    tmp = log_path + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("".join(line + "\n" for line in kept))
    os.replace(tmp, log_path)
    return len(kept)


def build_reliability(observations: List[Dict[str, Any]],
                      window_days: int = RELIABILITY_WINDOW_DAYS,
                      now: Optional[datetime] = None) -> Dict[str, Any]:
    """Observation log -> servable reliability table (pure, issue #780).

    Filters records to the trailing window_days, then aggregates per
    label: n_obs, fault_obs (fc/fcc > 0 pulls), planned_obs (pc/pcc >
    0), upcoming_obs (uc/ucc > 0), fault_customers (fcc sum),
    planned_customers (pcc sum), coverage (n_obs / expected pulls).
    Missing counters stay unknown for their class (never zero-filled
    into calm — same rule as the hetkeseis scorer).
    """
    at = now or datetime.now(tz=timezone.utc)
    cutoff = at.timestamp() - window_days * 86400
    expected = window_days * EXPECTED_PULLS_PER_DAY
    areas: Dict[str, Dict[str, Any]] = {}
    n_total = 0
    for rec in observations:
        try:
            ts = datetime.fromisoformat(str(rec.get("ts", "")))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if ts.timestamp() < cutoff:
            continue
        n_total += 1
        rows = rec.get("areas")
        if not isinstance(rows, dict):
            continue
        for label, counters in rows.items():
            if not isinstance(label, str) or not isinstance(counters, dict):
                continue
            agg = areas.setdefault(label, {
                "n_obs": 0, "fault_obs": 0, "planned_obs": 0,
                "upcoming_obs": 0, "fault_customers": 0,
                "planned_customers": 0,
            })
            agg["n_obs"] += 1
            fc, fcc = counters.get("fc"), counters.get("fcc")
            pc, pcc = counters.get("pc"), counters.get("pcc")
            uc, ucc = counters.get("uc"), counters.get("ucc")
            if (isinstance(fc, int) and fc > 0) or \
                    (isinstance(fcc, int) and fcc > 0):
                agg["fault_obs"] += 1
            if (isinstance(pc, int) and pc > 0) or \
                    (isinstance(pcc, int) and pcc > 0):
                agg["planned_obs"] += 1
            if (isinstance(uc, int) and uc > 0) or \
                    (isinstance(ucc, int) and ucc > 0):
                agg["upcoming_obs"] += 1
            if isinstance(fcc, int):
                agg["fault_customers"] += fcc
            if isinstance(pcc, int):
                agg["planned_customers"] += pcc
    for agg in areas.values():
        agg["coverage"] = round(agg["n_obs"] / expected, 4) if expected else 0.0
    return {
        "built_at": at.isoformat(),
        "window_days": window_days,
        "metric": RELIABILITY_METRIC,
        "expected_pulls_per_day": EXPECTED_PULLS_PER_DAY,
        "n_obs_total": n_total,
        "areas": areas,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI: --pull fetches live and writes the sidecar; --build-reliability
    aggregates the observation log into the servable table. Returns exit code."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pull", action="store_true",
                    help="fetch GetApplicationData and write the sidecar")
    ap.add_argument("--build-reliability", action="store_true",
                    help="aggregate the observation log into reliability.json")
    ap.add_argument("--cache-dir", default="/tmp/hf-outage")
    ap.add_argument("--out", default=None,
                    help="sidecar path (default <cache-dir>/outage-table.json)")
    ap.add_argument("--log", default=None,
                    help="observation log path "
                         "(default <cache-dir>/observations.jsonl)")
    ap.add_argument("--window-days", type=int,
                    default=RELIABILITY_WINDOW_DAYS)
    ap.add_argument("--retain-days", type=int, default=RETAIN_DAYS)
    args = ap.parse_args(argv)
    log_path = args.log or os.path.join(args.cache_dir, OBSERVATIONS_NAME)
    if args.build_reliability:
        table = build_reliability(read_observations(log_path),
                                  window_days=args.window_days)
        out = args.out or os.path.join(args.cache_dir, "reliability.json")
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        tmp = out + ".part"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(table, fh, ensure_ascii=False)
        os.replace(tmp, out)
        print("wrote reliability (%d obs, %d d window) -> %s"
              % (table["n_obs_total"], table["window_days"], out))
        return 0
    if not args.pull:
        print("error: keeldun - elavat tõmmet pole (--pull puudub): "
              "hetkeseisu ei ehitata vahemälust, ainult päris "
              "GetApplicationData päringust.", file=sys.stderr)
        return 2
    try:
        body = fetch_application_data(args.cache_dir)
        decoded = decode_application_data(body)
        if decoded is None:
            print("vastuse kest ei parsinud (EI OLE kirjet)", file=sys.stderr)
            return 1
        sidecar = build_sidecar(decoded)
    except Exception as exc:  # transport/HTTP errors stay errors
        print("tõmme ebaõnnestus: %s" % exc, file=sys.stderr)
        return 1
    out = args.out or os.path.join(args.cache_dir, "outage-table.json")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    tmp = out + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(sidecar, fh, ensure_ascii=False)
    os.replace(tmp, out)
    # Issue #780: every successful pull appends one compact record to
    # the rolling log (failures/corrupt pulls return above — the old
    # sidecar AND the log stay untouched: no loss on failure, corrupt
    # never logged as data), then prunes past retention.
    obs = observation_from_sidecar(sidecar)
    if obs is not None:
        append_observation(log_path, obs)
    prune_observations(log_path, retain_days=args.retain_days)
    print("wrote %d areas -> %s" % (len(sidecar["areas"]), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
