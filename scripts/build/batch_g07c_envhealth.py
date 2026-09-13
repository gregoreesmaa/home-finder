"""Group 7C vector-habitat county master (issue #142): p257.

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; the full-county build runs only
via the documented rebuild command.

HONESTY (load-bearing): no pest-surveillance registry (seire: trap
counts, incidence, risk classes) exists in the 2026-09-12 snapshot, so
this is a disease-vector HABITAT proximity proxy — nearest mapped
tick/mosquito
habitat (tick: natural=wood/scrub/heath + landuse=forest/meadow;
mosquito: natural=wetland). Titles, legends and sources say
"proksi (hinnang)", never surveillance claims. Green = far/calm,
red = at/inside habitat. In-bbox absence of mapped habitat IS the calm
evidence, so the master emits no in-bbox unknowns (0 = known-exposed on
the habitat, never 255); out-of-coverage stays 255 server-side
(cover mask).

Model (locked 2026-09-12, county probes Balti/Viru/Kadriorg/Õismäe/
Nõmme-mets/Viimsi/rural = 75/43/20/26/33/60/0; open farmland Paldiski
87; county median 90 with 27% exposed-zero — a calm-by-default field
that still discriminates the city 20-75):
* vectorhabitat (p257): exact full-grid 8-connectivity Dijkstra distance
  to the nearest habitat cell -> quiet = 100*d/(d+300 m). Polygon
  interiors count (scanline fill of outer rings): standing IN a mapped
  wood scores 0, not edge distance. Open linear ways (tree rows) and
  points score edge-only. Holes are NOT cut (conservative: a clearing
  inside a mapped wood still reads exposed — documented).
* Sources kept (24 816 extraction features): 17 269 habitat polys
  (17 304 rings, 36 847 stride-25 edge samples); 6400 micro-fragments
  < 2500 m2 dropped (incl. the 30 m scrub 180 m east of Balti jaam);
  1147 non-habitat tags dropped.

NO metro master (documented): a distance-decay proxy is smooth at
75 m; 9.375 m cells would be fake precision. The window route serves
county everywhere (metro slot stays empty).

Extraction (local PBF only, result NOT committed — snapshot scratch):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/natural=wood nwr/landuse=forest nwr/natural=scrub \\
      nwr/natural=heath nwr/landuse=meadow nwr/natural=wetland \\
      -o /tmp/hf-g07c-habitat.pbf --overwrite
  osmium export -u type_id /tmp/hf-g07c-habitat.pbf \\
      -o /tmp/hf-g07c-habitat.geojson
Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  python3 scripts/build/batch_g07c_envhealth.py --layer vectorhabitat \\
      --snap ~/hf-data/2026-09-12 --outdir ~/hf-data/2026-09-12/osm \\
      --habitat /tmp/hf-g07c-habitat.geojson --write-points --probe
Outputs: vectorhabitat-walk-raster.json (combined wire, WalkRasterDoc
shape so cleanRaster accepts it) + derived-vectorhabitat.json (thinned
edge-sample points for the overlay/fallback path, <= 20000).
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
# Constants (mirrors walk_raster / batch_g09_noise scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
EDGE_STEP_KM = 0.04  # open-way densification (<= 40 m gaps)
POINT_CAP = 20000  # derived-vectorhabitat.json thinning cap

LAYER_IDS = ("vectorhabitat",)

#: (natural values, landuse values) kept as vector habitat (p257).
HABITAT_NATURAL = {"wood", "scrub", "heath", "wetland"}
HABITAT_LANDUSE = {"forest", "meadow"}

#: Minimum polygon area kept (m2). Tick/mosquito populations need
#: sustained habitat: a 30 m traffic-island bush (e.g. the scrub patch
#: 180 m east of Balti jaam) is not missed data, it is not habitat.
#: 2500 m2 ~= half a football field. Open ways/points have no area and
#: are kept as edge (rare: ~0 in Harju — documented in stats).
MIN_AREA_M2 = 2500.0

#: Ring-vertex sampling stride for the derived edge-sample points.
RING_SAMPLE_STRIDE = 25

# Calibration locked 2026-09-12.
# NOTE: apps/web/lib/layers_group07c.ts G07C_CAL mirrors these numbers
# exactly (a pytest parses that file and fails on drift).
G07C_CAL = {
    "vectorhabitat": {"half_m": 300, "sigma": 0.3},
}

PROBE_POINTS = {
    "Balti": (24.7369, 59.4405),
    "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386),
    "Oismae": (24.655, 59.412),
    "Nommemets": (24.6611, 59.3862),
    "Viimsi": (24.83, 59.51),
    "rural": (24.5, 59.2),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


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

def _is_habitat(props):
    return (props.get("natural") in HABITAT_NATURAL
            or props.get("landuse") in HABITAT_LANDUSE)


def _densify_segment(p, q, step_km=EDGE_STEP_KM):
    pts = [p]
    d = hav_km(p[0], p[1], q[0], q[1])
    if d > step_km:
        n = int(d / step_km)
        for k in range(1, n):
            t = k / n
            pts.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    pts.append(q)
    return pts


def _densify_ring(ring, step_km=EDGE_STEP_KM):
    pts = []
    for i in range(1, len(ring)):
        pts.extend(_densify_segment(ring[i - 1], ring[i], step_km)[:-1])
    if ring:
        pts.append(ring[-1])
    return pts


def ring_area_m2(ring):
    """Equirectangular shoelace area (m2) of a lon/lat ring."""
    s = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2 * (LON_KM * 1000) * (LAT_KM * 1000)


def read_habitat_geoms(habitat_path):
    """Habitat features -> (outer rings, edge points with tags, stats).

    Polygons/MultiPolygons yield outer rings (holes ignored: conservative,
    documented); closed LineStrings (first == last) count as rings; open
    LineStrings yield densified edge vertices; Points yield one vertex.
    Rings below MIN_AREA_M2 are dropped (micro-fragments are not
    sustained vector habitat — documented judgment call). Ring vertices
    are stride-sampled into the edge list for the overlay/fallback path.
    Returns ([[(lon, lat)]], [((lon, lat), tags)], {"features": n, ...}).
    """
    rings, verts = [], []
    feats = kept = dropped_tags = dropped_small = 0

    def keep_ring(ring, tags):
        if len(ring) < 4:
            return False
        if ring_area_m2(ring) < MIN_AREA_M2:
            return False
        rings.append(ring)
        for v in ring[::RING_SAMPLE_STRIDE]:
            verts.append((v, tags))
        return True
    with open(habitat_path, encoding="utf-8") as f:
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
            props = feat.get("properties") or {}
            if not _is_habitat(props):
                dropped_tags += 1
                continue
            tags = {k: props[k] for k in ("natural", "landuse") if props.get(k)}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            gtype = geom.get("type")
            if gtype == "Point" and coords:
                kept += 1
                verts.append(((coords[0], coords[1]), tags))
            elif gtype == "LineString" and coords:
                ring = [(c[0], c[1]) for c in coords]
                if len(ring) >= 4 and ring[0] == ring[-1]:
                    if keep_ring(ring, tags):
                        kept += 1
                    else:
                        dropped_small += 1
                else:
                    kept += 1
                    for v in _densify_ring(ring):
                        verts.append((v, tags))
            elif gtype == "Polygon" and coords:
                if coords and coords[0]:
                    ring = [(c[0], c[1]) for c in coords[0]]
                    if keep_ring(ring, tags):
                        kept += 1
                    else:
                        dropped_small += 1
            elif gtype == "MultiPolygon" and coords:
                n0 = len(rings)
                for poly in coords:
                    if poly and poly[0]:
                        keep_ring([(c[0], c[1]) for c in poly[0]], tags)
                if len(rings) > n0:
                    kept += 1
                else:
                    dropped_small += 1
    stats = {"features": feats, "kept": kept, "dropped_tags": dropped_tags,
             "dropped_small": dropped_small,
             "rings": len(rings), "verts": len(verts)}
    return rings, verts, stats


def ring_scan_cells(grid, ring):
    """Cell ids whose centre falls strictly inside the ring (even-odd).

    Scanline over the ring's row span: row/ring crossings sorted, cells
    filled between pairs. Holes are not cut (conservative, documented).
    """
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    minlon, minlat, _, _ = grid.bbox
    ix0 = max(0, int((min(lons) - minlon) * LON_KM * 1000 / grid.step))
    ix1 = min(grid.cols - 1, int((max(lons) - minlon) * LON_KM * 1000 / grid.step))
    iy0 = max(0, int((min(lats) - minlat) * LAT_KM * 1000 / grid.step))
    iy1 = min(grid.rows - 1, int((max(lats) - minlat) * LAT_KM * 1000 / grid.step))
    cells = set()
    n = len(ring)
    for iy in range(iy0, iy1 + 1):
        lat = minlat + (iy + 0.5) * grid.step / 1000 / LAT_KM
        xs = []
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            if (y1 > lat) != (y2 > lat):
                xs.append(x1 + (lat - y1) / (y2 - y1) * (x2 - x1))
        xs.sort()
        for j in range(0, len(xs) - 1, 2):
            xa, xb = xs[j], xs[j + 1]
            # Cell centre strictly inside: first centre with clon > xa.
            ka = max(ix0, int(math.floor((xa - minlon) * LON_KM * 1000
                                         / grid.step - 0.5)) + 1)
            kb = min(ix1, int(math.ceil((xb - minlon) * LON_KM * 1000
                                        / grid.step - 0.5)) - 1)
            for ix in range(ka, kb + 1):
                cells.add(iy * grid.cols + ix)
    return cells


def habitat_cells(grid, rings, verts):
    """Source cells: polygon interiors (scanline) + edge vertices."""
    cells = set()
    for ring in rings:
        if len(ring) >= 4:
            cells.update(ring_scan_cells(grid, ring))
    for (lon, lat), _tags in verts:
        k = grid.cell_of(lon, lat)
        if k is not None:
            cells.add(k)
    return cells


# ---------------------------------------------------------------------------
# Fields: exact grid Dijkstra + quiet scoring.
# ---------------------------------------------------------------------------

def dijkstra_km(grid, source_cells):
    """Exact 8-connectivity distance (km) to the nearest source cell.

    No cutoff (sparse sources: no cliffs). Orthogonal step = cell km,
    diagonal = *sqrt(2). Returns array('d') (+inf where unreachable).
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


def score_distance(d_km, half_m):
    """Nearest-source quietness 100*d/(d+half) for one distance field."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G07C_CAL[layer]
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


def thin_points(verts, cap=POINT_CAP):
    """Deterministic stride thin of edge vertices to <= cap points."""
    if len(verts) <= cap or cap <= 0:
        pts = verts if cap > 0 else []
    else:
        stride = len(verts) / cap
        pts = [verts[int(i * stride)] for i in range(cap)]
    return pts


def write_points_file(outdir, layer, verts):
    pts = thin_points(verts)
    doc = [{"lat": lat, "lon": lon, "tags": tags} for (lon, lat), tags in pts]
    with open(os.path.join(outdir, "derived-%s.json" % layer), "w",
              encoding="utf-8") as f:
        json.dump(doc, f)
    print("wrote derived-%s.json (%d of %d edge pts)" % (layer, len(doc), len(verts)),
          flush=True)


def build_all(snap, grid, habitat_path, cache_path):
    """Habitat cells -> Dijkstra -> per-layer byte masters."""
    t0 = time.time()
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            import pickle
            fields = pickle.load(f)
        print("fields: loaded %s (skipped stamping)" % cache_path, flush=True)
        rings, verts, stats = [], [], {"features": 0, "kept": 0,
                                       "dropped_tags": 0, "dropped_small": 0,
                                       "rings": 0, "verts": 0}
    else:
        print("habitat: reading %s..." % habitat_path, flush=True)
        rings, verts, stats = read_habitat_geoms(habitat_path)
        print("habitat: %s" % (stats,), flush=True)
        print("habitat cells (scanline fill)...", flush=True)
        cells = habitat_cells(grid, rings, verts)
        print("habitat cells=%d; dijkstra..." % len(cells), flush=True)
        d_hab = dijkstra_km(grid, cells)
        fields = {"d_hab": d_hab}
        if cache_path:
            with open(cache_path, "wb") as f:
                import pickle
                pickle.dump(fields, f, protocol=4)
            print("fields: saved %s" % cache_path, flush=True)
    print("fields ready (%.1fs)" % (time.time() - t0), flush=True)

    out = {}
    out["vectorhabitat"] = score_distance(
        fields["d_hab"], G07C_CAL["vectorhabitat"]["half_m"])
    return out, (rings, verts, stats)


def probe_scores(masters, grid):
    print("probe (quietness 0..100, high = calm):", flush=True)
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
    ap.add_argument("--habitat", required=True,
                    help="habitat geojson (see extraction command above)")
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--stamp-cache", default=None)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-<layer>.json edge samples")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    cache = args.stamp_cache or os.path.join(args.outdir, "g07c-fields.pkl")
    masters, (_rings, verts, _stats) = build_all(
        args.snap, grid, args.habitat, cache if args.layer == "all" else None)
    for layer in layers:
        write_outputs(args.outdir, layer, grid, masters[layer], args.format)
        vals = masters[layer]
        known = sum(1 for v in vals if v != 255)
        print("%s: cells=%d known=%d zeros(known-exposed)=%d" %
              (layer, len(vals), known, sum(1 for v in vals if v == 0)), flush=True)
        if args.write_points:
            write_points_file(args.outdir, layer, verts)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()