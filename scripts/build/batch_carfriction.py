"""Car-friction county master (issue #829): OSM motor-vehicle restrictions.

Stdlib only. Offline, snapshot-only (NO network): restriction vectors
come from the LOCAL Harjumaa PBF via the documented osmium
pre-steps, never from a live service. Pure logic + snapshot readers
live at module top so unit tests stay hermetic; full-county builds
run only via the documented rebuild commands.

SCOPE (one layer, honest): this builder serves ONLY the
motor-vehicle access-restriction hinnang. The congestion side is
covered by the delay-* corridor layers (layers_p4_delay.ts) and is
NOT duplicated here. The Tallinna paid-parking zone regime (fees,
hours, resident permits) is NOT in the 2026-09-12 snapshot — no
verifiable mappable source exists (Tallinn open data carries no
parking-zone polygons; the snapshot carries zero zone:parking /
parking:fee / fee tags, verified 2026-09-26) — so paid zones ship
as a documented gap in the layer source label, never inferred
(OTA PR #131 precedent: unmappable legs stay NULLs, never
gradients).

Models (locked 2026-09-26): carfriction is a Euclidean Gaussian
count kernel over kept restriction sample points (sigma 0.3 ==
street-scale friction, cutoff 4 sigma, INVERTED saturating score
100*half/(S+half), unstamped cells stay 255 unknown —
G18B-daylight sparse precedent). half=60: built-master probe on
the 75 m grid reads Vanalinn 29 (red old-town core), Mustamae
73, Oismae 82, Pirita 68, Lasnamae 95, Viimsi 88, Nomme 100
(measured open). sigma 0.3 (not 0.5/0.8): wider kernels smear
the old-town core into the suburbs (verified 2026-09-26 probe:
sigma 0.8 reads Mustamae/Oismae ~2x Vanalinn — the field answers
nothing about where driving is actually hard).

Sources (predicates verified on the snapshot extract):
* restrictions: motor_vehicle / vehicle / motorcar values in
  {no, private, permit, destination, customers} (first value).
  Verified 2026-09-26: 2382 access-tagged objects Harjumaa-wide,
  1545 kept restrictive (motor_vehicle no 955 + private 447 +
  permit 46 + destination 21 + customers 12 + vehicle/motorcar
  slices); permissive values (yes/designated/permissive) and
  key-only filter artefacts are dropped by keep_restriction.

Computation: graph-free Gaussian count kernel on the 75 m county
grid (57.29/110.57 scales). NO metro master (documented): a dense
count kernel at 9.375 m cells would be fake precision. The window
route serves county everywhere for this layer (metro slot stays
empty, like G02B/G03/G03D/G08B/G05C/G17A/G17B).

Feeding (sample points, not rings): restricted street lines feed
densified at 25 m (a 200 m no-entry street is more friction than
a 10 m gate); closed-area polygons feed ONE bbox-centre point
each (one closure = one friction unit — rings would explode
areas into ~1M samples); barrier nodes feed directly.
Node+area twins dedupe at 20 m like sibling batches.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/motor_vehicle nwr/vehicle nwr/motorcar \\
      -o /tmp/hf-carfriction.pbf --overwrite
  osmium export /tmp/hf-carfriction.pbf -o /tmp/hf-carfriction.geojson
  python3 scripts/build/batch_carfriction.py --layer carfriction \\
      --restrictions /tmp/hf-carfriction.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: carfriction-walk-raster.json (inverted-count sparse
master, WalkRasterDoc shape so cleanRaster accepts it) +
derived-carfriction.json (fallback points for the Euclidean
route + overlay). Restart the web server afterwards — the server
caches masters per process.
"""

import argparse
import base64
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_p4_parking.py scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 25.0  # line vertex spacing for restriction rasterisation
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-26 (see module docstring).
# NOTE: apps/web/lib/layers_p4_carfriction.ts CARFRICTION_CAL mirrors
# these numbers exactly — test_batch_carfriction.py parses that file
# and fails on drift.
CARFRICTION_CAL = {
    "carfriction": {"half": 60.0, "sigma": 0.3},
}

LAYER_IDS = ("carfriction",)

# Motor-vehicle access values that make driving genuinely hard.
RESTRICTIVE_VALUES = frozenset(
    {"no", "private", "permit", "destination", "customers"}
)
ACCESS_KEYS = ("motor_vehicle", "vehicle", "motorcar")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Vanalinn": (24.7454, 59.4374), "Mustamae": (24.68, 59.405),
    "Lasnamae": (24.82, 59.44), "Pirita": (24.821, 59.468),
    "Viimsi": (24.83, 59.51), "Nomme": (24.68, 59.375),
    "rural": (24.50, 59.32), "Oismae": (24.65, 59.42),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def kernel(d_km, sigma):
    """Gaussian kernel weight (moorage precedent: exp(-d^2/2σ^2))."""
    return math.exp(-(d_km * d_km) / (2.0 * sigma * sigma))


def sparse_score(s, half):
    """Inverted count score 100*half/(S+half) (daylight precedent)."""
    return 100.0 * half / (s + half)


def keep_restriction(props):
    """True for genuinely car-restrictive motor-vehicle access tags.

    motor_vehicle / vehicle / motorcar in {no, private, permit,
    destination, customers}. Permissive values (yes, designated,
    permissive, delivery ...) and untagged filter artefacts are
    dropped — they say nothing about driving hardship.
    """
    if not isinstance(props, dict):
        return False
    for key in ACCESS_KEYS:
        if props.get(key) in RESTRICTIVE_VALUES:
            return True
    return False


# ---------------------------------------------------------------------------
# Grid (local copy for self-containment, mirrors batch_g17_b.py).
# ---------------------------------------------------------------------------

class Grid:
    """75 m county grid (mirrors walk_raster.Grid indexing)."""

    def __init__(self, bbox, step_m=STEP_M):
        self.bbox = bbox
        self.step = step_m
        minlon, minlat, maxlon, maxlat = bbox
        self.cols = int(round((maxlon - minlon) * LON_KM * 1000 / step_m))
        self.rows = int(round((maxlat - minlat) * LAT_KM * 1000 / step_m))

    def cell_of(self, lon, lat):
        minlon, minlat, maxlon, maxlat = self.bbox
        if not (minlon <= lon <= maxlon and minlat <= lat <= maxlat):
            return None
        ix = int((lon - minlon) * LON_KM * 1000 / self.step)
        iy = int((lat - minlat) * LAT_KM * 1000 / self.step)
        ix = min(ix, self.cols - 1)
        iy = min(iy, self.rows - 1)
        return iy * self.cols + ix

    def center_of(self, k):
        minlon, minlat, _, _ = self.bbox
        ix = k % self.cols
        iy = k // self.cols
        return (minlon + (ix + 0.5) * self.step / 1000 / LON_KM,
                minlat + (iy + 0.5) * self.step / 1000 / LAT_KM)


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    for feat in feats:
        if isinstance(feat, dict):
            yield feat


def _densify_line(co, step_m=DENSIFY_M):
    """Interpolated points along a restricted street (~25 m spacing).

    A 200 m no-entry street is more friction than a 10 m gate —
    endpoints alone would underweight long closures.
    """
    pts = []
    step_km = step_m / 1000.0
    for i in range(1, len(co)):
        if i == 0:
            continue
        plon, plat = co[i - 1]
        lon, lat = co[i]
        pts.append((plon, plat))
        d = hav_km(plon, plat, lon, lat)
        if d > step_km:
            n = int(d / step_km)
            for k in range(1, n):
                t = k / n
                pts.append((plon + (lon - plon) * t, plat + (lat - plat) * t))
    if co:
        pts.append(co[-1])
    return pts


def _flat_coords(coords):
    """Yield every (lon, lat) pair of a nested geojson coordinate array."""
    if isinstance(coords, (list, tuple)) and len(coords) >= 2 and \
            all(isinstance(c, (int, float)) for c in coords[:2]):
        yield (coords[0], coords[1])
        return
    if isinstance(coords, (list, tuple)):
        for c in coords:
            yield from _flat_coords(c)


def _bbox_center(coords):
    """Bbox centre of a polygon/line coordinate array (one friction unit).

    The documented polygon convention (dims_group18c.py): a count
    kernel needs one point per closure, not stride-sampled rings —
    rings would explode small areas into ~1M samples.
    """
    lons = []
    lats = []
    for lon, lat in _flat_coords(coords):
        lons.append(lon)
        lats.append(lat)
    if not lons:
        return None
    return ((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)


def read_restriction_points(restrictions_path):
    """Car-restriction sample dots from an access-tag geojson extract.

    Barrier nodes feed directly; restricted street lines feed
    densified at 25 m (a long no-entry street is more friction
    than a short gate); closure polygons feed ONE bbox-centre
    point each (one closure = one friction unit). Returns
    ([(lon, lat)], stats).
    """
    pts = []
    stats = {"closures": 0, "dropped": 0}
    for feat in _iter_features(restrictions_path):
        if not keep_restriction(feat.get("properties") or {}):
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
            stats["closures"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                c = _bbox_center(coords)
                if c is None:
                    stats["dropped"] += 1
                    continue
                pts.append(c)
            else:
                pts.extend(_densify_line(co))
            stats["closures"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords] if gtype == "Polygon" \
                else [p for p in coords if p]
            for ring in rings:
                c = _bbox_center(ring)
                if c is not None:
                    pts.append(c)
            stats["closures"] += 1
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
# Fields: Gaussian count kernel (sparse) — G18B-daylight precedent.
# ---------------------------------------------------------------------------

def count_kernel_field(grid, points, sigma):
    """Gaussian count accumulation: cell -> S (moorage precedent).

    Bounded O(points * range^2) sweep: each restriction sample
    stamps kernel(d, sigma) into cells within 4 sigma. Unstamped
    cells stay absent (the scorer renders them 255 unknown, never
    a faked zero).
    """
    cutoff_km = 4.0 * sigma
    acc = {}
    minlon, minlat, _, _ = grid.bbox
    for lon, lat in points:
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
                acc[k] = acc.get(k, 0.0) + kernel(d, sigma)
    return acc


# ---------------------------------------------------------------------------
# Layer scores (low = dense restrictions; open stays 100, never unknown).
# ---------------------------------------------------------------------------

def score_sparse_cells(grid, acc, half):
    """Inverted restriction score 100*half/(S+half) (daylight shape).

    S=0 over the loaded county set reads 100 (measured open,
    honestly known — NOT unknown like area-kind deserts); cells
    outside every kernel footprint stay 255.
    """
    out = bytearray(grid.cols * grid.rows)
    for k in range(grid.cols * grid.rows):
        s = acc.get(k)
        if s is None:
            out[k] = 255
        else:
            out[k] = max(0, min(100, int(round(sparse_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = CARFRICTION_CAL[layer]
    return cal["half"], cal["sigma"]


def encode_wire(grid, values, layer="carfriction"):
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
    if len(pts) > OVERLAY_CAP:  # stride-thin huge centroid samples, keep spread
        stride = len(pts) / OVERLAY_CAP
        pts = [pts[int(i * stride)] for i in range(OVERLAY_CAP)]
    doc = [{"lon": round(lon, 6), "lat": round(lat, 6)}
           for lon, lat in pts]
    with open(os.path.join(outdir, "derived-%s.json" % layer), "w",
              encoding="utf-8") as f:
        json.dump(doc, f)
    print("wrote derived-%s.json (%d pts)" % (layer, len(doc)), flush=True)
    return doc


def build_layer(grid, layer, restrictions_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer != "carfriction":
        raise SystemExit("unknown layer %s" % layer)
    if not restrictions_path:
        raise SystemExit("carfriction needs --restrictions access-tag extract")
    raw, stats = read_restriction_points(restrictions_path)
    print("carfriction=%s raw_pts=%d" % (stats, len(raw)), flush=True)
    pts = dedupe_cells(raw)
    print("carfriction: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
    acc = count_kernel_field(grid, pts, CARFRICTION_CAL[layer]["sigma"])
    vals = score_sparse_cells(grid, acc, CARFRICTION_CAL[layer]["half"])
    print("carfriction field ready (%.1fs)" % (time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (low = dense restrictions, 255 = outside footprint):",
          flush=True)
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
    ap.add_argument("--restrictions", default=None,
                    help="motor-vehicle access-tag geojson extract")
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
        vals, pts = build_layer(grid, layer, args.restrictions)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d open(>=50)=%d red(<50)=%d" %
              (layer, len(vals),
               sum(1 for v in vals if v != 255 and v >= 50),
               sum(1 for v in vals if v != 255 and v < 50)),
              flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
