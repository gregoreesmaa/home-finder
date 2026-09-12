"""Build network walk-access rasters for Group 14 public-safety layers (batch B5).

Usage (local 2026-09-12 snapshot ONLY — no network; inputs are local files):
  # 1. Extract Batch-5 features from the snapshot PBF (osmium reads local data):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      n/emergency=fire_hydrant n/amenity=fire_station n/amenity=police \\
      n/amenity=hospital -o /tmp/hf-b5-safety.pbf --overwrite
  osmium export /tmp/hf-b5-safety.pbf -o /tmp/hf-b5-safety.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      w/highway=motorway w/highway=trunk w/highway=primary \\
      -o /tmp/hf-b5-evac.pbf --overwrite
  osmium export /tmp/hf-b5-evac.pbf -o /tmp/hf-b5-evac.geojson
  # 2. Stamp one county raster per layer (75 m master; metro tiling is
  #    optional — the window endpoint falls back to county-only windows):
  python3 scripts/build/batch_b5_safety.py --layer hydrants \\
      --graph ~/hf-data/2026-09-12/osm/harju-foot-graph.json \\
      --poi /tmp/hf-b5-safety.geojson \\
      --out ~/hf-data/2026-09-12/osm/hydrants-walk-raster.json
  python3 scripts/build/batch_b5_safety.py --layer evac \\
      --graph ~/hf-data/2026-09-12/osm/harju-foot-graph.json \\
      --hwy /tmp/hf-b5-evac.geojson \\
      --out ~/hf-data/2026-09-12/osm/evac-walk-raster.json

Layers share the foot graph and 75 m county grid; only features, kernel
and scoring differ (see walk_raster.py). Calibration flags default to the
numbers locked in apps/web/lib/layers_batch5.ts (BATCH5_HALVES/DECAY);
the wire doc carries them so the server rejects stale rasters
(loadLayerRaster/matchesContract).

HONESTY: p13 is a police-proximity *estimate*, never measured crime (the
PPA CSVs are not in the snapshot); p315 scores hydrant proximity, not
flow rate; p78/p467 score station proximity, not measured times; p335
scores major-road proximity, not an official evacuation plan. The map
titles/legends/sources say so (pinned by layers_batch5.test.ts).

Scoring mirrors apps/web/lib/layers_batch5.ts exactly: unweighted count
kernels (evac: trunk/primary road-km), area-kind saturating scores
100*S/(S+half), null below 3 (unknown -> 255 -> red). Evac half is 2,
not pedinfra's 12: trunk/primary road-km is sparse (2330 ways county-
wide) versus dense footway networks, and a Tallinn-window histogram
with half=2 reads median 36 / max 71 (mid-ramp, corridors green),
while half=12 capped the whole window at 29 (nothing green).
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

# Locked calibration — must match BATCH5_HALVES / BATCH5_DECAY in
# apps/web/lib/layers_batch5.ts (pinned by test_batch_b5_safety.py).
LAYER_DEFAULTS = {
    "safety": {"sigma": 0.8, "half": 1},  # p13 police hinnang (21 stations)
    "emergency": {"sigma": 0.8, "half": 2},  # p78 fire(30)+hospital(21)
    "hydrants": {"sigma": 0.3, "half": 6},  # p315 hydrants (723, grocery-like)
    "evac": {"sigma": 0.5, "half": 2},  # p335 trunk/primary km (sparse network, see note)
    "dispatch": {"sigma": 0.8, "half": 3},  # p467 police+fire+hospital (~72)
}

B5_LAYERS = sorted(LAYER_DEFAULTS)

# Major egress roads for p335. highway=motorway is ~absent in Harjumaa
# (Estonia has no motorways) but stays listed so a future recount that
# finds motorways picks them up without a code change.
MAJOR_HIGHWAY = {"motorway", "trunk", "primary"}


def is_police(tags):
    """PPA station proxy for the p13 safety hinnang (NOT crime data)."""
    return isinstance(tags, dict) and tags.get("amenity") == "police"


def is_fire_station(tags):
    return isinstance(tags, dict) and tags.get("amenity") == "fire_station"


def is_hospital(tags):
    return isinstance(tags, dict) and tags.get("amenity") == "hospital"


def is_hydrant(tags):
    return isinstance(tags, dict) and tags.get("emergency") == "fire_hydrant"


def is_dispatch(tags):
    """Combined 112 services for p467 (police + fire + hospital)."""
    return (
        isinstance(tags, dict)
        and tags.get("amenity") in ("police", "fire_station", "hospital")
    )


def is_emergency(tags):
    """Fire + hospital for p78 response-proximity."""
    return (
        isinstance(tags, dict) and tags.get("amenity") in ("fire_station", "hospital")
    )


LAYER_PRED = {
    "safety": is_police,
    "emergency": is_emergency,
    "hydrants": is_hydrant,
    "dispatch": is_dispatch,
}

# ~20 m spatial dedupe cells (mirrors snapshot.ts DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def dedupe_points(feats):
    """Collapse co-located points (~20 m cells, first wins).

    Needed because osmium export emits untagged member nodes (skipped by
    the predicates) AND node+area pairs for the same station (a node
    inside its own building polygon): OSM-id dedupe in resolve_pois
    cannot see those pairs, and double-counting one station would double
    its kernel weight. Distinct hydrants >20 m apart (e.g. opposite
    street corners) stay separate — a cluster reads as more capacity.
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
    """Unweighted count kernel over POI points (safety/emergency/hydrants/dispatch)."""
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


def build_evac(graph, grid, half, sigma, hwy_path, name="evac"):
    """Road-km kernel over trunk/primary ways (p335 egress-density proxy).

    Per-vertex incident km aggregate onto 75 m cells first (conserves
    total km, <=54 m error — same as _length_feats in
    scripts/build-walk-raster.py), so stamping costs cells, not vertices.
    """
    pts, stats = wr.resolve_length_km(hwy_path, MAJOR_HIGHWAY)
    print("%s: %s" % (name, stats), flush=True)
    cells = {}
    for lon, lat, w in pts:
        k = grid.cell_of(lon, lat)
        if k is not None:
            cells[k] = cells.get(k, 0.0) + w
    feats = []
    for k, w in cells.items():
        lon, lat = grid.center_of(k)
        feats.append((lon, lat, w, None))
    print("%s: %d cell-sources" % (name, len(feats)), flush=True)
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("%s: snapped=%d euclid=%d" % (name, snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=B5_LAYERS)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--poi", default=None, help="safety geojson (point layers)")
    ap.add_argument("--hwy", default=None, help="major-road geojson (evac only)")
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
    if args.layer == "evac":
        if not args.hwy:
            ap.error("--hwy is required for evac")
        score_of, contract = build_evac(graph, grid, half, sigma, args.hwy)
    else:
        if not args.poi:
            ap.error("--poi is required for this layer")
        score_of, contract = build_points_layer(
            graph, grid, half, sigma, args.poi, args.layer, args.derived
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
