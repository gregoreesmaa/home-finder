"""Build the network walk-access rasters for the Group 6 leftover layers (batch G06B).

Usage (local 2026-09-12 snapshot ONLY — no network; inputs are local files):
  # 1. Extract material/antiques features from the snapshot PBF (osmium
  #    reads local data). MUST be nwr/ (nodes+ways+relations): plaster and
  #    wooden houses are usually mapped as building/area ways, and a
  #    node-only (n/) filter silently drops them (PR #118). resolve_pois
  #    centroids every geometry and dedupe_points merges node+area pairs
  #    in ~20 m cells.
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/building:material -o /tmp/hf-g06b-material.pbf --overwrite
  osmium export -u type_id /tmp/hf-g06b-material.pbf -o /tmp/hf-g06b-material.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/shop=antiques -o /tmp/hf-g06b-antiques.pbf --overwrite
  osmium export -u type_id /tmp/hf-g06b-antiques.pbf -o /tmp/hf-g06b-antiques.geojson
  # 2. Stamp the county rasters (75 m masters; metro tiling is optional —
  #    the window endpoint falls back to county-only windows):
  python3 scripts/build/batch_g06b_heritage.py --layer plaster \\
      --graph ~/hf-data/2026-09-12/osm/harju-foot-graph.json \\
      --poi /tmp/hf-g06b-material.geojson \\
      --derived ~/hf-data/2026-09-12/osm/derived-plaster.json \\
      --out ~/hf-data/2026-09-12/osm/plaster-walk-raster.json
  # (same for --layer antiques with the antiques geojson / derived-antiques.json,
  # and --layer woodfire with the material geojson / derived-woodfire.json)

The layers share the foot graph and 75 m county grid with the sibling
batches; only features, kernel and scoring differ (see walk_raster.py).
Calibration flags default to the numbers locked in
apps/web/lib/layers_group06b.ts (GROUP06B_HALVES/GROUP06B_DECAY); the wire
doc carries them so the server rejects stale rasters
(loadLayerRaster/matchesContract).

HONESTY: p352/p356 score MAPPED building-material proximity and p353
mapped antiques-shop proximity — never a Muinsuskaitseamet registry
verdict, a craft-availability guarantee, or a construction survey (the
registry is not in the snapshot; titles/legends say hinnang/proksi,
pinned by layers_group06b.test.ts). p354/p355/p359/p360 ship NO map
(see GROUP06B_NO_MAP in layers_group06b.ts + services/scoring/
dims_group06b.py).

Scoring mirrors apps/web/lib/layers_group06b.ts exactly:
* plaster/antiques: unweighted count kernel, area-kind saturating score
  100*S/(S+half), null below 3 (unknown -> 255 -> red).
* woodfire: INVERSE nearest-wood walk distance, 100*(1-2^(-d/half))
  (0 on the wooden house, 50 at half km, ->100 far away), via ONE
  multi-source Dijkstra (not per-feature stamps). Beyond 4 sigma the
  cell is unknown -> 255 -> red: with thin wood-material mapping this
  reads unknown rather than fake-safe (a wider sigma would paint
  untagged wooden districts confidently green — the worst error here).
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from walk_graph import SnapIndex, lonlat_of, load_graph  # noqa: E402

# Locked calibration — must match GROUP06B_HALVES / GROUP06B_DECAY in
# apps/web/lib/layers_group06b.ts (pinned by test_batch_g06b_heritage.py).
# woodfire half 0.21 == sigma*ln2 (the walk-km scoring 50).
LAYER_DEFAULTS = {
    "plaster": {"kind": "area", "sigma": 0.5, "half": 6},  # p352, 4396 pts
    "antiques": {"kind": "area", "sigma": 0.5, "half": 1},  # p353, 14 pts
    "woodfire": {"kind": "avoid", "sigma": 0.3, "half": 0.21},  # p356, 2376 pts
}


def is_plaster(tags):
    """building:material=plaster (p352 craft-need hinnang proxy)."""
    return isinstance(tags, dict) and tags.get("building:material") == "plaster"


def is_antiques(tags):
    """shop=antiques (p353 availability hinnang proxy)."""
    return isinstance(tags, dict) and tags.get("shop") == "antiques"


def is_wood(tags):
    """building:material=wood (p356 fire-spread hinnang proxy)."""
    return isinstance(tags, dict) and tags.get("building:material") == "wood"


PREDICATES = {"plaster": is_plaster, "antiques": is_antiques, "woodfire": is_wood}

# ~20 m spatial dedupe cells (mirrors snapshot.ts DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def dedupe_points(feats):
    """Collapse co-located points (~20 m cells, first wins).

    Needed because osmium export emits untagged member nodes (skipped by
    the predicate) AND node+area pairs for the same building: OSM-id
    dedupe in resolve_pois cannot see those pairs, and double-counting
    one house would double its kernel weight. Distinct houses >20 m
    apart stay separate — a row reads as a denser craft/fire area.
    """
    seen = {}
    for lon, lat, w in feats:
        k = (round(lon / DEDUPE_LON), round(lat / DEDUPE_LAT))
        if k not in seen:
            seen[k] = (lon, lat, w)
    return list(seen.values())


def write_derived(feats, layer, derived):
    """Unit-weighted fallback points for the Euclidean client path."""
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            # Unit weights: the area-kind Euclidean fallback splats these
            # with the layer half (mirrors build_poi_layer in
            # scripts/build-walk-raster.py); the avoid-kind fallback
            # scores nearest-point distance (see distanceField.ts).
            json.dump([{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats], f)
        print("%s: wrote %d fallback points to %s" % (layer, len(feats), derived))


def build_points_layer(layer, graph, grid, half, sigma, poi_path, derived=None):
    """Unweighted count kernel over POI points (p352/p353 hinnang)."""
    raw, stats = wr.resolve_pois(poi_path, PREDICATES[layer])
    feats = dedupe_points(raw)
    print("%s: %d point features (%d raw, %d co-located merged)"
          % (layer, len(feats), stats["kept"], stats["kept"] - len(feats)), flush=True)
    write_derived(feats, layer, derived)
    stamp = [(lon, lat, 1.0, None) for lon, lat, _ in feats]
    snapped, euclid = wr.stamp_sum(grid, graph, stamp, sigma, 4 * sigma)
    print("%s: snapped=%d euclid=%d" % (layer, snapped, euclid))

    def score_of(k, _grid=grid, _half=half):
        s = _grid.acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, _half)
        return sc if sc >= 3 else None

    return score_of, {"half": half, "sigma": sigma}


def build_avoid_layer(layer, graph, grid, half, sigma, poi_path, derived=None):
    """Inverse nearest-feature distance (p356 fire-spread hinnang).

    One multi-source Dijkstra from every snapped wooden house: each cell
    reads the walk distance to its NEAREST mapped wooden neighbour, then
    100*(1-2^(-d/half)). Cells past 4 sigma keep unknown (255, red) —
    with thin wood mapping, unknown is honest; fake-safe green is not.
    """
    raw, stats = wr.resolve_pois(poi_path, PREDICATES[layer])
    feats = dedupe_points(raw)
    print("%s: %d point features (%d raw, %d co-located merged)"
          % (layer, len(feats), stats["kept"], stats["kept"] - len(feats)), flush=True)
    write_derived(feats, layer, derived)
    idx = SnapIndex(graph)
    sources, skipped = [], 0
    for lon, lat, _ in feats:
        v, gap = idx.nearest(lon, lat, wr.SNAP_KM)
        if v is None:
            skipped += 1
        else:
            sources.append((v, gap))
    print("%s: snapped=%d skipped=%d (off-graph, stay unknown)" % (layer, len(sources), skipped))
    cutoff = 4 * sigma
    dist = wr.multi_source_dist(graph, sources, cutoff)
    best = {}
    for vk, dn in dist.items():
        k = grid.cell_of(*lonlat_of(vk))
        if k is None:
            continue
        prev = best.get(k)
        if prev is None or dn < prev:
            best[k] = dn
    print("%s: %d cells within %.1f km walk of mapped wood" % (layer, len(best), cutoff))

    def score_of(k, _best=best, _half=half):
        d = _best.get(k)
        if d is None:
            return None
        return 100 * (1 - pow(2, -d / _half))

    return score_of, {"half": half, "sigma": sigma}


BUILDERS = {"area": build_points_layer, "avoid": build_avoid_layer}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", choices=sorted(LAYER_DEFAULTS), required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--poi", required=True, help="material/antiques geojson (osmium export)")
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
    score_of, contract = BUILDERS[defs["kind"]](
        args.layer, graph, grid, half, sigma, args.poi, args.derived
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
