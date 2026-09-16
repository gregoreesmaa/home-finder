"""Annual Keskkonnaagentuur climate-normals harvest (issue #611, P4 microclimate cells).

Polls the keyless kliimaandmestik PostgREST feed for the 1991-2020
(WMO) normals of the three usable Harjumaa stations and ranks them
into the coarse honest cell bands the map paints
(apps/web/lib/layers_kliima.ts):

* frost_days: mean annual days with daily Tmin (DTAN) < 0 C, counted
  from f_kliima_paev daily rows (the monthly f_kliima_kuu view carries
  monthly aggregates only -- frost-day counts are NOT derivable from
  it, so the daily view is required, not optional).
* precip_mm: mean annual precipitation, summed from f_kliima_kuu
  monthly DPREC rows (12 complete months per year).

Bands mirror _rank_dim in services/scoring/dims_p4_kliima_stations.py:
3 joined cells -> 70/55/40 (dense rank, ties share the better band);
2 joined -> 70/40. A station with too-thin normals stays NULL for
that indicator (ranked out of the joined set, never zero-filled).

Politeness (AGENTS.md section 7.4): ~36 single GETs once a YEAR
(TTL 365 d), labelled one-off User-Agent, 2 s pacing, `--max-time`
via timeout=60, single attempts, HTTP 429/errors are a STOP signal
(never cached as data). Raw bodies live in /tmp only -- the only
committed output is the printed TS snippet + the extract JSON when
--out points at a file (both derived, aggregate normals only).

Coverage honesty: a year counts for frost only with >= 300 DTAN
daily rows, for precip only with all 12 DPREC months; a station
needs >= 24 of 30 usable years per indicator or it is NULL for it
(documented, reviewable -- partial decades must not pose as
normals).
"""

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

CLIMATE_BASE_URL = "https://keskkonnaandmed.envir.ee"
DAILY_VIEW = "f_kliima_paev"
MONTHLY_VIEW = "f_kliima_kuu"

KLIIMA_UA = (
    "home-finder-611-kliima-normals/1.0 "
    "(polite annual normals harvest, paced single GETs; "
    "GitHub gregoreesmaa/home-finder issue 611)"
)

#: Seconds between harvest GETs.
KLIIMA_PACE_S = 2

#: 1991-2020 normals move slowly (issue constraint: annual harvest).
KLIIMA_TTL_S = 365 * 24 * 3600

#: Minimum plausible JSON body: one monthly slice is ~2 KB, so anything
#: smaller is an error page, never data.
JSON_MIN_BYTES = 500

DEFAULT_CACHE_DIR = os.path.join("/tmp", "hf-611-kliima")

NORMALS_START = 1991
NORMALS_END = 2020

#: (code, name, lat, lon) -- mirrors HARJUMAA_STATIONS in
#: services/scoring/dims_p4_kliima_stations.py (no sibling imports).
STATIONS: List[Tuple[str, str, float, float]] = [
    ("AJHARK01", "Tallinn-Harku", 59.398122, 24.602870),
    ("AJPAKR01", "Pakri", 59.3895, 24.0401),
    ("AJKUUS01", "Kuusiku", 58.9732, 24.7340),
]

FROST_MIN_DAYS_PER_YEAR = 300
MIN_USABLE_YEARS = 24


def fetch_cached(view: str, params: Dict[str, str], cache_dir: str,
                 filename: str) -> Optional[str]:
    """Polite single-GET pull with a yearly TTL. Returns path or None.

    Cache hit (fresh mtime within KLIIMA_TTL_S): NO request is made.
    Otherwise one GET with KLIIMA_UA; the body is stored only on
    HTTP 200 with at least JSON_MIN_BYTES bytes, else None is
    returned and nothing is cached. No retries -- HTTP 429/errors are
    a stop signal. Tests cover the pure aggregators, never this.
    """
    os.makedirs(cache_dir, exist_ok=True)
    dest = os.path.join(cache_dir, filename)
    try:
        if (os.path.exists(dest)
                and time.time() - os.path.getmtime(dest) < KLIIMA_TTL_S):
            return dest
    except OSError:
        return None
    url = "%s/%s?%s" % (CLIMATE_BASE_URL, view,
                        urllib.parse.urlencode(params))
    req = urllib.request.Request(
        url, headers={"User-Agent": KLIIMA_UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
            if resp.status != 200:
                return None
            body = resp.read()
    except Exception:
        return None
    if len(body) < JSON_MIN_BYTES:
        return None
    try:
        with open(dest, "wb") as f:
            f.write(body)
    except OSError:
        return None
    return dest


def aggregate_frost_days(daily_rows: List[dict]) -> Optional[float]:
    """Mean annual frost days (DTAN < 0) over usable years, or None.

    Pure (tests cover this, never the network). A year is usable with
    >= FROST_MIN_DAYS_PER_YEAR DTAN rows; the station needs >=
    MIN_USABLE_YEARS usable years.
    """
    by_year: Dict[int, int] = {}
    counts: Dict[int, int] = {}
    for row in daily_rows:
        if row.get("element_kood") != "DTAN":
            continue
        try:
            year = int(row["aasta"])
            value = float(row["vaartus"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (NORMALS_START <= year <= NORMALS_END):
            continue
        counts[year] = counts.get(year, 0) + 1
        if value < 0:
            by_year[year] = by_year.get(year, 0) + 1
    usable = [by_year.get(y, 0) for y, n in counts.items()
              if n >= FROST_MIN_DAYS_PER_YEAR]
    if len(usable) < MIN_USABLE_YEARS:
        return None
    return sum(usable) / len(usable)


def aggregate_precip_mm(monthly_rows: List[dict]) -> Optional[float]:
    """Mean annual precipitation (summed monthly DPREC), or None.

    Pure (tests cover this, never the network). A year is usable with
    all 12 DPREC months; the station needs >= MIN_USABLE_YEARS usable
    years.
    """
    by_year_month: Dict[int, Dict[int, float]] = {}
    for row in monthly_rows:
        if row.get("element_kood") != "DPREC":
            continue
        try:
            year = int(row["aasta"])
            month = int(row["kuu"])
            value = float(row["vaartus"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (NORMALS_START <= year <= NORMALS_END):
            continue
        by_year_month.setdefault(year, {})[month] = value
    usable = [sum(months.values()) for months in by_year_month.values()
              if len(months) == 12]
    if len(usable) < MIN_USABLE_YEARS:
        return None
    return sum(usable) / len(usable)


def rank_bands(values: Dict[str, float]) -> Dict[str, int]:
    """Dense-rank band per station: 3 joined -> 70/55/40, 2 -> 70/40.

    Byte parity with _rank_dim in dims_p4_kliima_stations.py (ties
    share the better band). Fewer than 2 joined -> {} (no ranking
    possible -- the slices stay honestly empty).
    """
    if len(values) < 2:
        return {}
    ordered = sorted(set(values.values()))
    bands: Dict[str, int] = {}
    for code, value in values.items():
        rank = ordered.index(value)
        if len(values) == 2:
            bands[code] = 70 if rank == 0 else 40
        else:
            bands[code] = 70 if rank == 0 else (55 if rank == 1 else 40)
    return bands


def harvest(cache_dir: str) -> Tuple[Dict[str, dict], List[str]]:
    """Pull normals for all stations. Returns (cells, stops).

    `cells` maps station code -> {name, lat, lon, frost_days|None,
    precip_mm|None}. `stops` names fatal transport failures (429/stop
    signal) -- a non-empty stops list means the harvest is partial and
    the caller must NOT publish bands from it.
    """
    cells: Dict[str, dict] = {}
    stops: List[str] = []
    first = True
    for code, name, lat, lon in STATIONS:
        cell: dict = {"name": name, "lat": lat, "lon": lon,
                      "frost_days": None, "precip_mm": None}
        # Monthly DPREC 1991-2020: ~3.2k rows -> paged GETs (limit 1000).
        # The 1000-row cap truncates silently (short page = done), so a
        # single GET would rank a partial decade as normals -- paginate.
        monthly_rows: List[dict] = []
        monthly_offset = 0
        monthly_ok = True
        while True:
            if not first:
                time.sleep(KLIIMA_PACE_S)
            first = False
            page_path = fetch_cached(
                MONTHLY_VIEW,
                {"jaam_kood": "eq.%s" % code,
                 "aasta": "gte.%d" % NORMALS_START,
                 "limit": "1000", "offset": str(monthly_offset)},
                cache_dir,
                "kuu-%s-%d.json" % (code, monthly_offset))
            if page_path is None:
                monthly_ok = False
                break
            with open(page_path, encoding="utf-8") as f:
                page = json.load(f)
            monthly_rows.extend(page)
            if len(page) < 1000:
                break
            monthly_offset += 1000
        # NOTE: the pull asks aasta>=1991 and aggregate_* enforces the
        # 1991-2020 window locally.
        if not monthly_ok:
            stops.append("%s monthly (DPREC offset %d)"
                         % (code, monthly_offset))
        else:
            cell["precip_mm"] = aggregate_precip_mm(monthly_rows)
        # Daily DTAN 1991-2020: ~11k rows -> paged GETs (limit 1000).
        daily_rows: List[dict] = []
        offset = 0
        daily_ok = True
        while True:
            page_path = fetch_cached(
                DAILY_VIEW,
                {"jaam_kood": "eq.%s" % code,
                 "element_kood": "eq.DTAN",
                 "aasta": "gte.%d" % NORMALS_START,
                 "limit": "1000", "offset": str(offset)},
                cache_dir, "paev-dtan-%s-%d.json" % (code, offset))
            if page_path is None:
                daily_ok = False
                break
            with open(page_path, encoding="utf-8") as f:
                page = json.load(f)
            daily_rows.extend(page)
            time.sleep(KLIIMA_PACE_S)
            if len(page) < 1000:
                break
            offset += 1000
        if not daily_ok:
            stops.append("%s daily (DTAN offset %d)" % (code, offset))
        else:
            cell["frost_days"] = aggregate_frost_days(daily_rows)
        cells[code] = cell
        time.sleep(KLIIMA_PACE_S)
    return cells, stops


def read_cached_pages(cache_dir: str, template: str,
                     code: str) -> List[dict]:
    """Stitch paged cache files (template % (code, offset)) into rows.

    Pure local read (used by --no-fetch): concatenates page files from
    offset 0 until a missing file or a short (< 1000-row) page -- the
    same stop rule the live harvest's pagination uses, so a truncated
    single page can never pose as a full pull.
    """
    rows: List[dict] = []
    offset = 0
    while os.path.exists(os.path.join(cache_dir, template % (code, offset))):
        with open(os.path.join(cache_dir, template % (code, offset)),
                  encoding="utf-8") as f:
            page = json.load(f)
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    return rows


def build_extract(cells: Dict[str, dict], vintage: str) -> dict:
    """Rank joined cells per indicator; assemble the publishable extract."""
    frost = {c: v["frost_days"] for c, v in cells.items()
             if v["frost_days"] is not None}
    wet = {c: v["precip_mm"] for c, v in cells.items()
           if v["precip_mm"] is not None}
    frost_bands = rank_bands(frost)
    wet_bands = rank_bands(wet)
    stations = []
    for code, _, _, _ in STATIONS:
        cell = cells[code]
        stations.append({
            "code": code, "name": cell["name"],
            "lat": cell["lat"], "lon": cell["lon"],
            "frost_days": cell["frost_days"],
            "precip_mm": cell["precip_mm"],
            "frost_band": frost_bands.get(code),
            "wet_band": wet_bands.get(code),
        })
    return {
        "vintage": vintage,
        "normals_window": "%d-%d" % (NORMALS_START, NORMALS_END),
        "attribution": "Keskkonnaagentuur (kliimaandmestik), CC BY 4.0",
        "stations": stations,
    }


def ts_snippet(extract: dict) -> str:
    """TS constant block for apps/web/lib/layers_kliima.ts (paste between
    the KLIIMA-CELLS markers; regenerate, never hand-edit)."""
    lines = ["export const KLIIMA_CELLS: KliimaCell[] = ["]
    for station in extract["stations"]:
        frost = ("%.1f" % station["frost_days"]
                 if station["frost_days"] is not None else "null")
        precip = ("%.1f" % station["precip_mm"]
                  if station["precip_mm"] is not None else "null")
        frost_band = (str(station["frost_band"])
                      if station["frost_band"] is not None else "null")
        wet_band = (str(station["wet_band"])
                    if station["wet_band"] is not None else "null")
        lines.append(
            "  { code: \"%s\", lat: %s, lon: %s, frostDays: %s, "
            "precipMm: %s, frostBand: %s, wetBand: %s }," % (
                station["code"], station["lat"], station["lon"], frost,
                precip, frost_band, wet_band))
    lines.append("];")
    return "\n".join(lines) + "\n"


def main() -> int:
    """Annual normals harvest (paced single GETs, 429 = stop) + extract."""
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    ap.add_argument("--out", default=None,
                    help="extract JSON path (default: <cache-dir>/kliima-extract.json)")
    ap.add_argument("--vintage", default="2026-09-16",
                    help="vintage label stamped on the extract")
    ap.add_argument("--no-fetch", action="store_true",
                    help="rank from warm cache only (no GETs; CI/tests)")
    args = ap.parse_args()

    if args.no_fetch:
        cells = {}
        for code, name, lat, lon in STATIONS:
            daily_rows = read_cached_pages(
                args.cache_dir, "paev-dtan-%s-%d.json", code)
            monthly_rows = read_cached_pages(
                args.cache_dir, "kuu-%s-%d.json", code)
            cells[code] = {"name": name, "lat": lat, "lon": lon,
                           "frost_days": aggregate_frost_days(daily_rows),
                           "precip_mm": aggregate_precip_mm(monthly_rows)}
        stops: List[str] = []
    else:
        cells, stops = harvest(args.cache_dir)
    if stops:
        print("STOP: partial harvest (%s) -- refusing to publish bands "
              "from it; fix transport and re-run" % "; ".join(stops))
        return 1
    extract = build_extract(cells, args.vintage)
    out = args.out or os.path.join(args.cache_dir, "kliima-extract.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(extract, f, ensure_ascii=False, indent=1)
    ranked_frost = sum(1 for s in extract["stations"]
                       if s["frost_band"] is not None)
    ranked_wet = sum(1 for s in extract["stations"]
                     if s["wet_band"] is not None)
    print("stations=%d frost_ranked=%d wet_ranked=%d -> %s"
          % (len(extract["stations"]), ranked_frost, ranked_wet, out))
    for station in extract["stations"]:
        print("  %s frost_days=%s precip_mm=%s frost_band=%s wet_band=%s"
              % (station["code"], station["frost_days"],
                 station["precip_mm"], station["frost_band"],
                 station["wet_band"]))
    print()
    print(ts_snippet(extract))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
