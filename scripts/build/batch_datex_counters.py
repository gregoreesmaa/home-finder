"""Keyed TarkTee DATEX traffic-counter harvester (issue #684).

Runs ONLY on a user-supplied env key (DATEX_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test); it travels only
as the X-DATEX-API-KEY request header of the polite GETs.

ToS step-zero verdict (docs/datex_restrictions.md section 0, pasted
in docs/datex_counters.md section 0): SHORT-TERM CACHE ONLY. No
sidecars are committed and no tables are stored: --pull fills a
git-ignored operator cache dir (TTL-capped at 1 h - counter flow is
measured in 15-minute intervals per profile section 6.5), --build
reads that cache (or a fixture file) and prints the table to stdout.
Built tables live on the harvest pole only (pole
built/datex-counters/table.json, served with honest 503 until first
keyed pull).

Endpoint profile: DATEX II 2.0 XML, ``GET /api/v1/datex/<feed>`` -
counter site locations (MeasurementSiteTablePublication,
TRAFFIC_COUNTER_SITES) plus measured values (MeasuredDataPublication:
vehicle flow in vehicles/hour + average speed). Feed slugs are
operator-overridable (--feeds); non-200 feeds skip honestly (never
faked, never cached).

Usage:
  DATEX_API_KEY=... python3 scripts/build/batch_datex_counters.py \\
      --pull --build --cache-dir DIR [--feeds trafficCounterSites,traffic]
Key placement: export the variable in the operator shell only (see
docs/datex_counters.md section 7); never commit it, never put it in
repo files.
"""

import argparse
import glob
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

#: Base-URL override (operator shell only, never committed).
DATEX_BASE_ENV = "DATEX_BASE_URL"
DATEX_BASE_DEFAULT = "https://tarktee.transpordiamet.ee"

#: Counter-site + measured-value feeds (profile sections 6.1/6.5).
#: Slugs are confirmed at the first keyed run via --feeds; non-200
#: feeds skip honestly.
FEEDS_DEFAULT = ["trafficCounterSites", "traffic"]

#: Short-lived cache only (ToS verdict): flow measured in 15 min
#: intervals -> 1 h TTL cap.
TTL_S = 1 * 3600

#: Harvest budget: 2 feeds x 24 pulls/day = 48; cap 50 per 24 h
#: window; 429 = stop.
QUOTA_MAX_CALLS = 50

#: Identifying user agent for the polite pull.
UA = "home-finder datex-counters harvest (keyed, quota-capped)"

#: Minimum plausible feed body.
MIN_BYTES = 64

CACHE_PREFIX = "datex_counters_"
QUOTA_FILE = "datex_counters_quota.json"


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


def fetch_feed(feed: str, cache_dir: str,
               api_key: Optional[str] = None,
               base_url: Optional[str] = None,
               ttl_s: int = TTL_S) -> Optional[str]:
    """Polite keyed DATEX pull for one counter feed. Path or None.

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
    dest_path = os.path.join(cache_dir, CACHE_PREFIX + feed + ".xml")
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


def _text_at(node: ET.Element, local: str) -> Optional[str]:
    """First descendant text under a namespace-stripped tag. Pure."""
    for sub in node.iter():
        if _local(sub.tag) == local and (sub.text or "").strip():
            return sub.text.strip()
    return None


def _as_float(text: Optional[str]) -> Optional[float]:
    try:
        return float(text) if text else None
    except ValueError:
        return None


def parse_counters(path: str) -> List[dict]:
    """Parse a cached counter site/measured XML body. Offline.

    Returns per-counter dicts: ``counter_id`` (UUID+direction when
    present), ``lat``/``lon`` (float|None), ``flow_vph``
    (float|None, vehicles/hour), ``speed_kmh`` (float|None).
    Namespace-tolerant; unparseable bodies yield [] (honest empty,
    never guessed).
    """
    try:
        with open(path, "rb") as fh:
            root = ET.fromstring(fh.read())
    except (OSError, ET.ParseError):
        return []
    counters: dict = {}
    for node in root.iter():
        loc = _local(node.tag)
        if loc == "measurementSite":
            cid = node.get("id")
            counters[cid] = {
                "counter_id": cid,
                "lat": _as_float(_text_at(node, "latitude")),
                "lon": _as_float(_text_at(node, "longitude")),
                "flow_vph": None, "speed_kmh": None}
        elif loc == "siteMeasurements":
            ref = None
            for sub in node.iter():
                if _local(sub.tag) == "measurementSiteReference":
                    ref = sub.get("id") or (sub.text or "").strip()
                    break
            flow = _as_float(_text_at(node, "trafficFlow"))
            if flow is None:
                flow = _as_float(_text_at(node, "vehicleFlowRate"))
            speed = _as_float(_text_at(node, "averageVehicleSpeed"))
            if speed is None:
                speed = _as_float(_text_at(node, "speed"))
            key = ref or "teadmata"
            rec = counters.setdefault(
                key, {"counter_id": key, "lat": None, "lon": None,
                      "flow_vph": None, "speed_kmh": None})
            if flow is not None:
                rec["flow_vph"] = flow
            if speed is not None:
                rec["speed_kmh"] = speed
    return list(counters.values())


def build_table(rows: List[dict]) -> dict:
    """Per-counter rows -> snapshot table. Pure."""
    out_rows = [r for r in rows if isinstance(r, dict)]
    measured = sum(1 for r in out_rows
                   if r.get("flow_vph") is not None
                   or r.get("speed_kmh") is not None)
    located = sum(1 for r in out_rows
                  if r.get("lat") is not None and r.get("lon") is not None)
    return {"rows": out_rows,
            "counts": {"counters": len(out_rows), "measured": measured,
                       "located": located}}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed DATEX counters pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--feeds", default=",".join(FEEDS_DEFAULT),
                    help="Comma-separated counter feed slugs.")
    ap.add_argument("--fixture", default=None,
                    help="Fixture XML body for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True
    feeds = [f.strip() for f in args.feeds.split(",") if f.strip()]

    if not os.environ.get(DATEX_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TarkTee DATEX võti selles terminalis (vt "
              "docs/datex_counters.md §7); midagi ei päritud, midagi "
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
        print("ok: %d loendurivoogu puhvritatud (%s)"
              % (pulled, args.cache_dir), file=sys.stderr)
    if args.build:
        rows: List[dict] = []
        if args.fixture:
            rows = parse_counters(args.fixture)
        else:
            paths = sorted(glob.glob(os.path.join(
                args.cache_dir, CACHE_PREFIX + "*.xml")))
            if not paths:
                print("error: puhvritatud vooge pole - käivita --pull "
                      "võtmega või anna --fixture.", file=sys.stderr)
                return 1
            merged: dict = {}
            for path in paths:
                for rec in parse_counters(path):
                    key = rec.get("counter_id") or "teadmata"
                    slot = merged.setdefault(
                        key, {"counter_id": key, "lat": None, "lon": None,
                              "flow_vph": None, "speed_kmh": None})
                    for field in ("lat", "lon", "flow_vph", "speed_kmh"):
                        if rec.get(field) is not None:
                            slot[field] = rec[field]
            rows = list(merged.values())
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
