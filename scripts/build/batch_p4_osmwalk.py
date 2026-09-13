"""P4 OSM walkability + darkness county masters (issue #480): P4-029
block-observer and P4-035 darkness proxies.

Stdlib only. Offline, snapshot-only (NO network): walkability vectors
come from the LOCAL Harjumaa PBF via the documented osmium
pre-steps, never from a live service. Pure logic + snapshot readers
live at module top so unit tests stay hermetic; full-county builds
run only via the documented rebuild commands.

SCOPE (two layers, honest): this builder serves ONLY the mapped
footway/sidewalk/surface/lit count hinnangud. The eye-level legs stay
elsewhere: facade truth needs Mapillary/KartaView frames
(dims_p4_streetimg, docs/p4_streetimg.md), lamp counts need the
Tallinna street-lighting map + VIIRS (docs/p4_viirs.md, P4-035
NULL-adjacent), arrival feel stays dims_p4_osm.dim_arrival. OTA PR
#131 precedent: the unmappable legs ship as scorer NULLs or stated
absences, never gradients.

HONESTY (load-bearing): Mapillary/KartaView frames, the Tallinna
tänavavalgustuse kaart and VIIRS night lights are NOT in the
2026-09-12 snapshot, so neither master is eye-level truth nor a lamp
census. blockwalk scores the COUNT of mapped footway/sidewalk/
asphalt/lit evidence nearby (area-kind, grocery/waste/lawncare
precedent); darkness scores the COUNT of mapped lit=yes evidence
nearby. Titles, legends and sources say "kaardistatud" and
"hinnang"/"proksi" (pinned by layers_p4osm.test.ts).

Models (locked 2026-09-13, probes below): both layers are Euclidean
Gaussian count kernels over kept evidence points (sigma 0.5 == the
P4-029/P4-035 500 m tiers, cutoff 4 sigma, saturating score
100*S/(S+half), unstamped cells stay 255 unknown — grocery/waste/
lawncare shape with DENSITY halves). half=1000 (blockwalk) /
half=500 (darkness): with 246k / 59k evidence points a small half
saturates the whole county to ~99 (verified 2026-09-13 probe:
half=20 reads Vanalinn 100, Nomme 89, rural 96) and the field
answers nothing. Density halves spread the real variation —
built-master --probe on the 75 m grid (2026-09-13): blockwalk
Vanalinn 83, Mustamae 86, Lasnamae 74, Kalamaja 76, Oismae 73,
Viimsi 47, Pirita 40, rural 36, Nomme 15; darkness Vanalinn 81,
Mustamae 79, Lasnamae 64, Kalamaja 67, Oismae 56, Viimsi 26,
Pirita 20, Nomme 10, rural 18 — while forgiving unmapped
driveways and unlit yards. Nomme's near-zero is a documented
mapping hole (footways/lit sparsely mapped there), not
walkability truth. Green sits NEAR dense mapped evidence.

Sources (predicates verified on the snapshot extracts):
* footway: highway=footway exactly (first value). Verified
  2026-09-13: 30360 ways (+166 member-node objects, docs/p4_osm.md
  §3: 166990 highway=footway objects Harjumaa-wide); 54k feed
  points after 40 m downsampling.
* sidewalk: sidewalk key present and not "no". Verified 2026-09-13:
  2734 ways (docs/p4_osm.md §3: 16846 sidewalk-key objects);
  3.5k feed points.
* asphalt: surface=asphalt exactly (first value). Verified
  2026-09-13: 46590 ways (docs/p4_osm.md §3: 303336
  surface=asphalt objects); 130k feed points.
* lit: lit=yes exactly (first value, ways/areas/nodes — mapped
  lamps as points count). Verified 2026-09-13: 25991 ways +
  2058 tagged nodes (docs/p4_osm.md §3: 145725 lit=yes objects);
  59k feed points.
Overlap with dims_p4_osm.dim_block_observer / dim_darkness
(nearest ≤500 m) is DOCUMENTED (ehitus/buildout G05A+G05B
precedent): those ask how far the closest mapped evidence is,
blockwalk/darkness ask how much mapped evidence surrounds the
listing.

Computation: graph-free Gaussian count kernel on the 75 m county
grid (57.29/110.57 scales). Sources snap to 150 m cells WITH
multiplicity (a full cell counts its points, never one vote —
position error ≤106 m per source, <2% weight error at sigma 0.5,
stated not hidden); each occupied source cell stamps ONE
precomputed 4-sigma stencil, so the sweep is O(occupied cells),
not O(points × cells) like the sparse batches. NO metro master
(documented): a dense count kernel at 9.375 m cells would be fake
precision — the window route serves county everywhere.

Feeding (evidence dots, not rings): tagged nodes feed directly
(mapped lamps ARE the darkness signal); open lines feed
downsampled to ~40 m vertices (a 100 m footway is several dots,
not one — parking-builder densify precedent, inverted for dense
sources); closed lines and polygons feed ONE bbox-centre point
each (one lit yard = one unit — rings would explode areas into
~1M samples). No field dedupe: the stencil sweep over raw dots
reproduces exact per-point sums at every witness, while twin
merges flatten the best-mapped streets (57/73 vs 83 at Vanalinn);
residual node-vertex doubles are ≤1.1% of dots. Dedupe survives
only in write_points (overlay thinning).

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      'nwr/highway=footway' -o /tmp/hf-p4w-footway.pbf --overwrite
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      'nwr/sidewalk' -o /tmp/hf-p4w-sidewalk.pbf --overwrite
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      'nwr/surface=asphalt' -o /tmp/hf-p4w-asphalt.pbf --overwrite
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      'nwr/lit=yes' -o /tmp/hf-p4w-lit.pbf --overwrite
  for t in footway sidewalk asphalt lit; do
    osmium export /tmp/hf-p4w-$t.pbf -o /tmp/hf-p4w-$t.geojson --overwrite
  done
  python3 scripts/build/batch_p4_osmwalk.py --layer all \\
      --footway /tmp/hf-p4w-footway.geojson \\
      --sidewalk /tmp/hf-p4w-sidewalk.geojson \\
      --asphalt /tmp/hf-p4w-asphalt.geojson --lit /tmp/hf-p4w-lit.geojson \\
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: blockwalk-walk-raster.json + darkness-walk-raster.json
(count-kernel area masters, WalkRasterDoc shape so cleanRaster
accepts them) + derived-blockwalk.json + derived-darkness.json
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
# Constants (mirrors walk_raster / batch_g17_b.py scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
SOURCE_SNAP_M = 150.0  # source multiplicity snap (documented above)
DOWNSAMPLE_M = 40.0  # open-line vertex spacing for dense sources
DEDUPE_M = 20.0  # node+line twin guard (mirrors sibling batches)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-13 (see module docstring).
# NOTE: apps/web/lib/layers_p4osm.ts P4OSM_CAL mirrors these
# numbers exactly — test_batch_p4_osmwalk.py parses that file and
# fails on drift.
P4OSM_CAL = {
    "blockwalk": {"half": 1000.0, "sigma": 0.5},
    "darkness": {"half": 500.0, "sigma": 0.5},
}

LAYER_IDS = ("blockwalk", "darkness")

#: Extract kind feeding each layer (blockwalk consumes all four).
LAYER_SOURCES = {
    "blockwalk": ("footway", "sidewalk", "asphalt", "lit"),
    "darkness": ("lit",),
}

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Vanalinn": (24.7454, 59.4374), "Mustamae": (24.68, 59.405),
    "Lasnamae": (24.82, 59.44), "Pirita": (24.821, 59.468),
    "Viimsi": (24.83, 59.51), "Nomme": (24.62, 59.375),
    "Kalamaja": (24.7413, 59.4476), "Oismae": (24.655, 59.412),
    "rural": (24.55, 59.32),
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
# Grid (local copy for self-containment, mirrors batch_g17_b.py).
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


def keep_evidence(kind, props):
    """True when an extract feature is mapped walkability evidence.

    footway: highway=footway exactly (first value). sidewalk: the
    sidewalk key present and not "no" (a street tagged sidewalk=no
    is evidence of absence, never of presence). asphalt:
    surface=asphalt exactly (first value). lit: lit=yes exactly
    (first value — mapped lamps as nodes count). Untagged relation
    members carry none of these keys, so they drop out.
    """
    props = props or {}
    if kind == "footway":
        return _first(props.get("highway")) == "footway"
    if kind == "sidewalk":
        return "sidewalk" in props and \
            str(props.get("sidewalk")).strip() not in ("", "no") and \
            _first(props.get("sidewalk")) != "no"
    if kind == "asphalt":
        return _first(props.get("surface")) == "asphalt"
    if kind == "lit":
        return _first(props.get("lit")) == "yes"
    return False


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    return [x for x in feats if isinstance(x, dict)]


def _downsample_line(coords, step_km=DOWNSAMPLE_M / 1000.0):
    """Keep a vertex every ~step_km (dense-source inversion of densify).

    The parking builder DENSIFIES sparse bay lines (one feature must
    spread); footway/asphalt/lit lines are individually dense, so the
    same 40 m characteristic scale SUBSAMPLES them instead — one dot
    per 40 m of mapped line either way.
    """
    pts = []
    last = None
    for lon, lat in coords:
        if last is None or hav_km(last[0], last[1], lon, lat) >= step_km:
            pts.append((lon, lat))
            last = (lon, lat)
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
    """Bbox centre of a polygon/line coordinate array (one evidence unit).

    The documented polygon convention (dims_group18c.py): a count
    kernel needs one point per area, not stride-sampled rings — rings
    would explode lit yards and asphalt lots into ~1M samples.
    """
    lons = []
    lats = []
    for lon, lat in _flat_coords(coords):
        lons.append(lon)
        lats.append(lat)
    if not lons:
        return None
    return ((min(lons) + max(lons)) / 2.0, (min(lats) + max(lats)) / 2.0)


def read_evidence_points(path, kind):
    """Mapped evidence dots from one tag-extract geojson.

    Tagged nodes feed directly (mapped lamps ARE the darkness
    signal); open lines feed downsampled to ~40 m vertices; closed
    lines and polygons feed ONE bbox-centre point each. Returns
    ([(lon, lat)], stats).
    """
    pts = []
    stats = {"kept": 0, "dropped": 0}
    for feat in _iter_features(path):
        if not keep_evidence(kind, feat.get("properties") or {}):
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
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                c = _bbox_center(coords)
                if c is None:
                    stats["dropped"] += 1
                    continue
                pts.append(c)
            else:
                pts.extend(_downsample_line(co))
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords] if gtype == "Polygon" \
                else [p for p in coords if p]
            for ring in rings:
                c = _bbox_center(ring)
                if c is not None:
                    pts.append(c)
        else:
            stats["dropped"] += 1
            continue
        stats["kept"] += 1
    return pts, stats


def dedupe_cells(points, cell_m=DEDUPE_M):
    """Merge node+line twins falling in the same ~cell_m cell."""
    cells = {}
    for lon, lat in points:
        k = (round(lon * LON_KM * 1000 / cell_m),
             round(lat * LAT_KM * 1000 / cell_m))
        if k not in cells:
            cells[k] = (lon, lat)
    return list(cells.values())


# ---------------------------------------------------------------------------
# Fields: Gaussian count kernel (area) — grocery/waste/lawncare precedent.
# ---------------------------------------------------------------------------

def snap_sources(points, cell_m=SOURCE_SNAP_M):
    """Snap evidence to cell_m cells WITH multiplicity (cell -> count).

    Dense sources (246k blockwalk dots) make the sparse batches'
    per-point sweep O(points × cells) — hours in stdlib Python.
    Snapping keeps every dot's vote (a full cell counts its points,
    never one vote) while the sweep drops to O(occupied cells).
    Position error per source is ≤~160 m worst case (150 m snap +
    75 m cell centring) with ≤5% weight error on the nearest cells
    at sigma 0.5 — stated, and the --probe witnesses pin the field.
    """
    cells = {}
    for lon, lat in points:
        k = (round(lon * LON_KM * 1000 / cell_m),
             round(lat * LAT_KM * 1000 / cell_m))
        cells[k] = cells.get(k, 0) + 1
    return cells


def stencil_weights(sigma, step_m=STEP_M):
    """Precomputed (dx_cells, dy_cells, weight) within 4 sigma.

    One stencil serves every source cell: the 75 m grid is square in
    metres, so the km offset of a (dx, dy) pair is isotropic —
    step_m/1000 * hypot(dx, dy) — independent of absolute position
    (same equirectangular approximation the per-point sweep makes
    per pair, verified against it by test_stencil_matches_pointwise).
    """
    cutoff_km = 4.0 * sigma
    step_km = step_m / 1000.0
    r = int(math.ceil(cutoff_km / step_km))
    out = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            d = step_km * math.hypot(dx, dy)
            if d > cutoff_km:
                continue
            out.append((dx, dy, kernel(d, sigma)))
    return out


def count_kernel_field(grid, source_cells, sigma, snap_m=SOURCE_SNAP_M):
    """Gaussian count accumulation: cell -> S (moorage precedent).

    Each occupied source cell stamps the precomputed stencil once,
    scaled by its multiplicity. Unstamped cells stay absent (the
    scorer renders them 255 unknown, never a faked zero).
    """
    stencil = stencil_weights(sigma, grid.step)
    snap_step = snap_m / 1000.0
    minlon, minlat, _, _ = grid.bbox
    acc = {}
    for (ckx, cky), mult in source_cells.items():
        # Snap keys are absolute 150 m lattice multiples (same round()
        # convention as dedupe_cells), so centres need no bbox origin.
        clon = ckx * snap_step / LON_KM
        clat = cky * snap_step / LAT_KM
        cix = int(math.floor((clon - minlon) * LON_KM * 1000 / grid.step))
        ciy = int(math.floor((clat - minlat) * LAT_KM * 1000 / grid.step))
        for dx, dy, w in stencil:
            ix = cix + dx
            iy = ciy + dy
            if 0 <= ix < grid.cols and 0 <= iy < grid.rows:
                k = iy * grid.cols + ix
                acc[k] = acc.get(k, 0.0) + mult * w
    return acc


# ---------------------------------------------------------------------------
# Layer scores (high = dense mapped evidence; desert stays honestly unknown).
# ---------------------------------------------------------------------------

def score_area_cells(grid, acc, half):
    """Saturating evidence score 100*S/(S+half); desert stays 255."""
    out = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k, s in acc.items():
        out[k] = max(0, min(100, int(round(area_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = P4OSM_CAL[layer]
    return cal["half"], cal["sigma"]


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


def build_layer(grid, layer, paths):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer not in LAYER_IDS:
        raise SystemExit("unknown layer %s" % layer)
    raw = []
    for kind in LAYER_SOURCES[layer]:
        path = paths.get(kind)
        if not path:
            raise SystemExit("%s needs --%s <kind> extract" % (layer, kind))
        pts, stats = read_evidence_points(path, kind)
        print("%s/%s=%s pts=%d" % (layer, kind, stats, len(pts)), flush=True)
        raw.extend(pts)
    # NO field dedupe (verified 2026-09-13): the stencil sweep over
    # raw dots reproduces the exact per-point kernel sums at every
    # witness (Vanalinn 83/81, Mustamae 85/79, Lasnamae 74/65,
    # Nomme 14/10 — identical), while any 20 m twin-merge flattens
    # exactly the best-mapped streets (combined dedupe read Vanalinn
    # 57, per-kind 73, exact 83). The 40 m downsampling already
    # spaces line dots; residual node↔vertex doubles are bounded by
    # the tagged-node share (2.7k of 246k dots, ~1.1%), far below
    # half-scale. Dedupe survives only in write_points (overlay
    # thinning, where one visual dot per cell is the point).
    print("%s: evidence dots %d" % (layer, len(raw)), flush=True)
    pts = raw
    snapped = snap_sources(pts)
    print("%s: snapped to %d occupied %dm cells"
          % (layer, len(snapped), int(SOURCE_SNAP_M)), flush=True)
    acc = count_kernel_field(grid, snapped, P4OSM_CAL[layer]["sigma"])
    vals = score_area_cells(grid, acc, P4OSM_CAL[layer]["half"])
    print("%s field ready (%.1fs)" % (layer, time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = dense mapped evidence):", flush=True)
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
    ap.add_argument("--footway", default=None,
                    help="highway=footway geojson extract")
    ap.add_argument("--sidewalk", default=None,
                    help="sidewalk-key geojson extract")
    ap.add_argument("--asphalt", default=None,
                    help="surface=asphalt geojson extract")
    ap.add_argument("--lit", default=None,
                    help="lit=yes geojson extract")
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
    paths = {"footway": args.footway, "sidewalk": args.sidewalk,
             "asphalt": args.asphalt, "lit": args.lit}
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    masters = {}
    for layer in layers:
        vals, pts = build_layer(grid, layer, paths)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d dense-mapped(>=50)=%d"
              % (layer, len(vals), sum(1 for v in vals if v != 255 and v >= 50)),
              flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
