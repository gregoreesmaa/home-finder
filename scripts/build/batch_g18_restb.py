"""Group 18 rest-B county masters (issue #173): p468 fishbowl + p479
mossrisk + p405 daylight.

Stdlib only. Offline, snapshot-only (NO network): junction vectors
come from the LOCAL foot graph, forest vectors from the LOCAL
Harjumaa PBF via the documented osmium pre-step, and building vectors
from the committed snapshot derived file — never from a live service.
Pure logic + snapshot readers live at module top so unit tests stay
hermetic; full-county builds run only via the documented rebuild
commands.

SCOPE (three layers, honest): this builder serves ONLY p468 (corner
lot fishbowl effect) as a settled-junction proximity hinnang, p479
(roof moss/algae shading) as a mapped-forest distance hinnang, and
p405 (circadian lighting potential) as a building-openness
(INVERTED count) hinnang. The sibling params are documented no-map
(see apps/web/lib/layers_group18restb.ts): p394 patio sun
orientation (a per-building azimuth fact — the snapshot carries
centroids only) and p403 natural EM shielding (a terrain +
transmitter fact — no DEM, no transmitter register) ship as scorer
dims only (services/scoring/dims_group18restb.py), OTA PR #131
precedent.

HONESTY (load-bearing): Maa-amet LoD2 3D CityGML meshes, ALS LiDAR
point clouds, PVLib/PVGIS solar models and any RF transmitter
register are NOT in the 2026-09-12 snapshot, so no master is a
3D-simulation result. fishbowl scores nearness to SETTLED ≥3-arm
foot-graph junctions (corner lots face streets on ≥2 sides — never a
cadastral ruling); mossrisk scores distance to MAPPED forest stands
(polygons filled: inside the stand reads 0 — never a moisture
reading); daylight scores the INVERTED COUNT of mapped buildings
nearby (open sky — never a lux measurement). Titles, legends and
sources say "hinnang" (pinned by layers_group18restb.test.ts).

Models (locked 2026-09-12):
* fishbowl (p468): exact full-grid 8-connectivity Dijkstra distance
  to the nearest settled-junction cell (same machinery as
  batch_g05c_plans.py, local Grid copy for self-containment),
  score = 100*d/(d+150). halfM=150 m: corner exposure is
  sub-block-scale — dense-grid districts read honestly low, detached
  Nõmme reads calm. Settled = junction within ~1 cell of a mapped
  building on a 200 m grid (trail forks in empty forest drop out: a
  fork with no house nearby is not a corner lot — the rural probe
  moves 98 m → 1064 m, city probes unchanged).
* mossrisk (p479): exact full-grid Dijkstra distance to the nearest
  forest-stand cell, score = 100*d/(d+250). halfM=250 m: stand
  shade/spore range — Nõmme/Viimsi read honestly low, Paljassaare
  reads calm. Forest polygons are FILLED (a parcel inside the stand
  reads 0: inside IS the pressure); wood lines feed densified.
  43,522 mapped street/park trees are OUT by design (a street tree is
  not a moss stand — a panel is not a farm, #163 precedent).
* daylight (p405): Euclidean Gaussian INVERTED count kernel over the
  252,140 mapped building centroids (sigma 0.3, cutoff 4 sigma,
  score 100*half/(S+half) with half=150 — new "sparse" kind, the
  mirror image of the moorage area shape). Zero buildings in range
  reads 100 (measured open, honestly known — NOT 255 unknown like
  viewshed deserts: buildings ARE the obstruction and the inventory
  is near-complete). Tallinn S spans 31 (Nõmme) → 476 (Toompea), so
  half 150 parks the city median mid-ramp. Green sits where buildings
  are SPARSE (open sky).

Sources (predicates verified on the snapshot extract):
* junctions: harju-foot-graph.json (721,873 nodes / 796,269
  undirected edges): degree≥3 = 144,580 county-wide (74,932 in the
  Tallinn window); the settled filter keeps 139,474 county-wide.
* forest: natural=wood or landuse=forest (verified 2026-09-12:
  8,683 polygons + 8,367 lines + 63 points = 17,113 kept
  county-wide). natural=tree points are OUT by design (43,522: a
  street tree is not a moss stand). Untagged members carry no
  natural/landuse, so they drop out in keep_forest.
* buildings: derived-buildings.json (252,140 bare centroids, reused
  directly — no tags to verify).

Computation: fishbowl + mossrisk are graph-free Euclidean fields
on the 75 m county grid (57.29/110.57 scales) — exact-grid Dijkstra
nearest-source distance; daylight is a graph-free Gaussian inverted
count kernel on the same grid. NO metro masters (documented): smooth
distance-decay fields and a county-wide count kernel at 9.375 m
cells would be fake precision — the window route serves county
everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/natural=wood nwr/landuse=forest \
      -o /tmp/hf-g18b-forest.pbf --overwrite
  osmium export /tmp/hf-g18b-forest.pbf -o /tmp/hf-g18b-forest.geojson
  python3 scripts/build/batch_g18_restb.py --layer all \
      --graph ~/hf-data/2026-09-12/osm/harju-foot-graph.json \
      --buildings ~/hf-data/2026-09-12/osm/derived-buildings.json \
      --forest /tmp/hf-g18b-forest.geojson \
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: fishbowl/mossrisk-walk-raster.json (Dijkstra quiet masters)
+ daylight-walk-raster.json (inverted-count sparse master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-<layer>.json
(fallback points for the Euclidean route + overlay). Restart the web
server afterwards — the server caches masters per process.
"""

import argparse
import array
import base64
import collections
import heapq
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_g05c_plans scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # line vertex spacing for source rasterisation
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)
SETTLE_M = 200.0  # settled-junction grid: junction within ~1 cell of a
# building counts as a corner-lot candidate (trail forks in empty
# forest drop out).

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group18restb.ts G18B_CAL mirrors these numbers
# exactly — test_batch_g18_restb.py parses that file and fails on drift.
G18B_CAL = {
    "fishbowl": {"half_m": 150.0, "sigma": 0.3},
    "mossrisk": {"half_m": 250.0, "sigma": 0.3},
    "daylight": {"half": 150.0, "sigma": 0.3},
}

LAYER_IDS = ("fishbowl", "mossrisk", "daylight")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
    "Ulemiste": (24.7956, 59.4229), "Kohtuotsa": (24.7399, 59.4357),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> calmness 0..100: 0 on the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


def kernel(d_km, sigma):
    """Gaussian kernel weight (moorage precedent: exp(-d^2/2σ^2))."""
    return math.exp(-(d_km * d_km) / (2.0 * sigma * sigma))


def area_score(s, half):
    """Saturating count score 100*S/(S+half) (mirrors walk_raster.saturate)."""
    return 100.0 * s / (s + half)


def sparse_score(s, half):
    """Inverted count score 100*half/(S+half): 100 where open, 50 at half."""
    return 100.0 * half / (s + half)


# ---------------------------------------------------------------------------
# Grid (local copy for self-containment, mirrors batch_g05c_plans).
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
# Source predicates + readers (offline snapshot files only).
# ---------------------------------------------------------------------------

def _first(value):
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def keep_forest(props):
    """True when a forest-extract feature is a moss-pressure stand.

    natural=wood or landuse=forest (polygons, lines and points).
    natural=tree points are OUT by design (a street tree is not a moss
    stand — a panel is not a farm, #163 precedent). Untagged members
    drop out here.
    """
    props = props or {}
    # NOTE: _first(None) reads "None" (str of None) — missing keys never
    # match "wood"/"forest", so untagged members drop out (no twin purge
    # needed beyond the cell dedupe).
    if _first(props.get("natural")) == "wood":
        return True
    return _first(props.get("landuse")) == "forest"


def _densify_line(coords, step_km=DENSIFY_M / 1000.0):
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


def _stride_ring(ring, per=25):
    pts = [(c[0], c[1]) for c in ring]
    return pts[:: max(1, len(pts) // per)]


def _point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # NOTE: parenthesised on purpose — Python would CHAIN
        # `yi > lat != yj > lat` into different semantics (and divide
        # by zero on horizontal edges); the JS twin (ringContains in
        # snapshot.ts) groups as (yi > lat) !== (yj > lat).
        if (yi > lat) != (yj > lat) and \
                lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    return [x for x in feats if isinstance(x, dict)]


def read_graph_junctions(graph_path):
    """All ≥3-arm foot-graph nodes (walkability precedent).

    Returns ([(lon, lat)], stats). The graph is undirected; degree
    counts both endpoints. Loaded whole (35 MB) — the settled filter
    below needs the full node set anyway.
    """
    with open(graph_path, encoding="utf-8") as f:
        graph = json.load(f)
    nodes = graph["nodes"]
    deg = collections.Counter()
    for e in graph["edges"]:
        deg[e[0]] += 1
        deg[e[1]] += 1
    pts = [tuple(nodes[i]) for i, d in deg.items() if d >= 3]
    return pts, {"junctions": len(pts), "nodes": len(nodes)}


def read_building_cells(buildings_path, cell_m=SETTLE_M):
    """Mapped-building occupancy on a cell_m grid (settled filter index).

    derived-buildings.json is a bare [{lon, lat}] list. Returns
    (set of (cx, cy), count).
    """
    with open(buildings_path, encoding="utf-8") as f:
        doc = json.load(f)
    pts = doc if isinstance(doc, list) else doc.get("points", doc)
    cells = set()
    n = 0
    for p in pts:
        try:
            lon, lat = p["lon"], p["lat"]
        except (TypeError, KeyError):
            continue
        cells.add((round(lon * LON_KM * 1000 / cell_m),
                   round(lat * LAT_KM * 1000 / cell_m)))
        n += 1
    return cells, n


def settled_junctions(junctions, building_cells, cell_m=SETTLE_M):
    """Keep junctions within ~1 settled-grid cell of a mapped building.

    Trail forks in empty forest drop out (a fork with no house nearby
    is not a corner lot); city junctions are unchanged (the rural
    probe moves 98 m → 1064 m, Balti stays 16 m).
    """
    out = []
    for lon, lat in junctions:
        cx = round(lon * LON_KM * 1000 / cell_m)
        cy = round(lat * LAT_KM * 1000 / cell_m)
        if any((cx + dx, cy + dy) in building_cells
               for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            out.append((lon, lat))
    return out


def read_forest_points(forest_path):
    """Forest-stand source cells from a forest geojson extract.

    Points feed directly; open lines are densified; polygons are
    boundary-sampled AND filled (a parcel inside the stand reads 0:
    inside IS the pressure). Returns ([(lon, lat)], fill_polys,
    stats).
    """
    pts = []
    polys = []  # outer rings for the grid fill
    stats = {"stands": 0, "dropped": 0}
    for feat in _iter_features(forest_path):
        if not keep_forest(feat.get("properties") or {}):
            stats["dropped"] += 1
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            stats["dropped"] += 1
            continue
        gtype = geom.get("type")
        if gtype == "Point":
            pts.append((coords[0], coords[1]))
            stats["stands"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))
            else:
                pts.extend(_densify_line(co))
            stats["stands"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
                polys.append([(c[0], c[1]) for c in ring])
            stats["stands"] += 1
        else:
            stats["dropped"] += 1
    return pts, polys, stats


def read_building_points(buildings_path):
    """Building centroids from derived-buildings.json (bare list)."""
    with open(buildings_path, encoding="utf-8") as f:
        doc = json.load(f)
    pts = doc if isinstance(doc, list) else doc.get("points", doc)
    out = []
    for p in pts:
        try:
            out.append((p["lon"], p["lat"]))
        except (TypeError, KeyError):
            continue
    return out


def fill_poly_cells(grid, polys):
    """Grid cells whose centre falls inside a polygon ring."""
    cells = set()
    for ring in polys:
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        minlon, minlat, _, _ = grid.bbox
        ix_lo = max(0, int((min(lons) - minlon) * LON_KM * 1000 / grid.step))
        ix_hi = min(grid.cols - 1,
                    int((max(lons) - minlon) * LON_KM * 1000 / grid.step))
        iy_lo = max(0, int((min(lats) - minlat) * LAT_KM * 1000 / grid.step))
        iy_hi = min(grid.rows - 1,
                    int((max(lats) - minlat) * LAT_KM * 1000 / grid.step))
        for iy in range(iy_lo, iy_hi + 1):
            for ix in range(ix_lo, ix_hi + 1):
                clon = minlon + (ix + 0.5) * grid.step / 1000 / LON_KM
                clat = minlat + (iy + 0.5) * grid.step / 1000 / LAT_KM
                if _point_in_ring(clon, clat, ring):
                    cells.add(iy * grid.cols + ix)
    return cells


def dedupe_cells(points, cell_m=DEDUPE_M):
    """Merge node+area twins falling in the same ~cell_m cell."""
    cells = {}
    for lon, lat in points:
        k = (round(lon * LON_KM * 1000 / cell_m),
             round(lat * LAT_KM * 1000 / cell_m))
        if k not in cells:
            cells[k] = (lon, lat)
    return list(cells.values())


# ---------------------------------------------------------------------------
# Fields: exact grid Dijkstra (quiet) + Gaussian kernels (area/sparse).
# ---------------------------------------------------------------------------

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


def count_kernel_field(grid, points, sigma):
    """Gaussian count accumulation: cell -> S (moorage precedent).

    Bounded O(points * range^2) sweep: each point stamps
    kernel(d, sigma) into cells within 4 sigma. Unstamped cells stay
    absent (the quiet/area scorers render them 255 unknown, never a
    faked zero — the SPARSE scorer instead reads absent as measured
    open, see score_sparse_cells).
    """
    cutoff_km = 4.0 * sigma
    acc = {}
    minlon, minlat, _, _ = grid.bbox
    for lon, lat in points:
        x0 = (lon - minlon) * LON_KM
        y0 = (lat - minlat) * LAT_KM
        ix_lo = max(0, int((x0 - cutoff_km) * 1000 / grid.step))
        ix_hi = min(grid.cols - 1, int((x0 + cutoff_km) * 1000 / grid.step))
        iy_lo = max(0, int((y0 - cutoff_km) * 1000 / grid.step))
        iy_hi = min(grid.rows - 1, int((y0 + cutoff_km) * 1000 / grid.step))
        for iy in range(iy_lo, iy_hi + 1):
            for ix in range(ix_lo, ix_hi + 1):
                clon = minlon + (ix + 0.5) * grid.step / 1000 / LON_KM
                clat = minlat + (iy + 0.5) * grid.step / 1000 / LAT_KM
                d = hav_km(lon, lat, clon, clat)
                if d > cutoff_km:
                    continue
                k = iy * grid.cols + ix
                acc[k] = acc.get(k, 0.0) + kernel(d, sigma)
    return acc


# ---------------------------------------------------------------------------
# Layer scores (high = calm/open; 0 = known-exposed, never 255 — except
# nothing: all three G18B masters are full-grid, honestly known
# everywhere. Daylight desert reads 100 = measured open, NOT unknown).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-source calmness 100*d/(d+half) for one distance field."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


def score_sparse_cells(grid, acc, half):
    """Inverted building-count score 100*half/(S+half) on the FULL grid.

    New "sparse" kind (daylight): green where SPARSE. Unstamped cells
    (S=0) read 100 — measured open, honestly known: buildings ARE the
    obstruction and the inventory is near-complete. Never 255.
    """
    out = bytearray(grid.cols * grid.rows)
    for k in range(len(out)):
        out[k] = max(0, min(100, int(round(sparse_score(acc.get(k, 0.0), half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G18B_CAL[layer]
    return cal.get("half_m", cal.get("half")), cal["sigma"]


def encode_wire(grid, values, layer="fishbowl"):
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


def write_points(outdir, layer, points):
    """Thinned overlay/fallback points (loadSnapshotPoints reads these)."""
    pts = dedupe_cells(points)
    if len(pts) > OVERLAY_CAP:  # stride-thin huge ring samples, keep spread
        stride = len(pts) / OVERLAY_CAP
        pts = [pts[int(i * stride)] for i in range(OVERLAY_CAP)]
    doc = [{"lon": round(lon, 6), "lat": round(lat, 6)}
           for lon, lat in pts]
    with open(os.path.join(outdir, "derived-%s.json" % layer), "w",
              encoding="utf-8") as f:
        json.dump(doc, f)
    print("wrote derived-%s.json (%d pts)" % (layer, len(doc)), flush=True)
    return doc


def build_layer(grid, layer, graph_path=None, buildings_path=None,
                forest_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer == "fishbowl":
        if not graph_path or not buildings_path:
            raise SystemExit("fishbowl needs --graph foot graph + --buildings")
        raw_jun, jstats = read_graph_junctions(graph_path)
        bcells, nbuild = read_building_cells(buildings_path)
        print("fishbowl: junctions=%d buildings=%d" % (jstats["junctions"], nbuild),
              flush=True)
        pts = settled_junctions(raw_jun, bcells)
        print("fishbowl: settled %d -> %d (trail forks drop out)" %
              (len(raw_jun), len(pts)), flush=True)
        dist = dijkstra_km(grid, cells_of_points(grid, pts))
        vals = score_distance(dist, G18B_CAL[layer]["half_m"])
    elif layer == "mossrisk":
        if not forest_path:
            raise SystemExit("mossrisk needs --forest forest extract")
        raw, polys, stats = read_forest_points(forest_path)
        print("mossrisk=%s raw_pts=%d polys=%d" % (stats, len(raw), len(polys)),
              flush=True)
        pts = dedupe_cells(raw)
        print("mossrisk: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        cells = cells_of_points(grid, pts) | fill_poly_cells(grid, polys)
        dist = dijkstra_km(grid, cells)
        vals = score_distance(dist, G18B_CAL[layer]["half_m"])
    else:
        if not buildings_path:
            raise SystemExit("daylight needs --buildings")
        raw = read_building_points(buildings_path)
        print("daylight: buildings=%d" % len(raw), flush=True)
        acc = count_kernel_field(grid, raw, G18B_CAL[layer]["sigma"])
        vals = score_sparse_cells(grid, acc, G18B_CAL[layer]["half"])
        pts = raw
    print("%s field ready (%.1fs)" % (layer, time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = calm/open):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-11s outside grid" % name, flush=True)
            continue
        print("  %-11s %s" % (name, {l: masters[l][k] for l in masters}),
              flush=True)


def window_counts(points, bbox=(24.5, 59.35, 24.9, 59.5)):
    """How many source points fall in the Tallinn window (source strings)."""
    minlon, minlat, maxlon, maxlat = bbox
    return sum(1 for lon, lat in points
               if minlon <= lon <= maxlon and minlat <= lat <= maxlat)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True,
                    choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--graph", default=None,
                    help="harju foot-graph JSON (fishbowl junctions)")
    ap.add_argument("--buildings", default=None,
                    help="derived-buildings.json (fishbowl settle filter + daylight)")
    ap.add_argument("--forest", default=None,
                    help="forest geojson extract (mossrisk)")
    ap.add_argument("--out", default=None,
                    help="single-layer master path (implies --outdir)")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--format", choices=["combined", "split"],
                    default="combined")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-<layer>.json overlay points")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args(argv)
    outdir = args.outdir or (os.path.dirname(args.out) if args.out else None)
    if not outdir:
        raise SystemExit("need --outdir (or --out)")
    os.makedirs(outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step),
          flush=True)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    masters = {}
    for layer in layers:
        vals, pts = build_layer(grid, layer, args.graph, args.buildings,
                                args.forest)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d window_pts=%d zeros(known-exposed)=%d" %
              (layer, len(vals), window_counts(pts),
               sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
