"""Keyed TarkTee DATEX road-restrictions harvester (issue #681).

Runs ONLY on a user-supplied env key (DATEX_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test); it travels only
as the X-DATEX-API-KEY request header of the single polite GET.

ToS step-zero verdict (docs/datex_restrictions.md section 0):
SHORT-TERM CACHE ONLY. No sidecars are committed and no tables are
stored: --pull fills a git-ignored operator cache dir (TTL-capped at
24 h, daily refresh), --build reads that cache (or a fixture file)
and prints the table to stdout. Built tables live on the harvest pole
only (pole built/datex-restrictions/table.json, served with honest
503 until first keyed pull).

Endpoint profile (verified live 2026-09-18 per the issue): DATEX II
2.3 XML, ``GET /api/v1/datex/restrictions`` (1316 situations at the
time). Feed slug and base URL are operator-overridable
(--feed / DATEX_BASE_URL) so the first keyed run can confirm them
against the gateway registration; non-200 feeds are skipped honestly
(never faked, never cached).

Usage:
  DATEX_API_KEY=... python3 scripts/build/batch_datex_restrictions.py \\
      --pull --build --cache-dir DIR
Key placement: export the variable in the operator shell only (see
docs/datex_restrictions.md section 7); never commit it, never put it
in repo files.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Optional

#: Env var carrying the user-supplied key (never committed, never
#: printed, never written to any file - pinned by test).
DATEX_KEY_ENV = "DATEX_API_KEY"

#: Base-URL override (operator shell only, never committed). Default is
#: the host named by the DATEX profile / feed-registry notes; the
#: first keyed run confirms it.
DATEX_BASE_ENV = "DATEX_BASE_URL"
DATEX_BASE_DEFAULT = "https://tarktee.transpordiamet.ee"

#: Feed slug (operator-overridable via --feed; "restrictions" is the
#: slug verified live 2026-09-18 per the issue).
FEED_DEFAULT = "restrictions"

#: Short-lived cache only (ToS verdict, docs/datex_restrictions.md
#: section 0): restrictions refresh daily -> 24 h TTL cap.
TTL_S = 24 * 3600

#: Harvest budget: one GET per pull, daily cadence -> 4 calls per
#: 24 h window leaves headroom for operator retries; 429 = stop.
QUOTA_MAX_CALLS = 4

#: Identifying user agent for the polite pull.
UA = "home-finder datex-restrictions harvest (keyed, quota-capped)"

#: Minimum plausible feed body.
MIN_BYTES = 64

CACHE_FILE = "datex_restrictions.xml"
QUOTA_FILE = "datex_restrictions_quota.json"


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


def _local(tag: str) -> str:
    """Strip any XML namespace from a tag. Pure."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def fetch_feed(feed: str, cache_dir: str, filename: str = CACHE_FILE,
               api_key: Optional[str] = None,
               base_url: Optional[str] = None,
               ttl_s: int = TTL_S) -> Optional[str]:
    """Polite keyed DATEX pull for one feed. Path or None.

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
    dest_path = os.path.join(cache_dir, filename)
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
                     "Accept": "application/xml"})
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


def parse_restrictions(path: str) -> List[dict]:
    """Parse a cached DATEX 2.3 SituationPublication body. Offline.

    Returns per-situation dicts: ``situation_id``, ``record`` (local
    record-element name, e.g. MaintenanceWorks), ``severity`` (when
    present). Namespace-tolerant; unparseable bodies yield [] (honest
    empty, never guessed).
    """
    try:
        with open(path, "rb") as fh:
            root = ET.fromstring(fh.read())
    except (OSError, ET.ParseError):
        return []
    out = []
    for sit in root.iter():
        if _local(sit.tag) != "situation":
            continue
        sid = sit.get("id")
        found = False
        for child in sit.iter():
            loc = _local(child.tag)
            if loc == "situationRecord":
                loc = child.get(
                    "{http://www.w3.org/2001/XMLSchema-instance}type",
                    "situationRecord")
            if loc in ("MaintenanceWorks", "RoadOrCarriagewayOrLaneManagement",
                       "SpeedManagement", "GeneralNetworkManagement",
                       "ReroutingManagement", "GeneralObstruction",
                       "EnvironmentalObstruction", "AnimalPresenceObstruction",
                       "PublicEvent", "WeatherRelatedRoadConditions",
                       "situationRecord"):
                sev = None
                for sub in child.iter():
                    if _local(sub.tag) == "severity":
                        sev = (sub.text or "").strip() or None
                        break
                out.append({"situation_id": sid, "record": loc,
                            "severity": sev})
                found = True
        if not found:
            out.append({"situation_id": sid, "record": None,
                        "severity": None})
    return out


def build_table(rows: List[dict]) -> dict:
    """Per-situation rows -> snapshot table. Pure.

    Returns ``{"rows": [...], "counts"}`` with per-record-type tallies.
    Unmeasured feeds keep honest empties, never guesses.
    """
    out_rows = [r for r in rows if isinstance(r, dict)]
    by_record: dict = {}
    for r in out_rows:
        by_record[r.get("record") or "teadmata"] = (
            by_record.get(r.get("record") or "teadmata", 0) + 1)
    return {"rows": out_rows,
            "counts": {"total": len(out_rows), "by_record": by_record}}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed DATEX restrictions pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--feed", default=FEED_DEFAULT,
                    help="DATEX feed slug (default: restrictions).")
    ap.add_argument("--fixture", default=None,
                    help="Fixture XML body for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if not os.environ.get(DATEX_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TarkTee DATEX võti selles terminalis (vt "
              "docs/datex_restrictions.md §7); midagi ei päritud, midagi "
              "ei kirjutatud." % DATEX_KEY_ENV, file=sys.stderr)
        return 2
    if args.pull:
        dest = fetch_feed(args.feed, args.cache_dir)
        if dest is None:
            if _quota_used(args.cache_dir) >= QUOTA_MAX_CALLS:
                print("error: keeldun - DATEX kvoot on täis (%d "
                      "päringut / 24 h); midagi ei päritud."
                      % QUOTA_MAX_CALLS, file=sys.stderr)
                return 2
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver või transport/viga) - midagi uut ei "
                  "puhvritatud.", file=sys.stderr)
            return 1
        print("ok: DATEX voog '%s' puhvritatud (%s)"
              % (args.feed, dest))
    if args.build:
        if args.fixture:
            rows = parse_restrictions(args.fixture)
        else:
            cached = os.path.join(args.cache_dir, CACHE_FILE)
            if not os.path.exists(cached):
                print("error: puhvritatud voogu pole - käivita --pull "
                      "võtmega või anna --fixture.", file=sys.stderr)
                return 1
            rows = parse_restrictions(cached)
        table = build_table(rows)
        print(json.dumps(table["counts"], ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
