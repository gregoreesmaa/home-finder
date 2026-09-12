"""Group 9 noise-proxy county masters (issue #104): p16/p138/p162/p301/p493.

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; the full-county build runs only
via the documented rebuild command.

HONESTY (load-bearing): Transpordiamet CNOSSOS-EU rasters are not in the
snapshot, so these are road/rail-traffic PROXIMITY proxies — titles,
legends and sources say "müraproksi", never dBA. Green = quiet/far,
red = loud/near. In-bbox absence of a mapped source IS the quiet
evidence, so masters emit no in-bbox unknowns (0 = known-loud on the
source, never 255); out-of-coverage stays 255 server-side (cover mask).

Model (locked 2026-09-12 from snapshot probes at Balti/Viru/Kadriorg/
Õismäe/Lasnamäe/Viimsi/rural/airport):
* trafficnoise (p16): road-vertex density kernel (sigma 0.3 km, 300 m
  reps with counts) -> loud_road = S/(S+400); rail kernel
  loud_rail = K(d_rail, 0.3); quiet = 100*(1-max(...)). Probe S_road:
  Balti 1033, Viru 761, Kadriorg 535, Viimsi 499, rural 33 -> half 400
  puts the city mid-ramp (28-44) and rural at 92. Class-blind (the car
  graph carries no highway class): a farm track counts like a street —
  conservative, documented.
* quietnature (p138): trafficnoise quiet + nature ramp
  +10*max(0, 1-d_nat/600 m) from park-areas.json coverage (+ parks points).
  Unmapped forest earns no bonus but keeps its traffic quietness.
* nuisance (p162): nearest nightlife (bar/pub/nightclub/casino, 265 pts —
  cinema excluded, seated culture) or industrial (54 polys) source:
  quiet = 100*d/(d+300). Probe: Balti 73 m -> 20, Viru 324 m -> 52,
  Kadriorg 786 m -> 72, rural -> ~100.
* lowfreq (p301): nearest rail (1291 LineStrings densified) or industrial:
  quiet = 100*d/(d+500). Probe: Balti 15 m -> 3, Viru 560 m -> 53.
* braking (p493): junction (distinct-neighbour >= 3, 71477) + stop (8049)
  + level-crossing kernel density (sigma 0.3): quiet = 100*120/(S+120).
  Probe S: Balti ~280, Viru ~240, Viimsi ~140, rural ~10.

Computation: density layers stamp Euclidean kernels from 300 m reps
(sums commute, <=150 m error); distance layers run exact full-grid
8-connectivity Dijkstra from rasterized source cells (no cutoff, no
cliffs). Grid mirrors walk_raster (75 m county, 57.29/110.57 scales).

NO metro masters (documented): a distance-decay proxy is smooth at
75 m; 9.375 m cells would be fake precision. The window route serves
county everywhere (metro slot stays empty).

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  python3 scripts/build/batch_g09_noise.py --layer all \\
      --snap ~/hf-data/2026-09-12 --outdir ~/hf-data/2026-09-12/osm
  # single layer, small test bbox:
  python3 scripts/build/batch_g09_noise.py --layer nuisance \\
      --snap ~/hf-data/2026-09-12 --outdir /tmp/g09 \\
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

# Calibration locked 2026-09-12 (see module docstring probes).
# NOTE: apps/web/lib/layers_group09.ts GROUP09_CAL mirrors these numbers
# exactly — test_batch_g09.py parses that file and fails on drift.
G09_CAL = {
    "trafficnoise": {"sigma": 0.3, "road_half": 400.0, "rail_sigma": 0.3},
    "quietnature": {"sigma": 0.3, "road_half": 400.0, "rail_sigma": 0.3,
                    "nature_bonus": 10.0, "nature_range_m": 600.0},
    "nuisance": {"half_m": 300.0, "sigma": 0.3},
    "lowfreq": {"half_m": 500.0, "sigma": 0.5},
    "braking": {"sigma": 0.3, "half": 120.0},
}

LAYER_IDS = ("trafficnoise", "quietnature", "nuisance", "lowfreq", "braking")

NUISANCE_AMENITIES = ("bar", "pub", "nightclub", "casino")
RAIL_VALUES = ("rail", "tram", "narrow_gauge", "light_rail")
CROSSING_VALUES = ("level_crossing", "tram_level_crossing",
                   "tram_crossing", "crossing")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "rural": (24.5, 59.2), "airport": (24.79659, 59.41646),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def kernel(d, sigma):
    return math.exp(-d * d / (2 * sigma * sigma))


def quiet_from_half(d_m, half_m):
    """Distance (m) -> quietness 0..100: 0 on the source, 50 at half_m."""
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


def read_road_reps(snap):
    """Car-graph vertices aggregated to 300 m reps: [(lon, lat, count)]."""
    g = json.load(open(os.path.join(snap, "osm", "harju-car-graph.json")))
    acc = {}
    for lon, lat in g["nodes"]:
        k = _rep_key(lon, lat)
        acc[k] = acc.get(k, 0) + 1
    out = [((k[0] + 0.5) * REP_M / 1000 / LON_KM,
            (k[1] + 0.5) * REP_M / 1000 / LAT_KM, v)
           for k, v in acc.items()]
    return out


def read_junction_reps(snap):
    """Distinct-neighbour (>= 3) car-graph junctions as 300 m reps."""
    g = json.load(open(os.path.join(snap, "osm", "harju-car-graph.json")))
    nbr = {}
    for a, b, _m in g["edges"]:
        if a == b:
            continue
        nbr.setdefault(a, set()).add(b)
        nbr.setdefault(b, set()).add(a)
    acc = {}
    for i, s in nbr.items():
        if len(s) >= 3:
            lon, lat = g["nodes"][i]
            k = _rep_key(lon, lat)
            acc[k] = acc.get(k, 0) + 1
    return [((k[0] + 0.5) * REP_M / 1000 / LON_KM,
             (k[1] + 0.5) * REP_M / 1000 / LAT_KM, v)
            for k, v in acc.items()]


def read_derived_points(snap, name):
    pts = json.load(open(os.path.join(snap, "osm", "derived-%s.json" % name)))
    return [(p["lon"], p["lat"]) for p in pts]


def _densify_line(coords, step_km=0.04):
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

    LineStrings densified to ~40 m; polygons yield their outer-ring points
    (interior coverage comes from the bbox+ring path where needed).
    Returns ([(lon, lat)], {"features": n, "kept": m}).
    """
    pts = []
    feats = kept = 0
    with open(os.path.join(snap, "osm", "harju-amenities.geojson"),
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


def read_nuisance_points(snap):
    """Nightlife (cinema excluded) + industrial-ring points."""
    nl = json.load(open(os.path.join(snap, "osm", "derived-nightlife.json")))
    pts = [(p["lon"], p["lat"]) for p in nl
           if (p.get("tags") or {}).get("amenity") in NUISANCE_AMENITIES]
    ind, stats = read_amenity_geoms(
        snap, lambda p: p.get("landuse") == "industrial")
    return pts + ind, {"nightlife": len(pts), "industrial_geoms": stats["kept"]}


def read_crossing_points(snap):
    pts, stats = read_amenity_geoms(
        snap, lambda p: p.get("railway") in CROSSING_VALUES)
    return pts, stats


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
    areas = json.load(open(os.path.join(snap, "osm", "park-areas.json")))
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
    # Equirectangular cell metric, hav_km-consistent: one orthogonal step
    # is step/1000 km in either axis (dx_deg*LON_KM == step/1000 by
    # construction), diagonals scale by hypot — latitude-independent.
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


# ---------------------------------------------------------------------------
# Layer scores (quietness 0..100, high = quiet; 0 = known-loud, never 255).
# ---------------------------------------------------------------------------

def score_trafficnoise(s_road, d_rail_km, cal):
    """quiet = 100*(1-max(road loudness, rail kernel))."""
    out = bytearray(len(s_road))
    for k in range(len(s_road)):
        loud_road = s_road[k] / (s_road[k] + cal["road_half"]) if s_road[k] > 0 else 0.0
        loud_rail = kernel(d_rail_km[k], cal["rail_sigma"]) \
            if d_rail_km[k] < float("inf") else 0.0
        out[k] = max(0, min(100, int(round(100 * (1 - max(loud_road, loud_rail))))))
    return out


def score_quietnature(s_road, d_rail_km, d_nat_km, cal):
    """trafficnoise quiet + nature ramp bonus (cap 100)."""
    out = bytearray(len(s_road))
    for k in range(len(s_road)):
        loud_road = s_road[k] / (s_road[k] + cal["road_half"]) if s_road[k] > 0 else 0.0
        loud_rail = kernel(d_rail_km[k], cal["rail_sigma"]) \
            if d_rail_km[k] < float("inf") else 0.0
        q = 100 * (1 - max(loud_road, loud_rail))
        dn = d_nat_km[k] * 1000.0
        if dn <= cal["nature_range_m"]:
            q += cal["nature_bonus"] * (1 - dn / cal["nature_range_m"])
        out[k] = max(0, min(100, int(round(q))))
    return out


def score_distance(d_km, half_m):
    """Nearest-source quietness 100*d/(d+half) for one distance field."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


def score_braking(s_brake, cal):
    out = bytearray(len(s_brake))
    for k in range(len(s_brake)):
        out[k] = max(0, min(100, int(round(100 * cal["half"] / (s_brake[k] + cal["half"])))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook.

    Density layers carry their S-half; distance layers carry half_m with
    sigma = half_m/1000 (same scale story as the Euclidean fallback).
    """
    cal = G09_CAL[layer]
    if layer in ("trafficnoise", "quietnature"):
        return cal["road_half"], cal["sigma"]
    if layer == "braking":
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
        print("junctions: reading car graph...", flush=True)
        junc_reps = read_junction_reps(snap)
        print("junctions: %d reps" % len(junc_reps), flush=True)
        print("stops...", flush=True)
        stop_pts = read_derived_points(snap, "transit")
        cross_pts, cross_stats = read_crossing_points(snap)
        print("stops=%d crossings=%s" % (len(stop_pts), cross_stats), flush=True)
        rail_pts, rail_stats = read_rail_points(snap)
        print("rail=%s" % (rail_stats,), flush=True)
        nuis_pts, nuis_stats = read_nuisance_points(snap)
        print("nuisance=%s" % (nuis_stats,), flush=True)
        ind_pts, ind_stats = read_amenity_geoms(
            snap, lambda p: p.get("landuse") == "industrial")
        print("industrial pts=%d" % len(ind_pts), flush=True)

        cal = G09_CAL
        print("stamp: road density...", flush=True)
        s_road = stamp_density(grid, road_reps, cal["trafficnoise"]["sigma"])
        print("stamp: brake density...", flush=True)
        brake_reps = ([(lo, la, 1.0) for lo, la in stop_pts]
                      + [(lo, la, 1.0) for lo, la in cross_pts]
                      + junc_reps)
        s_brake = stamp_density(grid, brake_reps, cal["braking"]["sigma"])
        print("dijkstra: rail...", flush=True)
        d_rail = dijkstra_km(grid, cells_of_points(grid, rail_pts))
        print("dijkstra: nuisance...", flush=True)
        d_nuis = dijkstra_km(grid, cells_of_points(grid, nuis_pts))
        print("dijkstra: lowfreq (rail+industrial)...", flush=True)
        d_low = dijkstra_km(grid, cells_of_points(grid, rail_pts + ind_pts))
        print("nature cells...", flush=True)
        nat_cells = read_nature_cells(grid, snap)
        print("nature cells=%d; dijkstra: nature..." % len(nat_cells), flush=True)
        d_nat = dijkstra_km(grid, nat_cells)
        fields = {"s_road": s_road, "s_brake": s_brake, "d_rail": d_rail,
                  "d_nuis": d_nuis, "d_low": d_low, "d_nat": d_nat}
        if cache_path:
            with open(cache_path, "wb") as f:
                import pickle
                pickle.dump(fields, f, protocol=4)
            print("fields: saved %s" % cache_path, flush=True)
    print("fields ready (%.1fs)" % (time.time() - t0), flush=True)

    out = {}
    out["trafficnoise"] = score_trafficnoise(
        fields["s_road"], fields["d_rail"], G09_CAL["trafficnoise"])
    out["quietnature"] = score_quietnature(
        fields["s_road"], fields["d_rail"], fields["d_nat"],
        G09_CAL["quietnature"])
    out["nuisance"] = score_distance(
        fields["d_nuis"], G09_CAL["nuisance"]["half_m"])
    out["lowfreq"] = score_distance(
        fields["d_low"], G09_CAL["lowfreq"]["half_m"])
    out["braking"] = score_braking(fields["s_brake"], G09_CAL["braking"])
    return out


def probe_scores(masters, grid):
    print("probe (quietness 0..100, high = quiet):", flush=True)
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
    cache = args.stamp_cache or os.path.join(args.outdir, "g09-fields.pkl")
    masters = build_all(args.snap, grid, cache if args.layer == "all" else None)
    for layer in layers:
        write_outputs(args.outdir, layer, grid, masters[layer], args.format)
        vals = masters[layer]
        known = sum(1 for v in vals if v != 255)
        print("%s: cells=%d known=%d zeros(known-loud)=%d" %
              (layer, len(vals), known, sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
