"""Group 5 plans-A county masters (issue #161): p42 ehitus + p44 korterstock.

Stdlib + scripts/ walk helpers only. Offline, snapshot-only (NO
network): construction-site vectors and apartment-footprint vectors
come from the LOCAL Harjumaa PBF via the documented osmium pre-steps,
never from a live service. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; full-county builds run only
via the documented rebuild commands.

SCOPE (two layers, honest): this builder serves ONLY p42 (future
development) as a mapped-construction-activity count hinnang and p44
(rental potential) as a mapped-apartment-stock count hinnang. The
sibling params are documented no-map (see
apps/web/lib/layers_group05a.ts): p45 adaptability, p47 zoning laws
and p74 rental restrictions are per-building/per-parcel legal facts
with no honest area signal in the snapshot — they ship as scorer dims
only (services/scoring/dims_group05a.py), OTA PR #131 precedent.

HONESTY (load-bearing): the Rahandusministeerium PLANK register and
the Tallinna Planeeringute Register (TPR) are NOT in the 2026-09-12
snapshot, so neither master is a planning decision. ehitus scores
nearness to MAPPED construction sites (landuse=construction areas +
building=construction footprints — development is visibly happening
there, the cause, never a plan ruling); korterstock scores nearness
to MAPPED apartment buildings (building=apartments footprints — an
established rental market needs rental stock, the cause, never a
rent register and never euros). Titles, legends and sources say
"hinnang" (pinned by layers_group05a.test.ts).

Models (locked 2026-09-12):
* ehitus (p42): EUCLIDEAN count kernel over kept construction-site
  points (Gaussian sigma 0.3, cutoff 4 sigma, saturating score
  100*S/(S+half), null below 3 -> 255). Euclidean, not walk-stamped,
  BY DESIGN (same story as moorage, #154: site centroids need no foot
  graph). half=1 (not 2): with 518 county sites (156 Tallinn-window)
  ONE mapped site reads 50 on its own cell (mid-amber) instead of
  vanishing; detached Nomme and rural read honestly null/low.
  Measured county-raster reads (--probe, 2026-09-12 full build):
  Balti 68, Viru 56, Pirita 50, Oismae 42, Lasnamae 16, Kadriorg /
  Viimsi / Nomme / Paljassaare / rural unknown. Construction is lumpy
  BY DESIGN — the map shows where cranes are, never a plan promise.
* korterstock (p44): EUCLIDEAN count kernel over kept apartment
  footprints (same kernel shape, sigma 0.3, saturating score
  100*S/(S+half), null below 3 -> 255). half=15 (not 1): with 6842
  county footprints (5827 Tallinn-window) slab districts would pin at
  100 under half=1 — half=15 keeps Lasnamae 68 / Oismae 72, town
  centre 84-87, detached Nomme honestly unknown, Viimsi 41 mid and
  Paljassaare/Pirita 10 low.
  Measured county-raster reads (--probe, 2026-09-12 full build):
  Balti 87, Viru 84, Oismae 72, Lasnamae 68, Kadriorg 65, Viimsi 41,
  Paljassaare 10, Pirita 10, Nomme / rural unknown.

Sources (predicates verified on the snapshot extract):
* dev: landuse=construction OR building=construction (verified
  2026-09-12: 1053 kept county-wide = 360 building rings + 360
  building MultiPolygons + 166 landuse rings + 166 landuse
  MultiPolygons + 1 point, merging to 518 deduped sites; 156 of them
  in the Tallinn window). The export's LineString/MultiPolygon duals
  of one closed way collapse to the same bbox center in
  read_site_points, so the 20 m dedupe merges them (535 merged).
  Untagged referrer nodes and relation members (31) drop out in the
  predicate.
* apt: building=apartments footprints (verified 2026-09-12: 13952
  kept county-wide, merging to 6842 deduped footprints; 5827 of them
  in the Tallinn window; 3457 untagged referrer nodes dropped).
  Staircase entrances and ADS address points carry no
  building=apartments tag, so one footprint casts exactly one vote —
  no entrance multi-count by construction.

Computation: both masters are graph-free Euclidean fields on the 75 m
county grid (57.29/110.57 scales) — Gaussian count kernels. NO metro
masters (documented): smooth count fields at 9.375 m cells would be
fake precision — the window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/landuse=construction nwr/building=construction \\
      -o /tmp/hf-g05a-dev.pbf --overwrite
  osmium export -u type_id /tmp/hf-g05a-dev.pbf -o /tmp/hf-g05a-dev.geojson
  python3 scripts/build/batch_g05a_plans.py --layer ehitus \\
      --poi /tmp/hf-g05a-dev.geojson \\
      --out ~/hf-data/2026-09-12/osm/ehitus-walk-raster.json \\
      --write-points --probe
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/building=apartments \\
      -o /tmp/hf-g05a-apt.pbf --overwrite
  osmium export -u type_id /tmp/hf-g05a-apt.pbf -o /tmp/hf-g05a-apt.geojson
  python3 scripts/build/batch_g05a_plans.py --layer korterstock \\
      --poi /tmp/hf-g05a-apt.geojson \\
      --out ~/hf-data/2026-09-12/osm/korterstock-walk-raster.json \\
      --write-points --probe
Outputs: ehitus-walk-raster.json (Euclidean count-kernel master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-ehitus.json
(fallback points for the Euclidean route + overlay) and
korterstock-walk-raster.json (same wire shape) +
derived-korterstock.json overlay sample. Restart the web server
afterwards — the server caches masters per process.
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

import walk_raster as wr  # noqa: E402

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_g03d_cadastre scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group05a.ts G05A_CAL mirrors these numbers
# exactly — test_batch_g05a.py parses that file and fails on drift.
G05A_CAL = {
    "ehitus": {"half": 1, "sigma": 0.3},
    "korterstock": {"half": 15, "sigma": 0.3},
}

LAYER_IDS = ("ehitus", "korterstock")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
}

# ~20 m spatial dedupe cells (mirrors batch_g03d_cadastre DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


# ---------------------------------------------------------------------------
# Site predicates (p42/p44 hinnang source sets).
# ---------------------------------------------------------------------------

def is_devsite(tags):
    """True when OSM tags mark visible development activity (NOT a plan).

    landuse=construction areas + building=construction footprints.
    Untagged referrer nodes / relation members return False (never
    throw on None).
    """
    if not isinstance(tags, dict):
        return False
    return tags.get("landuse") == "construction" or \
        tags.get("building") == "construction"


def is_apartstock(tags):
    """True when OSM tags mark an apartment building (NOT a rent fact).

    building=apartments footprints ONLY. Staircase entrances and ADS
    address points carry no building tag, so they drop out here — one
    footprint casts exactly one vote (no entrance multi-count).
    """
    if not isinstance(tags, dict):
        return False
    return tags.get("building") == "apartments"


LAYER_PRED = {
    "ehitus": is_devsite,
    "korterstock": is_apartstock,
}


def _bbox_center(coords):
    """Bbox-center representative of a ring list (one vote per site)."""
    xs = [c[0] for ring in coords for c in ring]
    ys = [c[1] for ring in coords for c in ring]
    if not xs or not ys:
        return None
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)


def read_site_points(poi_path, pred):
    """One representative point per kept site from an osmium export.

    Points feed directly; Polygon/MultiPolygon features collapse to
    their bbox center (ONE vote per footprint — no entrance
    multi-count); CLOSED LineString rings collapse to the same bbox
    center, so the export's LineString/MultiPolygon duals of one
    closed way merge in dedupe_points below (walk_raster's midpoint
    representative would strand large-site duals >20 m apart).
    Genuinely OPEN tagged lines (rare) feed their midpoint.
    Returns ([(lon, lat, 1.0)], stats). Never throws on junk.
    """
    feats = kept = dropped = 0
    out = []
    with open(poi_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line.startswith("{"):
                continue
            try:
                feat = json.loads(line)
            except ValueError:
                continue
            if feat.get("type") != "Feature":
                continue
            feats += 1
            props = feat.get("properties") or {}
            if not pred(props):
                dropped += 1
                continue
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            coords = geom.get("coordinates")
            pt = None
            if gtype == "Point" and isinstance(coords, list) and len(coords) >= 2:
                pt = (float(coords[0]), float(coords[1]))
            elif gtype == "MultiPolygon" and isinstance(coords, list):
                pt = _bbox_center([p[0] for p in coords if p])
            elif gtype == "Polygon" and isinstance(coords, list):
                pt = _bbox_center([coords[0]] if coords else [])
            elif gtype == "LineString" and isinstance(coords, list) and coords:
                co = [(c[0], c[1]) for c in coords]
                if len(co) > 1 and co[0] == co[-1]:
                    pt = _bbox_center([co])  # closed ring: same center as its MP twin
                else:
                    mid = co[len(co) // 2]
                    pt = (float(mid[0]), float(mid[1]))
            if pt is None:
                dropped += 1
                continue
            kept += 1
            out.append((pt[0], pt[1], 1.0))
    return out, {"features": feats, "kept": kept, "dropped": dropped}


def dedupe_points(feats):
    """Collapse co-located sites (~20 m cells, first wins).

    Needed because osmium export emits LineString + MultiPolygon duals
    for the same closed way: OSM-id dedupe cannot see those pairs
    (distinct representation ids), and double-counting one site would
    double its kernel weight. Distinct sites >20 m apart stay separate.
    """
    seen = {}
    for lon, lat, w in feats:
        k = (round(lon / DEDUPE_LON), round(lat / DEDUPE_LAT))
        if k not in seen:
            seen[k] = (lon, lat, w)
    return list(seen.values())


def _area_score(acc, half):
    """Mirror of the grocery/healthcare scorer: saturate, null below 3."""

    def score_of(k):
        s = acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= 3 else None

    return score_of


def build_count_field(grid, half, sigma, poi_path, layer):
    """Euclidean Gaussian count kernel over kept site points.

    Bounded O(points * range^2) sweep: each site stamps
    kernel(d, sigma) into cells within 4 sigma. Returns (acc, feats).
    Graph-free on purpose (same story as moorage, #154: site centroids
    sit off the foot graph or on water-adjacent fill — walk stamping
    would leave holes AT the sites themselves).
    """
    raw, stats = read_site_points(poi_path, LAYER_PRED[layer])
    feats = dedupe_points(raw)
    cutoff_km = 4.0 * sigma
    acc = {}
    minlon, minlat, _, _ = grid.bbox
    for lon, lat, _ in feats:
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
                acc[k] = acc.get(k, 0.0) + wr.kernel(d, sigma)
    print("%s: %d site features (%d raw, %d co-located merged), "
          "%d stamped cells"
          % (layer, len(feats), stats["kept"], stats["kept"] - len(feats), len(acc)),
          flush=True)
    return acc, feats


def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G05A_CAL[layer]
    return cal["half"], cal["sigma"]


def encode_wire(grid, values, layer="ehitus"):
    half, sigma = contract_of(layer)
    return {
        "cols": grid.cols, "rows": grid.rows,
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step, "half": half, "sigma": sigma,
        "per": 0, "cap": 0, "unknown": 255, "dtype": "uint8",
        "data": base64.b64encode(bytes(values)).decode("ascii"),
    }


def score_bytes(grid, score_of):
    """Per-cell FINAL uint8 scores (255 = unknown), as raw bytes."""
    vals = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k in range(grid.cols * grid.rows):
        s = score_of(k)
        if s is not None:
            vals[k] = int(round(min(100.0, s)))
    return bytes(vals)


def probe_field(vals, grid, layer):
    print("probe (%s goodness 0..100, high = sites near):" % layer, flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-11s outside grid" % name, flush=True)
            continue
        v = vals[k]
        print("  %-11s %s" % (name, "unknown" if v == 255 else v), flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--poi", default=None,
                    help="site geojson from the docstring osmium pre-step")
    ap.add_argument("--out", default=None,
                    help="single-layer raster output path (implies --outdir)")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-<layer>.json overlay/fallback sample")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args(argv)
    outdir = args.outdir or (os.path.dirname(args.out) if args.out else None)
    if not args.poi:
        ap.error("--poi is required")
    if not outdir:
        ap.error("need --outdir (or --out)")
    os.makedirs(outdir, exist_ok=True)
    grid = wr.Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step),
          flush=True)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    masters = {}
    for layer in layers:
        t0 = time.time()
        defs = G05A_CAL[layer]
        acc, feats = build_count_field(grid, defs["half"], defs["sigma"],
                                       args.poi, layer)
        vals = score_bytes(grid, _area_score(acc, defs["half"]))
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
            if args.write_points:
                pts = [{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats]
                derived = os.path.join(os.path.dirname(args.out),
                                       "derived-%s.json" % layer)
                with open(derived, "w", encoding="utf-8") as f:
                    json.dump(pts, f)
                print("wrote derived-%s.json (%d fallback points)"
                      % (layer, len(pts)), flush=True)
        else:
            name = "%s-walk-raster" % layer
            with open(os.path.join(outdir, name + ".json"), "w",
                      encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s.json" % name, flush=True)
            if args.write_points:
                pts = [{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats]
                with open(os.path.join(outdir, "derived-%s.json" % layer), "w",
                          encoding="utf-8") as f:
                    json.dump(pts, f)
                print("wrote derived-%s.json (%d fallback points)"
                      % (layer, len(pts)), flush=True)
        raw = bytes(vals)
        known = sum(1 for v in raw if v != 255)
        print("%s: cells=%d known=%d (%.1f%%) (%.1fs)"
              % (layer, len(raw), known, 100 * known / len(raw),
                 time.time() - t0), flush=True)
    if args.probe:
        for layer in layers:
            probe_field(masters[layer], grid, layer)


if __name__ == "__main__":
    main()
