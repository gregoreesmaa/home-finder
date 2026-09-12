"""Group 9b/18b environmental-exposure county masters (issue #124):
vibration (p234) / lowspec (p408) / flightcorr (p445) / darksky (p63) /
coolisland (p181).

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; the full-county build runs only
via the documented rebuild command.

HONESTY (load-bearing): Transpordiamet CNOSSOS-EU rasters, VIIRS
nighttime lights and Landsat thermal UHI are not in the snapshot, so
these are OSM PROXIMITY/DENSITY proxies — titles, legends and sources
say "proksi (hinnang)", never dBA, magnitudes, Bortle classes, Celsius
or seasonal schedules. Green = calm/dark/cool (far/sparse), red =
exposed/lit/sealed (near/dense). In-bbox absence of a mapped source IS
the quiet evidence, so masters emit no in-bbox unknowns (0 =
known-exposed on the source, never 255); out-of-coverage stays 255
server-side (cover mask).

Model (locked 2026-09-12 from snapshot probes at Balti/Viru/Kadriorg/
Oismae/Lasnamae/Viimsi/Nomme/rural/airport — full witness table in
PR #124):
* vibration (p234): nearest rail/tram (steel-on-steel, 1291 geoms) or
  heavy road (motorway/trunk/primary, 3320 ways): calm =
  100*d/(d+300). Ground vibration decays faster than airborne rumble,
  hence the shorter half vs lowspec; industry excluded (plant hum is
  airborne, not ground-borne).
* lowspec (p408): nearest heavy road, rail/tram or industrial area:
  calm = 100*d/(d+500). The heavy-road spectrum is what a
  frequency-sensitive person notices; p301 (sibling) lacks roads.
* flightcorr (p445): two tiers. MAJOR = paved runways (surface
  asphalt/concrete/paved: Tallinn 08/26, Amari) with runway-axis
  extensions +-8 km (sampled every 200 m): calm = 100*d/(d+1500).
  MINOR = grass strips + aerodrome points: calm = 100*d/(d+400), no
  extensions. Score = min (worst exposure wins). Seasonality itself is
  NOT in OSM — the reason/legend says "hooajalisus teadmata".
* darksky (p63): lit-density kernel (sigma 0.3 km, lit=yes nodes + lit
  way points + street lamps, 20 m deduped to 74798 cells) ->
  dark = 100*H/(S+H), H = 120. Probe S: Balti ~320, Viru ~150,
  Nomme ~23, rural 0.
* coolisland (p181): impervious-density kernel (sigma 0.3 km, 252140
  building area-assembly centroids + car-graph vertex reps) ->
  cool = 100*H/(S+H), H = 120, + mapped-green ramp +8*(1-d/500 m)
  (park-areas.json + derived-parks.json, mirrors p138). Detached-house
  sprawl (Nomme: 187 footprints/250 m) honestly reads hot — the claim
  is footprint density, not temperature; mapped gardens lift it via
  the ramp.

Computation: density layers stamp Euclidean kernels from 300 m reps
(sums commute, <=150 m error); distance layers run exact full-grid
8-connectivity Dijkstra from rasterized source cells (no cutoff, no
cliffs). Grid mirrors walk_raster (75 m county, 57.29/110.57 scales).

NO metro masters (documented): a distance-decay/density proxy is smooth
at 75 m; 9.375 m cells would be fake precision. The window route serves
county everywhere (metro slot stays empty).

One-time PBF exports (snapshot dir inputs, NOT committed — same pattern
as batch_g15_edu.py derived-water.geojson):
  S=~/hf-data/2026-09-12/osm
  osmium tags-filter $S/harjumaa-260911.osm.pbf nwr/aeroway \\
      -o /tmp/genv-aero.pbf --overwrite
  osmium export /tmp/genv-aero.pbf -o $S/derived-aeroway.geojson --overwrite
  osmium tags-filter $S/harjumaa-260911.osm.pbf \\
      w/highway=motorway w/highway=trunk w/highway=primary \\
      -o /tmp/genv-heavy.pbf --overwrite
  osmium export /tmp/genv-heavy.pbf -o $S/derived-heavyroads.geojson --overwrite
  osmium tags-filter $S/harjumaa-260911.osm.pbf nwr/building \\
      -o /tmp/genv-bld.pbf --overwrite
  osmium export /tmp/genv-bld.pbf -o /tmp/genv-bld.geojson --overwrite
  # -> $S/derived-buildings.json: ONE centroid per MultiPolygon area
  # assembly (largest outer ring); 252140 kept, 251912 LineString twins
  # (same closed ways re-emitted) + 5604 entrance/part nodes dropped.
  osmium tags-filter $S/harjumaa-260911.osm.pbf nwr/lit=yes \\
      -o /tmp/genv-lit.pbf --overwrite
  osmium export /tmp/genv-lit.pbf -o /tmp/genv-lit.geojson --overwrite
  # -> $S/derived-lit.json: nodes as-is + densified (<=50 m) LineStrings
  # (open lamp rows AND closed-ring twins); 720 MultiPolygon area-twins
  # dropped. Builder dedupes union+lamps into 20 m cells (74798).
  osmium tags-filter $S/harjumaa-260911.osm.pbf n/highway=street_lamp \\
      -o /tmp/genv-lamp.pbf --overwrite
  osmium export /tmp/genv-lamp.pbf -o $S/derived-streetlamps.geojson --overwrite
Residual twin risk (documented, PR #118 family): a lit=yes node sitting
on a lit=yes way merges in the 20 m dedupe; a closed lit way whose
LineString twin is missing (relation-only areas, <=22) is dropped with
its multi; an open building way (no area assembly, ~0 observed) is
dropped with its LineString. None of these moves a 75 m cell by more
than one kernel weight.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  python3 scripts/build/batch_genv_exposure.py --layer all \\
      --snap ~/hf-data/2026-09-12 --outdir ~/hf-data/2026-09-12/osm
  # single layer, small test bbox:
  python3 scripts/build/batch_genv_exposure.py --layer darksky \\
      --snap ~/hf-data/2026-09-12 --outdir /tmp/genv \\
      --bbox 24.6 59.35 24.9 59.5 --probe
Outputs per layer: <id>-walk-raster.json (combined wire, WalkRasterDoc
shape so cleanRaster accepts it); --format split writes <id>-walk-raster.json
(meta, data stubbed) + <id>-walk-raster.u8 (raw master).
"""

import argparse
import array
import base64
import heapq
import json
import math
import os
import sys
import time

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_b4_common scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
REP_M = 300.0  # source aggregation cell (density stamp error <= ~150 m)
KERNEL_CUTOFF_SIGMAS = 4.0
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)

# Calibration locked 2026-09-12 (see module docstring probes).
# NOTE: apps/web/lib/layers_genv.ts GENV_CAL mirrors these numbers
# exactly — test_batch_genv.py parses that file and fails on drift.
GENV_CAL = {
    "vibration": {"half_m": 300.0, "sigma": 0.3},
    "lowspec": {"half_m": 500.0, "sigma": 0.5},
    "flightcorr": {"major_half_m": 1500.0, "minor_half_m": 400.0,
                   "sigma": 0.3, "ext_km": 8.0, "ext_step_m": 200.0},
    "darksky": {"sigma": 0.3, "half": 120.0},
    "coolisland": {"sigma": 0.3, "half": 120.0,
                   "green_bonus": 8.0, "green_range_m": 500.0},
}

LAYER_IDS = ("vibration", "lowspec", "flightcorr", "darksky", "coolisland")

RAIL_VALUES = ("rail", "tram", "narrow_gauge", "light_rail")
PAVED_SURFACES = ("asphalt", "concrete", "paved")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.68, 59.375),
    "rural": (24.5, 59.2), "airport": (24.79659, 59.41646),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def kernel(d, sigma):
    return math.exp(-d * d / (2 * sigma * sigma))


def quiet_from_half(d_m, half_m):
    """Distance (m) -> calmness 0..100: 0 on the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


# ---------------------------------------------------------------------------
# Grid.
# ---------------------------------------------------------------------------

class Grid:
    """75 m county grid (mirrors walk_raster.Grid indexing)."""

    def __init__(self, bbox, step_m=STEP_M):
        self.bbox = list(bbox)
        self.step = step_m
        minlon, minlat, maxlon, maxlat = bbox
        self.cols = int(round((maxlon - minlon) * LON_KM * 1000 / step_m))
        self.rows = int(round((maxlat - minlat) * LAT_KM * 1000 / step_m))

    def cell_of(self, lon, lat):
        minlon, minlat, _, _ = self.bbox
        ix = int((lon - minlon) * LON_KM * 1000 / self.step)
        iy = int((lat - minlat) * LAT_KM * 1000 / self.step)
        if 0 <= ix < self.cols and 0 <= iy < self.rows:
            return iy * self.cols + ix
        return None

    def center_of(self, k):
        minlon, minlat, _, _ = self.bbox
        ix, iy = k % self.cols, k // self.cols
        return (minlon + (ix + 0.5) * self.step / 1000 / LON_KM,
                minlat + (iy + 0.5) * self.step / 1000 / LAT_KM)


# ---------------------------------------------------------------------------
# Snapshot readers (offline files only).
# ---------------------------------------------------------------------------

def _rep_key(lon, lat, size_m=REP_M):
    return (round(lon * LON_KM * 1000 / size_m),
            round(lat * LAT_KM * 1000 / size_m))


def _need(snap, *parts):
    p = os.path.join(snap, *parts)
    if not os.path.exists(p):
        raise SystemExit(
            "missing %s — run the one-time osmium exports in this "
            "module's docstring (snapshot-only, no network)" % p)
    return p


def read_road_reps(snap):
    """Car-graph vertices aggregated to 300 m reps: [(lon, lat, count)]."""
    g = json.load(open(_need(snap, "osm", "harju-car-graph.json")))
    acc = {}
    for lon, lat in g["nodes"]:
        k = _rep_key(lon, lat)
        acc[k] = acc.get(k, 0) + 1
    return [((k[0] + 0.5) * REP_M / 1000 / LON_KM,
             (k[1] + 0.5) * REP_M / 1000 / LAT_KM, v)
            for k, v in acc.items()]


def read_derived_points(snap, name):
    pts = json.load(open(_need(snap, "osm", "derived-%s.json" % name)))
    return [(p["lon"], p["lat"]) for p in pts]


def _densify_line(coords, step_km=0.05):
    pts = []
    for i, (lon, lat) in enumerate(coords):
        pts.append((lon, lat))
        if i == 0:
            continue
        plon, plat = coords[i - 1]
        d = hav_km(plon, plat, lon, lat)
        if d > step_km:
            n = int(d / step_km)
            for k in range(1, n):
                t = k / n
                pts.append((plon + (lon - plon) * t, plat + (lat - plat) * t))
    return pts


def read_amenity_geoms(snap, pred):
    """harju-amenities.geojson features matching pred(props) -> point lists.

    LineStrings densified to ~50 m; polygons yield their outer-ring points
    (interior coverage comes from the bbox+ring path where needed).
    Returns ([(lon, lat)], {"features": n, "kept": m}).
    """
    pts = []
    feats = kept = 0
    with open(_need(snap, "osm", "harju-amenities.geojson"),
              encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line.startswith("{"):
                continue
            try:
                feat = json.loads(line)
            except ValueError:
                continue
            if feat.get("type") != "Feature":
                continue
            feats += 1
            if not pred(feat.get("properties") or {}):
                continue
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            if geom.get("type") == "LineString" and coords:
                pts.extend(_densify_line([(c[0], c[1]) for c in coords]))
                kept += 1
            elif geom.get("type") == "MultiLineString" and coords:
                for linec in coords:
                    pts.extend(_densify_line([(c[0], c[1]) for c in linec]))
                kept += 1
            elif geom.get("type") == "Point" and coords:
                pts.append((coords[0], coords[1]))
                kept += 1
            elif geom.get("type") in ("Polygon", "MultiPolygon") and coords:
                rings = [coords[0]] if geom["type"] == "Polygon" \
                    else [p[0] for p in coords if p]
                for ring in rings:
                    pts.extend((c[0], c[1]) for c in ring[:: max(1, len(ring) // 50)])
                kept += 1
    return pts, {"features": feats, "kept": kept}


def read_rail_points(snap):
    pts, stats = read_amenity_geoms(
        snap, lambda p: p.get("railway") in RAIL_VALUES)
    return pts, stats


def read_industrial_points(snap):
    pts, stats = read_amenity_geoms(
        snap, lambda p: p.get("landuse") == "industrial")
    return pts, stats


def read_heavy_points(snap):
    """Motorway/trunk/primary carriageways (one-time PBF export)."""
    d = json.load(open(_need(snap, "osm", "derived-heavyroads.geojson"),
                       encoding="utf-8"))
    pts = []
    n = 0
    for f in d["features"] if isinstance(d, dict) else d:
        g = (f.get("geometry") or {})
        if g.get("type") != "LineString":
            continue
        pts.extend(_densify_line([(c[0], c[1]) for c in g["coordinates"]]))
        n += 1
    return pts, {"ways": n}


def runway_axis_extension(coords, ext_km, step_m):
    """Sampled points along the runway axis beyond both ends."""
    (x0, y0), (x1, y1) = coords[0], coords[-1]
    dx, dy = (x1 - x0) * LON_KM, (y1 - y0) * LAT_KM
    L = math.hypot(dx, dy)
    if L <= 0:
        return []
    ux, uy = dx / L, dy / L
    out = []
    # Integer step count (a float accumulator would drop the last step:
    # 0.2+0.2+0.2 > 0.6 in binary floating point).
    n_steps = int(round(ext_km * 1000.0 / step_m))
    for i in range(1, n_steps + 1):
        d = i * step_m / 1000.0
        for ex, ey in ((x0 * LON_KM - ux * d, y0 * LAT_KM - uy * d),
                       (x1 * LON_KM + ux * d, y1 * LAT_KM + uy * d)):
            out.append((ex / LON_KM, ey / LAT_KM))
    return out


def read_runway_sources(snap, cal):
    """(major_pts, minor_pts, stats): paved runways + extensions vs rest.

    Major = surface asphalt/concrete/paved (length-tiered judgment: jets
    and military traffic). Minor = grass strips + aerodrome points.
    Area twins (runway MultiPolygons) densify to the same cells as their
    LineString — harmless for a distance field, kept.
    """
    d = json.load(open(_need(snap, "osm", "derived-aeroway.geojson"),
                       encoding="utf-8"))
    feats = d["features"] if isinstance(d, dict) else d
    major, minor = [], []
    stats = {"major_seg": 0, "minor_seg": 0, "airfields": 0}
    for f in feats:
        p = f.get("properties") or {}
        g = f.get("geometry") or {}
        if p.get("aeroway") == "aerodrome" and g.get("type") == "Point":
            minor.append(tuple(g["coordinates"]))
            stats["airfields"] += 1
            continue
        if p.get("aeroway") != "runway":
            continue
        if g.get("type") == "LineString":
            co = [(c[0], c[1]) for c in g["coordinates"]]
        elif g.get("type") in ("Polygon", "MultiPolygon"):
            rings = [g["coordinates"][0]] if g["type"] == "Polygon" \
                else [poly[0] for poly in g["coordinates"] if poly]
            co = [(c[0], c[1]) for ring in rings for c in ring]
        else:
            continue
        co = _densify_line(co)
        if p.get("surface") in PAVED_SURFACES:
            major.extend(co)
            stats["major_seg"] += 1
            ends = ([(c[0], c[1]) for c in
                     (f.get("geometry") or {}).get("coordinates", [])]
                    if (f.get("geometry") or {}).get("type") == "LineString"
                    else co[:: max(1, len(co) - 1)])
            if len(ends) >= 2:
                major.extend(runway_axis_extension(
                    [ends[0], ends[-1]], cal["ext_km"], cal["ext_step_m"]))
        else:
            minor.extend(co)
            stats["minor_seg"] += 1
    return major, minor, stats


def dedupe_cells(points, cell_m=DEDUPE_M):
    """Merge node+area twins falling in the same ~cell_m cell."""
    cells = {}
    for lon, lat in points:
        k = (round(lon * LON_KM * 1000 / cell_m),
             round(lat * LAT_KM * 1000 / cell_m))
        if k not in cells:
            cells[k] = (lon, lat)
    return list(cells.values())


def read_lit_points(snap):
    """lit=yes points + street lamps, 20 m deduped (twin guard)."""
    pts = read_derived_points(snap, "lit")
    d = json.load(open(_need(snap, "osm", "derived-streetlamps.geojson"),
                       encoding="utf-8"))
    feats = d["features"] if isinstance(d, dict) else d
    for f in feats:
        g = f.get("geometry") or {}
        if g.get("type") == "Point":
            pts.append((g["coordinates"][0], g["coordinates"][1]))
    raw = len(pts)
    pts = dedupe_cells(pts)
    return pts, {"raw": raw, "cells": len(pts)}


def ring_contains(ring, lon, lat):
    """Mirror of ringContains() in snapshot.ts (ray cast, same tests)."""
    inside = False
    n = len(ring)
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[n - 1] if i == 0 else ring[i - 1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
    return inside


def read_nature_cells(grid, snap):
    """Cells whose centre falls inside a park-areas.json polygon, plus
    derived-parks.json point cells. Returns a set of cell ids (d_nat = 0)."""
    areas = json.load(open(_need(snap, "osm", "park-areas.json")))
    cells = set()
    for pa in areas:
        b = pa["b"]
        ix0 = max(0, int((b[0] - grid.bbox[0]) * LON_KM * 1000 / grid.step))
        ix1 = min(grid.cols - 1, int((b[2] - grid.bbox[0]) * LON_KM * 1000 / grid.step))
        iy0 = max(0, int((b[1] - grid.bbox[1]) * LAT_KM * 1000 / grid.step))
        iy1 = min(grid.rows - 1, int((b[3] - grid.bbox[1]) * LAT_KM * 1000 / grid.step))
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                k = iy * grid.cols + ix
                lon, lat = grid.center_of(k)
                if any(ring_contains(r, lon, lat) for r in pa["r"]):
                    cells.add(k)
    for lon, lat in read_derived_points(snap, "parks"):
        k = grid.cell_of(lon, lat)
        if k is not None:
            cells.add(k)
    return cells


# ---------------------------------------------------------------------------
# Fields: Euclidean density stamps + exact grid Dijkstra.
# ---------------------------------------------------------------------------

def stamp_density(grid, reps, sigma):
    """Kernel-density S per cell from [(lon, lat, weight)] reps.

    Stamps within 4*sigma (kernel tail beyond is < 1e-4 per unit weight).
    Returns array('d', len=cols*rows).
    """
    acc = array.array("d", [0.0]) * (grid.cols * grid.rows)
    cutoff = KERNEL_CUTOFF_SIGMAS * sigma
    for lon, lat, w in reps:
        if w <= 0:
            continue
        x0 = (lon - grid.bbox[0]) * LON_KM
        y0 = (lat - grid.bbox[1]) * LAT_KM
        ix0 = max(0, int((x0 - cutoff) * 1000 / grid.step))
        ix1 = min(grid.cols - 1, int((x0 + cutoff) * 1000 / grid.step))
        iy0 = max(0, int((y0 - cutoff) * 1000 / grid.step))
        iy1 = min(grid.rows - 1, int((y0 + cutoff) * 1000 / grid.step))
        for iy in range(iy0, iy1 + 1):
            clat = grid.bbox[1] + (iy + 0.5) * grid.step / 1000 / LAT_KM
            for ix in range(ix0, ix1 + 1):
                clon = grid.bbox[0] + (ix + 0.5) * grid.step / 1000 / LON_KM
                d = hav_km(lon, lat, clon, clat)
                if d <= cutoff:
                    acc[iy * grid.cols + ix] += w * kernel(d, sigma)
    return acc


def dijkstra_km(grid, source_cells):
    """Exact 8-connectivity distance (km) to the nearest source cell.

    No cutoff (sparse sources: no cliffs). Orthogonal step = cell km,
    diagonal = *sqrt(2); longitude scaled by LON_KM at cell latitude.
    Returns array('d') with +inf where unreachable (never in practice).
    """
    INF = float("inf")
    dist = array.array("d", [INF]) * (grid.cols * grid.rows)
    ortho = grid.step / 1000.0
    step_w = {1: ortho, 2: ortho * math.sqrt(2.0)}
    pq = []
    for k in source_cells:
        if 0 <= k < len(dist) and dist[k] > 0:
            dist[k] = 0.0
            heapq.heappush(pq, (0.0, k))
    cols, rows = grid.cols, grid.rows
    while pq:
        d, k = heapq.heappop(pq)
        if d > dist[k]:
            continue
        ix, iy = k % cols, k // cols
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < cols and 0 <= jy < rows):
                continue
            nd = d + step_w[dx * dx + dy * dy]
            j = jy * cols + jx
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(pq, (nd, j))
    return dist


def cells_of_points(grid, points):
    out = set()
    for lon, lat in points:
        k = grid.cell_of(lon, lat)
        if k is not None:
            out.add(k)
    return out


def to_reps(points, size_m=REP_M):
    """Aggregate points to weighted 300 m reps (sums commute)."""
    acc = {}
    for lon, lat in points:
        k = _rep_key(lon, lat, size_m)
        acc[k] = acc.get(k, 0) + 1
    return [((k[0] + 0.5) * size_m / 1000 / LON_KM,
             (k[1] + 0.5) * size_m / 1000 / LAT_KM, v)
            for k, v in acc.items()]


# ---------------------------------------------------------------------------
# Layer scores (high = calm/dark/cool; 0 = known-exposed, never 255).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-source calmness 100*d/(d+half) for one distance field."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


def score_flightcorr(d_major_km, d_minor_km, cal):
    """Worst exposure wins: min over the two runway tiers."""
    out = bytearray(len(d_major_km))
    for k in range(len(d_major_km)):
        q = min(quiet_from_half(d_major_km[k] * 1000.0, cal["major_half_m"]),
                quiet_from_half(d_minor_km[k] * 1000.0, cal["minor_half_m"]))
        out[k] = max(0, min(100, int(round(q))))
    return out


def score_density(s_acc, half):
    """Density exposure 100*half/(S+half): 100 where nothing mapped."""
    out = bytearray(len(s_acc))
    for k in range(len(s_acc)):
        out[k] = max(0, min(100, int(round(100.0 * half / (s_acc[k] + half)))))
    return out


def score_coolisland(s_imp, d_nat_km, cal):
    """Impervious coolness + mapped-green ramp (cap 100)."""
    out = bytearray(len(s_imp))
    for k in range(len(s_imp)):
        q = 100.0 * cal["half"] / (s_imp[k] + cal["half"])
        dn = d_nat_km[k] * 1000.0
        if dn <= cal["green_range_m"]:
            q += cal["green_bonus"] * (1 - dn / cal["green_range_m"])
        out[k] = max(0, min(100, int(round(q))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = GENV_CAL[layer]
    if layer == "flightcorr":
        return cal["major_half_m"], cal["sigma"]
    if layer in ("darksky", "coolisland"):
        return cal["half"], cal["sigma"]
    return cal["half_m"], cal["sigma"]


def encode_wire(grid, values, layer):
    half, sigma = contract_of(layer)
    return {
        "cols": grid.cols, "rows": grid.rows,
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step, "half": half, "sigma": sigma,
        "per": 0, "cap": 0, "unknown": 255, "dtype": "uint8",
        "data": base64.b64encode(bytes(values)).decode("ascii"),
    }


def write_outputs(outdir, layer, grid, values, fmt):
    name = "%s-walk-raster" % layer
    if fmt == "split":
        with open(os.path.join(outdir, name + ".json"), "w",
                  encoding="utf-8") as f:
            doc = encode_wire(grid, values, layer)
            doc["data"] = "AA=="  # meta only; bytes live in the .u8 master
            json.dump(doc, f)
        with open(os.path.join(outdir, name + ".u8"), "wb") as f:
            f.write(bytes(values))
        print("wrote %s.json + .u8" % name, flush=True)
    else:
        with open(os.path.join(outdir, name + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(encode_wire(grid, values, layer), f)
        print("wrote %s.json" % name, flush=True)


def build_all(snap, grid, cache_path):
    """Shared fields once -> per-layer byte masters. Returns {layer: bytes}."""
    t0 = time.time()
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            import pickle
            fields = pickle.load(f)
        print("fields: loaded %s (skipped stamping)" % cache_path, flush=True)
    else:
        print("roads: reading car graph...", flush=True)
        road_reps = read_road_reps(snap)
        print("roads: %d reps" % len(road_reps), flush=True)
        print("buildings...", flush=True)
        bld_pts = read_derived_points(snap, "buildings")
        print("buildings: %d centroids" % len(bld_pts), flush=True)
        print("rail...", flush=True)
        rail_pts, rail_stats = read_rail_points(snap)
        print("rail=%s" % (rail_stats,), flush=True)
        print("heavy roads...", flush=True)
        heavy_pts, heavy_stats = read_heavy_points(snap)
        print("heavy=%s" % (heavy_stats,), flush=True)
        print("industrial...", flush=True)
        ind_pts, ind_stats = read_industrial_points(snap)
        print("industrial=%s" % (ind_stats,), flush=True)
        print("runways...", flush=True)
        major_pts, minor_pts, rwy_stats = read_runway_sources(
            snap, GENV_CAL["flightcorr"])
        print("runways=%s" % (rwy_stats,), flush=True)
        print("lit...", flush=True)
        lit_pts, lit_stats = read_lit_points(snap)
        print("lit=%s" % (lit_stats,), flush=True)

        cal = GENV_CAL
        print("stamp: impervious density...", flush=True)
        imp_reps = to_reps(bld_pts) + road_reps
        s_imp = stamp_density(grid, imp_reps, cal["coolisland"]["sigma"])
        print("stamp: lit density...", flush=True)
        s_lit = stamp_density(grid, to_reps(lit_pts), cal["darksky"]["sigma"])
        print("dijkstra: rail+heavy (vibration)...", flush=True)
        d_vib = dijkstra_km(grid, cells_of_points(grid, rail_pts + heavy_pts))
        print("dijkstra: heavy+rail+industrial (lowspec)...", flush=True)
        d_low = dijkstra_km(
            grid, cells_of_points(grid, heavy_pts + rail_pts + ind_pts))
        print("dijkstra: runway tiers...", flush=True)
        d_major = dijkstra_km(grid, cells_of_points(grid, major_pts))
        d_minor = dijkstra_km(grid, cells_of_points(grid, minor_pts))
        print("nature cells...", flush=True)
        nat_cells = read_nature_cells(grid, snap)
        print("nature cells=%d; dijkstra: nature..." % len(nat_cells), flush=True)
        d_nat = dijkstra_km(grid, nat_cells)
        fields = {"s_imp": s_imp, "s_lit": s_lit, "d_vib": d_vib,
                  "d_low": d_low, "d_major": d_major, "d_minor": d_minor,
                  "d_nat": d_nat}
        if cache_path:
            with open(cache_path, "wb") as f:
                import pickle
                pickle.dump(fields, f, protocol=4)
            print("fields: saved %s" % cache_path, flush=True)
    print("fields ready (%.1fs)" % (time.time() - t0), flush=True)

    out = {}
    out["vibration"] = score_distance(
        fields["d_vib"], GENV_CAL["vibration"]["half_m"])
    out["lowspec"] = score_distance(
        fields["d_low"], GENV_CAL["lowspec"]["half_m"])
    out["flightcorr"] = score_flightcorr(
        fields["d_major"], fields["d_minor"], GENV_CAL["flightcorr"])
    out["darksky"] = score_density(fields["s_lit"], GENV_CAL["darksky"]["half"])
    out["coolisland"] = score_coolisland(
        fields["s_imp"], fields["d_nat"], GENV_CAL["coolisland"])
    return out


def probe_scores(masters, grid):
    print("probe (high = calm/dark/cool):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-9s outside grid" % name, flush=True)
            continue
        print("  %-9s %s" % (name, {l: masters[l][k] for l in LAYER_IDS}),
              flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--snap", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--stamp-cache", default=None)
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    cache = args.stamp_cache or os.path.join(args.outdir, "genv-fields.pkl")
    masters = build_all(args.snap, grid, cache if args.layer == "all" else None)
    for layer in layers:
        write_outputs(args.outdir, layer, grid, masters[layer], args.format)
        vals = masters[layer]
        known = sum(1 for v in vals if v != 255)
        print("%s: cells=%d known=%d zeros(known-exposed)=%d" %
              (layer, len(vals), known, sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
