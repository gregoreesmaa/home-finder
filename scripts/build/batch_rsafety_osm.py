"""OSM road-safety county master (issue #481): P4-012 blackspot proxy.

Stdlib only. Offline, snapshot-only (NO network): crossing/calming
vectors come from the LOCAL Harjumaa PBF via the documented osmium
pre-steps, never from a live service. Pure logic + snapshot readers live
at module top so unit tests stay hermetic; full-county builds run only
via the documented rebuild commands.

SCOPE (one layer, honest): this builder serves ONLY "roadsafety"
(mapped crossing + traffic-calming furniture density as an
accident-blackspot proksi). The Transpordiamet accident-point register
and Päästeamet drive times are NOT in the snapshot, so the master is
NOT measured safety — titles, legends and sources say "hinnang"/"proksi"
with the usage-not-safety caveat (pinned by
layers_roadsafety.test.ts). The per-listing scorer dim lives in
services/scoring/dims_p4_osm.py (dim_blackspots, nearest-furniture
bands <=500 m); this master answers the map question (how much calming
furniture surrounds the cell).

HONESTY (load-bearing): green sits NEAR the mapped furniture
(calming-visible streetscape), never on accident truth. Unstamped desert
stays 255 unknown (unmapped != safe — the absence fallback is unknown,
never a faked zero).

Models (locked 2026-09-13): roadsafety is a Euclidean Gaussian count
kernel over kept crossing/calming centroids (sigma 0.5, cutoff 4 sigma,
saturating score 100*S/(S+60), unstamped cells stay 255 unknown —
grocery/hydrant shape with a DENSITY half). half=60 (not 6): with
~10.5k Tallinn-window centroids a grocery half saturates the whole
city to 93+ (verified 2026-09-13 probe: Viru/Vanalinn/Balti all 96+)
and the field answers nothing. half=60 spreads the real variation
(probe S -> score: Viru 345 -> 85, Vanalinn 241 -> 80, Balti 208 -> 78,
Oismae 158 -> 72, Lasnamae 109 -> 64, Pirita 59 -> 50, Nomme 36 -> 37,
rural 0 -> 255) while forgiving unmapped crossings on garden-city
streets. Nomme's low (S=36) is a documented mapping hole — private
drive calming is unmapped there — not safety truth.

Sources (predicates verified on the snapshot extract):
* crossing: highway=crossing exactly (first value). Verified
  2026-09-13: 12348 key uses county-wide (matches docs/p4_osm.md).
* calming: traffic_calming key present (any value: bump, hump,
  chicane, island, ...). Verified 2026-09-13: 2672 key uses
  county-wide (docs/p4_osm.md prints 4860 — that figure counts a
  broader pre-filter; 2672 is the plain key-use count on the same PBF).
* osmium tags-filter ... 'nwr/highway=crossing'
  'nwr/traffic_calming' + export -> 14445 deduped features with
  geometry (10527 in the Tallinn window); ~635 carry both tags
  (raised crossings) and dedupe_cells merges the twins.
  Rebuild: osmium tags-filter ~/hf-data/2026-09-12/osm/\
harjumaa-260911.osm.pbf 'nwr/highway=crossing' 'nwr/traffic_calming' \
-o crosscalm.pbf && osmium export crosscalm.pbf -o crosscalm.geojson
"""

import argparse
import base64
import json
import math
import os
import time

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_g17_b scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # line vertex spacing for source rasterisation
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-13 (see module docstring).
# NOTE: apps/web/lib/layers_roadsafety.ts RSAFE_CAL mirrors these numbers
# exactly — test_batch_rsafety_osm.py parses that file and fails on drift.
RSAFE_CAL = {
    "roadsafety": {"half": 60.0, "sigma": 0.5},
}

LAYER_IDS = ("roadsafety",)

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Vanalinn": (24.7454, 59.4374), "Viru": (24.7536, 59.4364),
    "Balti": (24.7369, 59.4405), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Pirita": (24.83, 59.465),
    "Nomme": (24.685, 59.375), "rural": (24.5, 59.2),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def kernel(d_km, sigma):
    """Gaussian kernel weight (moorage precedent)."""
    return math.exp(-(d_km * d_km) / (2.0 * sigma * sigma))


def area_score(s, half):
    """Saturating count score 100*S/(S+half) (mirrors walk_raster.saturate)."""
    return 100.0 * s / (s + half)


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


def keep_crosscalm(props):
    """True when a crossing/calming-extract feature is calming furniture.

    highway=crossing exactly (first value: marked zebra/signal/island
    crossings) OR any traffic_calming key (bump, hump, chicane, island,
    ...). Footway/sidewalk/lit features are OUT by design (pedinfra and
    the P4-029 block observer own those gradients — a second footway
    field would duplicate them). Untagged relation members drop out.
    """
    props = props or {}
    if _first(props.get("highway")) == "crossing":
        return True
    return "traffic_calming" in props and props.get("traffic_calming") not in (None, "")


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
    """Bbox centre of a polygon/line coordinate array (one furniture unit)."""
    lons = []
    lats = []
    for lon, lat in _flat_coords(coords):
        lons.append(lon)
        lats.append(lat)
    if not lons:
        return None
    return ((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)


def read_crosscalm_points(crosscalm_path):
    """Calming-furniture dots from a crossing/calming geojson extract.

    Points feed directly; open lines feed densified (a way-mapped chicane
    counts along its length); polygons feed ONE bbox-centre point each
    (one table = one furniture unit). Returns ([(lon, lat)], stats).
    """
    pts = []
    stats = {"furniture": 0, "dropped": 0}
    for feat in _iter_features(crosscalm_path):
        if not keep_crosscalm(feat.get("properties") or {}):
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
            stats["furniture"] += 1
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
            stats["furniture"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords] if gtype == "Polygon" \
                else [p for p in coords if p]
            for ring in rings:
                c = _bbox_center(ring)
                if c is not None:
                    pts.append(c)
            stats["furniture"] += 1
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

    Bounded O(points * range^2) sweep: each furniture centroid stamps
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
# Layer scores (high = calming-visible; unstamped desert stays honestly unknown).
# ---------------------------------------------------------------------------

def score_area_cells(grid, acc, half):
    """Saturating furniture score 100*S/(S+half); desert stays 255."""
    out = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k, s in acc.items():
        out[k] = max(0, min(100, int(round(area_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = RSAFE_CAL[layer]
    return cal["half"], cal["sigma"]


def encode_wire(grid, values, layer="roadsafety"):
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


def build_layer(grid, layer, crosscalm_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer != "roadsafety":
        raise SystemExit("unknown layer %s" % layer)
    if not crosscalm_path:
        raise SystemExit("roadsafety needs --crosscalm crossing/calming extract")
    raw, stats = read_crosscalm_points(crosscalm_path)
    print("roadsafety=%s raw_pts=%d" % (stats, len(raw)), flush=True)
    pts = dedupe_cells(raw)
    print("roadsafety: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
    acc = count_kernel_field(grid, pts, RSAFE_CAL[layer]["sigma"])
    vals = score_area_cells(grid, acc, RSAFE_CAL[layer]["half"])
    print("roadsafety field ready (%.1fs)" % (time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = calming-visible):", flush=True)
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
    ap.add_argument("--crosscalm", default=None,
                    help="crossing/calming geojson extract (roadsafety)")
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
        vals, pts = build_layer(grid, layer, args.crosscalm)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d calming-visible(>=50)=%d" %
              (layer, len(vals), sum(1 for v in vals if v != 255 and v >= 50)),
              flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
