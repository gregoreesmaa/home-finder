"""Build the network walk-access raster for the Group 2 batch-B lift proxy (p196).

Usage (local 2026-09-12 snapshot ONLY — no network; inputs are local files):
  # 1. Extract leveled buildings from the snapshot PBF (osmium reads local data).
  # MUST be nwr/ (nodes+ways+relations): high-rises are usually mapped as
  # building/area ways, and a node-only (n/) filter silently drops nearly
  # all of them. resolve_pois centroids every geometry and dedupe_points
  # merges node+area pairs in ~20 m cells.
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/building -o /tmp/hf-g02b-buildings.pbf --overwrite
  osmium export -u type_id /tmp/hf-g02b-buildings.pbf -o /tmp/hf-g02b-buildings.geojson
  # 2. Stamp the county raster (75 m master; no metro master by documented
  #    decision — the window endpoint serves county everywhere):
  python3 scripts/build/batch_g02b_lift.py --layer liftproxy \\
      --graph ~/hf-data/2026-09-12/osm/harju-foot-graph.json \\
      --poi /tmp/hf-g02b-buildings.geojson \\
      --derived ~/hf-data/2026-09-12/osm/derived-liftproxy.json \\
      --out ~/hf-data/2026-09-12/osm/liftproxy-walk-raster.json

The layer shares the foot graph and 75 m county grid; only features differ
(see walk_raster.py). Calibration flags default to the numbers locked in
apps/web/lib/layers_group02b.ts (G02B_HALVES/G02B_DECAY); the wire doc
carries them so the server rejects stale rasters
(loadLayerRaster/matchesContract).

HONESTY: the EHR registries are NOT in the snapshot (registries/ is
empty), so this is a mapped-high-rise *estimate*, never measured EHR
lift data. 5+ storeys is the lift-plausible cutoff (Estonian practice:
new 5+ storey blocks have lifts; older 5-storey panel blocks often do
NOT — the layer scores high-rise density, never a per-flat promise).
Map titles/legends/sources say so (pinned by layers_group02b.test.ts).

Scoring mirrors apps/web/lib/layers_group02b.ts exactly: unweighted
count kernel, area-kind saturating score 100*S/(S+half), null below 3
(unknown -> 255 -> red). Mapped high-rises are hyper-clustered (panel
districts vs detached suburbs), so the field is bimodal BY DESIGN:
half=2 keeps a lone tower visible (100*1/3 = 33, amber — the B5
safety-layer lone-station idea) while Lasnamäe/Mustamäe/Õismäe
saturate green. Tallinn-window Euclidean histogram (2026-09-12):
median 0.2 / p75 72.8 / p90 91.2 / max 97.7, 34% of cells above 30.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from walk_graph import load_graph  # noqa: E402

# Locked calibration — must match G02B_HALVES / G02B_DECAY in
# apps/web/lib/layers_group02b.ts (pinned by test_batch_g02b.py).
LAYER_DEFAULTS = {
    "liftproxy": {"sigma": 0.3, "half": 2},  # p196 high-rise hinnang (5023 levels>=5)
}

G02B_LAYERS = sorted(LAYER_DEFAULTS)

#: Minimum mapped storeys counted as lift-plausible (see module docstring).
LIFT_MIN_LEVELS = 5


def levels_of(tags):
    """First building:levels value as float, else None (never throws)."""
    if not isinstance(tags, dict):
        return None
    raw = tags.get("building:levels")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return float(raw.split(";")[0].strip())
    except ValueError:
        return None


def is_liftproxy(tags):
    """Mapped high-rise proxy for the p196 lift hinnang (NOT EHR lift data)."""
    lv = levels_of(tags)
    return lv is not None and lv >= LIFT_MIN_LEVELS


LAYER_PRED = {
    "liftproxy": is_liftproxy,
}

# ~20 m spatial dedupe cells (mirrors snapshot.ts DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def dedupe_points(feats):
    """Collapse co-located points (~20 m cells, first wins).

    Needed because osmium export emits node+area pairs for the same
    building: OSM-id dedupe in resolve_pois cannot see those pairs, and
    double-counting one tower would double its kernel weight. Distinct
    towers >20 m apart (e.g. opposite sides of a panel-block yard) stay
    separate — a cluster reads as more lift-dense.
    """
    seen = {}
    for lon, lat, w in feats:
        k = (round(lon / DEDUPE_LON), round(lat / DEDUPE_LAT))
        if k not in seen:
            seen[k] = (lon, lat, w)
    return list(seen.values())


def _area_score(grid, half):
    """Mirror of the grocery/healthcare scorer: saturate, null below 3."""

    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= 3 else None

    return score_of


def build_points_layer(graph, grid, half, sigma, poi_path, name, derived=None):
    """Unweighted count kernel over high-rise points (p196 lift hinnang)."""
    raw, stats = wr.resolve_pois(poi_path, LAYER_PRED[name])
    feats = dedupe_points(raw)
    print("%s: %d point features (%d raw, %d co-located merged)" % (name, len(feats), stats["kept"], stats["kept"] - len(feats)), flush=True)
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            # Unit weights: the area-kind Euclidean fallback splats these
            # with the layer half (mirrors build_poi_layer in
            # scripts/build-walk-raster.py).
            json.dump([{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats], f)
        print("%s: wrote %d fallback points to %s" % (name, len(feats), derived))
    stamp = [(lon, lat, 1.0, None) for lon, lat, _ in feats]
    snapped, euclid = wr.stamp_sum(grid, graph, stamp, sigma, 4 * sigma)
    print("%s: snapped=%d euclid=%d" % (name, snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=G02B_LAYERS)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--poi", default=None, help="leveled-buildings geojson")
    ap.add_argument("--derived", default=None, help="write fallback points here")
    ap.add_argument("--out", required=True)
    ap.add_argument("--half", type=float, default=None)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--step-m", type=float, default=75.0)
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--bbox", nargs=4, type=float, default=[23.3, 58.4, 25.5, 59.65])
    args = ap.parse_args()
    defs = LAYER_DEFAULTS[args.layer]
    half = args.half if args.half is not None else defs["half"]
    sigma = args.sigma if args.sigma is not None else defs["sigma"]

    t0 = time.time()
    graph = load_graph(args.graph)
    print("graph: %d verts (%.1fs)" % (len(graph), time.time() - t0), flush=True)
    grid = wr.Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    if not args.poi:
        ap.error("--poi is required for this layer")
    score_of, contract = build_points_layer(
        graph, grid, half, sigma, args.poi, args.layer, args.derived
    )
    per, cap = contract.get("per", 0), contract.get("cap", 0)
    half, sigma_c = contract.get("half"), contract.get("sigma")
    doc = wr.encode_raster(grid, score_of, per=per, cap=cap, half=half, sigma=sigma_c)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    import base64

    raw = base64.b64decode(doc["data"])
    known = sum(1 for v in raw if v != 255)
    print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
    print("wrote %s (%.1f MB, %.1fs)" % (args.out, os.path.getsize(args.out) / 1e6, time.time() - t0))


if __name__ == "__main__":
    main()
