"""Group 5 plans-D county master (issue #164): p230 strsat saturation field.

Stdlib only. Offline, snapshot-only (NO network): tourist-accommodation
vectors come from the LOCAL Harjumaa PBF via the documented osmium
pre-steps, never from a live service. Pure logic + snapshot readers live
at module top so unit tests stay hermetic; full-county builds run only
via the documented rebuild commands.

SCOPE (one layer, honest): this builder serves ONLY p230 (short-term
rental saturation) as a mapped-accommodation inverse-proximity hinnang.
The sibling params are documented no-map (see
apps/web/lib/layers_group05d.ts): p226 heritage tree ordinances (9
mapped significant trees county-wide cannot carry a restriction
gradient — false green), p244/p275 non-conforming use facts
(per-parcel legal status, zero OSM signal) and p280 eminent domain
history (needs expropriation records) ship as scorer dims only
(services/scoring/dims_group05d.py), OTA PR #131 precedent.

HONESTY (load-bearing): the PLANK WFS, the Tallinna Planeeringute
Register and any Airbnb/booking listing register are NOT in the
2026-09-12 snapshot, so this master is NOT measured STR supply. strsat
scores inverse nearness to MAPPED tourist beds (guest turnover drives
the saturation pressure the param names — the beds are the mapped
cause, never a listing count). Titles, legends and sources say
"hinnang"/"proksi" (pinned by layers_group05d.test.ts); unmapped
holiday flats do not count (said in the source line).

Model (locked 2026-09-12):
* strsat (p230): exact full-grid 8-connectivity Dijkstra distance to
  the nearest mapped bed (same machinery as batch_g08b_flood.py, local
  Grid copy for self-containment), score = 100*(1-2^(-d/half)),
  half=0.35 km == sigma*ln2 (the walk-km 50-score, woodfire
  convention). NO cutoff (far reads genuinely calm-green, NOT
  unknown-red — STR supply really is centre-concentrated, so
  Nomme/Oismae calm is honest; this differs from woodfire on purpose).
  Measured county-raster reads (--probe, 2026-09-12 full build):
  Balti 14, Pelgulinn 14, Viru 26, Kalamaja 26, Pirita 47, Kadriorg
  69, Oismae 81, Lasnamae 87, Nomme 94, rural 100. The centre reads
  saturated BY DESIGN — mapped beds blanket Vanalinn/Kesklinn (the
  Viru probe sits ~150 m from the nearest mapped bed, hence 26).

Sources (predicates verified on the snapshot extract):
* stay: tourism first ;-value in {apartment, guest_house, hostel,
  hotel, motel} (verified 2026-09-12: 334 kept = hotel 168 +
  guest_house 84 + hostel 55 + apartment 25 + motel 2; 209 in the
  Tallinn window; 203 Points + 74 closed footprint rings + 74
  MultiPolygons). Hotels are usually area-mapped, so closed rings and
  multipolygons feed stride-sampled (footprint rings are NOT twins —
  they carry their own tourism tags); untagged relation members drop
  out in keep_strstay. Food/drink tags are OUT by design (bars do not
  host overnight guests — saturation is guest turnover, not foot
  traffic).

Computation: graph-free Euclidean field on the 75 m county grid
(57.29/110.57 scales) — exact-grid Dijkstra nearest-source distance.
NO metro master (documented): a smooth inverse-distance saturation
field at 9.375 m cells would be fake precision — the window route
serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/tourism=apartment nwr/tourism=guest_house nwr/tourism=hostel \\
      nwr/tourism=hotel nwr/tourism=motel \\
      -o /tmp/hf-g05d-stay.pbf --overwrite
  osmium export -u type_id /tmp/hf-g05d-stay.pbf -o /tmp/hf-g05d-stay.geojson
  python3 scripts/build/batch_g05d_plans.py --layer strsat \\
      --poi /tmp/hf-g05d-stay.geojson \\
      --out ~/hf-data/2026-09-12/osm/strsat-walk-raster.json \\
      --write-points --probe
Outputs: strsat-walk-raster.json (Dijkstra avoid master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-strsat.json
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
# Constants (mirrors walk_raster / batch_g08b_flood scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # line vertex spacing for source rasterisation
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group05d.ts G05D_CAL mirrors these numbers
# exactly — test_batch_g05d.py parses that file and fails on drift.
# half is the walk-km 50-score (== sigma*ln2, woodfire convention).
G05D_CAL = {
    "strsat": {"half": 0.35, "sigma": 0.5},
}

LAYER_IDS = ("strsat",)

#: Tourist-accommodation values carrying overnight-guest signal.
STAY_VALUES = frozenset(
    {"apartment", "guest_house", "hostel", "hotel", "motel"}
)

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Kalamaja": (24.738, 59.448),
    "Pelgulinn": (24.71, 59.438), "Nomme": (24.66, 59.36),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def avoid_from_half(d_km, half):
    """Distance (km) -> saturation 0..100: 0 on the beds, 50 at half."""
    return 100.0 * (1.0 - pow(2.0, -d_km / half)) if d_km < float("inf") else 100.0


# ---------------------------------------------------------------------------
# Grid (local copy for self-containment, mirrors batch_g08b_flood).
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
# Source predicate + reader (offline geojson extract only).
# ---------------------------------------------------------------------------

def first_tourism(value):
    """First ;-separated tourism value, else empty string."""
    if not isinstance(value, str):
        return ""
    return value.split(";")[0].strip()


def keep_strstay(props):
    """True when a tourism-extract feature hosts overnight guests.

    tourism first ;-value in STAY_VALUES (holiday apartments, guest
    houses, hostels, hotels, motels). Food/drink tags are OUT by design
    (bars do not host overnight guests); untagged relation members drop
    out here.
    """
    return first_tourism((props or {}).get("tourism")) in STAY_VALUES


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


def read_stay_points(poi_path):
    """Tourist-bed source points from a tourism geojson extract.

    Points feed directly; MultiPolygon outer rings stride-sample (a
    distance field only needs the boundary); CLOSED LineStrings are
    hotel footprint rings — NOT relation twins (footprints carry their
    own tourism tags; untagged members already dropped by
    keep_strstay) — so they feed stride-sampled too. Genuinely OPEN
    tagged lines (rare) are densified. Returns ([(lon, lat)], stats).
    """
    with open(poi_path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    pts = []
    stats = {"beds": 0, "dropped": 0}
    for feat in feats:
        if not isinstance(feat, dict):
            stats["dropped"] += 1
            continue
        if not keep_strstay(feat.get("properties") or {}):
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
            stats["beds"] += 1
        elif gtype == "MultiPolygon":
            for poly in coords:
                if poly:
                    pts.extend(_stride_ring(poly[0]))
            stats["beds"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))  # footprint ring, not a twin
            else:
                pts.extend(_densify_line(co))
            stats["beds"] += 1
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
# Field: exact grid Dijkstra.
# ---------------------------------------------------------------------------

def dijkstra_km(grid, source_cells):
    """Exact 8-connectivity distance (km) to the nearest source cell.

    No cutoff (saturation is centre-concentrated: far reads genuinely
    calm-green, never unknown-red). Orthogonal step = cell km,
    diagonal = *sqrt(2). Returns array('d') with +inf where unreachable
    (never in practice).
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
# Layer score (low = saturated; far = calm, never 255).
# ---------------------------------------------------------------------------

def score_avoid(d_km, half):
    """Inverse nearest-source saturation 100*(1-2^(-d/half))."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        out[k] = max(0, min(100, int(round(avoid_from_half(d_km[k], half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G05D_CAL[layer]
    return cal["half"], cal["sigma"]


def encode_wire(grid, values, layer="strsat"):
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


def build_layer(grid, layer, poi_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer != "strsat":
        raise SystemExit("unknown G05D layer: %s" % layer)
    if not poi_path:
        raise SystemExit("strsat needs --poi tourism extract")
    raw, stats = read_stay_points(poi_path)
    print("strsat=%s raw_pts=%d" % (stats, len(raw)), flush=True)
    pts = dedupe_cells(raw)
    print("%s: deduped %d -> %d" % (layer, len(raw), len(pts)), flush=True)
    dist = dijkstra_km(grid, cells_of_points(grid, pts))
    vals = score_avoid(dist, G05D_CAL[layer]["half"])
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
                    help="tourism geojson extract (strsat)")
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
        vals, pts = build_layer(grid, layer, args.poi)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d zeros(known-saturated)=%d" %
              (layer, len(vals), sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
