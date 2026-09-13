"""Group 5 plans-F county master (issue #166): p485 upcycle.

Stdlib only. Offline, snapshot-only (NO network): derelict-stock
vectors come from the LOCAL Harjumaa PBF via the documented osmium
pre-step, never from a live service. Pure logic + snapshot readers
live at module top so unit tests stay hermetic; full-county builds
run only via the documented rebuild commands.

SCOPE (one layer, honest): this builder serves ONLY p485 (zoning
upcycling potential) as a mapped derelict-building proximity
hinnang. The sibling param is a documented no-map (see
apps/web/lib/layers_group05f.ts): p389 dark sky community
designation (an IDA-register fact with zero snapshot signal)
ships as a scorer dim only
(services/scoring/dims_group05f.py), OTA PR #131 precedent.

HONESTY (load-bearing): the PLANK register and the Tallinna
Planeeringute Register are NOT in the 2026-09-12 snapshot, so the
master is NOT a rezoning readout. upcycle scores the COUNT of
MAPPED abandoned/disused buildings nearby (area-kind, buildout
precedent — never a KOV decision that any parcel WILL be
rezoned). Titles, legends and sources say "hinnang" (pinned by
layers_group05f.test.ts).

Model (locked 2026-09-12):
* upcycle (p485): Euclidean Gaussian count kernel over kept
  derelict-stock dots (sigma 0.3, cutoff 4 sigma, saturating score
  100*S/(S+2), unstamped cells stay 255 unknown — same shape as
  buildout, batch_g05b_plans.py). half=2 (not 1): with 138
  Tallinn-window sites, clustered, TWO nearby derelict buildings
  read 50 — a single fenced ruin does not paint the block green
  alone. Green sits NEAR the stock (reuse potential likely).

Source (predicate verified on the snapshot extract):
* derelict: abandoned=yes or disused=yes WITH a building key, or
  abandoned:building with a building-ish value (verified
  2026-09-12: 202 kept county-wide, 114 after the 20 m dedupe,
  77 in the Tallinn window; raw window extract 69 outlines +
  69 building lines, zero points: way-mapped stock).
  Bunkers (building=bunker, 72+12: forest military, not rezoning
  stock), bare disused=yes without a building key (stale flags —
  incl. the ACTIVE Reisisadama A-terminal), abandoned=tunnel/
  highway fragments, abandoned:landuse=quarry/landfill (quarries
  already score as nuisance in p408 lowspec) and mistagged
  abandoned:building=roof/level_crossing are OUT by design.
  Zero overlap with landuse=industrial/brownfield (verified), so
  industprox (G07) and brownsoil (G07B) are never re-skinned.

Computation: upcycle is a graph-free Gaussian count kernel on the
75 m county grid (57.29/110.57 scales). ONE point per kept feature
(outline/line centroid — a distance field would need boundaries,
but a count kernel must not multi-count one building; residual
twin risk per PR #118 is handled by the 20 m dedupe). NO metro
master (documented): a sparse count kernel at 9.375 m cells would
be fake precision — the window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/abandoned nwr/disused nwr/abandoned:building \\
      nwr/disused:building nwr/abandoned:landuse \\
      -o /tmp/hf-g05f-aband.pbf --overwrite
  osmium export /tmp/hf-g05f-aband.pbf -o /tmp/hf-g05f-aband.geojson
  python3 scripts/build/batch_g05f_plans.py --layer all \\
      --aband /tmp/hf-g05f-aband.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: upcycle-walk-raster.json (count-kernel area master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-upcycle.json
(fallback points for the Euclidean route + overlay). Restart the web
server afterwards — the server caches masters per process.
"""

import argparse
import array
import base64
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
# NOTE: apps/web/lib/layers_group05f.ts G05F_CAL mirrors these numbers
# exactly — test_batch_g05f.py parses that file and fails on drift.
G05F_CAL = {
    "upcycle": {"half": 2.0, "sigma": 0.3},
}

LAYER_IDS = ("upcycle",)

#: abandoned:building values that count as reuse stock (bunkers, roof
#: fragments and level_crossing mistags are OUT by design).
KEEP_AB_BUILDING = (
    "yes", "garage", "apartments", "school", "house", "detached",
    "industrial", "warehouse", "church", "hospital", "hangar",
    "retail", "commercial", "office", "civic", "terrace",
    "semidetached_house", "hut", "shed", "stable", "barn",
    "greenhouse", "dormitory", "kindergarten", "hotel", "shop",
)

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


def kernel(d_km, sigma):
    """Gaussian kernel weight (moorage precedent: exp(-d^2/2σ^2))."""
    return math.exp(-(d_km * d_km) / (2.0 * sigma * sigma))


def area_score(s, half):
    """Saturating count score 100*S/(S+half) (mirrors walk_raster.saturate)."""
    return 100.0 * s / (s + half)


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
# Source predicate + reader (offline geojson extract only).
# ---------------------------------------------------------------------------

def _first(value):
    # NOTE: key presence is tested with `in`, never truthiness — _first
    # stringifies None to "None", so `if _first(x)` would be truthy for
    # a missing key (the ferry-terminal trap: bare disused=yes with no
    # building key must stay OUT).
    if value is None:
        return ""
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def keep_upcycle(props):
    """True when a lifecycle-extract feature is reuse candidate stock.

    abandoned=yes or disused=yes WITH a building key, or
    abandoned:building with a building-ish value (KEEP_AB_BUILDING).
    building=bunker is OUT by design (forest military bunkers are
    not rezoning stock); bare lifecycle flags without a building key
    are OUT (stale flags — incl. the ACTIVE Reisisadama A-terminal,
    which carries disused=yes); abandoned=tunnel/highway fragments,
    abandoned:landuse=quarry/landfill and roof/level_crossing
    mistags are OUT (infrastructure, env-health, or not buildings).
    Untagged relation members carry no lifecycle keys, so they drop
    out here.
    """
    props = props or {}
    if "building" in props and _first(props.get("building")) == "bunker":
        return False
    if _first(props.get("abandoned")) == "yes" and "building" in props:
        return True
    if _first(props.get("disused")) == "yes" and "building" in props:
        return True
    return _first(props.get("abandoned:building")) in KEEP_AB_BUILDING


def _centroid_of_coords(coords):
    n = len(coords)
    return (sum(p[0] for p in coords) / n, sum(p[1] for p in coords) / n)


def feature_point(geom):
    """ONE point per kept feature (count kernels must not multi-count).

    Points feed directly; lines feed their vertex-average centroid;
    polygons feed the outer-ring average (first polygon for multis —
    derelict stock maps as single footprints in practice). Returns
    (lon, lat) or None when there is nothing to score.
    """
    geom = geom or {}
    coords = geom.get("coordinates")
    if not coords:
        return None
    gtype = geom.get("type")
    if gtype == "Point":
        return (coords[0], coords[1])
    if gtype == "LineString":
        return _centroid_of_coords(coords)
    if gtype == "Polygon":
        ring = coords[0] if coords else None
        return _centroid_of_coords(ring) if ring else None
    if gtype == "MultiPolygon":
        ring = coords[0][0] if coords and coords[0] else None
        return _centroid_of_coords(ring) if ring else None
    return None


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    return [x for x in feats if isinstance(x, dict)]


def read_upcycle_points(aband_path):
    """Derelict-stock dots from a lifecycle-key geojson extract."""
    pts = []
    stats = {"stock": 0, "dropped": 0}
    for feat in _iter_features(aband_path):
        if not keep_upcycle(feat.get("properties") or {}):
            stats["dropped"] += 1
            continue
        pt = feature_point(feat.get("geometry") or {})
        if pt is None:
            stats["dropped"] += 1
            continue
        pts.append(pt)
        stats["stock"] += 1
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
# Field: Gaussian count kernel (area).
# ---------------------------------------------------------------------------

def count_kernel_field(grid, points, sigma):
    """Gaussian count accumulation: cell -> S (moorage precedent).

    Bounded O(points * range^2) sweep: each stock dot stamps
    kernel(d, sigma) into cells within 4 sigma. Unstamped cells stay
    absent (the scorer renders them 255 unknown, never a faked
    zero).
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
# Layer scores (high = reuse potential; desert stays 255 unknown).
# ---------------------------------------------------------------------------

def score_area_cells(grid, acc, half):
    """Saturating stock score 100*S/(S+half); desert stays 255."""
    out = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k, s in acc.items():
        out[k] = max(0, min(100, int(round(area_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G05F_CAL[layer]
    return cal.get("half_m", cal.get("half")), cal["sigma"]


def encode_wire(grid, values, layer="upcycle"):
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
    if len(pts) > OVERLAY_CAP:  # stride-thin huge samples, keep spread
        stride = len(pts) / OVERLAY_CAP
        pts = [pts[int(i * stride)] for i in range(OVERLAY_CAP)]
    doc = [{"lon": round(lon, 6), "lat": round(lat, 6)}
           for lon, lat in pts]
    with open(os.path.join(outdir, "derived-%s.json" % layer), "w",
              encoding="utf-8") as f:
        json.dump(doc, f)
    print("wrote derived-%s.json (%d pts)" % (layer, len(doc)), flush=True)
    return doc


def build_layer(grid, layer, aband_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer != "upcycle":
        raise SystemExit("unknown G05F layer: %s" % layer)
    if not aband_path:
        raise SystemExit("upcycle needs --aband lifecycle extract")
    raw, stats = read_upcycle_points(aband_path)
    print("upcycle=%s raw_pts=%d" % (stats, len(raw)), flush=True)
    pts = dedupe_cells(raw)
    print("upcycle: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
    acc = count_kernel_field(grid, pts, G05F_CAL[layer]["sigma"])
    vals = score_area_cells(grid, acc, G05F_CAL[layer]["half"])
    print("%s field ready (%.1fs)" % (layer, time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = reuse potential):", flush=True)
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
    ap.add_argument("--aband", default=None,
                    help="lifecycle-key geojson extract (upcycle)")
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
        vals, pts = build_layer(grid, layer, args.aband)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d zeros(known-bare)=%d" %
              (layer, len(vals), sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
