"""Group 17 HOA-rest county master (issue #196): p245 privroad.

Stdlib only. Offline, snapshot-only (NO network): private-road
vectors come from the LOCAL Harjumaa PBF via the documented osmium
pre-step, never from a live service. Pure logic + snapshot readers
live at module top so unit tests stay hermetic; full-county builds
run only via the documented rebuild command.

SCOPE (one layer, honest): this builder serves ONLY p245 (private
road maintenance) as a mapped-shared-private-road proximity
hinnang. The eleven sibling params are documented no-map (see
apps/web/lib/layers_group17rest.ts): p4 maintenance costs, p49 HOA
restrictions, p142 reserves, p145 vehicle restrictions, p152
owner-occupancy, p167 trash etiquette, p246 special assessments,
p247 sub-metering, p278 shared-maintenance phrasing, p368 rental
caps and p427 initiation fees are per-KÜ/per-building document
facts with no area signal — they ship as scorer dims only
(services/scoring/dims_group17rest.py), OTA PR #131 precedent.

HONESTY (load-bearing): the e-Äriregister KÜ annual reports, board
cards, Creditinfo/MTA arrears and EKÜL baselines are NOT in the
2026-09-12 snapshot, so the master is NOT registry data. privroad
scores nearness to MAPPED access=private shared roads (erateed),
never a KÜ maintenance agreement: the map cannot know WHICH
private roads carry an upkeep agreement or what it costs. Titles,
legends and sources say "hinnang" (pinned by
layers_group17rest.test.ts).

Model (locked 2026-09-12):
* privroad (p245): exact full-grid 8-connectivity Dijkstra distance
  to the nearest shared-private-road cell (same machinery as
  batch_g07b_envhealth.py, local Grid copy for self-containment),
  score = 100*d/(d+200). halfM=200 m (tighter than commbleed
  300 m): an upkeep burden is parcel-scale — your street, not the
  block. Tiskrevälja/Kakumäe eratee parcels read honestly low,
  public-street Viru reads calm. Roads feed densified (open lines)
  or stride-sampled (closed rings); there is NO polygon fill (a
  road is linear — filling blocks would mark parcels as "on the
  road"). Points feed directly.

Sources (predicates verified on the snapshot extract):
* privroad: access=private AND highway in (service, track,
  unclassified, residential, living_street) AND service NOT IN
  (driveway, parking_aisle) (verified 2026-09-12: 1086 kept
  county-wide, 541 in the Tallinn window lon 24.55-24.90 lat
  59.36-59.50). 20351 access=private objects drop out BY DESIGN in
  keep_privroad: 18290 non-road objects (parking lots, pitches,
  pools — a car park is not a road), 874 private
  driveways/parking aisles (single-parcel, never an agreement
  road), the rest footway/path/cycleway/crossing fragments.
  Untagged relation members carry no access/highway, so they drop
  out in keep_privroad — no twin purge needed beyond the cell
  dedupe. Gates (6547 barrier=gate) are DOCUMENTED but not
  consumed: a gate marks a compound entrance, not an agreement
  (documented in the TS verdict, not hidden).

Computation: graph-free Euclidean field on the 75 m county grid
(57.29/110.57 scales) — exact-grid Dijkstra nearest-source
distance. NO metro master (documented): a smooth distance-decay
field at 9.375 m cells would be fake precision — the window route
serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      w/access=private \
      -o /tmp/hf-g17r-priv.pbf --overwrite
  osmium export /tmp/hf-g17r-priv.pbf -o /tmp/hf-g17r-priv.geojson
  python3 scripts/build/batch_g17_rest.py --layer all \
      --priv /tmp/hf-g17r-priv.geojson \
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: privroad-walk-raster.json (Dijkstra quiet master) +
derived-privroad.json (fallback points for the Euclidean route +
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
# NOTE: apps/web/lib/layers_group17rest.ts G17R_CAL mirrors these numbers
# exactly — test_batch_g17_rest.py parses that file and fails on drift.
G17R_CAL = {
    "privroad": {"half_m": 200.0, "sigma": 0.3},
}

LAYER_IDS = ("privroad",)

#: highway values that are shared maintained-road candidates.
KEEP_HIGHWAY = ("service", "track", "unclassified", "residential",
                "living_street")

#: service values that are single-parcel, never agreement roads.
DROP_SERVICE = ("driveway", "parking_aisle")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
    "Ulemiste": (24.7956, 59.4229), "Kohtuotsa": (24.7399, 59.4357),
    "Tiskrevala": (24.57679, 59.44256),
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

def _first(value):
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def keep_privroad(props):
    """True when a private-access extract feature is a shared road.

    access=private AND highway in (service, track, unclassified,
    residential, living_street) AND service not driveway/
    parking_aisle. Parking lots, pitches and pools are OUT by design
    (not roads); private driveways/parking aisles are OUT by design
    (single-parcel, never an agreement road); footway/path/cycleway
    fragments are OUT (not maintained roads). Untagged relation
    members drop out here.
    """
    props = props or {}
    if _first(props.get("access")) != "private":
        return False
    if _first(props.get("highway")) not in KEEP_HIGHWAY:
        return False
    return _first(props.get("service")) not in DROP_SERVICE


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


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    return [x for x in feats if isinstance(x, dict)]


def read_priv_points(priv_path):
    """Shared-private-road source points from an access=private extract.

    Points feed directly; open lines are densified; closed rings
    (courtyard loops, roundabouts) are boundary-sampled. There is NO
    polygon fill: a road is linear — filling blocks would mark
    parcels as "on the road". Returns ([(lon, lat)], stats).
    """
    pts = []
    stats = {"roads": 0, "dropped": 0}
    for feat in _iter_features(priv_path):
        if not keep_privroad(feat.get("properties") or {}):
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
            stats["roads"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))
            else:
                pts.extend(_densify_line(co))
            stats["roads"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            # Closed-way duals from osmium export: boundary only,
            # never filled (see docstring).
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
            stats["roads"] += 1
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
# Fields: exact grid Dijkstra (quiet).
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
# Layer scores (high = calm; 0 = known-exposed, never 255 — the whole
# county field is stamped: open public-street land is genuinely calm).
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
    cal = G17R_CAL[layer]
    return cal.get("half_m", cal.get("half")), cal["sigma"]


def encode_wire(grid, values, layer="privroad"):
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


def build_layer(grid, layer, priv_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer == "privroad":
        if not priv_path:
            raise SystemExit("privroad needs --priv access=private extract")
        raw, stats = read_priv_points(priv_path)
        print("privroad=%s raw_pts=%d" % (stats, len(raw)), flush=True)
        pts = dedupe_cells(raw)
        print("privroad: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        dist = dijkstra_km(grid, cells_of_points(grid, pts))
        vals = score_distance(dist, G17R_CAL[layer]["half_m"])
    else:
        raise SystemExit("unknown layer %s" % layer)
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
    ap.add_argument("--priv", default=None,
                    help="access=private geojson extract (privroad)")
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
        vals, pts = build_layer(grid, layer, args.priv)
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
