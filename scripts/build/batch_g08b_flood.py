"""Group 8 flood/climate-B county masters (issue #168): p255 windtunnel + p333 saltspray.

Stdlib only. Offline, snapshot-only (NO network): tall-building
vectors and sea-coast vectors come from the LOCAL Harjumaa PBF via
the documented osmium pre-steps, never from a live service. Pure
logic + snapshot readers live at module top so unit tests stay
hermetic; full-county builds run only via the documented rebuild
commands.

SCOPE (two layers, honest): this builder serves ONLY p255 (wind
tunneling effects) as a mapped-tall-building proximity hinnang and
p333 (salt air corrosion exposure) as a nearest-SEA distance field.
The sibling params are documented no-map (see
apps/web/lib/layers_group08b.ts):
p118 drought tolerance and p182 prevailing wind direction are
per-register/per-site facts with no honest area signal in the
snapshot — they ship as scorer dims only
(services/scoring/dims_group08b.py), OTA PR #131 precedent.

HONESTY (load-bearing): Ilmateenistus/ERA5 wind fields, the Maa-amet
mullakaart soil survey and a coastal corrosion register are NOT in
the 2026-09-12 snapshot, so neither master is measured data.
windtunnel scores nearness to MAPPED 5+-storey buildings (tunneling
happens in their canyons — the buildings are the mapped cause, not
a wind measurement); saltspray scores distance to the MAPPED SEA
shore (salt spray decays with distance from surf — the param's own
ST_Distance shape, never a corrosion-rate ruling). Titles, legends
and sources say "hinnang" (pinned by layers_group08b.test.ts).

Models (locked 2026-09-12):
* windtunnel (p255): exact full-grid 8-connectivity Dijkstra distance
  to the nearest tall-building cell (same machinery as
  batch_g07b_envhealth.py, local Grid copy for self-containment),
  score = 100*d/(d+200). halfM=200 m: street-canyon acceleration is
  a block-scale effect — Oismae/Mustamae 9-storey slab districts
  read honestly low, detached Nomme reads 80. Measured
  county-raster reads (--probe, 2026-09-12 full build): Viru 0,
  Oismae 0 and Lasnamae 0 (tower districts), Balti 27, Viimsi 43,
  Kadriorg 71, Paljassaare 75, Pirita 76, Nomme 80 (detached),
  rural 99. Panel/tower districts read low BY DESIGN — 5/9-storey
  slab canyons DO channel wind; detached stock reads calm.
* saltspray (p333): exact full-grid Dijkstra distance to the nearest
  SEA cell, score = 100*d/(d+500). halfM=500 m tracks salt-spray
  deposition literature (significant within a few hundred metres of
  surf, negligible past ~1 km). SEA ONLY (natural=coastline):
  lake/pond spray is not salty, so standing water is OUT by design —
  this is what keeps saltspray from re-skinning p340 shoredist
  (#154, shore + lakes, halfM 100). Measured county-raster reads
  (--probe, 2026-09-12 full build): filled in after the first full
  build (see PROBE_POINTS): Pirita 0 (on the beach), Paljassaare
  40 (peninsula), Kadriorg 51, Viimsi 64, Balti 65, Lasnamae 73,
  Viru 76, Oismae 80, Nomme 94 (inland), rural 98. Seaside reads
  low BY DESIGN — salt spray is a surf-zone effect.

Sources (predicates verified on the snapshot extract):
* tall: building:levels first ;-value >= 5 (verified 2026-09-12:
  5622 kept county-wide = 4 Points + 2794 closed footprint rings +
  2824 MultiPolygons; 5512 of them in the Tallinn window).
  building:height is OUT by design (metres confound a 2-storey villa
  with a tower); building:part sections are IN (same tower, merged
  by the 20 m dedupe). Untagged relation members carry no levels,
  so they drop out in keep_tall — no twin purge needed beyond the
  cell dedupe.
* sea: natural=coastline ONLY (verified 2026-09-12: 885 kept =
  620 lines + 265 islet/island MultiPolygons). Closed coastline
  rings are REAL island shores (Aegna, Naissaar, Malusi...), NOT
  area twins — they are densified, never dropped (this differs from
  the G07B twin rule on purpose, documented here). No interior
  fill (differs from G03D lake fill on purpose: an island interior
  is land, and the ring Dijkstra already gives the true distance).

Computation: both masters are graph-free Euclidean fields on the 75 m
county grid (57.29/110.57 scales) — exact-grid Dijkstra nearest-source
distance. NO metro masters (documented): smooth distance-decay fields
at 9.375 m cells would be fake precision — the window route serves
county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/building:levels \\
      -o /tmp/hf-g08b-levels.pbf --overwrite
  osmium export -u type_id /tmp/hf-g08b-levels.pbf -o /tmp/hf-g08b-levels.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/natural=coastline \\
      -o /tmp/hf-g08b-coast.pbf --overwrite
  osmium export -u type_id /tmp/hf-g08b-coast.pbf -o /tmp/hf-g08b-coast.geojson
  python3 scripts/build/batch_g08b_flood.py --layer windtunnel \\
      --poi /tmp/hf-g08b-levels.geojson \\
      --out ~/hf-data/2026-09-12/osm/windtunnel-walk-raster.json \\
      --write-points --probe
  python3 scripts/build/batch_g08b_flood.py --layer saltspray \\
      --shore /tmp/hf-g08b-coast.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: windtunnel-walk-raster.json (Dijkstra quiet master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-windtunnel.json
(fallback points for the Euclidean route + overlay) and
saltspray-walk-raster.json (same wire shape) + derived-saltspray.json
overlay sample. Restart the web server afterwards — the server caches
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
# Constants (mirrors walk_raster / batch_g07b_envhealth scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # line vertex spacing for source rasterisation
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group08b.ts G08B_CAL mirrors these numbers
# exactly — test_batch_g08b.py parses that file and fails on drift.
G08B_CAL = {
    "windtunnel": {"half_m": 200.0, "sigma": 0.2},
    "saltspray": {"half_m": 500.0, "sigma": 0.5},
}

LAYER_IDS = ("windtunnel", "saltspray")

#: Tall threshold: 5+ storeys (panel/tower stock that channels wind).
TALL_LEVELS = 5.0

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> calmness 0..100: 0 on the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


# ---------------------------------------------------------------------------
# Grid (local copy for self-containment, mirrors batch_g07b_envhealth).
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

def first_levels(value):
    """First ;-separated building:levels value as float, else None."""
    try:
        return float(str(value).split(";")[0].strip())
    except (TypeError, ValueError, AttributeError):
        return None


def keep_tall(props):
    """True when a levels-extract feature is a wind-channeling tower.

    building:levels >= 5 (panel/tower stock). building:height is OUT
    by design (metres confound a tall villa with a tower);
    building:part sections are IN (same tower, merged by dedupe).
    Untagged relation members carry no levels, so they drop out here.
    """
    lv = first_levels((props or {}).get("building:levels"))
    return lv is not None and lv >= TALL_LEVELS


def keep_sea(props):
    """True when a coast-extract feature is genuine SEA shore.

    natural=coastline ONLY. Standing water is OUT by design: lake
    spray is not salty, and lakes already feed p340 shoredist (#154)
    — keeping them here would re-skin that layer.
    """
    return (props or {}).get("natural") == "coastline"


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


def read_tall_points(poi_path):
    """Tall-building source points from a levels geojson extract.

    Points feed directly; MultiPolygon outer rings are stride-sampled
    (a distance field only needs the boundary); CLOSED LineStrings are
    building footprint rings — NOT relation twins (footprints carry
    their own building:levels tags; untagged members already dropped
    by keep_tall) — so they feed stride-sampled too. Genuinely OPEN
    tagged lines (rare) are densified. Returns ([(lon, lat)], stats).
    """
    with open(poi_path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    pts = []
    stats = {"towers": 0, "dropped": 0}
    for feat in feats:
        if not isinstance(feat, dict):
            stats["dropped"] += 1
            continue
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
            stats["towers"] += 1
        elif gtype == "MultiPolygon":
            for poly in coords:
                if poly:
                    pts.extend(_stride_ring(poly[0]))
            stats["towers"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))  # footprint ring, not a twin
            else:
                pts.extend(_densify_line(co))
            stats["towers"] += 1
        else:
            stats["dropped"] += 1
    return pts, stats


def read_sea_points(shore_path):
    """Sea-shore source points from a coastline geojson extract.

    Points feed directly; open coastline ways are densified to 40 m;
    CLOSED coastline rings are REAL island shores (Aegna, Naissaar,
    Malusi...) — densified, never dropped (differs from the G07B twin
    rule on purpose); islet/island MultiPolygons feed stride-sampled
    outer rings with NO interior fill (differs from G03D lake fill on
    purpose: an island interior is land, and the ring Dijkstra already
    gives the true distance). Returns ([(lon, lat)], stats).
    """
    with open(shore_path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    pts = []
    stats = {"shore": 0, "dropped": 0}
    for feat in feats:
        if not isinstance(feat, dict):
            stats["dropped"] += 1
            continue
        if not keep_sea(feat.get("properties") or {}):
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
            stats["shore"] += 1
        elif gtype == "LineString":
            # Open mainland ways AND closed island rings alike.
            pts.extend(_densify_line([(c[0], c[1]) for c in coords]))
            stats["shore"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            polys = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in polys:
                pts.extend(_stride_ring(ring, per=40))
            stats["shore"] += 1
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
# Layer scores (high = calm; 0 = known-exposed, never 255).
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
    cal = G08B_CAL[layer]
    return cal["half_m"], cal["sigma"]


def encode_wire(grid, values, layer="saltspray"):
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


def build_layer(grid, layer, poi_path=None, shore_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer == "windtunnel":
        if not poi_path:
            raise SystemExit("windtunnel needs --poi levels extract")
        raw, stats = read_tall_points(poi_path)
        print("windtunnel=%s raw_pts=%d" % (stats, len(raw)), flush=True)
    else:
        if not shore_path:
            raise SystemExit("saltspray needs --shore coastline extract")
        raw, stats = read_sea_points(shore_path)
        print("saltspray=%s raw_pts=%d" % (stats, len(raw)), flush=True)
    pts = dedupe_cells(raw)
    print("%s: deduped %d -> %d" % (layer, len(raw), len(pts)), flush=True)
    dist = dijkstra_km(grid, cells_of_points(grid, pts))
    vals = score_distance(dist, G08B_CAL[layer]["half_m"])
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
    ap.add_argument("--poi", default=None,
                    help="levels geojson extract (windtunnel)")
    ap.add_argument("--shore", default=None,
                    help="coastline geojson extract (saltspray)")
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
        vals, pts = build_layer(grid, layer, args.poi, args.shore)
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
