"""Group 8 flood/climate county master, batch D (issue #170): vernalpool (p447).

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; the full-county build runs only
via the documented rebuild command.

HONESTY (load-bearing): the Keskkonnaagentuur flood-hazard WFS, EFAS /
CMEMS reanalyses and Ilmateenistus archives are NOT in the snapshot,
so this is an OSM PROXIMITY proxy — titles, legends and sources say
"proksi (hinnang)", never flood zones, return periods or water-table
claims. Green = far/clean (hinnang), red = near/exposed (hinnang).
In-bbox absence of a mapped ephemeral pond IS the clean evidence, so
the master emits no in-bbox unknowns (high = known-dry where nothing
mapped, never 255); out-of-coverage stays 255 server-side (cover
mask).

Model (locked 2026-09-12 from snapshot probes — witness table in PR
#170):
* vernalpool (p447): nearest explicitly-ephemeral still-water body
  (natural=water + water=pond/basin + intermittent=yes, one-time PBF
  export below: 17 unique bodies = 8 ponds + 9 basins): dryness =
  100*d/(d+300). Parcel-scale still-water nuisance (soggy ground +
  mosquitoes), same half as the #151 drainage and #142 vectorhabitat
  layers.
* intermittent=yes ditches (167), drains (44), rivers (14) and
  streams (7) are DELIBERATELY excluded — flow features belong to
  p50 drainage (#151); a ditch is not a vernal pool.
* natural=wetland (1306 features, zero intermittent/seasonal tags)
  is DELIBERATELY excluded — all-wetland proximity would re-skin
  p50 drainage (#151) and p257 vectorhabitat (#142). ONLY
  explicitly-ephemeral water ships.
* seasonal=* (133 features) lives on tourism features, never on
  water/wetland: no vernal signal, excluded.

Deliberately NOT mapped (documented no-map, OTA PR #131 precedent):
p377 frost heave (no soil/geotech in the snapshot; wetland nearness
would duplicate p50), p378 saltwater intrusion (salt tags are ~all
salt=no freshwater confirmations + 2 salt=yes wetlands — zero
aquifer signal; shore distance would duplicate p340), p429 flood
zone creep (needs zone time series; 12 flood_prone=yes tags are
anecdotal, not a zone; water proximity would duplicate p50). Their
scorer dims live in services/scoring/dims_group08d.py and stay NULL,
never faked.

Computation: exact full-grid 8-connectivity Dijkstra from rasterized
source cells (no cutoff, no cliffs). Grid mirrors walk_raster (75 m
county, 57.29/110.57 scales).

NO metro masters (documented): a distance-decay proxy is smooth at the
75 m county step; 9.375 m cells would be fake precision. The window
route serves county everywhere (metro slot stays empty).

One-time PBF export (snapshot dir input, NOT committed — same pattern
as batch_g07b_envhealth.py derived-tanks.geojson):
  S=~/hf-data/2026-09-12/osm
  osmium tags-filter $S/harjumaa-260911.osm.pbf \\
      nwr/intermittent=yes -o /tmp/g08d-ephem.pbf --overwrite
  osmium export -u type_id /tmp/g08d-ephem.pbf \\
      -o $S/derived-ephemeral.geojson --overwrite
  # 299 features: 167 ditches + 44 drains + 14 rivers + 7 streams
  # (flow: dropped by the keeper) + 33 pond/basin features (17 areas
  # + 16 closed-way twins = 17 unique bodies: 8 ponds + 9 basins; 2
  # intermittent=no ponds correctly dropped) + untagged member
  # objects (dropped by the reader).

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  python3 scripts/build/batch_g08d_flood.py --layer all \\
      --snap ~/hf-data/2026-09-12 --outdir ~/hf-data/2026-09-12/osm \\
      --write-points --probe
  # small test bbox:
  python3 scripts/build/batch_g08d_flood.py --layer vernalpool \\
      --snap ~/hf-data/2026-09-12 --outdir /tmp/g08d \\
      --bbox 24.6 59.35 24.9 59.5 --probe
Outputs: vernalpool-walk-raster.json (combined wire, WalkRasterDoc
shape so cleanRaster accepts it); --write-points also writes
derived-vernalpool.json (thinned overlay/fallback points, {lon, lat}).
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
# Constants (mirrors walk_raster / batch_g07b_envhealth scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DEDUPE_M = 20.0  # twin guard (mirrors scorer _count_cells_within_m)

# Calibration locked 2026-09-12 (see module docstring probes).
# NOTE: apps/web/lib/layers_group08d.ts G08D_CAL mirrors these numbers
# exactly — test_batch_g08d.py parses that file and fails on drift.
G08D_CAL = {
    "vernalpool": {"half_m": 300.0, "sigma": 0.3},
}

LAYER_IDS = ("vernalpool",)

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.68, 59.375), "Paljassaare": (24.698, 59.466),
    "rural": (24.5, 59.2), "airport": (24.79659, 59.41646),
    "ephempond": (24.7972, 59.4425),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> dryness 0..100: 0 on the source, 50 at half_m."""
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


def _read_derived_areas(snap, fname, keep, stats):
    """Shared derived-*.geojson reader (FeatureCollection from osmium).

    Keeps tagged MultiPolygons (ring-sampled), genuinely OPEN tagged
    LineStrings (densified) and tagged Points; drops closed-way
    LineString twins (same area re-emitted) and untagged member objects
    pulled in for relation completeness. `keep(props)` returns the
    stats key for a wanted feature, else None. Returns ([(lon, lat)],
    stats).
    """
    with open(_need(snap, "osm", fname), encoding="utf-8") as f:
        d = json.load(f)
    feats = d["features"] if isinstance(d, dict) else d
    pts = []
    for feat in feats:
        if not isinstance(feat, dict):
            stats["untagged_dropped"] += 1
            continue
        props = feat.get("properties") or {}
        key = keep(props)
        if key is None:
            stats["untagged_dropped"] += 1
            continue
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if not coords:
            stats["untagged_dropped"] += 1
            continue
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


def keep_vernalpool(props):
    """Strict ephemeral-still-water predicate (the honest core).

    natural=water + water=pond/basin + intermittent=yes ONLY.
    Intermittent ditches/drains/rivers/streams (flow: p50's),
    all wetlands (p50/p257's) and permanent ponds are dropped by
    returning None.
    """
    if props.get("natural") != "water":
        return None
    if props.get("water") not in ("pond", "basin"):
        return None
    if props.get("intermittent") != "yes":
        return None
    return "ponds" if props.get("water") == "pond" else "basins"


def read_vernalpool_points(snap):
    """Ephemeral-pond source points (derived-ephemeral.geojson).

    Verified 2026-09-12: 299 intermittent=yes features, of which
    17 areas (8 ponds + 9 basins) are kept; 211 ditches/drains + 14
    rivers + 7 streams + 2 intermittent=no ponds (dropped by the
    keeper), 16 closed-way twins by the shared reader. Returns
    ([(lon, lat)], stats).
    """
    stats = {"ponds": 0, "basins": 0, "twins_dropped": 0,
             "untagged_dropped": 0}
    return _read_derived_areas(snap, "derived-ephemeral.geojson",
                               keep_vernalpool, stats)


def dedupe_cells(points, cell_m=DEDUPE_M):
    """Merge area twins falling in the same ~cell_m cell."""
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
# Layer scores (high = dry; 0 = known-exposed, never 255).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-source dryness 100*d/(d+half) for one distance field."""
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
    cal = G08D_CAL[layer]
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
    print("vernalpool: reading derived-ephemeral.geojson...", flush=True)
    ephem_pts, ephem_stats = read_vernalpool_points(snap)
    print("vernalpool=%s raw_pts=%d" % (ephem_stats, len(ephem_pts)),
          flush=True)

    print("dijkstra: vernalpool...", flush=True)
    d_ephem = dijkstra_km(grid, cells_of_points(grid, ephem_pts))
    print("fields ready (%.1fs)" % (time.time() - t0), flush=True)

    out = {}
    out["vernalpool"] = score_distance(
        d_ephem, G08D_CAL["vernalpool"]["half_m"])
    return out, {"vernalpool": ephem_pts}


def probe_scores(masters, grid):
    print("probe (high = dry):", flush=True)
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