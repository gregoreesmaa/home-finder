"""Group 3 cadastre-A drainage-proxy county master (issue #151): p50.

Stdlib only. Offline, snapshot-only (NO network): hydro vectors come
from the LOCAL Harjumaa PBF via the documented osmium pre-step, never
from a live service. Pure logic + snapshot readers live at module top
so unit tests stay hermetic; the full-county build runs only via the
documented rebuild command.

SCOPE (one layer, honest): this builder serves ONLY p50 (topography /
drainage) as a distance-to-open-water hinnang proxy. The sibling
params are documented no-map (see apps/web/lib/layers_group03.ts):
p29 lot size, p68 soil stability, p71 easements and p75 property-line
clarity are per-parcel Maa-amet registry facts with no honest area
signal in the snapshot — they ship as scorer dims only
(services/scoring/dims_group03.py), OTA PR #131 precedent.

HONESTY (load-bearing): the Maa-amet LiDAR DEM / EELIS hydrological
flow grids are NOT in the 2026-09-12 snapshot, so this is an
open-water PROXIMITY proxy — title, legend and source say
"drenaažiproksi (hinnang)", never metres of elevation, flow rate or
flood zone. Green = far from mapped open water (good-drainage
assumption), red = on/near water (high-water-table / flood-check
hint). In-bbox absence of mapped water IS the dry evidence, so the
master emits no in-bbox unknowns (0 = on open water, never 255);
out-of-coverage stays 255 server-side (cover mask).

Model (locked 2026-09-12 from snapshot probes at Balti / Viru /
Kadriorg / Oismae / Lasnamae / Viimsi / rural / airport / Kalamaja /
Kopli / Nomme / Pirita):
* drainage (p50): exact full-grid 8-connectivity Dijkstra distance to
  the nearest source cell, score = 100*d/(d+300). Probes (with sea):
  Kadriorg pond 41 m -> 12, Pirita river 104 m -> 26, Balti 159 m ->
  35, Viru 291 m -> 49, Lasnamae ditches 305 m -> 50, Nomme 507 m ->
  63, Oismae 532 m -> 64, Viimsi shore 429 m -> 59, rural 669 m -> 69.
  The city spreads mid-ramp instead of blobbing; the sea keeps
  Kalamaja/Kopli/Pirita honestly low (low fill near the bay).

Sources (predicate verified on the snapshot extract): natural=coastline
(sea shore — WITHOUT this the coast reads dry, the exact failure
calibration caught: Kalamaja read 916 m from the sea-less extract),
natural=water except man-made water=wastewater/basin/fountain,
natural=wetland, waterway=river/stream/canal/ditch/drain. Excluded by
design: ponds' ornamental cousins (fountain), treatment/basin infra,
untagged coastline-node leftovers, bank vegetation (scrub/wood/
grassland) and watermill/slipway points — none is open water.

Computation: polygon interiors become source cells (bbox + ray-cast
ring test, like batch_g09_noise.read_nature_cells) so lake centres
read 0, not green; lines are densified to ~40 m; grid mirrors
walk_raster (75 m county, 57.29/110.57 scales). NO metro master
(documented): a smooth distance-decay proxy at 9.375 m cells would be
fake precision — the window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/natural=coastline nwr/natural=water nwr/natural=wetland \\
      nwr/waterway=river nwr/waterway=stream nwr/waterway=canal \\
      nwr/waterway=ditch nwr/waterway=drain \\
      -o /tmp/hf-g03-hydro.pbf --overwrite
  osmium export -u type_id /tmp/hf-g03-hydro.pbf -o /tmp/hf-g03-hydro.geojson
  python3 scripts/build/batch_g03_cadastre.py --layer drainage \\
      --hydro /tmp/hf-g03-hydro.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
  # single small test bbox:
  python3 scripts/build/batch_g03_cadastre.py --layer drainage \\
      --hydro /tmp/hf-g03-hydro.geojson --outdir /tmp/g03 \\
      --bbox 24.6 59.35 24.9 59.5 --probe
Outputs: drainage-walk-raster.json (combined wire, WalkRasterDoc shape
so cleanRaster accepts it) + derived-drainage.json overlay sample
(thinned honest source points; the raster holds the full field).
Restart :3108 afterwards — the server caches masters per process.
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
# Constants (mirrors walk_raster / batch_g09_noise scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # line-vertex spacing for source rasterisation
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring probes).
# NOTE: apps/web/lib/layers_group03.ts G03_CAL mirrors these numbers
# exactly — test_batch_g03.py parses that file and fails on drift.
G03_CAL = {
    "drainage": {"half_m": 300.0, "sigma": 0.3},
}

LAYER_IDS = ("drainage",)

#: water= values that are fenced/ornamental infra, not open water.
SKIP_WATER = ("wastewater", "basin", "fountain")
#: Flowing-water line kinds (still water enough to wet the ground).
FLOW_WATERWAYS = ("river", "stream", "canal", "ditch", "drain")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "rural": (24.5, 59.2), "airport": (24.79659, 59.41646),
    "Kalamaja": (24.738, 59.448), "Kopli": (24.68, 59.455),
    "Nomme": (24.68, 59.39), "Pirita": (24.82, 59.47),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> drainage goodness 0..100: 0 on water, 50 at half_m."""
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

def keep_hydro(props):
    """True when a hydro-extract feature is genuine open water.

    Predicate locked with the module docstring: coastline (sea shore),
    natural=water except fenced/ornamental water=*, wetlands, and
    flowing waterways. Everything else in the extract (bank vegetation,
    mills, slipways, untagged node leftovers) is NOT a drainage source.
    """
    p = props or {}
    if p.get("natural") == "coastline":
        return True
    if p.get("natural") in ("water", "wetland"):
        return (p.get("water") or "") not in SKIP_WATER
    return (p.get("waterway") or "") in FLOW_WATERWAYS


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


def read_hydro_sources(grid, hydro_path):
    """Rasterise kept hydro features to source cells (d = 0).

    Polygon interiors are filled (bbox + ring test) so lake centres
    read 0; lines feed densified vertices; points feed directly.
    Returns (set_of_cells, {"features": n, "kept": m, "points": p}).
    """
    with open(hydro_path, encoding="utf-8") as f:
        doc = json.load(f)
    cells = set()
    overlay = []
    feats = kept = 0
    for feat in doc.get("features", []):
        feats += 1
        if not keep_hydro(feat.get("properties") or {}):
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        kept += 1
        gtype = geom.get("type")
        if gtype == "Point":
            k = grid.cell_of(coords[0], coords[1])
            if k is not None:
                cells.add(k)
            overlay.append((coords[0], coords[1]))
        elif gtype == "LineString":
            pts = _densify_line([(c[0], c[1]) for c in coords])
            for lon, lat in pts:
                k = grid.cell_of(lon, lat)
                if k is not None:
                    cells.add(k)
            overlay.extend(pts[:: max(1, len(pts) // 25)])
        elif gtype in ("Polygon", "MultiPolygon"):
            polys = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in polys:
                ring_pts = [(c[0], c[1]) for c in ring]
                for lon, lat in ring_pts[:: max(1, len(ring_pts) // 40)]:
                    k = grid.cell_of(lon, lat)
                    if k is not None:
                        cells.add(k)
                    overlay.append((lon, lat))
                xs = [c[0] for c in ring_pts]
                ys = [c[1] for c in ring_pts]
                ix0 = max(0, int((min(xs) - grid.bbox[0]) * LON_KM * 1000 / grid.step))
                ix1 = min(grid.cols - 1,
                          int((max(xs) - grid.bbox[0]) * LON_KM * 1000 / grid.step))
                iy0 = max(0, int((min(ys) - grid.bbox[1]) * LAT_KM * 1000 / grid.step))
                iy1 = min(grid.rows - 1,
                          int((max(ys) - grid.bbox[1]) * LAT_KM * 1000 / grid.step))
                for iy in range(iy0, iy1 + 1):
                    for ix in range(ix0, ix1 + 1):
                        k = iy * grid.cols + ix
                        if k in cells:
                            continue
                        lon, lat = grid.center_of(k)
                        if ring_contains(ring_pts, lon, lat):
                            cells.add(k)
    return cells, {"features": feats, "kept": kept, "points": len(overlay),
                   "overlay": overlay}


# ---------------------------------------------------------------------------
# Fields: exact grid Dijkstra + quietness scores.
# ---------------------------------------------------------------------------

def dijkstra_km(grid, source_cells):
    """Exact 8-connectivity distance (km) to the nearest source cell.

    No cutoff (sparse sources: no cliffs). Orthogonal step = cell km,
    diagonal = *sqrt(2). Returns array('d') with +inf where unreachable
    (never in practice on a wet county like Harjumaa).
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
    """Nearest-water drainage goodness 100*d/(d+half), 0 on the water."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook.

    Distance layers carry half_m on the wire half field with
    sigma = half_m/1000 (same scale story as the Euclidean fallback,
    GENV convention).
    """
    cal = G03_CAL[layer]
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


def write_outputs(outdir, layer, grid, values):
    name = "%s-walk-raster" % layer
    with open(os.path.join(outdir, name + ".json"), "w",
              encoding="utf-8") as f:
        json.dump(encode_wire(grid, values, layer), f)
    print("wrote %s.json" % name, flush=True)


def thin_overlay(overlay, cap=OVERLAY_CAP):
    """Deterministic stride thin of source points for derived-*.json.

    Dedupes to ~10 m so polygon/LineString export twins (same feature
    twice, G09 twin warning) collapse to one dot; stride keeps spatial
    spread under the cap. Returns [{"lon","lat"}].
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


def build_all(hydro_path, grid):
    """Hydro extract -> per-layer byte masters. Returns {layer: bytes}."""
    t0 = time.time()
    print("hydro: reading %s ..." % hydro_path, flush=True)
    cells, stats = read_hydro_sources(grid, hydro_path)
    print("hydro: features=%d kept=%d source_cells=%d" %
          (stats["features"], stats["kept"], len(cells)), flush=True)
    print("dijkstra: water distance ...", flush=True)
    d_water = dijkstra_km(grid, cells)
    print("fields ready (%.1fs)" % (time.time() - t0), flush=True)
    out = {"drainage": score_distance(d_water, G03_CAL["drainage"]["half_m"])}
    return out, stats


def probe_scores(masters, grid):
    print("probe (drainage goodness 0..100, high = dry):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-9s outside grid" % name, flush=True)
            continue
        print("  %-9s %s" % (name, {l: masters[l][k] for l in LAYER_IDS}),
              flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=list(LAYER_IDS))
    ap.add_argument("--hydro", required=True,
                    help="hydro geojson from the docstring osmium pre-step")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-drainage.json overlay sample")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    masters, stats = build_all(args.hydro, grid)
    vals = masters[args.layer]
    write_outputs(args.outdir, args.layer, grid, vals)
    print("%s: cells=%d zeros(on-water)=%d min=%d max=%d" %
          (args.layer, len(vals), sum(1 for v in vals if v == 0),
           min(vals), max(vals)), flush=True)
    if args.write_points:
        pts = thin_overlay(stats["overlay"])
        with open(os.path.join(args.outdir, "derived-drainage.json"), "w",
                  encoding="utf-8") as f:
            json.dump(pts, f)
        print("wrote derived-drainage.json (%d thinned dots)" % len(pts),
              flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
