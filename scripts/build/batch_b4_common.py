"""Batch 4 shared helpers (parameters3.md groups 12-13): p125, p343, p141, p282, p342.

Stdlib only. Pure logic + snapshot-file readers live here so unit tests
stay hermetic (no network, no walk_raster/walk_graph import at module top;
raster stamping imports those lazily inside build entry points, which only
run via the documented offline rebuild command).

Snapshot contract (verified 2026-09-12):
  <snap>/gtfs/tallinn-gtfs-2026-09-11.zip   Peatus.ee/Tallinn GTFS static feed
  <snap>/osm/harju-amenities.geojson        line-delimited OSM features
    amenity=parcel_locker x517, amenity=post_office x38 (grep-verified)
  <snap>/osm/derived-transit.json           8049 OSM stop points (base split)
  <snap>/osm/harju-car-graph.json           car nodes (497815) + edges
Airport GTFS stops: 138901/138215/138869 ("Lennujaam").
"""

import csv
import io
import math
import zipfile

# County raster bbox shared by every layer (mirrors build-walk-raster.py).
COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
# Metro master bbox (mirrors the base transit-metro.json).
METRO_BBOX = [24.3, 59.28, 25.2, 59.56]

# Equirectangular degrees-to-km at Harjumaa latitude (mirrors walk_graph).
LON_KM = 57.29
LAT_KM = 110.57

# Batch 4 calibration, locked 2026-09-12 from snapshot histograms
# (euclidean kernel-sum probes at Balti/Oismae/Lasnamae/Viimsi/rural;
# walk-kernel reads slightly lower, same ordering):
#   p125 weekend departures: Balti S~3100, Oismae ~1200, Viimsi ~95.
#   p343 airport-route departures: Balti S~350, Oismae 0 (corridor-only).
#   p141 locker counts: Balti S~7.2, Oismae ~6.5, Lasnamae ~1.7.
#   p282 secure-pickup weights: Balti S~8.4, Lasnamae ~1.7.
#   p342 car nodes <0.5km: Balti 1580 ... rural 51.
CAL = {
    "teens": {"sigma": 0.2, "half": 800.0},        # p125 weekend departures
    "airport": {"sigma": 0.3, "half": 150.0},      # p343 airport-route departures
    "lockers": {"sigma": 0.3, "half": 4.0},        # p141 locker counts
    "securepickup": {"sigma": 0.3, "half": 6.0},   # p282 locker+postoffice weights
    # p342 wait proxy: transit norm half + road-density norm half (see rideshare).
    "rideshare": {"sigma": 0.3, "transit_half": 1500.0, "road_half": 800.0,
                  "wait_min": 2.0, "wait_max": 15.0},
}

# Score floor mirroring the base builders: cells below 3 read unknown (255).
SCORE_FLOOR = 3.0


def hav_km(lon1, lat1, lon2, lat2):
    """Mirror of walk_graph.hav_km (same constants, same arg order)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def kernel(d, sigma):
    return math.exp(-d * d / (2 * sigma * sigma))


def saturate(s, half):
    return (100.0 * s / (s + half)) if s > 0 else 0.0


def read_gtfs(zip_path):
    """Read GTFS tables from the snapshot zip (offline, stdlib)."""
    out = {}
    with zipfile.ZipFile(zip_path) as zf:
        for name in ("calendar.txt", "trips.txt", "stop_times.txt",
                      "stops.txt", "routes.txt"):
            with zf.open(name) as fh:
                out[name] = list(
                    csv.DictReader(fh.read().decode("utf-8-sig").splitlines()))
    return out


def service_ids_for(calendar_rows, *days):
    """service_ids running on ALL of the given weekday columns."""
    return {c["service_id"] for c in calendar_rows
            if all(c.get(d) == "1" for d in days)}


def service_ids_for_any(calendar_rows, *days):
    """service_ids running on ANY of the given weekday columns."""
    return {c["service_id"] for c in calendar_rows
            if any(c.get(d) == "1" for d in days)}


def departures_per_stop(gtfs, service_ids):
    """stop_id -> departures over the given services; plus trip->route map."""
    trip_route = {t["trip_id"]: t["route_id"] for t in gtfs["trips.txt"]
                  if t["service_id"] in service_ids}
    cnt = {}
    for row in gtfs["stop_times.txt"]:
        if row["trip_id"] in trip_route:
            cnt[row["stop_id"]] = cnt.get(row["stop_id"], 0) + 1
    return cnt, trip_route


def feature_point(geom):
    """Point / line-midpoint / polygon-bbox-center representative.

    Mirrors walk_raster._feature_point (same three cases, same midpoint).
    """
    if not isinstance(geom, dict):
        return None
    kind = geom.get("type")
    coords = geom.get("coordinates")
    if kind == "Point" and isinstance(coords, list) and len(coords) >= 2:
        return (float(coords[0]), float(coords[1]))
    if kind == "LineString" and isinstance(coords, list) and coords:
        mid = coords[len(coords) // 2]
        return (float(mid[0]), float(mid[1]))
    if kind in ("Polygon", "MultiPolygon") and isinstance(coords, list):
        rings = [coords[0]] if kind == "Polygon" else [p[0] for p in coords if p]
        xs = [x for r in rings for x, _ in r]
        ys = [y for r in rings for _, y in r]
        if xs and ys:
            return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return None
