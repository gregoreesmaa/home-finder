"""Group 5 plans-E county master (issue #165): p381 equestrian.

Stdlib only. Offline, snapshot-only (NO network): riding-facility
vectors come from the LOCAL Harjumaa PBF via the documented osmium
pre-step, never from a live service. Pure logic + snapshot readers
live at module top so unit tests stay hermetic; full-county builds
run only via the documented rebuild commands.

SCOPE (one layer, honest): this builder serves ONLY p381
(equestrian community access) as a mapped-facility count hinnang.
The sibling params are documented no-map (see
apps/web/lib/layers_group05e.ts): p365 multi-family conversion
zoning (a per-parcel legal fact with no area signal), p382 fly-in
residential airparks (small-airfield proximity already scored twice:
flightcorr p445 + droneclear p220), p384 55+ age-restricted
enforcement (a community-rules fact with zero OSM signal) and p387
agrihoods (growing-soil halves already scored twice: gardens p106 +
agrifield p409) ship as scorer dims only
(services/scoring/dims_group05e.py), OTA PR #131 precedent.

HONESTY (load-bearing): the PLANK register, Tallinna Planeeringute
Register, any conversion-zoning table and any riding-community
membership list are NOT in the 2026-09-12 snapshot, so the master is
NOT a planned-community map. equestrian scores the COUNT of mapped
riding centres (leisure=horse_riding), equestrian arenas
(sport=equestrian, mostly leisure=pitch arena polygons), stable
buildings (building=stable) and bridleways (highway=bridleway)
nearby — area-kind, viewshed/moorage/gardens precedent, never a KOV
zoning decision. Titles, legends and sources say "hinnang" (pinned
by layers_group05e.test.ts).

Model (locked 2026-09-12):
* equestrian (p381): Euclidean Gaussian count kernel over kept
  riding-facility dots (sigma 0.3, cutoff 4 sigma, saturating score
  100*S/(S+1), unstamped cells stay 255 unknown — same shape as
  viewshed, batch_g05c_plans.py). half=1 (not 2): with ~46 county
  sites (15 Tallinn-window: Veskimetsa ratsakeskus, Vääna tallid,
  Lagedi, Jüri, Suuresti + arena pitches) ONE mapped campus reads 50
  on its own cell (mid-amber) instead of vanishing; facility deserts
  read honestly unknown. Green sits NEAR the amenity (access
  likely).

Sources (predicate verified on the snapshot extract):
* riding: leisure=horse_riding or sport=equestrian or
  highway=bridleway or building=stable (verified 2026-09-12: 86 raw
  features, ~46 unique sites — osmium export doubles closed ways as
  LineString + MultiPolygon twins, collapsed by the 20 m cell
  dedupe; 15 in the Tallinn window). leisure=pitch WITHOUT
  sport=equestrian is OUT by design (a football pitch is not an
  arena); untagged relation members drop out in keep_equi. Near
  twins (arena + stable ~30 m apart on one campus) stay separate
  dots — documented residual twin risk per PR #118, bounded by the
  saturating half (extra twins past 3 barely move the score).

Computation: graph-free Gaussian count kernel on the 75 m county
grid (57.29/110.57 scales). NO metro master (documented): a sparse
count kernel at 9.375 m cells would be fake precision — the window
route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/leisure=horse_riding nwr/sport=equestrian \
      nwr/highway=bridleway nwr/building=stable \
      -o /tmp/hf-g05e-equi.pbf --overwrite
  osmium export /tmp/hf-g05e-equi.pbf -o /tmp/hf-g05e-equi.geojson
  python3 scripts/build/batch_g05e_plans.py --layer all \
      --equi /tmp/hf-g05e-equi.geojson \
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: equestrian-walk-raster.json (count-kernel area master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-equestrian.json
(fallback points for the Euclidean route + overlay). Restart the web
server afterwards — the server caches masters per process.
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
# Constants (mirrors walk_raster / batch_g05c_plans scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # line vertex spacing for source rasterisation
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group05e.ts G05E_CAL mirrors these numbers
# exactly — test_batch_g05e.py parses that file and fails on drift.
G05E_CAL = {
    "equestrian": {"half": 1.0, "sigma": 0.3},
}

LAYER_IDS = ("equestrian",)

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
    "Veskimetsa": (24.66428, 59.42642), "Kohtuotsa": (24.7399, 59.4357),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def kernel(d_km, sigma):
    """Gaussian kernel weight (viewshed/moorage precedent: exp(-d^2/2σ^2))."""
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
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def keep_equi(props):
    """True when an extract feature is a riding facility.

    leisure=horse_riding (riding centres) or sport=equestrian
    (arenas — mostly leisure=pitch polygons where the sport tag
    carries the meaning) or highway=bridleway (deeded trails, named
    in the param) or building=stable (communal stables, named in the
    param). leisure=pitch WITHOUT sport=equestrian is OUT by design
    (a football pitch is not an arena). Untagged relation members
    drop out here.
    """
    props = props or {}
    if _first(props.get("leisure")) == "horse_riding":
        return True
    if _first(props.get("sport")) == "equestrian":
        return True
    if _first(props.get("highway")) == "bridleway":
        return True
    return _first(props.get("building")) == "stable"


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


def read_equi_points(equi_path):
    """Riding-facility dots from a combined geojson extract.

    Points feed directly; bridleway lines are densified; arena /
    campus polygons feed stride-sampled outer rings (a count kernel
    only needs the shape — the kernel peak sits on the ring at
    75 m cells). Returns ([(lon, lat)], stats).
    """
    pts = []
    stats = {"sites": 0, "dropped": 0}
    for feat in _iter_features(equi_path):
        if not keep_equi(feat.get("properties") or {}):
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
            stats["sites"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))
            else:
                pts.extend(_densify_line(co))
            stats["sites"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
            stats["sites"] += 1
        else:
            stats["dropped"] += 1
    return pts, stats


def dedupe_cells(points, cell_m=DEDUPE_M):
    """Merge export twins falling in the same ~cell_m cell.

    osmium export doubles closed ways as LineString + MultiPolygon
    twins with identical coordinates — they collapse here. Near
    twins (arena + stable ~30 m apart on one campus) stay separate
    dots: documented residual twin risk per PR #118.
    """
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
    """Gaussian count accumulation: cell -> S (viewshed precedent).

    Bounded O(points * range^2) sweep: each facility stamps
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
# Layer scores (high = good access; unstamped desert stays 255 unknown).
# ---------------------------------------------------------------------------

def score_area_cells(grid, acc, half):
    """Saturating facility score 100*S/(S+half); desert stays 255."""
    out = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k, s in acc.items():
        out[k] = max(0, min(100, int(round(area_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G05E_CAL[layer]
    return cal.get("half_m", cal.get("half")), cal["sigma"]


def encode_wire(grid, values, layer="equestrian"):
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


def build_layer(grid, layer, equi_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer == "equestrian":
        if not equi_path:
            raise SystemExit("equestrian needs --equi riding-facility extract")
        raw, stats = read_equi_points(equi_path)
        print("equestrian=%s raw_pts=%d" % (stats, len(raw)), flush=True)
        pts = dedupe_cells(raw)
        print("equestrian: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        acc = count_kernel_field(grid, pts, G05E_CAL[layer]["sigma"])
        vals = score_area_cells(grid, acc, G05E_CAL[layer]["half"])
    else:
        raise SystemExit("unknown layer %s" % layer)
    print("%s field ready (%.1fs)" % (layer, time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = good access):", flush=True)
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
    ap.add_argument("--equi", default=None,
                    help="riding-facility geojson extract (equestrian)")
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
        vals, pts = build_layer(grid, layer, args.equi)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d desert255=%d" %
              (layer, len(vals), sum(1 for v in vals if v == 255)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
