"""Group 7 environmental-health county masters (issue #140):
industprox (p61) / odorsrc (p62).

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; the full-county build runs only
via the documented rebuild command.

HONESTY (load-bearing): Keskkonnaagentuur air-quality stations and any
measured odor/pollen/radon survey are NOT in the snapshot, so these are
OSM PROXIMITY proxies — titles, legends and sources say "proksi
(hinnang)", never AQI, OU/m3, Bq/m3 or pollen grains/m3. Green =
far/clean (hinnang), red = near/exposed (hinnang). In-bbox absence of a
mapped source IS the clean evidence, so masters emit no in-bbox unknowns
(100 = known-clean where nothing mapped, never 255); out-of-coverage
stays 255 server-side (cover mask).

Model (locked 2026-09-12 from snapshot probes — witness table in PR
#140):
* industprox (p61): nearest industrial area (landuse=industrial, 27
  areas from harju-amenities.geojson — 54 features, half closed-way
  LineString twins of the same areas, correctly used once; same areas
  the GENV lowspec layer stamps): clean = 100*d/(d+500). The half
  matches lowspec (same source class, same carry); the layer differs
  by showing industry ALONE, where lowspec mixes
  roads/rail/quarries/wind/motorsport.
* odorsrc (p62): nearest mapped odor-capable site (man_made=
  wastewater_plant, ~36 areas, + landuse=landfill, ~24 areas, one-time
  PBF export below): clean = 100*d/(d+500). Smell carries like
  low-frequency rumble, hence the lowspec-scale half. Wastewater nodes
  sitting on plant polygons merge in the 20 m dedupe (twin guard).

Deliberately NOT mapped (documented no-map, OTA PR #131 precedent):
p66 radon (no geology/WFS in the snapshot), p67 pests/wildlife (no
survey in the snapshot) and p137 seasonal allergens (no pollen traps
in the snapshot; mapped green would read INVERTED — parks emit
pollen). Their scorer dims live in services/scoring/dims_group07.py
and stay NULL, never faked.

Computation: exact full-grid 8-connectivity Dijkstra from rasterized
source cells (no cutoff, no cliffs). Grid mirrors walk_raster (75 m
county, 57.29/110.57 scales).

NO metro masters (documented): a distance-decay proxy is smooth at the
75 m county step; 9.375 m cells would be fake precision. The window
route serves county everywhere (metro slot stays empty).

One-time PBF export (snapshot dir input, NOT committed — same pattern
as batch_genv_exposure.py derived-aeroway.geojson; industrial reuses
the existing harju-amenities.geojson sidecar, no export needed):
  S=~/hf-data/2026-09-12/osm
  osmium tags-filter $S/harjumaa-260911.osm.pbf \\
      nwr/man_made=wastewater_plant nwr/landuse=landfill \\
      -o /tmp/g07-odor.pbf --overwrite
  osmium export /tmp/g07-odor.pbf -o $S/derived-odor.geojson --overwrite
  # 132 features: ~36 wastewater_plant areas + ~24 landfill areas, each
  # as a MultiPolygon + its closed-way LineString twin, plus 14 untagged
  # member objects (dropped by the reader).

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  python3 scripts/build/batch_g07_envhealth.py --layer all \\
      --snap ~/hf-data/2026-09-12 --outdir ~/hf-data/2026-09-12/osm \\
      --write-points --probe
  # single layer, small test bbox:
  python3 scripts/build/batch_g07_envhealth.py --layer odorsrc \\
      --snap ~/hf-data/2026-09-12 --outdir /tmp/g07 \\
      --bbox 24.6 59.35 24.9 59.5 --probe
Outputs per layer: <id>-walk-raster.json (combined wire, WalkRasterDoc
shape so cleanRaster accepts it); --write-points also writes
derived-<id>.json (thinned overlay/fallback points, {lon, lat}).
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
# Constants (mirrors walk_raster / batch_genv_exposure scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)

# Calibration locked 2026-09-12 (see module docstring probes).
# NOTE: apps/web/lib/layers_group07.ts G07_CAL mirrors these numbers
# exactly — test_batch_g07.py parses that file and fails on drift.
G07_CAL = {
    "industprox": {"half_m": 500.0, "sigma": 0.5},
    "odorsrc": {"half_m": 500.0, "sigma": 0.5},
}

LAYER_IDS = ("industprox", "odorsrc")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.68, 59.375), "Paljassaare": (24.698, 59.466),
    "rural": (24.5, 59.2), "airport": (24.79659, 59.41646),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> cleanliness 0..100: 0 on the source, 50 at half_m."""
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

def _need(snap, *parts):
    p = os.path.join(snap, *parts)
    if not os.path.exists(p):
        raise SystemExit(
            "missing %s — run the one-time osmium exports in this "
            "module's docstring (snapshot-only, no network)" % p)
    return p


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


def _is_closed(coords):
    return len(coords) > 1 and coords[0] == coords[-1]


def read_industrial_points(snap):
    """Industrial-area ring points (harju-amenities.geojson sidecar).

    Same 54-area source set the GENV lowspec layer stamps (verified
    2026-09-12: 54 landuse=industrial features). Polygons yield
    stride-sampled outer-ring points (interior coverage comes free:
    a distance field only needs the boundary); densified to ~50 m so
    long straight fences stamp continuous cells.
    Returns ([(lon, lat)], {"areas": n}).
    """
    pts = []
    areas = 0
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
            if (feat.get("properties") or {}).get("landuse") != "industrial":
                continue
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            if geom.get("type") == "Point" and coords:
                pts.append((coords[0], coords[1]))
                areas += 1
            elif geom.get("type") in ("Polygon", "MultiPolygon") and coords:
                rings = [coords[0]] if geom["type"] == "Polygon" \
                    else [p[0] for p in coords if p]
                for ring in rings:
                    samp = [(c[0], c[1])
                            for c in ring[:: max(1, len(ring) // 50)]]
                    pts.extend(_densify_line(samp))
                areas += 1
    return pts, {"areas": areas}


def read_odor_points(snap):
    """Wastewater-plant + landfill source points (derived-odor.geojson).

    Keeps tagged MultiPolygons (ring-sampled), genuinely OPEN tagged
    LineStrings (densified) and tagged Points; drops closed-way
    LineString twins (same area re-emitted) and untagged member objects
    pulled in for relation completeness. Returns ([(lon, lat)], stats).
    """
    with open(_need(snap, "osm", "derived-odor.geojson"),
              encoding="utf-8") as f:
        d = json.load(f)
    feats = d["features"] if isinstance(d, dict) else d
    pts = []
    stats = {"plants": 0, "landfills": 0, "twins_dropped": 0,
             "untagged_dropped": 0}
    for feat in feats:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        kind = props.get("man_made") if props.get("man_made") == \
            "wastewater_plant" else props.get("landuse")
        if kind not in ("wastewater_plant", "landfill"):
            stats["untagged_dropped"] += 1
            continue
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if not coords:
            stats["untagged_dropped"] += 1
            continue
        key = "plants" if kind == "wastewater_plant" else "landfills"
        if gtype == "Point":
            pts.append((coords[0], coords[1]))
            stats[key] += 1
        elif gtype == "MultiPolygon":
            for poly in coords:
                if not poly:
                    continue
                ring = poly[0]
                pts.extend((c[0], c[1])
                           for c in ring[:: max(1, len(ring) // 50)])
            stats[key] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if _is_closed(co):
                stats["twins_dropped"] += 1  # closed-way area twin
                continue
            pts.extend(_densify_line(co))
            stats[key] += 1
        else:
            stats["untagged_dropped"] += 1
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
# Fields: exact grid Dijkstra.
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
# Layer scores (high = clean; 0 = known-exposed, never 255).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-source cleanliness 100*d/(d+half) for one distance field."""
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
    cal = G07_CAL[layer]
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


def write_points(outdir, layer, points):
    """Thinned overlay/fallback points (loadSnapshotPoints reads these)."""
    pts = dedupe_cells(points)
    if len(pts) > 3000:  # stride-thin huge ring samples, keep spread
        stride = len(pts) / 3000
        pts = [pts[int(i * stride)] for i in range(3000)]
    doc = [{"lon": round(lon, 6), "lat": round(lat, 6)}
           for lon, lat in pts]
    with open(os.path.join(outdir, "derived-%s.json" % layer), "w",
              encoding="utf-8") as f:
        json.dump(doc, f)
    print("wrote derived-%s.json (%d pts)" % (layer, len(doc)), flush=True)
    return doc


def build_all(snap, grid):
    """Source points -> per-layer byte masters. Returns ({layer: bytes}, pts)."""
    t0 = time.time()
    print("industrial: reading amenity sidecar...", flush=True)
    ind_pts, ind_stats = read_industrial_points(snap)
    print("industrial=%s raw_pts=%d" % (ind_stats, len(ind_pts)), flush=True)
    print("odor: reading derived-odor.geojson...", flush=True)
    odor_pts, odor_stats = read_odor_points(snap)
    print("odor=%s raw_pts=%d" % (odor_stats, len(odor_pts)), flush=True)

    print("dijkstra: industrial...", flush=True)
    d_ind = dijkstra_km(grid, cells_of_points(grid, ind_pts))
    print("dijkstra: odor...", flush=True)
    d_odor = dijkstra_km(grid, cells_of_points(grid, odor_pts))
    print("fields ready (%.1fs)" % (time.time() - t0), flush=True)

    out = {}
    out["industprox"] = score_distance(
        d_ind, G07_CAL["industprox"]["half_m"])
    out["odorsrc"] = score_distance(
        d_odor, G07_CAL["odorsrc"]["half_m"])
    return out, {"industprox": ind_pts, "odorsrc": odor_pts}


def probe_scores(masters, grid):
    print("probe (high = clean):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-11s outside grid" % name, flush=True)
            continue
        print("  %-11s %s" % (name, {l: masters[l][k] for l in LAYER_IDS}),
              flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True,
                    choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--snap", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--format", choices=["combined", "split"],
                    default="combined")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-<layer>.json overlay points")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args(argv)
    os.makedirs(args.outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step),
          flush=True)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    masters, point_sets = build_all(args.snap, grid)
    for layer in layers:
        write_outputs(args.outdir, layer, grid, masters[layer], args.format)
        if args.write_points:
            write_points(args.outdir, layer, point_sets[layer])
        vals = masters[layer]
        print("%s: cells=%d zeros(known-exposed)=%d" %
              (layer, len(vals), sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
