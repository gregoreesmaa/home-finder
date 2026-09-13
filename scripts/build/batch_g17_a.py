"""Group 17 municipal-services-A county masters (issue #177): p187 compost +
p311 gritbin + p312 leafdrop.

Stdlib only. Offline, snapshot-only (NO network): compost-station vectors,
grit-bin vectors and green-waste drop-off vectors come from the LOCAL
Harjumaa PBF via the documented osmium pre-steps, never from a live
service. Pure logic + snapshot readers live at module top so unit tests
stay hermetic; full-county builds run only via the documented rebuild
commands.

SCOPE (three layers, honest): this builder serves ONLY p187 (municipal
composting infrastructure) as a mapped-station count hinnang, p311 (snow
plowing priority) as a mapped grit-bin count hinnang, and p312 (leaf
collection and yard waste) as a mapped green-waste drop-off count
hinnang. The sibling params are documented no-map (see
apps/web/lib/layers_group17a.ts): p60 municipal service schedules (a
per-district calendar with no area signal) and p347 garbage-can
concealment (a per-parcel courtyard attribute with no area signal) ship
as scorer dims only (services/scoring/dims_group17a.py), OTA PR #131
precedent.

HONESTY (load-bearing): the Tallinna Linnavalitsus / KOV service
registers — collection calendars, plow-priority classes
(hooldusklassid), bin-enclosure records — are NOT in the 2026-09-12
snapshot, so no master is registry data. compost scores the COUNT of
mapped green-accepting jäätmejaamad + bio/food-waste points nearby
(area-kind, viewshed/moorage precedent — never a capacity ruling);
gritbin scores the COUNT of mapped grit bins nearby (area-kind — never
a plow-route ruling); leafdrop scores the COUNT of mapped green-waste
drop-offs nearby (area-kind — never a route ruling). Titles, legends
and sources say "hinnang" (pinned by layers_group17a.test.ts).

Deliberately NOT a road-class field (gritbin): p446 snowplow berms
(services/scoring/dims_group18veg.py) already scores road class
INVERTED (near arterials = berm burden) — a second road-class gradient
would duplicate it with the arrow flipped. winter_service tags: zero
in the snapshot; hooldusklassid: not in the snapshot registries.

Models (locked 2026-09-12): all three are Euclidean Gaussian count
kernels over kept dots (sigma 0.3, cutoff 4 sigma, saturating score
100*S/(S+1), unstamped cells stay 255 unknown — same shape as
viewshed, batch_g05c_plans.py). half=1 (not 2): with 44 compost / 30
grit-bin / 131 leafdrop county features, ONE mapped point reads 50 on
its own cell (mid-amber) instead of vanishing; service deserts read
honestly unknown. Green sits NEAR the service.

Sources (predicates verified on the snapshot extract):
* compost: amenity=recycling AND (recycling_type=centre with
  green_waste/garden_waste=yes, OR food_waste/organic=yes).
  Verified 2026-09-12: 44 kept county-wide (18 green centres —
  Pääsküla, Rahumäe, Pärnamäe, Paljassaare jäätmejaamad — + 26
  bio/food collection points; 35 in the Tallinn window). Plain
  paper/glass/plastic containers are OUT by design (p54's own):
  a bottle bank is not composting infrastructure.
* grit: amenity=grit_bin ONLY (verified 2026-09-12: 30 kept
  county-wide, 25 in the Tallinn window). Thin but honest: bins sit
  on city-maintained winter-service streets.
* leaf: amenity=recycling with green_waste/garden_waste=yes (any
  type) OR amenity=waste_disposal with green_waste=yes. Verified
  2026-09-12: 131 kept county-wide (77 green recycling + 54
  green-accepting household points; 122 in the Tallinn window).
  555 untagged waste_disposal litter/dog bins drop out BY DESIGN
  (a litter bin is not yard-waste collection).
  Overlap with compost (green centres + food/green containers sit in
  both sets) is DOCUMENTED (ehitus/buildout G05A+G05B precedent):
  a jäätmejaam both composts and takes yard waste; the TS verdict
  says so, it is not hidden.

Computation: all three are graph-free Gaussian count kernels on the
75 m county grid (57.29/110.57 scales). NO metro masters
(documented): sparse count kernels at 9.375 m cells would be fake
precision — the window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/amenity=recycling nwr/amenity=waste_disposal \\
      nwr/amenity=waste_transfer_station nwr/amenity=grit_bin \\
      -o /tmp/hf-g17a-waste.pbf --overwrite
  osmium export /tmp/hf-g17a-waste.pbf -o /tmp/hf-g17a-waste.geojson
  python3 scripts/build/batch_g17_a.py --layer all \\
      --waste /tmp/hf-g17a-waste.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: compost/gritbin/leafdrop-walk-raster.json (count-kernel area
masters, WalkRasterDoc shape so cleanRaster accepts it) +
derived-<layer>.json (fallback points for the Euclidean route +
overlay). Restart the web server afterwards — the server caches
masters per process.
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
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group17a.ts G17A_CAL mirrors these numbers
# exactly — test_batch_g17_a.py parses that file and fails on drift.
G17A_CAL = {
    "compost": {"half": 1.0, "sigma": 0.3},
    "gritbin": {"half": 1.0, "sigma": 0.3},
    "leafdrop": {"half": 1.0, "sigma": 0.3},
}

LAYER_IDS = ("compost", "gritbin", "leafdrop")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
    "Paaskula": (24.64352, 59.36103), "Mustamae": (24.66856, 59.39576),
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


def keep_compost(props):
    """True when a waste-extract feature is composting infrastructure.

    amenity=recycling AND (a green/garden-waste CENTRE — the city's
    jäätmejaamad — or a bio/food-waste collection point). Plain
    paper/glass/plastic containers are OUT by design (p54's own):
    a bottle bank is not composting infrastructure. Untagged relation
    members carry no amenity, so they drop out here.
    """
    props = props or {}
    if _first(props.get("amenity")) != "recycling":
        return False
    green = _first(props.get("recycling:green_waste")) == "yes" or \
        _first(props.get("recycling:garden_waste")) == "yes"
    bio = _first(props.get("recycling:food_waste")) == "yes" or \
        _first(props.get("recycling:organic")) == "yes"
    if bio:
        return True
    return props.get("recycling_type") == "centre" and green


def keep_grit(props):
    """True when a waste-extract feature is a mapped grit bin.

    amenity=grit_bin ONLY. Bins sit on city-maintained winter-service
    streets — thin but honest. Road class is deliberately NOT consumed
    here: it already scores inverted as p446 berms.
    """
    return _first((props or {}).get("amenity")) == "grit_bin"


def keep_leaf(props):
    """True when a waste-extract feature takes yard waste.

    amenity=recycling with green/garden-waste=yes (any type) OR
    amenity=waste_disposal with green_waste=yes (household collection
    accepting garden waste). Untagged litter/dog bins are OUT by
    design: a litter bin is not yard-waste collection.
    """
    props = props or {}
    green = _first(props.get("recycling:green_waste")) == "yes" or \
        _first(props.get("recycling:garden_waste")) == "yes"
    if _first(props.get("amenity")) == "recycling" and green:
        return True
    return _first(props.get("amenity")) == "waste_disposal" and \
        _first(props.get("recycling:green_waste")) == "yes"


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    return [x for x in feats if isinstance(x, dict)]


def _stride_ring(ring, per=25):
    pts = [(c[0], c[1]) for c in ring]
    return pts[:: max(1, len(pts) // per)]


def read_source_points(waste_path, keep, key):
    """Kept dots from a waste geojson extract (points + ring samples).

    Points feed directly; polygons feed stride-sampled outer rings
    (jäätmejaamad are areas — a count kernel only needs the shape).
    Returns ([(lon, lat)], stats).
    """
    pts = []
    stats = {key: 0, "dropped": 0}
    for feat in _iter_features(waste_path):
        if not keep(feat.get("properties") or {}):
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
            stats[key] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            pts.extend(_stride_ring(co))
            stats[key] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
            stats[key] += 1
        else:
            stats["dropped"] += 1
    return pts, stats


def read_compost_points(waste_path):
    """Composting-station dots from a waste geojson extract."""
    return read_source_points(waste_path, keep_compost, "stations")


def read_grit_points(waste_path):
    """Grit-bin dots from a waste geojson extract."""
    return read_source_points(waste_path, keep_grit, "bins")


def read_leaf_points(waste_path):
    """Green-waste drop-off dots from a waste geojson extract."""
    return read_source_points(waste_path, keep_leaf, "drops")


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
# Fields: Gaussian count kernel (area) — viewshed/moorage precedent.
# ---------------------------------------------------------------------------

def count_kernel_field(grid, points, sigma):
    """Gaussian count accumulation: cell -> S (moorage precedent).

    Bounded O(points * range^2) sweep: each service point stamps
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
# Layer scores (high = serviced; unstamped desert stays honestly unknown).
# ---------------------------------------------------------------------------

def score_area_cells(grid, acc, half):
    """Saturating service score 100*S/(S+half); desert stays 255."""
    out = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k, s in acc.items():
        out[k] = max(0, min(100, int(round(area_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G17A_CAL[layer]
    return cal["half"], cal["sigma"]


def encode_wire(grid, values, layer="compost"):
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


_READERS = {
    "compost": (read_compost_points, "stations"),
    "gritbin": (read_grit_points, "bins"),
    "leafdrop": (read_leaf_points, "drops"),
}


def build_layer(grid, layer, waste_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer not in _READERS:
        raise SystemExit("unknown layer %s" % layer)
    if not waste_path:
        raise SystemExit("%s needs --waste waste extract" % layer)
    reader, _ = _READERS[layer]
    raw, stats = reader(waste_path)
    print("%s=%s raw_pts=%d" % (layer, stats, len(raw)), flush=True)
    pts = dedupe_cells(raw)
    print("%s: deduped %d -> %d" % (layer, len(raw), len(pts)), flush=True)
    acc = count_kernel_field(grid, pts, G17A_CAL[layer]["sigma"])
    vals = score_area_cells(grid, acc, G17A_CAL[layer]["half"])
    print("%s field ready (%.1fs)" % (layer, time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = serviced):", flush=True)
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
    ap.add_argument("--waste", default=None,
                    help="waste geojson extract (all three layers)")
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
        vals, pts = build_layer(grid, layer, args.waste)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d serviced(>=50)=%d" %
              (layer, len(vals), sum(1 for v in vals if v != 255 and v >= 50)),
              flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
