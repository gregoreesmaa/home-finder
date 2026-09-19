"""Keyed TarkTee DATEX truck-parking harvester (issue #686).

Runs ONLY on a user-supplied env key (DATEX_API_KEY) - without it the
command hard-refuses (exit 2, tested on both --pull and --build paths)
having touched nothing: no request, no files. The key is never
printed, never written to any file (pinned by test); it travels only
as the X-DATEX-API-KEY request header of the polite GET.

ToS step-zero verdict (docs/datex_restrictions.md section 0, pasted
in docs/datex_truckpark.md section 0): SHORT-TERM CACHE ONLY. No
sidecars are committed and no tables are stored: --pull fills a
git-ignored operator cache dir (TTL-capped at 30 d - static
locations, monthly refresh per the issue), --build reads that cache
(or a fixture file) and prints the table to stdout. Built tables live
on the harvest pole only (pole built/datex-truckpark/table.json,
served with honest 503 until first keyed pull).

Endpoint profile: DATEX II 2.3 XML GenericPublication with a
parkingTablePublication extension (profile section 6.11), UUID ids.
Static amenity/disamenity: logistics-worker amenity nearby,
heavy-vehicle noise/traffic disamenity next door. Feed slug is
operator-overridable (--feed); non-200 skips honestly (never faked,
never cached).

Usage:
  DATEX_API_KEY=... python3 scripts/build/batch_datex_truckpark.py \\
      --pull --build --cache-dir DIR [--feed truckParking]
Key placement: export the variable in the operator shell only (see
docs/datex_truckpark.md section 7); never commit it, never put it in
repo files.
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

#: Base-URL override (operator shell only, never committed).
DATEX_BASE_ENV = "DATEX_BASE_URL"
DATEX_BASE_DEFAULT = "https://tarktee.transpordiamet.ee"

#: Truck-parking feed (profile section 6.11, GenericPublication +
#: parkingTablePublication extension). Slug confirmed at the first
#: keyed run via --feed; non-200 skips honestly.
FEED_DEFAULT = "truckParking"

#: Short-lived cache only (ToS verdict): static locations, monthly
#: refresh -> 30 d TTL cap.
TTL_S = 30 * 24 * 3600

#: Harvest budget: one GET per pull, monthly cadence -> 4 calls per
#: 30 d window leaves headroom for operator retries; 429 = stop.
QUOTA_MAX_CALLS = 4

#: Identifying user agent for the polite pull.
UA = "home-finder datex-truckpark harvest (keyed, quota-capped)"

#: Minimum plausible feed body.
MIN_BYTES = 64

CACHE_FILE = "datex_truckpark.xml"
QUOTA_FILE = "datex_truckpark_quota.json"


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
    """Polite keyed DATEX pull for the truck-parking feed. Path or None.

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


def _as_int(text: Optional[str]) -> Optional[int]:
    try:
        return int(float(text)) if text else None
    except ValueError:
        return None


def parse_truckpark(path: str) -> List[dict]:
    """Parse a cached truck-parking GenericPublication body. Offline.

    Returns per-site dicts: ``site_id`` (UUID when present), ``name``
    (when present), ``lat``/``lon`` (float|None), ``spaces``
    (int|None). Namespace-tolerant; unparseable bodies yield []
    (honest empty, never guessed).
    """
    try:
        with open(path, "rb") as fh:
            root = ET.fromstring(fh.read())
    except (OSError, ET.ParseError):
        return []
    sites: dict = {}
    for node in root.iter():
        loc = _local(node.tag)
        if loc in ("parkingSite", "truckParkingSite",
                   "parkingRecord", "parkingSpace"):
            sid = node.get("id")
            name = (_text_at(node, "parkingName")
                    or _text_at(node, "name"))
            if not sid and not name and _text_at(node, "latitude") is None:
                continue  # container, not a site entry
            key = sid or name or "teadmata"
            rec = sites.setdefault(
                key, {"site_id": sid, "name": name, "lat": None,
                      "lon": None, "spaces": None})
            lat = _as_float(_text_at(node, "latitude"))
            lon = _as_float(_text_at(node, "longitude"))
            spaces = (_as_int(_text_at(node, "numberOfSpaces"))
                      or _as_int(_text_at(node, "parkingNumberOfSpaces")))
            if lat is not None:
                rec["lat"] = lat
            if lon is not None:
                rec["lon"] = lon
            if spaces is not None:
                rec["spaces"] = spaces
            if name and not rec["name"]:
                rec["name"] = name
    return list(sites.values())


def build_table(rows: List[dict]) -> dict:
    """Per-site rows -> snapshot table. Pure."""
    out_rows = [r for r in rows if isinstance(r, dict)]
    located = sum(1 for r in out_rows
                  if r.get("lat") is not None and r.get("lon") is not None)
    spaces = sum(r["spaces"] for r in out_rows
                 if isinstance(r.get("spaces"), int))
    return {"rows": out_rows,
            "counts": {"sites": len(out_rows), "located": located,
                       "spaces": spaces}}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyed DATEX truckpark pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--feed", default=FEED_DEFAULT,
                    help="DATEX feed slug (default: truckParking).")
    ap.add_argument("--fixture", default=None,
                    help="Fixture XML body for --build without a pull.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if not os.environ.get(DATEX_KEY_ENV):
        print("error: keeldun - %s ei ole määratud. Ekspordi oma "
              "TarkTee DATEX võti selles terminalis (vt "
              "docs/datex_truckpark.md §7); midagi ei päritud, midagi "
              "ei kirjutatud." % DATEX_KEY_ENV, file=sys.stderr)
        return 2
    if args.pull:
        dest = fetch_feed(args.feed, args.cache_dir)
        if dest is None:
            if _quota_used(args.cache_dir) >= QUOTA_MAX_CALLS:
                print("error: keeldun - DATEX kvoot on täis (%d "
                      "päringut / 30 ööpäeva); midagi ei päritud."
                      % QUOTA_MAX_CALLS, file=sys.stderr)
                return 2
            print("error: päring ebaõnnestus või jäi vahele (värske "
                  "puhver või transport/viga) - midagi uut ei "
                  "puhvritatud.", file=sys.stderr)
            return 1
        print("ok: DATEX voog '%s' puhvritatud (%s)"
              % (args.feed, dest), file=sys.stderr)
    if args.build:
        if args.fixture:
            rows = parse_truckpark(args.fixture)
        else:
            cached = os.path.join(args.cache_dir, CACHE_FILE)
            if not os.path.exists(cached):
                print("error: puhvritatud voogu pole - käivita --pull "
                      "võtmega või anna --fixture.", file=sys.stderr)
                return 1
            rows = parse_truckpark(cached)
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
