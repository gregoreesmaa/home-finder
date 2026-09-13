"""P4 GTFS stop overlay (issue #483): peatus/Elron/TLT stops as points.

Group A layer issue. Acceptance criteria: stops as a POINT overlay only
(no frequency kernel, no walk raster); evening-ridership NULLs stay NULL
with EI OLE reasons (pinned by tests/test_dims_p4_gtfsstops.py).

FEED HONESTY (verified 2026-09-13 against real files, not the issue text —
the issue body's "feeds verified open" overstates; AGENTS.md section 7.2):
* TLT city network: OPEN as a snapshot vintage, not a live poll. The file
  ``gtfs/tallinn-gtfs-2026-09-11.zip`` (2.6 MB, agency Tallinn /
  transport.tallinn.ee) sits in the 2026-09-12 snapshot: 1120 stops,
  80 routes (bus route_type 3 + tram 900 + troll 800), 20 081 trips,
  483 986 stop_times rows. Stop positions, modes and SCHEDULED
  departures per window below are measured from that vintage.
* Peatus.ee national GTFS: CLOSED live (dated negative 2026-09-13, see
  dims_p4_peatus: /gtfs/gtfs.zip 302s to a "Rakendus on suletud" page).
  The vintage's stops.txt carries peatus-style ``thoreb_id`` codes, but
  regional stops outside the TLT city network have no vintage behind
  them and are NOT plotted — beyond-vintage is unknown, never faked.
* Elron rail: NO machine feed (dated negative 2026-09-13, see
  dims_p4_elron). Elron stations ride the overlay as MAPPED-ONLY points
  from the snapshot OSM extract (railway=station/stop, 112 points),
  with NO departure counts — a mapped position is a walk fact, a
  frequency join that has no source would be fake precision.
* Evening RIDERSHIP (how full the vehicle is, P4-032 Elron/TLT slices):
  unpublished everywhere. GTFS static carries scheduled departures,
  never occupancy — so the overlay shows schedules and the
  ridership dims keep returning None with EI OLE reasons. A scheduled
  evening departure is not a passenger count; the legend says so.

Style mirrors dims_p4_peatus.py (pure offline readers over a cached zip,
stdlib only) and scripts/build/batch_b4_common.py (same table split).
Network lives NOWHERE in this module — not even a fetcher: the vintage
is snapshot data, and tests cover everything with fixtures. The offline
builder scripts/build/batch_gtfs_stops.py imports the pure helpers here
(single source of truth) and writes osm/derived-gtfsstops.json.

Judgment calls (reviewable per AGENTS.md section 7.5):
* Mode per stop comes from the route_id middle segment (bus/tram/trol)
  with a route_type cross-check; on conflict the route_type wins and the
  builder reports the mismatch count (zero on the 2026-09-11 vintage).
* One point per GTFS stop_id: directional pairs (~40 m apart, e.g.
  Harkujärve 47009-1/20813-3) are distinct boarding points, kept.
  OSM rail points never duplicate GTFS stops (the feed has no rail).
* Wednesday departures size the markers (t, like the transit overlay);
  Elron mapped-only stations carry no t (unknown, never 0).
"""

import csv
import io
import math
import zipfile
from typing import Dict, List, Optional, Set, Tuple

#: Snapshot vintage this overlay is measured from (local file, never a URL).
GTFS_VINTAGE = "gtfs/tallinn-gtfs-2026-09-11.zip"

#: Evening window floor for the scheduled-evening leg (P4-045 access leg
#: only — scheduled departures, never ridership).
EVENING_FROM = "18:00:00"

#: GTFS tables the offline readers need.
GTFS_TABLES = ("calendar.txt", "trips.txt", "stop_times.txt",
               "stops.txt", "routes.txt")

#: route_type -> Estonian mode label (Tallinn feed: 3 buss, 900 tramm,
#: 800 troll — verified on the 2026-09-11 vintage, see builder output).
ROUTE_TYPE_MODE = {"3": "buss", "800": "troll", "900": "tramm"}

#: OSM railway values counted as Elron heavy-rail stops (mapped-only leg).
#: tram_stop/platform excluded — the tram network rides the GTFS leg, and
#: technical_station is not a passenger stop.
ELRON_RAILWAY_VALUES = ("station", "halt", "stop")


def read_gtfs_tables(zip_path: str) -> Dict[str, List[dict]]:
    """Read the five GTFS tables from a snapshot vintage zip. Offline."""
    out: Dict[str, List[dict]] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in GTFS_TABLES:
            with zf.open(name) as fh:
                out[name] = list(csv.DictReader(
                    io.TextIOWrapper(fh, encoding="utf-8-sig")))
    return out


def services_for(calendar_rows: List[dict], day: str) -> Set[str]:
    """service_ids running on the given weekday column. Pure."""
    return {c["service_id"] for c in calendar_rows if c.get(day) == "1"}


def window_counts(gtfs: Dict[str, List[dict]],
                  service_ids: Set[str],
                  after: Optional[str] = None) -> Dict[str, int]:
    """stop_id -> scheduled departures over the services (time floor opt).

    after="18:00:00" keeps evening departures only (zero-padded HH:MM:SS
    strings compare safely; past-midnight 25:xx:xx still sorts after).
    Counts are SCHEDULED departures — never ridership. Pure.
    """
    trip_ok = {t["trip_id"] for t in gtfs["trips.txt"]
               if t.get("service_id") in service_ids}
    cnt: Dict[str, int] = {}
    for row in gtfs["stop_times.txt"]:
        if row.get("trip_id") not in trip_ok:
            continue
        if after is not None and (row.get("departure_time") or "") < after:
            continue
        sid = row.get("stop_id")
        if sid:
            cnt[sid] = cnt.get(sid, 0) + 1
    return cnt


def stop_modes(gtfs: Dict[str, List[dict]]) -> Dict[str, str]:
    """stop_id -> one of buss/tramm/troll from serving routes. Pure.

    Mode comes from the route_id middle segment (tallinna-lin_<mode>_N)
    cross-checked against route_type; on conflict route_type wins. Stops
    served by several modes read "mitu" (mixed) — the point marks the
    stop, not a line verdict.
    """
    route_mode: Dict[str, str] = {}
    for r in gtfs["routes.txt"]:
        rid = r.get("route_id") or ""
        seg = rid.split("_")[1] if len(rid.split("_")) > 2 else ""
        seg_mode = {"bus": "buss", "tram": "tramm", "trol": "troll"}.get(seg)
        type_mode = ROUTE_TYPE_MODE.get(r.get("route_type") or "")
        route_mode[rid] = type_mode or seg_mode or "buss"
    trip_route = {t["trip_id"]: t.get("route_id")
                  for t in gtfs["trips.txt"]}
    modes: Dict[str, Set[str]] = {}
    for row in gtfs["stop_times.txt"]:
        rid = trip_route.get(row.get("trip_id") or "")
        sid = row.get("stop_id")
        if rid in route_mode and sid:
            modes.setdefault(sid, set()).add(route_mode[rid])
    return {sid: (next(iter(m)) if len(m) == 1 else "mitu")
            for sid, m in modes.items()}


def stop_coords(stops_rows: List[dict]) -> Dict[str, Tuple[float, float]]:
    """stop_id -> (lon, lat); malformed rows skipped, never faked. Pure."""
    out: Dict[str, Tuple[float, float]] = {}
    for row in stops_rows:
        try:
            sid = row.get("stop_id")
            lon = float(row["stop_lon"])
            lat = float(row["stop_lat"])
        except (TypeError, ValueError, KeyError):
            continue
        if sid and math.isfinite(lon) and math.isfinite(lat):
            out[sid] = (lon, lat)
    return out


def overlay_points(coords: Dict[str, Tuple[float, float]],
                   counts_wed: Dict[str, int],
                   modes: Dict[str, str],
                   elron_stations: List[dict]) -> Tuple[List[dict], dict]:
    """GTFS stops + mapped Elron stations -> overlay point dicts. Pure.

    coords/counts_wed/modes: GTFS leg (scheduled Wednesday departures in
    ``t``; stops with no Wednesday service keep no ``t`` — unknown,
    never 0). elron_stations: OSM rail points {lon, lat, tags} with
    railway=station/halt/stop (mapped position only, no ``t`` — Elron
    publishes no machine timetable to join). GTFS points carry NO OSM
    tags (claiming mapped tags per stop would be unverified); Elron
    points keep their real railway tags. Returns (points, stats) where
    stats reports leg counts + mode split for the builder log / PR.
    Evening ridership appears NOWHERE: GTFS static has no occupancy
    column, so there is nothing to populate it from (P4-032 stays NULL).
    """
    points: List[dict] = []
    mode_split: Dict[str, int] = {}
    gtfs_with_wed = 0
    for sid, (lon, lat) in coords.items():
        pt: dict = {"lon": lon, "lat": lat}
        wed = counts_wed.get(sid)
        if isinstance(wed, int) and wed >= 0:
            pt["t"] = wed
            gtfs_with_wed += 1
        mode = modes.get(sid, "?")
        mode_split[mode] = mode_split.get(mode, 0) + 1
        points.append(pt)
    elron = 0
    for s in elron_stations:
        try:
            lon = float(s["lon"])
            lat = float(s["lat"])
        except (TypeError, ValueError, KeyError):
            continue
        if not (math.isfinite(lon) and math.isfinite(lat)):
            continue
        tags = s.get("tags") if isinstance(s.get("tags"), dict) else None
        pt = {"lon": lon, "lat": lat}
        if tags:
            pt["tags"] = {k: v for k, v in tags.items()
                          if k in ("railway", "public_transport")
                          and isinstance(v, str)}
        points.append(pt)
        elron += 1
    stats = {"gtfs_stops": len(coords),
             "gtfs_with_wed": gtfs_with_wed,
             "elron_mapped": elron,
             "mode_split": mode_split,
             "total": len(points)}
    return points, stats
