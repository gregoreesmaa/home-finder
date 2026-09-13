"""Build the network walk-access raster for the Group 6 heritage layer (batch G06).

Usage (local 2026-09-12 snapshot ONLY — no network; inputs are local files):
  # 1. Extract heritage features from the snapshot PBF (osmium reads local data).
  # MUST be nwr/ (nodes+ways+relations): manors/castles/forts are usually
  # mapped as building/area ways, and a node-only (n/) filter silently drops
  # them (issue: missing heritage on the Muinsusala map). resolve_pois
  # centroids every geometry and dedupe_points merges node+area pairs in
  # ~20 m cells.
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/heritage nwr/historic nwr/unesco -o /tmp/hf-g06-heritage.pbf --overwrite
  osmium export -u type_id /tmp/hf-g06-heritage.pbf -o /tmp/hf-g06-heritage.geojson
  # 2. Stamp the county raster (75 m master; metro tiling is optional —
  #    the window endpoint falls back to county-only windows):
  python3 scripts/build/batch_g06_heritage.py \\
      --graph ~/hf-data/2026-09-12/osm/harju-foot-graph.json \\
      --poi /tmp/hf-g06-heritage.geojson \\
      --derived ~/hf-data/2026-09-12/osm/derived-heritage.json \\
      --out ~/hf-data/2026-09-12/osm/heritage-walk-raster.json

The layer shares the foot graph and 75 m county grid with the sibling
batches; only features, kernel and scoring differ (see walk_raster.py).
Calibration flags default to the numbers locked in
apps/web/lib/layers_group06.ts (GROUP06_HALVES/GROUP06_DECAY); the wire
doc carries them so the server rejects stale rasters
(loadLayerRaster/matchesContract).

HONESTY: p72 scores mapped-heritage-object *proximity*, never an
official Muinsuskaitseamet conservation-zone decision (the registry is
not in the snapshot). The map title/legend/source say hinnang/proksi
(pinned by layers_group06.test.ts). p158/p272/p320/p351 ship NO map
(see GROUP06_NO_MAP in layers_group06.ts + services/scoring/
dims_group06.py) — a second heritage gradient would be fake precision.

Scoring mirrors apps/web/lib/layers_group06.ts exactly: unweighted
count kernel, area-kind saturating score 100*S/(S+half), null below 3
(unknown -> 255 -> red). half is 2, not 1: a lone rural manor then caps
at 100/3 = 33, not 50 — one manor is not a district. sigma 0.8 km is
the district coverage scale (like emergency/healthcare).
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

# Locked calibration — must match GROUP06_HALVES / GROUP06_DECAY in
# apps/web/lib/layers_group06.ts (pinned by test_batch_g06_heritage.py).
LAYER_DEFAULTS = {
    "heritage": {"sigma": 0.8, "half": 2},  # p72 mapped-heritage density (781 pts)
}


def is_heritage(tags):
    """Mapped-heritage proxy for the p72 hinnang (NOT registry data)."""
    return isinstance(tags, dict) and (
        "historic" in tags or "heritage" in tags or "unesco" in tags
    )


# ~20 m spatial dedupe cells (mirrors snapshot.ts DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def dedupe_points(feats):
    """Collapse co-located points (~20 m cells, first wins).

    Needed because osmium export emits untagged member nodes (skipped by
    the predicate) AND node+area pairs for the same object (a memorial
    node inside its own mapped ruin polygon): OSM-id dedupe in
    resolve_pois cannot see those pairs, and double-counting one object
    would double its kernel weight. Distinct objects >20 m apart stay
    separate — a cluster reads as a denser heritage area.
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


def build_points_layer(graph, grid, half, sigma, poi_path, derived=None):
    """Unweighted count kernel over heritage POI points (p72 hinnang)."""
    raw, stats = wr.resolve_pois(poi_path, is_heritage)
    feats = dedupe_points(raw)
    print("heritage: %d point features (%d raw, %d co-located merged)" % (len(feats), stats["kept"], stats["kept"] - len(feats)), flush=True)
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            # Unit weights: the area-kind Euclidean fallback splats these
            # with the layer half (mirrors build_poi_layer in
            # scripts/build-walk-raster.py).
            json.dump([{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats], f)
        print("heritage: wrote %d fallback points to %s" % (len(feats), derived))
    stamp = [(lon, lat, 1.0, None) for lon, lat, _ in feats]
    snapped, euclid = wr.stamp_sum(grid, graph, stamp, sigma, 4 * sigma)
    print("heritage: snapped=%d euclid=%d" % (snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True)
    ap.add_argument("--poi", required=True, help="heritage geojson (osmium export)")
    ap.add_argument("--derived", default=None, help="write fallback points here")
    ap.add_argument("--out", required=True)
    ap.add_argument("--half", type=float, default=None)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--step-m", type=float, default=75.0)
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--bbox", nargs=4, type=float, default=[23.3, 58.4, 25.5, 59.65])
    args = ap.parse_args()
    defs = LAYER_DEFAULTS["heritage"]
    half = args.half if args.half is not None else defs["half"]
    sigma = args.sigma if args.sigma is not None else defs["sigma"]

    t0 = time.time()
    graph = load_graph(args.graph)
    print("graph: %d verts (%.1fs)" % (len(graph), time.time() - t0), flush=True)
    grid = wr.Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    score_of, contract = build_points_layer(
        graph, grid, half, sigma, args.poi, args.derived
    )
    per, cap = contract.get("per", 0), contract.get("cap", 0)
    half, sigma_c = contract.get("half"), contract.get("sigma")
    if args.format == "split":
        prefix = args.out[:-5] if args.out.endswith(".json") else args.out
        wr.save_master(prefix, grid, score_of, half, sigma_c, per, cap)
        raw = open(prefix + ".u8", "rb").read()
        known = sum(1 for v in raw if v != 255)
        print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
        print(
            "wrote %s.json + .u8 (%.1f MB, %.1fs)"
            % (prefix, os.path.getsize(prefix + ".u8") / 1e6, time.time() - t0)
        )
    else:
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
