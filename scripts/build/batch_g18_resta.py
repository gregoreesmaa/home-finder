"""Group 18 rest-A county masters (issue #172): p34 dayopen + p305
glassglare.

Stdlib only. Offline, snapshot-only (NO network): tall-building
vectors and glass-facade vectors come from the LOCAL Harjumaa PBF via
the documented osmium pre-steps, never from a live service. Pure
logic + snapshot readers live at module top so unit tests stay
hermetic; full-county builds run only via the documented rebuild
commands.

SCOPE (two layers, honest): this builder serves ONLY p34 (natural
light) as a mapped tall-mass openness hinnang and p305 (exterior
reflective glare) as a mapped glass-facade distance hinnang. The
sibling params are documented no-map (see
apps/web/lib/layers_group18resta.ts): p100 window placement and
cross-ventilation (a per-floorplan fact — exactly 1 window tag
county-wide), p231 driveway incline angle (no DEM/DTM/contours in
the snapshot; incline tags are pedestrian steps + up/down
directionals, ~0 driveways carry a grade) and p287 zoom-ready
lighting (a per-room interior fact, unmappable by construction)
ship as scorer dims only
(services/scoring/dims_group18resta.py), OTA PR #131 precedent.

HONESTY (load-bearing): Maa-amet LoD2 3D meshes, PVLib ray-tracing,
sun-hour measurements, lux meters and floorplans are NOT in the
2026-09-12 snapshot, so no master is measured daylight or glare.
dayopen scores nearness to MAPPED tall buildings (levels >= 4,
sol_tall precedent from dims_group18_solar.py #123) as sky-openness
pressure, never sun hours; glassglare scores distance to MAPPED
glass/mirror facades as glare-exposure pressure, never lux.
Titles, legends and sources say "hinnang" (pinned by
layers_group18resta.test.ts).

Models (locked 2026-09-13):
* dayopen (p34): exact full-grid 8-connectivity Dijkstra distance
  to the nearest tall-mass cell (same machinery as
  batch_g05c_plans.py, local Grid copy for self-containment),
  score = 100*d/(d+150). halfM=150 m: a 15 m block 150 m away
  subtends ~6 degrees of sky (minor loss) while adjacency is
  severe — Ülemiste-center towers read honestly low, detached
  Nõmme reads calm. Tower polygons are FILLED (a parcel inside the
  mass reads 0: inside IS the obstruction); untagged buildings
  read as low-rise BY DESIGN (levels coverage is sparse, so
  absence is weak evidence of lowness). Trees are OUT by design
  (deciduous bias precedent, #123): leafy low-rise streets have
  good daylight — only tall masses count.
* glassglare (p305): exact full-grid Dijkstra distance to the
  nearest glass-facade cell, score = 100*d/(d+200). halfM=200 m:
  reflected glare is a street/plaza-scale line-of-sight fact, and
  low winter sun extends its reach. Facade polygons feed
  stride-sampled outer rings with NO fill (glare is an
  outside-view fact — the tower interior does not suffer its own
  reflection); facade points/lines feed directly/densified.

Sources (predicates verified on the snapshot extract):
* tall: building:levels integer >= 4 (verified 2026-09-13:
  levels-tagged buildings parse; >= 4 reads tall). Untagged
  buildings drop out in keep_tall — no twin purge needed beyond
  the cell dedupe.
* glass: building:material glass or mirror (verified 2026-09-13:
  382 kept county-wide: 337 glass + 12 mirror + relation members
  that survive keep_glass). Plaster/wood/brick/concrete drop out
  BY DESIGN (not reflective).

Computation: both layers are graph-free Euclidean fields on the
75 m county grid (57.29/110.57 scales) — exact-grid Dijkstra
nearest-source distance. NO metro masters (documented): smooth
distance-decay fields at 9.375 m cells would be fake precision —
the window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/building:levels \
      -o /tmp/hf-g18a-tall.pbf --overwrite
  osmium export /tmp/hf-g18a-tall.pbf -o /tmp/hf-g18a-tall.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/building:material=glass nwr/building:material=mirror \
      -o /tmp/hf-g18a-glass.pbf --overwrite
  osmium export /tmp/hf-g18a-glass.pbf -o /tmp/hf-g18a-glass.geojson
  python3 scripts/build/batch_g18_resta.py --layer all \
      --tall /tmp/hf-g18a-tall.geojson --glass /tmp/hf-g18a-glass.geojson \
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: dayopen/glassglare-walk-raster.json (Dijkstra quiet
masters, WalkRasterDoc shape so cleanRaster accepts them) +
derived-<layer>.json (fallback points for the Euclidean route +
overlay). Restart the web server afterwards — the server caches
masters per process.
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

# Calibration locked 2026-09-13 (see module docstring).
# NOTE: apps/web/lib/layers_group18resta.ts G18A_CAL mirrors these
# numbers exactly — test_batch_g18_resta.py parses that file and
# fails on drift.
G18A_CAL = {
    "dayopen": {"half_m": 150.0, "sigma": 0.3},
    "glassglare": {"half_m": 200.0, "sigma": 0.3},
}

LAYER_IDS = ("dayopen", "glassglare")

#: Levels at/above which a building is a daylight-obstructing mass
#: (sol_tall precedent, dims_group18_solar.py #123).
TALL_LEVELS = 4

#: Facade materials that reflect (glare sources).
KEEP_GLASS_MAT = ("glass", "mirror")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
    "Ulemiste": (24.7956, 59.4229), "Tornimae": (24.7619, 59.4313),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> calmness 0..100: 0 on the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


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
# Source predicates + readers (offline geojson extracts only).
# ---------------------------------------------------------------------------

def _first(value):
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def keep_tall(props):
    """True when a levels-extract feature is a daylight-obstructing mass.

    building:levels integer >= 4 (sol_tall precedent, #123: ~12 m+,
    casts meaningful shade at Tallinn latitudes). Non-numeric and
    untagged levels drop out here — untagged buildings read as
    low-rise BY DESIGN (absence is weak evidence of lowness).
    """
    props = props or {}
    try:
        return int(_first(props.get("building:levels"))) >= TALL_LEVELS
    except (ValueError, TypeError):
        return False


def keep_glass(props):
    """True when a material-extract feature is a reflective facade.

    building:material glass or mirror. Plaster/wood/brick/concrete
    drop out BY DESIGN (not reflective). Untagged relation members
    drop out here.
    """
    return _first((props or {}).get("building:material")) in KEEP_GLASS_MAT


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


def read_tall_points(tall_path):
    """Tall-mass source cells from a building:levels geojson extract.

    Points feed directly; open lines are densified; polygons are
    boundary-sampled AND filled (a parcel inside the mass reads 0:
    inside IS the obstruction). Returns ([(lon, lat)],
    fill_cells_hint, stats) — the fill runs on the caller grid via
    fill_tall_cells.
    """
    pts = []
    polys = []  # outer rings for the grid fill
    stats = {"masses": 0, "dropped": 0}
    for feat in _iter_features(tall_path):
        if not keep_tall(feat.get("properties") or {}):
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
            stats["masses"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))
            else:
                pts.extend(_densify_line(co))
            stats["masses"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
                polys.append([(c[0], c[1]) for c in ring])
            stats["masses"] += 1
        else:
            stats["dropped"] += 1
    return pts, polys, stats


def fill_tall_cells(grid, polys):
    """Grid cells whose centre falls inside a tall-mass polygon."""
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


def read_glass_points(glass_path):
    """Glass-facade source points from a material geojson extract.

    Points feed directly; lines are densified; polygons feed
    stride-sampled outer rings with NO fill — glare is an
    outside-view fact (the tower interior does not suffer its own
    reflection), so only the facade ring sources the field.
    Returns ([(lon, lat)], stats).
    """
    pts = []
    stats = {"facades": 0, "dropped": 0}
    for feat in _iter_features(glass_path):
        if not keep_glass(feat.get("properties") or {}):
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
            stats["facades"] += 1
        elif gtype == "LineString":
            pts.extend(_densify_line([(c[0], c[1]) for c in coords]))
            stats["facades"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
            stats["facades"] += 1
        else:
            stats["dropped"] += 1
    return pts, stats


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
# Fields: exact grid Dijkstra (quiet) + layer scores.
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


# ---------------------------------------------------------------------------
# Layer scores (high = calm; 0 = known-exposed, never 255 — both layers
# are total fields: far-from-source reads calm, honestly).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-source calmness 100*d/(d+half) for one distance field."""
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
    cal = G18A_CAL[layer]
    return cal["half_m"], cal["sigma"]


def encode_wire(grid, values, layer="dayopen"):
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


def build_layer(grid, layer, tall_path=None, glass_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer == "dayopen":
        if not tall_path:
            raise SystemExit("dayopen needs --tall levels extract")
        raw, polys, stats = read_tall_points(tall_path)
        print("dayopen=%s raw_pts=%d polys=%d" % (stats, len(raw), len(polys)),
              flush=True)
        pts = dedupe_cells(raw)
        print("dayopen: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        cells = cells_of_points(grid, pts) | fill_tall_cells(grid, polys)
        dist = dijkstra_km(grid, cells)
        vals = score_distance(dist, G18A_CAL[layer]["half_m"])
    else:
        if not glass_path:
            raise SystemExit("glassglare needs --glass material extract")
        raw, stats = read_glass_points(glass_path)
        print("glassglare=%s raw_pts=%d" % (stats, len(raw)), flush=True)
        pts = dedupe_cells(raw)
        print("glassglare: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        dist = dijkstra_km(grid, cells_of_points(grid, pts))
        vals = score_distance(dist, G18A_CAL[layer]["half_m"])
    print("%s field ready (%.1fs)" % (layer, time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = calm):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-11s outside grid" % name, flush=True)
            continue
        print("  %-11s %s" % (name, {l: masters[l][k] for l in masters}),
              flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True,
                    choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--tall", default=None,
                    help="building:levels geojson extract (dayopen)")
    ap.add_argument("--glass", default=None,
                    help="material geojson extract (glassglare)")
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
        vals, pts = build_layer(grid, layer, args.tall, args.glass)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d zeros(known-exposed)=%d" %
              (layer, len(vals), sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
