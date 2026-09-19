"""Micromobility GBFS harvester (issue #688).

Pole-native per AGENTS.md section 9: the repo holds this code plus
hermetic tests; cadence, caches and any future URLs live on the pole.

FEED VERDICT (2026-09-19, polite single GETs, UA
``home-finder-research/0.1``, ``--max-time`` 20-25, paced, 429 as
stop, raw bodies in /tmp only — full evidence in docs/p4_gbfs.md
section 6): there is NO verified keyless GBFS feed for Tallinn or
Tartu, so FEEDS is empty and --pull honestly refuses (exit 2)
until an operator verifies a discovery URL:
* the official MobilityData GBFS registry (systems.csv,
  2026-09-19) lists zero Estonian systems;
* "Smart Bike" is a Tartu-only brand (Bewegen/WeGoShare tenant
  ``europe/tartu``, app API ``serverapp.ratas.tartu.ee``) — its
  2.6 MB app bundle contains zero ``gbfs`` references and its
  public map endpoint (``/api/map/stations/``) answers anonymous
  GETs with app-level ``{"message":"Wrong request!"}`` (HTTP 500):
  session-keyed, not pollable;
* Dott's public keyless pattern
  (``gbfs.api.ridedott.com/public/v2/<city>/gbfs.json``) answers
  ``ERR_REGION_NOT_FOUND`` for both ``tallinn`` and ``tartu``;
* no municipal "Tallinn Smart Bike" system exists at all.

The parse/join machinery below (auto-discovery, station_information
+ station_status join) is proven on hermetic fixtures so a future
verified feed plugs straight into FEEDS; until then nothing is
polled and nothing is faked.

Usage:
  python3 scripts/build/batch_gbfs.py --pull --build \\
      --cache-dir DIR --discovery https://.../gbfs.json [--city tartu]
  (without --discovery the pull refuses; --build accepts --info/--status
  fixture files for offline table builds.)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

#: Verified keyless GBFS auto-discovery URLs per city. EMPTY by the
#: 2026-09-19 verdict above — add a URL here only after a live
#: re-verification (polite single GET, /tmp only, documented in
#: docs/p4_gbfs.md). Nothing polls an unverified URL, ever.
FEEDS: Dict[str, str] = {}

#: Identifying user agent for the polite pull.
UA = "home-finder-research/0.1"

#: Minimum plausible feed body.
MIN_BYTES = 16

#: Seconds between feed GETs (one discovery + two feeds per city).
PACE_S = 3.0


def fetch_json(url: str, cache_dir: str, name: str) -> Optional[str]:
    """Polite keyless GET of one GBFS JSON body. Path or None.

    One request, 30 s timeout, no retries; HTTP 429 is a stop
    signal (nothing stored, caller stops the city); transport
    errors are never cached. Scorers never call this.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, name)
    try:
        req = urllib.request.Request(
            url, method="GET",
            headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if getattr(resp, "status", 200) != 200:
                return None
            body = resp.read()
        if len(body) < MIN_BYTES:
            return None
        try:
            json.loads(body)
        except ValueError:
            return None
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest
    except Exception:
        return None


def parse_discovery(doc: dict) -> Dict[str, str]:
    """GBFS auto-discovery body -> {feed_name: url}. Pure."""
    out: Dict[str, str] = {}
    try:
        feeds = doc["data"]["feeds"]
    except (KeyError, TypeError, AttributeError):
        return out
    if isinstance(feeds, dict):
        # GBFS v3 language-keyed shape.
        for lang_feeds in feeds.values():
            if isinstance(lang_feeds, list):
                for f in lang_feeds:
                    if isinstance(f, dict) and f.get("name") and f.get("url"):
                        out.setdefault(f["name"], f["url"])
    elif isinstance(feeds, list):
        for f in feeds:
            if isinstance(f, dict) and f.get("name") and f.get("url"):
                out.setdefault(f["name"], f["url"])
    return out


def _load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def build_table(info: dict, status: dict) -> dict:
    """station_information + station_status -> snapshot table. Pure.

    Join key is ``station_id``; status rows without a known station
    are dropped (never faked). Empty inputs yield the honest empty
    table (never faked stations).
    """
    stations: Dict[str, dict] = {}
    data = info.get("data") if isinstance(info, dict) else None
    rows = data.get("stations") if isinstance(data, dict) else None
    for s in rows if isinstance(rows, list) else []:
        if not isinstance(s, dict):
            continue
        sid = s.get("station_id")
        lat, lon = s.get("lat"), s.get("lon")
        if not sid or not isinstance(lat, (int, float)) \
                or not isinstance(lon, (int, float)):
            continue
        stations[str(sid)] = {
            "station_id": str(sid),
            "name": s.get("name") if isinstance(s.get("name"), str) else "?",
            "lat": float(lat),
            "lon": float(lon),
            "capacity": s.get("capacity")
            if isinstance(s.get("capacity"), int) else None,
            "bikes": 0,
            "docks": 0,
        }
    sdata = status.get("data") if isinstance(status, dict) else None
    srows = sdata.get("stations") if isinstance(sdata, dict) else None
    for s in srows if isinstance(srows, list) else []:
        if not isinstance(s, dict):
            continue
        pt = stations.get(str(s.get("station_id")))
        if pt is None:
            continue
        bikes = s.get("num_bikes_available")
        docks = s.get("num_docks_available")
        pt["bikes"] = bikes if isinstance(bikes, int) and bikes >= 0 else 0
        pt["docks"] = docks if isinstance(docks, int) and docks >= 0 else 0
    points = sorted(stations.values(), key=lambda p: p["station_id"])
    with_bikes = sum(1 for p in points if p["bikes"] > 0)
    return {"points": points,
            "counts": {"total": len(points), "with_bikes": with_bikes}}


def pull_city(city: str, discovery_url: str, cache_dir: str
              ) -> Optional[Tuple[str, str]]:
    """Pull one city's info+status pair. (info_path, status_path) or None."""
    disc = fetch_json(discovery_url, cache_dir, "gbfs_%s_disc.json" % city)
    if disc is None:
        return None
    feeds = parse_discovery(_load(disc))
    info_url = feeds.get("station_information")
    status_url = feeds.get("station_status")
    if not info_url or not status_url:
        return None
    time.sleep(PACE_S)
    info = fetch_json(info_url, cache_dir, "gbfs_%s_info.json" % city)
    if info is None:
        return None
    time.sleep(PACE_S)
    status = fetch_json(status_url, cache_dir, "gbfs_%s_status.json" % city)
    if status is None:
        return None
    return info, status


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Keyless GBFS station pull.")
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--discovery", default=None,
                    help="Operator-verified GBFS auto-discovery URL "
                         "(required for --pull until FEEDS verifies).")
    ap.add_argument("--city", default="tartu")
    ap.add_argument("--info", default=None,
                    help="Fixture station_information file for --build.")
    ap.add_argument("--status", default=None,
                    help="Fixture station_status file for --build.")
    args = ap.parse_args(argv)
    if not args.pull and not args.build:
        args.pull = args.build = True

    if args.pull:
        discovery = args.discovery or FEEDS.get(args.city)
        if not discovery:
            print("error: keeldun - keyless GBFS-voogu pole "
                  "verifitseeritud (vt docs/p4_gbfs.md §6): anna "
                  "--discovery operaatori kontrollitud URL-iga; "
                  "midagi ei päritud, midagi ei kirjutatud.",
                  file=sys.stderr)
            return 2
        pair = pull_city(args.city, discovery, args.cache_dir)
        if pair is None:
            print("error: päring ebaõnnestus või jäi vahele "
                  "(transport/viga või 429-stopp) - midagi uut ei "
                  "puhvritatud.", file=sys.stderr)
            return 1
        print("ok: GBFS-jaamad puhvritatud (%s)" % args.cache_dir)
    if args.build:
        if args.info and args.status:
            table = build_table(_load(args.info), _load(args.status))
        else:
            table = build_table({}, {})
            if table["counts"]["total"] == 0 and not (args.info
                                                      or args.status):
                print("error: puhvritatud GBFS-vooge pole - käivita "
                      "--pull --discovery URL-iga või anna --info/--status "
                      "teavikud.", file=sys.stderr)
                return 1
        print(json.dumps(table["counts"], ensure_ascii=False))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
