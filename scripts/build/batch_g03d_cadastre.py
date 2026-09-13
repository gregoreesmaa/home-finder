"""Group 3 cadastre-D county masters (issue #154): p332 moorage + p340 shoredist.

Stdlib + scripts/ walk helpers only. Offline, snapshot-only (NO
network): mooring vectors and shore vectors come from the LOCAL
Harjumaa PBF via the documented osmium pre-steps, never from a live
service. Pure logic + snapshot readers live at module top so unit
tests stay hermetic; full-county builds run only via the documented
rebuild commands.

SCOPE (two layers, honest): this builder serves ONLY p332 (dock /
mooring opportunity) as a mapped-facility count hinnang and p340
(shoreline setback) as a nearest-shore distance field. The sibling
params are documented no-map (see apps/web/lib/layers_group03d.ts):
p331 seawall structure, p337 lake level fluctuation and p339 well
recharge are per-structure/per-register facts with no honest area
signal in the snapshot — they ship as scorer dims only
(services/scoring/dims_group03d.py), OTA PR #131 precedent.

HONESTY (load-bearing): the Maa-amet cadastre/permit WFS, EELIS gauge
time series and hydrogeology grids are NOT in the 2026-09-12 snapshot,
so neither master is measured registry data. moorage scores nearness
to MAPPED marinas/moorings/harbours (the permit itself stays a
per-parcel fact); shoredist scores distance to the MAPPED shoreline
(the param's own ST_Distance formula, never a legal ruling). Titles,
legends and sources say "hinnang" (pinned by layers_group03d.test.ts).

Models (locked 2026-09-12):
* moorage (p332): EUCLIDEAN count kernel over kept mooring points
  (Gaussian sigma 0.3, cutoff 4 sigma, saturating score 100*S/(S+half),
  null below 3 -> 255). Euclidean, not walk-stamped, BY DESIGN: marina
  centroids sit on water where the foot graph has no vertices, so walk
  stamping leaves holes AT the facilities themselves (verified: Pirita
  sadam read 255 under stamp_sum). half=1 (not 2): with 195 county
  facilities (41 Tallinn-window: Kakumae, Hundipea,
  Lennusadam/Noblessner, Kalasadam, Vanasadam, Pirita, Kalevi) ONE
  mapped marina reads 50 on its own cell (mid-amber) instead of
  vanishing; inland Nomme/Lasnamae read honestly low.
* shoredist (p340): exact full-grid 8-connectivity Dijkstra distance
  to the nearest shore cell (same machinery as batch_g03_cadastre.py,
  local Grid copy for self-containment), score = 100*d/(d+100).
  halfM=100 m tracks the legal zones (Veeseadus 50-100 m). Measured
  county-raster reads (--probe, 2026-09-12 full build): Pirita 0 and
  Vanasadam 0 (probe points sit on marina/harbour water), Kakumae 43
  (shore-adjacent peninsula), Viru 77 (pond 291 m out), Kalamaja 78,
  Nomme 84 (unnamed water 507 m out), Lasnamae 91, rural 94. Most of
  Tallinn reads high BY DESIGN — most of Tallinn IS outside the
  setback zones. Rivers/streams/wetlands are EXCLUDED (they belong to
  p50 drainage, #151); lake centres read 0 via polygon fill.

Sources (predicates verified on the snapshot extract):
* moorage: leisure=marina, seamark:type in (mooring, harbour),
  harbour=yes, mooring in (yes, yacht, private, declaration,
  commercial); mooring=no explicitly OUT. Bare man_made=pier (544,
  incl. cargo/industrial) is OUT by design: a cargo quay is not
  mooring opportunity. Breakwaters/quays (p331-adjacent shore
  structures) are OUT: they answer condition, not opportunity.
* shore: natural=coastline (sea shore) + natural=water polygons
  except fenced/ornamental water=* (wastewater/basin/fountain).
  Flowing waterways and wetlands are OUT (p50's signal, not shore).

Computation: both masters are graph-free Euclidean fields on the 75 m
county grid (57.29/110.57 scales) — moorage a Gaussian count kernel,
shoredist exact-grid Dijkstra. NO metro masters (documented):
sparse/smooth fields at 9.375 m cells would be fake precision — the
window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/leisure=marina nwr/seamark:type=mooring \\
      nwr/seamark:type=harbour nwr/harbour=yes nwr/mooring=yes \\
      nwr/man_made=pier nwr/man_made=breakwater nwr/man_made=quay \\
      -o /tmp/hf-g03d-moor.pbf --overwrite
  osmium export -u type_id /tmp/hf-g03d-moor.pbf -o /tmp/hf-g03d-moor.geojson
  python3 scripts/build/batch_g03d_cadastre.py --layer moorage \\
      --poi /tmp/hf-g03d-moor.geojson \\
      --out ~/hf-data/2026-09-12/osm/moorage-walk-raster.json \\
      --write-points --probe
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/natural=coastline nwr/natural=water \\
      -o /tmp/hf-g03d-shore.pbf --overwrite
  osmium export -u type_id /tmp/hf-g03d-shore.pbf -o /tmp/hf-g03d-shore.geojson
  python3 scripts/build/batch_g03d_cadastre.py --layer shoredist \\
      --shore /tmp/hf-g03d-shore.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: moorage-walk-raster.json (Euclidean count-kernel master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-moorage.json
(fallback points for the Euclidean route + overlay) and
shoredist-walk-raster.json (same wire shape) + derived-shoredist.json
overlay sample. Restart :3108 afterwards — the server caches masters
per process.
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

import walk_raster as wr  # noqa: E402

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_g03_cadastre scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # shore-line vertex spacing for source rasterisation
OVERLAY_CAP = 1500  # thinned shore overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group03d.ts G03D_CAL mirrors these numbers
# exactly — test_batch_g03d.py parses that file and fails on drift.
G03D_CAL = {
    "moorage": {"half": 1, "sigma": 0.3},
    "shoredist": {"half_m": 100.0, "sigma": 0.3},
}

LAYER_IDS = ("moorage", "shoredist")

#: water= values that are fenced/ornamental infra, not shore.
SKIP_WATER = ("wastewater", "basin", "fountain")
#: mooring= values that still indicate mooring infrastructure nearby.
#: "no" is absent ON PURPOSE (explicit exclusion, pinned by test).
KEEP_MOORING = ("yes", "yacht", "private", "declaration", "commercial")
#: seamark:type values that are mooring opportunity (not navigation aids).
KEEP_SEAMARK = ("mooring", "harbour")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Pirita": (24.821, 59.468), "Kalamaja": (24.738, 59.448),
    "Kakumae": (24.604, 59.452), "Vanasadam": (24.759, 59.443),
    "Viru": (24.7611, 59.4278), "Nomme": (24.68, 59.39),
    "Lasnamae": (24.82, 59.44), "rural": (24.5, 59.2),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> shoredist goodness 0..100: 0 at shore, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


# ---------------------------------------------------------------------------
# Moorage predicate (p332 hinnang source set).
# ---------------------------------------------------------------------------

def is_moorage(tags):
    """True when OSM tags mark a dock/mooring opportunity (NOT a permit).

    Tight by design: marinas, seamark moorings/harbours and explicit
    harbour/mooring=yes. Bare piers (cargo/industrial/private) and
    breakwaters/quays (p331 shore structures) are OUT; mooring=no is
    explicitly OUT. Never throws.
    """
    if not isinstance(tags, dict):
        return False
    if tags.get("leisure") == "marina":
        return True
    if tags.get("seamark:type") in KEEP_SEAMARK:
        return True
    if tags.get("harbour") == "yes":
        return True
    return tags.get("mooring") in KEEP_MOORING


LAYER_PRED = {
    "moorage": is_moorage,
}

# ~20 m spatial dedupe cells (mirrors snapshot.ts DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def dedupe_points(feats):
    """Collapse co-located points (~20 m cells, first wins).

    Needed because osmium export emits node+area pairs for the same
    marina: OSM-id dedupe in resolve_pois cannot see those pairs, and
    double-counting one harbour would double its kernel weight.
    Distinct quays >20 m apart (e.g. Kai A..G in Kakumae) stay
    separate — a harbour basin reads as more mooring-dense.
    """
    seen = {}
    for lon, lat, w in feats:
        k = (round(lon / DEDUPE_LON), round(lat / DEDUPE_LAT))
        if k not in seen:
            seen[k] = (lon, lat, w)
    return list(seen.values())


def _area_score(acc, half):
    """Mirror of the grocery/healthcare scorer: saturate, null below 3."""

    def score_of(k):
        s = acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= 3 else None

    return score_of


def build_moorage_field(grid, half, sigma, poi_path):
    """Euclidean Gaussian count kernel over kept mooring points.

    Bounded O(points * range^2) sweep: each facility stamps
    kernel(d, sigma) into cells within 4 sigma. Returns (acc, stats).
    Graph-free on purpose (see module docstring: walk stamping leaves
    water-centroid holes at the facilities themselves).
    """
    raw, stats = wr.resolve_pois(poi_path, LAYER_PRED["moorage"])
    feats = dedupe_points(raw)
    cutoff_km = 4.0 * sigma
    acc = {}
    minlon, minlat, _, _ = grid.bbox
    for lon, lat, _ in feats:
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
                acc[k] = acc.get(k, 0.0) + wr.kernel(d, sigma)
    print("moorage: %d point features (%d raw, %d co-located merged), "
          "%d stamped cells"
          % (len(feats), stats["kept"], stats["kept"] - len(feats), len(acc)),
          flush=True)
    return acc, feats


# ---------------------------------------------------------------------------
# Shore grid (p340): local Grid + Dijkstra (mirrors batch_g03_cadastre for
# self-containment — one batch file, no cross-batch import).
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


def keep_shore(props):
    """True when a shore-extract feature is genuine shoreline.

    Sea coastline + standing-water polygons (lakes/ponds/reservoirs).
    Flowing waterways and wetlands are OUT (p50 drainage's signal);
    fenced/ornamental water=* and untagged leftovers are OUT.
    """
    p = props or {}
    if p.get("natural") == "coastline":
        return True
    if p.get("natural") == "water":
        return (p.get("water") or "") not in SKIP_WATER
    return False


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


def read_shore_sources(grid, shore_path):
    """Rasterise kept shore features to source cells (d = 0).

    Polygon interiors are filled (bbox + ring test) so lake centres
    read 0; coastline/ring lines feed densified vertices; points feed
    directly. Returns (set_of_cells, stats).
    """
    with open(shore_path, encoding="utf-8") as f:
        doc = json.load(f)
    cells = set()
    overlay = []
    feats = kept = 0
    for feat in doc.get("features", []):
        feats += 1
        if not keep_shore(feat.get("properties") or {}):
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


def dijkstra_km(grid, source_cells):
    """Exact 8-connectivity distance (km) to the nearest source cell.

    No cutoff (sparse sources: no cliffs). Orthogonal step = cell km,
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
    """Nearest-shore setback goodness 100*d/(d+half), 0 at the shore."""
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

    moorage carries the area-kind half; shoredist carries half_m on the
    wire half field with sigma = half_m/1000 scale story (GENV
    convention, like the G03 drainage master).
    """
    cal = G03D_CAL[layer]
    if layer == "moorage":
        return cal["half"], cal["sigma"]
    return cal["half_m"], cal["sigma"]


def encode_wire(grid, values, layer="shoredist"):
    half, sigma = contract_of(layer)
    return {
        "cols": grid.cols, "rows": grid.rows,
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step, "half": half, "sigma": sigma,
        "per": 0, "cap": 0, "unknown": 255, "dtype": "uint8",
        "data": base64.b64encode(bytes(values)).decode("ascii"),
    }


def write_shore_outputs(outdir, grid, values):
    with open(os.path.join(outdir, "shoredist-walk-raster.json"), "w",
              encoding="utf-8") as f:
        json.dump(encode_wire(grid, values), f)
    print("wrote shoredist-walk-raster.json", flush=True)


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


def build_shore(shore_path, grid):
    """Shore extract -> shoredist byte master. Returns (bytes, stats)."""
    t0 = time.time()
    print("shore: reading %s ..." % shore_path, flush=True)
    cells, stats = read_shore_sources(grid, shore_path)
    print("shore: features=%d kept=%d source_cells=%d" %
          (stats["features"], stats["kept"], len(cells)), flush=True)
    print("dijkstra: shore distance ...", flush=True)
    d_shore = dijkstra_km(grid, cells)
    print("field ready (%.1fs)" % (time.time() - t0), flush=True)
    return score_distance(d_shore, G03D_CAL["shoredist"]["half_m"]), stats


def probe_shore(vals, grid):
    print("probe (shoredist goodness 0..100, high = outside zones):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-9s outside grid" % name, flush=True)
            continue
        print("  %-9s %d" % (name, vals[k]), flush=True)


def score_bytes(grid, score_of):
    """Per-cell FINAL uint8 scores (255 = unknown), as raw bytes."""
    vals = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k in range(grid.cols * grid.rows):
        s = score_of(k)
        if s is not None:
            vals[k] = int(round(min(100.0, s)))
    return bytes(vals)


def probe_moorage(vals, grid):
    print("probe (moorage goodness 0..100, high = facilities near):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-9s outside grid" % name, flush=True)
            continue
        v = vals[k]
        print("  %-9s %s" % (name, "unknown" if v == 255 else v), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=list(LAYER_IDS))
    ap.add_argument("--poi", default=None,
                    help="mooring geojson (moorage only)")
    ap.add_argument("--shore", default=None,
                    help="shore geojson from the docstring osmium pre-step")
    ap.add_argument("--out", default=None,
                    help="moorage raster output path")
    ap.add_argument("--outdir", default=None,
                    help="shoredist raster output dir")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-*.json overlay/fallback sample")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args()
    if args.layer == "moorage":
        if not args.poi or not args.out:
            ap.error("--poi and --out are required for moorage")
        t0 = time.time()
        grid = Grid(args.bbox, args.step_m)
        print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
        defs = G03D_CAL["moorage"]
        acc, feats = build_moorage_field(grid, defs["half"], defs["sigma"], args.poi)
        vals = score_bytes(grid, _area_score(acc, defs["half"]))
        doc = encode_wire(grid, vals, "moorage")
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        raw = base64.b64decode(doc["data"])
        known = sum(1 for v in raw if v != 255)
        print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
        print("wrote %s (%.1f MB, %.1fs)"
              % (args.out, os.path.getsize(args.out) / 1e6, time.time() - t0))
        if args.write_points:
            pts = [{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats]
            derived = os.path.join(os.path.dirname(args.out), "derived-moorage.json")
            with open(derived, "w", encoding="utf-8") as f:
                json.dump(pts, f)
            print("wrote derived-moorage.json (%d fallback points)" % len(pts),
                  flush=True)
        if args.probe:
            probe_moorage(vals, grid)
        return
    if not args.shore or not args.outdir:
        ap.error("--shore and --outdir are required for shoredist")
    os.makedirs(args.outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    vals, stats = build_shore(args.shore, grid)
    write_shore_outputs(args.outdir, grid, vals)
    print("shoredist: cells=%d zeros(at-shore)=%d min=%d max=%d" %
          (len(vals), sum(1 for v in vals if v == 0),
           min(vals), max(vals)), flush=True)
    if args.write_points:
        pts = thin_overlay(stats["overlay"])
        with open(os.path.join(args.outdir, "derived-shoredist.json"), "w",
                  encoding="utf-8") as f:
            json.dump(pts, f)
        print("wrote derived-shoredist.json (%d thinned dots)" % len(pts),
              flush=True)
    if args.probe:
        probe_shore(vals, grid)


if __name__ == "__main__":
    main()
