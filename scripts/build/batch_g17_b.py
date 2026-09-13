"""Group 17 municipal-services-B county master (issue #178): p469 lawncare.

Stdlib only. Offline, snapshot-only (NO network): mown-lawn vectors come
from the LOCAL Harjumaa PBF via the documented osmium pre-steps, never
from a live service. Pure logic + snapshot readers live at module top so
unit tests stay hermetic; full-county builds run only via the documented
rebuild commands.

SCOPE (one layer, honest): this builder serves ONLY p469 (weed and lawn
ordinances) as a mapped-lawn count hinnang. The sibling params are
documented no-map (see apps/web/lib/layers_group17b.ts): p463 sidewalk
maintenance laws (a per-parcel legal duty; footway density already
scores as pedinfra), p464 street sweeping ticketing (a
schedule-plus-enforcement fact with zero snapshot keys) and p465 snow
shoveling mandates (a per-parcel legal duty; winter-service proximity
already scores via gritbin p311) ship as scorer dims only
(services/scoring/dims_group17b.py), OTA PR #131 precedent.

HONESTY (load-bearing): the Tallinna Linnavalitsus / KOV upkeep
registers — sidewalk-duty records, sweeping calendars and ticketing
logs, shoveling enforcement, lawn-height inspections — are NOT in the
2026-09-12 snapshot, so the master is NOT registry data. lawncare
scores the COUNT of mapped mown-grass areas nearby (area-kind,
viewshed/moorage/G17A precedent — never a mowing-inspection ruling).
Titles, legends and sources say "hinnang" (pinned by
layers_group17b.test.ts).

Deliberately NOT a footway field: mapped footway density already scores
as pedinfra (layers.ts pedinfra TAGS cover highway
footway|path|pedestrian|steps) — a second footway gradient would
duplicate it. Deliberately NOT a winter field: winter_service tags are
zero in the snapshot and winter-service proximity already scores via
gritbin p311 (G17A). sweeping/street_cleaning/cleaning/snow_removal
keys are all zero in the snapshot — nothing to calibrate for p464.

Models (locked 2026-09-12): lawncare is a Euclidean Gaussian count
kernel over kept lawn centroids (sigma 0.3, cutoff 4 sigma,
saturating score 100*S/(S+20), unstamped cells stay 255 unknown —
viewshed/moorage/G17A shape with a DENSITY half). half=20 (not 1):
with 18179 deduped centroids a half of 1 saturates all of Tallinn to
99 (verified 2026-09-12 probe: Balti/Viru/Kadriorg all 99) and the
field answers nothing. half=20 spreads the real variation (probe
S -> score: Mustamäe 238 -> 92, Õismäe 175 -> 90, Lasnamäe 122 -> 86,
Viru 102 -> 84, Kadriorg 85 -> 81, Vanalinn 68 -> 77, Pirita 20 -> 50,
Nõmme 0.03 -> 0, rural 0 -> 255) while forgiving unmapped private
gardens. Nõmme's near-zero (n800=0) is a documented mapping hole —
private gardens are unmapped there — not upkeep truth. Green sits
NEAR the lawns (upkeep-visible streetscape).

Sources (predicates verified on the snapshot extract):
* lawn: landuse=grass exactly (first value). Verified 2026-09-12:
  40499 kept county-wide (33524 in the Tallinn window:
  Mustamäe/Õismäe/Lasnamäe panel lawns, Kadriorg verges). 890
  untagged relation members drop out. landuse=meadow (1799 ways + 79
  relations) is OUT by design: a meadow is unmown BY DEFINITION, not
  a mowing-duty lawn. leisure=garden stays the parks layer's.
  Overlap with livability's nearest-"park" scorer kind (nature amenity,
  p270 yard leg, cooling) is DOCUMENTED (ehitus/buildout G05A+G05B
  precedent): those ask how far green relief is, lawncare asks how
  much mown grass surrounds the listing.

Computation: graph-free Gaussian count kernel on the 75 m county grid
(57.29/110.57 scales). NO metro master (documented): a dense count
kernel at 9.375 m cells would be fake precision — the window route
serves county everywhere.

Feeding (centroids, not rings): 40499 lawns are mostly small polygons;
stride-sampled rings would explode into ~1M samples for a kernel that
only needs one upkeep unit per lawn. Each kept feature feeds its bbox
centre (the documented polygon convention, dims_group18c.py) — points
feed directly, open lines feed densified. Node+area twins dedupe at
20 m like sibling batches.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/landuse=grass \\
      -o /tmp/hf-g17b-lawn.pbf --overwrite
  osmium export /tmp/hf-g17b-lawn.pbf -o /tmp/hf-g17b-lawn.geojson
  python3 scripts/build/batch_g17_b.py --layer lawncare \\
      --lawn /tmp/hf-g17b-lawn.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: lawncare-walk-raster.json (count-kernel area master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-lawncare.json
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
# NOTE: apps/web/lib/layers_group17b.ts G17B_CAL mirrors these numbers
# exactly — test_batch_g17_b.py parses that file and fails on drift.
G17B_CAL = {
    "lawncare": {"half": 20.0, "sigma": 0.3},
}

LAYER_IDS = ("lawncare",)

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
    "Mustamae": (24.66856, 59.39576), "Vanalinn": (24.7454, 59.4374),
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
# Source predicates + readers (offline geojson extracts only).
# ---------------------------------------------------------------------------

def _first(value):
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def keep_lawn(props):
    """True when a grass-extract feature is a mowing-duty lawn.

    landuse=grass exactly (first value): courtyard lawns, roadside
    verges, panel-district greens. landuse=meadow is OUT by design (a
    meadow is unmown by definition, not a mowing-duty lawn — and it
    stays livability's "park" kind). Footway/highway features are OUT
    (pedinfra's, never re-scored here). Untagged relation members
    carry no landuse, so they drop out here.
    """
    props = props or {}
    if _first(props.get("landuse")) != "grass":
        return False
    return True


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    return [x for x in feats if isinstance(x, dict)]


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
    """Bbox centre of a polygon/line coordinate array (one upkeep unit).

    The documented polygon convention (dims_group18c.py): a count
    kernel needs one point per lawn, not stride-sampled rings — rings
    would explode 40499 small polygons into ~1M samples.
    """
    lons = []
    lats = []
    for lon, lat in _flat_coords(coords):
        lons.append(lon)
        lats.append(lat)
    if not lons:
        return None
    return ((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)


def read_lawn_points(lawn_path):
    """Mown-lawn dots from a landuse=grass geojson extract.

    Points feed directly; open lines feed densified; polygons feed
    ONE bbox-centre point each (one lawn = one upkeep unit — rings
    would explode 40499 small polygons into ~1M samples). Returns
    ([(lon, lat)], stats).
    """
    pts = []
    stats = {"lawns": 0, "dropped": 0}
    for feat in _iter_features(lawn_path):
        if not keep_lawn(feat.get("properties") or {}):
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
            stats["lawns"] += 1
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
            stats["lawns"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords] if gtype == "Polygon" \
                else [p for p in coords if p]
            for ring in rings:
                c = _bbox_center(ring)
                if c is not None:
                    pts.append(c)
            stats["lawns"] += 1
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
# Fields: Gaussian count kernel (area) — viewshed/moorage/G17A precedent.
# ---------------------------------------------------------------------------

def count_kernel_field(grid, points, sigma):
    """Gaussian count accumulation: cell -> S (moorage precedent).

    Bounded O(points * range^2) sweep: each lawn centroid stamps
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
# Layer scores (high = upkeep-visible; unstamped desert stays honestly unknown).
# ---------------------------------------------------------------------------

def score_area_cells(grid, acc, half):
    """Saturating upkeep score 100*S/(S+half); desert stays 255."""
    out = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k, s in acc.items():
        out[k] = max(0, min(100, int(round(area_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G17B_CAL[layer]
    return cal["half"], cal["sigma"]


def encode_wire(grid, values, layer="lawncare"):
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


def build_layer(grid, layer, lawn_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer != "lawncare":
        raise SystemExit("unknown layer %s" % layer)
    if not lawn_path:
        raise SystemExit("lawncare needs --lawn grass extract")
    raw, stats = read_lawn_points(lawn_path)
    print("lawncare=%s raw_pts=%d" % (stats, len(raw)), flush=True)
    pts = dedupe_cells(raw)
    print("lawncare: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
    acc = count_kernel_field(grid, pts, G17B_CAL[layer]["sigma"])
    vals = score_area_cells(grid, acc, G17B_CAL[layer]["half"])
    print("lawncare field ready (%.1fs)" % (time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = upkeep-visible):", flush=True)
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
    ap.add_argument("--lawn", default=None,
                    help="grass geojson extract (lawncare)")
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
        vals, pts = build_layer(grid, layer, args.lawn)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d upkeep-visible(>=50)=%d" %
              (layer, len(vals), sum(1 for v in vals if v != 255 and v >= 50)),
              flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
