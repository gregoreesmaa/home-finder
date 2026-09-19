"""Keyed TarkTee DATEX SRTI safety-bundle harvester (issue #682).

Runs ONLY on a user-supplied env key (DATEX_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test); it travels only
as the X-DATEX-API-KEY request header of the polite GETs.

ToS step-zero verdict (docs/datex_restrictions.md section 0, pasted
in docs/datex_srti.md section 0): SHORT-TERM CACHE ONLY. No sidecars
are committed and no tables are stored: --pull fills a git-ignored
operator cache dir (TTL-capped at 6 h), --build reads that cache (or
a fixture file) and prints the table to stdout. Built tables live on
the harvest pole only (pole built/datex-srti/table.json, served with
honest 503 until first keyed pull).

Endpoint profile (verified live 2026-09-18 per the issues): DATEX II
3.6 SRTI JSON, ``GET /api/v1/datex/<feed>``; temporarySlipperyRoad
returned 200 EMPTY (honest off-season empty - never faked). The
bundle covers the seven SRTI classes of profile section 6.14
(slippery, animals/people/obstacles/debris, accident areas, short
roadworks, visibility, blockage, exceptional weather). Feed slugs are
operator-overridable (--feeds): only temporarySlipperyRoad is live-
verified, the rest are confirmed at the first keyed run; non-200
feeds are skipped honestly (never faked, never cached).

Usage:
  DATEX_API_KEY=... python3 scripts/build/batch_datex_srti.py \\
      --pull --build --cache-dir DIR [--feeds temporarySlipperyRoad,...]
Key placement: export the variable in the operator shell only (see
docs/datex_srti.md section 7); never commit it, never put it in repo
files.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any, List, Optional

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
DATEX_KEY_ENV = "DATEX_API_KEY"

#: Base-URL override (operator shell only, never committed).
DATEX_BASE_ENV = "DATEX_BASE_URL"
DATEX_BASE_DEFAULT = "https://tarktee.transpordiamet.ee"

#: SRTI bundle (profile section 6.14). Only temporarySlipperyRoad is
#: live-verified (2026-09-18, 200 empty); the rest are confirmed at
#: the first keyed run via --feeds. Non-200 feeds skip honestly.
FEEDS_DEFAULT = [
    "temporarySlipperyRoad",
    "animalsPeopleObstaclesDebris",
    "unprotectedAccidentArea",
    "shortTermRoadWorks",
    "reducedVisibility",
    "unmanagedBlockage",
    "exceptionalWeather",
]

#: Short-lived cache only (ToS verdict): safety bundle refreshes 4x
#: per day -> 6 h TTL cap.
TTL_S = 6 * 3600

#: Harvest budget: 7 feeds x 4 pulls/day = 28; cap 32 per 24 h window
#: leaves headroom; 429 = stop.
QUOTA_MAX_CALLS = 32

#: Identifying user agent for the polite pull.
UA = "home-finder datex-srti harvest (keyed, quota-capped)"

#: Minimum plausible feed body.
MIN_BYTES = 16

CACHE_PREFIX = "datex_srti_"
QUOTA_FILE = "datex_srti_quota.json"

#: Record-kind enum keys that identify an SRTI situation record when
#: the DATEX JSON carries no explicit xsi:type. Pure lookup.
KIND_KEYS = (
    "weatherRelatedRoadConditionType",
    "generalObstructionType",
    "environmentalObstructionType",
    "animalPresenceType",
    "poorEnvironmentType",
    "trafficConstrictionType",
    "roadMaintenanceType",
    "obstructionType",
    "situationRecordType",
)


def _quota_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, QUOTA_FILE)


def _quota_used(cache_dir: str) -> int:
    """Keyed calls already spent in the current TTL window. Pure."""
    try:
        with open(_quota_path(cache_dir), encoding="utf-8") as fh:
            rec = json.load(fh)
        if time.time() - float(rec.get("window_start", 0)) > TTL_S:
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
            if time.time() - float(rec.get("window_start", 0)) <= TTL_S:
                start = float(rec["window_start"])
                used = max(0, int(rec.get("used", 0)))
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            pass
        with open(_quota_path(cache_dir), "w", encoding="utf-8") as fh:
            json.dump({"window_start": start, "used": used + 1}, fh)
    except OSError:
        pass


def fetch_feed(feed: str, cache_dir: str,
               api_key: Optional[str] = None,
               base_url: Optional[str] = None,
               ttl_s: int = TTL_S) -> Optional[str]:
    """Polite keyed DATEX pull for one SRTI feed. Path or None.

    Key from the DATEX_API_KEY env (or the explicit arg - tests only,
    never a committed secret). No key, spent quota, or fresh cache: NO
    request. Otherwise one GET with the X-DATEX-API-KEY header; the
    body is stored only on HTTP 200 over MIN_BYTES, else None
    (transport errors never cached, 429 is a stop signal, no retries).
    Scorers never call this.
    """
    key = api_key or os.environ.get(DATEX_KEY_ENV)
    if not key:
        return None
    os.makedirs(cache_dir, exist_ok=True)
    dest_path = os.path.join(cache_dir, CACHE_PREFIX + feed + ".json")
    try:
        if os.path.exists(dest_path):
            age = time.time() - os.path.getmtime(dest_path)
            if age < ttl_s:
                return dest_path
    except OSError:
        return None
    if _quota_used(cache_dir) >= QUOTA_MAX_CALLS:
        return None
    base = (base_url or os.environ.get(DATEX_BASE_ENV)
            or DATEX_BASE_DEFAULT).rstrip("/")
    url = "%s/api/v1/datex/%s" % (base, feed)
    try:
        req = urllib.request.Request(
            url, method="GET",
            headers={"User-Agent": UA, "X-DATEX-API-KEY": key,
                     "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                return None
            body = resp.read()
        if len(body) < MIN_BYTES:
            return None
        with open(dest_path, "wb") as fh:
            fh.write(body)
        _quota_spend(cache_dir)
        return dest_path
    except Exception:
        return None


def _record_kind(node: Any) -> Optional[str]:
    """Best-effort SRTI record kind of a JSON node. Pure."""
    if isinstance(node, dict):
        for key in KIND_KEYS:
            val = node.get(key)
            if isinstance(val, str) and val:
                return val
        for val in node.values():
            found = _record_kind(val)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _record_kind(item)
            if found:
                return found
    return None


def _find_situations(node: Any) -> List[dict]:
    """Collect situation dicts under any *-situation(s) key. Pure."""
    found: List[dict] = []
    if isinstance(node, dict):
        for key, val in node.items():
            if "situation" in key.lower() and isinstance(val, list):
                found.extend(i for i in val if isinstance(i, dict))
            else:
                found.extend(_find_situations(val))
    elif isinstance(node, list):
        for item in node:
            found.extend(_find_situations(item))
    return found


def parse_srti(path: str) -> List[dict]:
    """Parse a cached DATEX 3.6 SRTI JSON body. Offline.

    Returns per-situation dicts: ``situation_id``, ``kind``
    (best-effort record kind, None when absent). Honest empties
    (off-season 200-empty bodies) yield [] - never faked.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    rows = []
    for sit in _find_situations(data):
        sid = sit.get("id") if isinstance(sit.get("id"), str) else None
        rows.append({"situation_id": sid, "kind": _record_kind(sit)})
    return rows


def build_table(rows: List[dict]) -> dict:
    """Per-situation rows -> snapshot table. Pure."""
    out_rows = [r for r in rows if isinstance(r, dict)]
    by_kind: dict = {}
    for r in out_rows:
        by_kind[r.get("kind") or "teadmata"] = (
            by_kind.get(r.get("kind") or "teadmata", 0) + 1)
    return {"rows": out_rows,
            "counts": {"total": len(out_rows), "by_kind": by_kind}}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed DATEX SRTI pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--feeds", default=",".join(FEEDS_DEFAULT),
                    help="Comma-separated SRTI feed slugs.")
    ap.add_argument("--fixture", default=None,
                    help="Fixture JSON body for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True
    feeds = [f.strip() for f in args.feeds.split(",") if f.strip()]

    if not os.environ.get(DATEX_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TarkTee DATEX võti selles terminalis (vt "
              "docs/datex_srti.md §7); midagi ei päritud, midagi "
              "ei kirjutatud." % DATEX_KEY_ENV, file=sys.stderr)
        return 2
    if args.pull:
        pulled = 0
        for feed in feeds:
            if fetch_feed(feed, args.cache_dir) is not None:
                pulled += 1
        if pulled == 0:
            if _quota_used(args.cache_dir) >= QUOTA_MAX_CALLS:
                print("error: keeldun - DATEX kvoot on täis (%d "
                      "päringut / 24 h); midagi ei päritud."
                      % QUOTA_MAX_CALLS, file=sys.stderr)
                return 2
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver või transport/viga) - midagi uut ei "
                  "puhvritatud.", file=sys.stderr)
            return 1
        print("ok: %d SRTI-voogu puhvritatud (%s)"
              % (pulled, args.cache_dir), file=sys.stderr)
    if args.build:
        rows: List[dict] = []
        if args.fixture:
            rows = parse_srti(args.fixture)
        else:
            import glob
            for path in sorted(glob.glob(os.path.join(
                    args.cache_dir, CACHE_PREFIX + "*.json"))):
                if os.path.basename(path) == QUOTA_FILE:
                    continue
                rows.extend(parse_srti(path))
            if not rows and not glob.glob(os.path.join(
                    args.cache_dir, CACHE_PREFIX + "*.json")):
                print("error: puhvritatud vooge pole - käivita --pull "
                      "võtmega või anna --fixture.", file=sys.stderr)
                return 1
        table = build_table(rows)
        # STDOUT CONTRACT (#776): exactly one JSON doc, the full table —
        # the pole wrapper redirects stdout into built/<feed>/table.json
        # and the web route parses it (rows + counts). Human status rides
        # stderr, never stdout.
        print(json.dumps(table, ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
