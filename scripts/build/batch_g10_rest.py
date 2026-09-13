"""Group 10 utilities-rest county master (issue #171): p215 skyview.

Stdlib only. Offline, snapshot-only (NO network): tall-building and
forest vectors come from the LOCAL Harjumaa PBF via the documented
osmium pre-step, never from a live service. Pure logic + snapshot
readers live at module top so unit tests stay hermetic; the
full-county build runs only via the documented rebuild command.

SCOPE (one layer, honest): this builder serves ONLY p215 (satellite
internet line-of-sight) as a mapped-obstruction open-sky hinnang.
The sibling param is documented no-map (see
apps/web/lib/layers_group10rest.ts): p491 indoor dead zones (a
per-room RF measurement with no area signal) ships as a scorer dim
only (services/scoring/dims_group10rest.py), OTA PR #131 precedent.

HONESTY (load-bearing): the TTJA Lairiba katvuskaart, OpenCellID /
CellMapper measurements and any dish-line-of-sight survey are NOT in
the 2026-09-12 snapshot (the snapshot carries zero satellite-dish
and zero indoor-signal keys — verified with osmium tags-count), so
the master is NOT measured coverage. skyview scores nearness to
MAPPED sky obstructions — tall buildings (building:levels >= 5) and
mapped forest (natural=wood / landuse=forest) — as an open-sky
hinnang: green = open (dish line-of-sight likely clear), red =
obstructed (check with the Starlink app obstruction tool). Titles,
legends and sources say "hinnang" (pinned by
layers_group10rest.test.ts). The field is radial while real dish
obstruction is directional (south-sky cone): red means "check",
never "no satellite here" (documented limitation, same class as the
commbleed untagged-member note). Unmapped forest clearings read
falsely low — a rural house in an unmapped clearing still needs the
on-site check (documented, not hidden).

Model (locked 2026-09-12):
* skyview (p215): exact full-grid 8-connectivity Dijkstra distance
  to the nearest obstruction cell (same machinery as
  batch_g05c_plans.py, local Grid copy for self-containment),
  score = 100*d/(d+150). halfM=150 m: dish obstruction is local —
  a 15-30 m obstacle blocks the sky cone within tens of metres, so
  open courtyards read calm while tower-adjacent and forest parcels
  read honestly low. Forest polygons are FILLED (a parcel inside
  mapped forest reads 0: inside IS the obstruction); tall-building
  rings feed boundary-sampled (interiors read near-zero through the
  ring Dijkstra at 75 m cells, windsolar precedent).

Sources (predicates verified on the snapshot extract):
* tall: building:levels >= 5 (verified 2026-09-12: 5604 kept
  county-wide, 5330 in the Tallinn window — Lasnamäe/Õismäe/Mustamäe
  panel districts). 1-4 storey houses are OUT by design (a family
  house does not block the sky cone); level-less buildings are OUT
  (guessing height would fake precision).
* forest: natural=wood or landuse=forest (verified 2026-09-12:
  15928 kept features county-wide incl. multipolygon member ways,
  ~8.7k true polygons, 4266 in the Tallinn window: Nõmme-Mustamäe,
  Pirita, Viimsi woods). Tree rows and lone trees are OUT by
  design (a tree row is not a canopy).

Computation: graph-free Euclidean field on the 75 m county grid
(57.29/110.57 scales) — exact-grid Dijkstra nearest-source
distance. NO metro master (documented): a smooth distance-decay
field at 9.375 m cells would be fake precision — the window route
serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/building:levels nwr/natural=wood nwr/landuse=forest \
      -o /tmp/hf-g10r-sky.osm.pbf --overwrite
  osmium export /tmp/hf-g10r-sky.osm.pbf -o /tmp/hf-g10r-sky.geojson
  python3 scripts/build/batch_g10_rest.py --layer all \
      --sky /tmp/hf-g10r-sky.geojson \
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: skyview-walk-raster.json (Dijkstra quiet master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-skyview.json
(fallback points for the Euclidean route + overlay). Restart the web
server afterwards — the server caches masters per process.
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
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group10rest.ts G10R_CAL mirrors these numbers
# exactly — test_batch_g10_rest.py parses that file and fails on drift.
G10R_CAL = {
    "skyview": {"half_m": 150.0, "sigma": 0.3},
}

LAYER_IDS = ("skyview",)

#: Storeys at/above which a mapped building counts as a sky obstruction
#: (a family house does not block the dish cone; ~5 storeys ~= 15 m).
TALL_LEVELS = 5

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


def is_tall(props):
    """True when a level-tagged feature is a sky obstruction (>= 5 storeys).

    1-4 storey houses are OUT by design (a family house does not block
    the dish cone); level-less buildings are OUT (guessing height
    would fake precision).
    """
    props = props or {}
    if "building:levels" not in props:
        return False
    try:
        return int(_first(props.get("building:levels"))) >= TALL_LEVELS
    except ValueError:
        return False


def is_forest(props):
    """True when a feature is mapped forest canopy (wood/forest).

    Tree rows and lone trees are OUT by design (a tree row is not a
    canopy); relation member ways carry no natural/landuse, so they
    drop out here — the parent multipolygon still fills.
    """
    props = props or {}
    return _first(props.get("natural")) == "wood" or \
        _first(props.get("landuse")) == "forest"


def keep_sky(props):
    """True when a sky-extract feature is a dish-cone obstruction."""
    return is_tall(props) or is_forest(props)


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


def read_sky_points(sky_path):
    """Obstruction source cells from a sky geojson extract.

    Tall-building points/rings feed boundary-sampled (interiors read
    near-zero through the ring Dijkstra at 75 m cells, windsolar
    precedent — buildings are small); forest polygons are
    boundary-sampled AND filled (a parcel inside mapped forest reads
    0: inside IS the obstruction). Returns ([(lon, lat)],
    fill_polys, stats).
    """
    pts = []
    polys = []  # forest outer rings for the grid fill
    stats = {"tall": 0, "forests": 0, "dropped": 0}
    for feat in _iter_features(sky_path):
        props = feat.get("properties") or {}
        tall = is_tall(props)
        forest = is_forest(props)
        if not tall and not forest:
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
            stats["tall" if tall else "forests"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))
                if forest:
                    polys.append(co)
            else:
                # Open member-way fragment: boundary sample only.
                pts.extend(_stride_ring(co))
            stats["tall" if tall else "forests"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
                if forest:
                    polys.append([(c[0], c[1]) for c in ring])
            stats["tall" if tall else "forests"] += 1
        else:
            stats["dropped"] += 1
    return pts, polys, stats


def fill_sky_cells(grid, polys):
    """Grid cells whose centre falls inside a mapped forest polygon."""
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
# Field: exact grid Dijkstra (quiet) + wire output + orchestration.
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
# Layer scores (high = calm; 0 = known-obstructed, never 255 — the whole
# county field is stamped: open land is genuinely open sky).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-obstruction calmness 100*d/(d+half) for one distance field."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G10R_CAL[layer]
    return cal.get("half_m", cal.get("half")), cal["sigma"]


def encode_wire(grid, values, layer="skyview"):
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


def build_layer(grid, layer, sky_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer != "skyview":
        raise SystemExit("unknown layer: %s" % layer)
    if not sky_path:
        raise SystemExit("skyview needs --sky obstruction extract")
    raw, polys, stats = read_sky_points(sky_path)
    print("skyview=%s raw_pts=%d fill_polys=%d" %
          (stats, len(raw), len(polys)), flush=True)
    pts = dedupe_cells(raw)
    print("skyview: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
    cells = cells_of_points(grid, pts) | fill_sky_cells(grid, polys)
    print("skyview: source cells=%d" % len(cells), flush=True)
    dist = dijkstra_km(grid, cells)
    vals = score_distance(dist, G10R_CAL[layer]["half_m"])
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
    ap.add_argument("--sky", default=None,
                    help="obstruction geojson extract (skyview)")
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
        vals, pts = build_layer(grid, layer, args.sky)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d zeros(known-obstructed)=%d" %
              (layer, len(vals), sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
