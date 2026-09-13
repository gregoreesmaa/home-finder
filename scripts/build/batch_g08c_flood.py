"""Group 8 flood/climate-C county masters (issue #169): p334 surgeroad + p336 slidebuf.

Stdlib only. Offline, snapshot-only (NO network): cliff vectors,
shore vectors and road vectors come from the LOCAL Harjumaa PBF via
the documented osmium pre-steps, never from a live service. Pure
logic + snapshot readers live at module top so unit tests stay
hermetic; full-county builds run only via the documented rebuild
commands.

SCOPE (two layers, honest): this builder serves ONLY p334 (high-tide
/ storm-surge street impassability) as a surge-band-street nearness
hinnang and p336 (avalanche/mudslide buffer) as a mapped-slope
distance hinnang. The sibling params are documented no-map (see
apps/web/lib/layers_group08c.ts): p371 burn scar mudslide risk and
p372 FEMA buyout history are per-register facts with no honest area
signal in the snapshot — they ship as scorer dims only
(services/scoring/dims_group08c.py), OTA PR #131 precedent.

HONESTY (load-bearing): the Keskkonnaagentuur flood-hazard WFS,
EFAS/CMEMS reanalyses, Ilmateenistus gauge series, EFFIS burn
perimeters and any payout register are NOT in the 2026-09-12
snapshot, so neither master is measured hazard data. surgeroad
scores nearness to MAPPED carriageways inside the <=150 m surge band
of the MAPPED sea shoreline (Tallinn's tide is centimetres; surge is
the street-impassability hazard); slidebuf scores distance to MAPPED
cliffs/earth_banks (the param's ST_Distance shape, never a
geotechnical ruling). Titles, legends and sources say "hinnang"
(pinned by layers_group08c.test.ts).

Models (locked 2026-09-12):
* surgeroad (p334): exact full-grid 8-connectivity Dijkstra distance
  to the nearest SURGE-BAND street cell, score = 100*d/(d+150).
  Band cells = carriageway vertices (motorway..service + road +
  living_street; footways/tracks/paths/pedestrian OUT — the param
  asks about STREET impassability) within SURGE_BAND_M = 150 m of a
  mapped SEA coastline vertex (exact haversine via a 150 m spatial
  hash — no grid rounding on the gate). Lakes are OUT (surge is
  marine). halfM=150 m IS the band: on an exposed street the score
  is 0, one band-width inland 50. Named witnesses in the
  Tallinn-coast slice: Pirita tee (130 band vertices), Reidi tee
  (82), Uus-Sadama (57), Regati pst (31), Merivälja tee (23).
  flood_prone=yes is OUT (12 features, all forest tracks/fords —
  zero streets).
* slidebuf (p336): exact full-grid 8-connectivity Dijkstra distance
  to the nearest cliff/earth_bank cell (same machinery as
  batch_g03d_cadastre.py, local Grid copy for self-containment),
  score = 100*d/(d+100). halfM=100 m tracks klint-debris runout
  plus margin (Türisalu-scale fans are tens of metres). 261 cliff
  lines (Leetse/Kakumae/Lasnamae-Maarjamae/Toompea pangad) + 20
  earth_bank features; rivers/wetlands EXCLUDED (p50 drainage's
  signal, #151 — the Pirita corridor reads clean here by design).

Computation: both masters are graph-free Euclidean fields on the 75 m
county grid (57.29/110.57 scales). NO metro masters (documented):
smooth distance-decay fields at 9.375 m cells would be fake
precision — the window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/natural=cliff nwr/natural=earth_bank \\
      -o /tmp/hf-g08c-cliff.pbf --overwrite
  osmium export -u type_id /tmp/hf-g08c-cliff.pbf -o /tmp/hf-g08c-cliff.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/natural=coastline -o /tmp/hf-g08c-shore.pbf --overwrite
  osmium export -u type_id /tmp/hf-g08c-shore.pbf -o /tmp/hf-g08c-shore.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      w/highway=motorway w/highway=trunk w/highway=primary \\
      w/highway=secondary w/highway=tertiary w/highway=unclassified \\
      w/highway=residential w/highway=living_street w/highway=service \\
      w/highway=road -o /tmp/hf-g08c-roads.pbf --overwrite
  osmium export -u type_id /tmp/hf-g08c-roads.pbf -o /tmp/hf-g08c-roads.geojson
  python3 scripts/build/batch_g08c_flood.py --layer slidebuf \\
      --cliff /tmp/hf-g08c-cliff.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
  python3 scripts/build/batch_g08c_flood.py --layer surgeroad \\
      --shore /tmp/hf-g08c-shore.geojson --roads /tmp/hf-g08c-roads.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: slidebuf-walk-raster.json (WalkRasterDoc shape so
cleanRaster accepts it) + derived-slidebuf.json (overlay/fallback
sample) and surgeroad-walk-raster.json + derived-surgeroad.json.
Restart the web server afterwards — the server caches masters per
process.
"""

import argparse
import array
import base64
import heapq
import json
import math
import os
import time

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_g03d_cadastre scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # cliff-line vertex spacing for source rasterisation
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

#: Carriageways within this band (m) of the mapped sea shore count as
#: surge-exposed streets. Tallinn tide is centimetres; the band marks
#: where Baltic storm surge reaches mapped streets (witness: Pirita
#: tee vertices 91 m out). Also the surgeroad raster halfM.
SURGE_BAND_M = 150.0

#: highway= values that are carriageways (STREETS for p334). Footways,
#: tracks, paths, cycleways, steps and pedestrian zones are OUT by
#: design (trail flooding is a different buyer question); "road" stays
#: IN (an unknown road is still a road).
KEEP_HIGHWAY = ("motorway", "trunk", "primary", "secondary",
                "tertiary", "unclassified", "residential",
                "living_street", "service", "road")

#: natural= values that are mapped slopes for p336 (same slope-failure
#: family; rivers/wetlands stay p50 drainage's, #151).
KEEP_SLOPE = ("cliff", "earth_bank")

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group08c.ts G08C_CAL mirrors these numbers
# exactly — test_batch_g08c_flood.py parses that file and fails on drift.
G08C_CAL = {
    "surgeroad": {"half_m": 150.0, "sigma": 0.3},
    "slidebuf": {"half_m": 100.0, "sigma": 0.3},
}

LAYER_IDS = ("surgeroad", "slidebuf")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Pirita": (24.821, 59.468), "Kalamaja": (24.738, 59.448),
    "Kakumae": (24.604, 59.452), "Vanasadam": (24.759, 59.443),
    "Viru": (24.7611, 59.4278), "Nomme": (24.68, 59.39),
    "Lasnamae": (24.82, 59.44), "rural": (24.5, 59.2),
    "PiritaTee": (24.81723, 59.46048), "LasnaCliff": (24.80809, 59.44208),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> goodness 0..100: 0 at the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


# ---------------------------------------------------------------------------
# Predicates (p334/p336 hinnang source sets).
# ---------------------------------------------------------------------------

def is_surge_road(props):
    """True when OSM tags mark a carriageway (a STREET for p334).

    Tight by design: motorway..service + road + living_street.
    Footways, tracks, paths, cycleways, steps and pedestrian zones are
    OUT (trail flooding is a different question); flood_prone=yes is
    OUT (12 forest-track features, zero streets). Never throws.
    """
    if not isinstance(props, dict):
        return False
    return props.get("highway") in KEEP_HIGHWAY


def is_slide_source(props):
    """True when OSM tags mark a mapped slope for p336.

    natural=cliff + natural=earth_bank (same slope-failure family).
    Rivers, wetlands and water are OUT (p50 drainage's signal, #151).
    Never throws.
    """
    if not isinstance(props, dict):
        return False
    return props.get("natural") in KEEP_SLOPE


# ---------------------------------------------------------------------------
# County grid (mirrors batch_g03d_cadastre for self-containment — one
# batch file, no cross-batch import).
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


def _iter_geom_points(geom):
    """Yield (lon, lat) vertices of any GeoJSON geometry (densified)."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return
    if gtype == "Point":
        yield (coords[0], coords[1])
    elif gtype == "LineString":
        for pt in _densify_line([(c[0], c[1]) for c in coords]):
            yield pt
    elif gtype in ("Polygon", "MultiPolygon"):
        polys = [coords] if gtype == "Polygon" else coords
        for poly in polys:
            if poly:
                for c in poly[0]:
                    yield (c[0], c[1])


def read_line_sources(grid, path, keep):
    """Rasterise kept line/point features to source cells (d = 0).

    Densified vertices for lines, direct cells for points. Returns
    (set_of_cells, stats with the overlay sample).
    """
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    cells = set()
    overlay = []
    feats = kept = 0
    for feat in doc.get("features", []):
        feats += 1
        if not keep(feat.get("properties") or {}):
            continue
        geom = feat.get("geometry") or {}
        pts = list(_iter_geom_points(geom))
        if not pts:
            continue
        kept += 1
        for lon, lat in pts:
            k = grid.cell_of(lon, lat)
            if k is not None:
                cells.add(k)
        overlay.extend(pts[:: max(1, len(pts) // 25)])
    return cells, {"features": feats, "kept": kept, "points": len(overlay),
                   "overlay": overlay}


def _bucket_key(lon, lat, cell_lon, cell_lat):
    # Degrees are anisotropic (at 59N one lon-degree is ~57 km, one
    # lat-degree ~111 km), so the hash cells are sized per axis: a
    # cell edge == the gate band, hence any two points within the band
    # land at most one bucket apart and the 3x3 probe cannot miss.
    return (math.floor(lon / cell_lon), math.floor(lat / cell_lat))


def gate_roads_to_surge_band(grid, shore_path, roads_path, band_m=SURGE_BAND_M):
    """Road vertices within band_m of a mapped SEA shore vertex.

    Exact haversine gate via a band-sized spatial hash (no grid
    rounding on the gate itself): shore vertices bucketed at
    band_m/111570 deg, each road vertex checks its 3x3 buckets.
    Returns (exposed_cells, stats). Only SEA coastline gates (lakes
    do not surge); only carriageways gate (see is_surge_road).
    """
    with open(shore_path, encoding="utf-8") as f:
        shore_doc = json.load(f)
    cell_lon = (band_m / 1000.0) / LON_KM
    cell_lat = (band_m / 1000.0) / LAT_KM
    buckets = {}
    shore_n = 0
    for feat in shore_doc.get("features", []):
        if (feat.get("properties") or {}).get("natural") != "coastline":
            continue
        for lon, lat in _iter_geom_points(feat.get("geometry") or {}):
            shore_n += 1
            buckets.setdefault(_bucket_key(lon, lat, cell_lon, cell_lat),
                               []).append((lon, lat))
    band_km = band_m / 1000.0
    cells = set()
    overlay = []
    feats = kept_feats = kept_verts = road_verts = 0
    with open(roads_path, encoding="utf-8") as f:
        roads_doc = json.load(f)
    for feat in roads_doc.get("features", []):
        feats += 1
        if not is_surge_road(feat.get("properties") or {}):
            continue
        pts = list(_iter_geom_points(feat.get("geometry") or {}))
        if not pts:
            continue
        hit_feat = False
        for lon, lat in pts:
            road_verts += 1
            bx, by = _bucket_key(lon, lat, cell_lon, cell_lat)
            exposed = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for slon, slat in buckets.get((bx + dx, by + dy), ()):  # noqa: B007
                        if hav_km(lon, lat, slon, slat) <= band_km:
                            exposed = True
                            break
                    if exposed:
                        break
                if exposed:
                    break
            if exposed:
                kept_verts += 1
                hit_feat = True
                k = grid.cell_of(lon, lat)
                if k is not None:
                    cells.add(k)
                overlay.append((lon, lat))
        if hit_feat:
            kept_feats += 1
    return cells, {"features": feats, "kept": kept_feats,
                   "road_verts": road_verts, "kept_verts": kept_verts,
                   "shore_verts": shore_n, "points": len(overlay),
                   "overlay": overlay}


def dijkstra_km(grid, source_cells):
    """Exact 8-connectivity distance (km) to the nearest source cell.

    No cutoff (sparse sources: cliffs). Orthogonal step = cell km,
    diagonal = *sqrt(2). Returns array('d') with +inf where unreachable.
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


def score_distance(d_km, half_m):
    """Nearest-source goodness 100*d/(d+half), 0 at the source."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


# ---------------------------------------------------------------------------
# Wire output + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook.

    Both layers carry the quiet-kind halfM on the wire half field
    (GENV convention, like the G03 drainage master).
    """
    cal = G08C_CAL[layer]
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


def thin_overlay(overlay, cap=OVERLAY_CAP):
    """Deterministic stride thin of source points for derived-*.json.

    Dedupes to ~10 m so LineString export twins collapse to one dot;
    stride keeps spatial spread under the cap. Returns [{"lon","lat"}].
    """
    seen = set()
    uniq = []
    for lon, lat in overlay:
        key = (round(lon, 4), round(lat, 4))
        if key in seen:
            continue
        seen.add(key)
        uniq.append((lon, lat))
    if len(uniq) > cap:
        stride = len(uniq) / cap
        uniq = [uniq[int(i * stride)] for i in range(cap)]
    return [{"lon": lon, "lat": lat} for lon, lat in uniq]


def probe_vals(vals, grid, name):
    print("probe (%s goodness 0..100, high = far from source):" % name,
          flush=True)
    for pname, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-10s outside grid" % pname, flush=True)
            continue
        print("  %-10s %d" % (pname, vals[k]), flush=True)


def build_layer(layer, grid, cells, stats):
    """Source cells -> scored byte master. Returns (bytes, stats)."""
    t0 = time.time()
    print("%s: source_cells=%d" % (layer, len(cells)), flush=True)
    print("dijkstra: %s distance ..." % layer, flush=True)
    d = dijkstra_km(grid, cells)
    print("field ready (%.1fs)" % (time.time() - t0), flush=True)
    return score_distance(d, G08C_CAL[layer]["half_m"]), stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=list(LAYER_IDS))
    ap.add_argument("--cliff", default=None,
                    help="cliff geojson from the docstring osmium pre-step")
    ap.add_argument("--shore", default=None,
                    help="coastline geojson from the docstring osmium pre-step")
    ap.add_argument("--roads", default=None,
                    help="carriageway geojson from the docstring osmium pre-step")
    ap.add_argument("--outdir", default=None,
                    help="raster output dir (snapshot osm/ dir)")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-*.json overlay/fallback sample")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args()
    if not args.outdir:
        ap.error("--outdir is required")
    os.makedirs(args.outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step),
          flush=True)
    if args.layer == "slidebuf":
        if not args.cliff:
            ap.error("--cliff is required for slidebuf")
        print("cliff: reading %s ..." % args.cliff, flush=True)
        cells, stats = read_line_sources(grid, args.cliff, is_slide_source)
        print("cliff: features=%d kept=%d" %
              (stats["features"], stats["kept"]), flush=True)
    else:
        if not args.shore or not args.roads:
            ap.error("--shore and --roads are required for surgeroad")
        print("shore+roads: reading %s %s ..." % (args.shore, args.roads),
              flush=True)
        cells, stats = gate_roads_to_surge_band(grid, args.shore, args.roads)
        print("surge gate: road_features=%d kept=%d road_verts=%d "
              "kept_verts=%d shore_verts=%d" %
              (stats["features"], stats["kept"], stats["road_verts"],
               stats["kept_verts"], stats["shore_verts"]), flush=True)
    vals, stats = build_layer(args.layer, grid, cells, stats)
    out = os.path.join(args.outdir, "%s-walk-raster.json" % args.layer)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(encode_wire(grid, vals, args.layer), f)
    print("%s: cells=%d zeros(at-source)=%d min=%d max=%d" %
          (args.layer, len(vals), sum(1 for v in vals if v == 0),
           min(vals), max(vals)), flush=True)
    print("wrote %s" % out, flush=True)
    if args.write_points:
        pts = thin_overlay(stats["overlay"])
        derived = os.path.join(args.outdir, "derived-%s.json" % args.layer)
        with open(derived, "w", encoding="utf-8") as f:
            json.dump(pts, f)
        print("wrote derived-%s.json (%d thinned dots)" % (args.layer, len(pts)),
              flush=True)
    if args.probe:
        probe_vals(vals, grid, args.layer)


if __name__ == "__main__":
    main()
