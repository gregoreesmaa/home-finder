"""Batch G11D walk-access rasters: Group 11 leftover-B layers (issue #135).

Layers (parameters3.md section 5.11, all absolute 0..100, Harjumaa scope):
  mailbox      p346 mailbox placement/security (amenity=post_box/letter_box)
  postal       p470 mail delivery location (amenity=post_office/parcel_locker)
  alley        p419 alleyway access (service=alley way-km)
  trailprivacy p466 trail privacy loss, INVERTED (highway=path way-km)

p317 (park maintenance/enforcement) is a DOCUMENTED NO-MAP: no OSM tag
encodes upkeep/enforcement quality, so any gradient would be fake
precision (AGENTS.md section 7.2, OTA PR #131 precedent). No builder
branch, no registry entry; the scorer stub in dims_group11.py stands.

Point layers stamp unweighted counts through the shared foot graph
(walk_raster.stamp_sum -- per-feature LOCAL Dijkstra), score =
100*S/(S+half), null below 3 (unknown stays 255, renders red, honest).
Way layers stamp per-vertex incident km aggregated onto 75 m cells first
(conserves total km, same as build_evac in batch_b5_safety.py), so
stamping costs cells, not vertices.

trailprivacy inverts through quiet_score = 100*half/(S+half): dense
trail networks read exposed (low), trail-free walk-network cells read
FAR_SCORE 90 -- the same 90 dim_trail_privacy returns for unmapped
surroundings (never a perfect 100: unmapped trails may exist). Cells the
foot graph never reaches (open water, outside the network) stay null/255
(red = honestly unknown, like every other layer). Only highway=path
counts -- urban footway/cycleway sidewalks are excluded, otherwise every
city cell would read exposed (same rule as dim_trail_privacy).

Every tag below was verified present in the snapshot before use
(osmium over harjumaa-260911.osm.pbf; Tallinn bbox 24.5-24.9/59.35-59.5
in brackets): post_box 122 nodes [75], letter_box 4 [1], post_office
76n+5w [13], parcel_locker 523n+3w [406], service=alley 34 ways [51/59
exported features touch Tallinn], highway=path 10746 ways (dense in
Tallinn). No live Overpass/network anywhere here.

County 75 m uint8 masters only (no metro: sparse count kernels and the
smooth privacy field gain no honest precision from 9.375 m cells --
B5/GENV precedent, windows fall back to county cleanly); the wire doc
carries half/sigma so the server rejects stale rasters
(matchesContract in snapshot.ts). trailprivacy carries halfM in METRES
on the wire (1500) so the quiet contract echoes bonusSpecFor exactly.

Rebuild (rasters are gitignored build artifacts; commit this builder +
tests + fixtures, never the .json outputs):
  SNAP=~/hf-data/2026-09-12
  GRAPH=$SNAP/osm/harju-foot-graph.json
  POI=$SNAP/osm/harju-amenities.geojson
  osmium tags-filter $SNAP/osm/harjumaa-260911.osm.pbf \\
      w/service=alley -o /tmp/hf-g11d-alley.pbf --overwrite
  osmium export /tmp/hf-g11d-alley.pbf -o /tmp/hf-g11d-alley.geojson
  osmium tags-filter $SNAP/osm/harjumaa-260911.osm.pbf \\
      w/highway=path -o /tmp/hf-g11d-path.pbf --overwrite
  osmium export /tmp/hf-g11d-path.pbf -o /tmp/hf-g11d-path.geojson
  for L in mailbox postal; do
    python3 scripts/build/batch_g11d_leftovers.py --layer $L \\
      --graph $GRAPH --snap $SNAP --poi $POI \\
      --derived $SNAP/osm/derived-$L.json \\
      --out $SNAP/osm/$L-walk-raster.json \\
      --stamp-cache /tmp/g11d-$L-county.stamp.pkl
  done
  python3 scripts/build/batch_g11d_leftovers.py --layer alley \\
    --graph $GRAPH --snap $SNAP --hwy /tmp/hf-g11d-alley.geojson \\
    --derived $SNAP/osm/derived-alley.json \\
    --out $SNAP/osm/alley-walk-raster.json \\
    --stamp-cache /tmp/g11d-alley-county.stamp.pkl
  python3 scripts/build/batch_g11d_leftovers.py --layer trailprivacy \\
    --graph $GRAPH --snap $SNAP --hwy /tmp/hf-g11d-path.geojson \\
    --derived $SNAP/osm/derived-trailprivacy.json \\
    --out $SNAP/osm/trailprivacy-walk-raster.json \\
    --stamp-cache /tmp/g11d-trailprivacy-county.stamp.pkl
# restart the map server afterwards -- masters are cached per process.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from batch_b5_safety import dedupe_points  # noqa: E402  (~20 m, first wins)
from walk_graph import load_graph, lonlat_of  # noqa: E402

#: Trail-free walk-network cells read private-but-never-perfect (matches
#: dim_trail_privacy's unmapped fallback and G11D_TRAIL_FAR_SCORE in
#: apps/web/lib/layers_group11d.ts -- the vitest suite locks the 90).
FAR_SCORE = 90

#: Noise floor shared with the point/area layers (unknown stays 255).
NULL_BELOW = 3

# sigma: neighbourhood amenities (mailbox) and short-range access/privacy
# effects (alley/trailprivacy) read at 0.5; destination trips (postal) at
# the healthcare scale 0.8. halves: anchor-calibrated 2026-09-12 so one
# adjacent feature reads ~70-85 while Tallinn known-cell medians sit
# mid-ramp (see the probe numbers in the PR). Locked with G11D_BONUS in
# apps/web/lib/layers_group11d.ts -- the wire doc carries them and the
# server rejects mismatches. trailprivacy's wire half is halfM in METRES.
LAYER_DEFAULTS = {
    # 126 boxes county-wide (75 in Tallinn): Tallinn known-cell median
    # 20 at half 2.5 (p10=5/p90=46), singletons read ~29.
    "mailbox": {"sigma": 0.5, "half": 2.5},
    # ~600 offices/lockers (406 lockers in Tallinn): median 25 at half
    # 12 (p10=6/p90=52); lone lockers read ~8, mall clusters green.
    "postal": {"sigma": 0.8, "half": 12.0},
    # 34 ways: sparse rear-lane convenience (median 14 at half 0.3),
    # absence stays unknown.
    "alley": {"sigma": 0.5, "half": 0.3},
    # Dense path network: half in TRAIL km, wire half in metres (quiet).
    "trailprivacy": {"sigma": 0.5, "half_km": 1.5, "wire_half": 1500},
}

G11D_LAYERS = sorted(LAYER_DEFAULTS)

#: Tags kept on derived fallback points (bounded; scoring uses unit
#: weights for points, km weights for way samples).
DERIVED_TAG_KEYS = ("amenity", "highway", "service")


def is_mailbox(tags):
    """Post boxes + letter boxes (same merge as dim_letterbox's kind;
    letter_box alone is 4 objects county-wide -- too sparse to score)."""
    return isinstance(tags, dict) and tags.get("amenity") in ("post_box", "letter_box")


def is_postal(tags):
    """Post offices + parcel lockers (same merge as dim_postal:
    parcel_locker -> post_office)."""
    return isinstance(tags, dict) and tags.get("amenity") in ("post_office", "parcel_locker")


LAYER_PRED = {
    "mailbox": is_mailbox,
    "postal": is_postal,
}


def resolve_service_km(geojson_path, key="service", value="alley"):
    """Per-vertex incident km for ways tagged key=value (alley resolver).

    Mirrors walk_raster.resolve_length_km (which only filters the highway
    key): each edge's length splits half/half over its endpoints, so the
    vertex weights sum to the network's total km (conserved, tested).
    """
    weights = {}
    kept = feats = 0
    with open(geojson_path, encoding="utf-8") as f:
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
            props = feat.get("properties", {})
            if not isinstance(props, dict) or props.get(key) != value:
                continue
            kept += 1
            for ring in wr._rings_of(feat.get("geometry")):
                pts = [(float(x), float(y)) for x, y in ring if isinstance(x, (int, float))]
                for i in range(len(pts) - 1):
                    (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                    half = wr.hav_km(x1, y1, x2, y2) / 2
                    if half <= 0:
                        continue
                    a, b = wr.key_of(x1, y1), wr.key_of(x2, y2)
                    weights[a] = weights.get(a, 0.0) + half
                    weights[b] = weights.get(b, 0.0) + half
    out = [(lonlat_of(k)[0], lonlat_of(k)[1], w) for k, w in weights.items()]
    return out, {"features": feats, "kept": kept}


def quiet_score(trail_km, half_km):
    """Inverted trail-privacy score: dense trails read exposed (low),
    trail-free reads FAR_SCORE (never 100 -- unmapped trails may exist).
    Mirrors g11dQuietScore() in layers_group11d.ts."""
    if not (trail_km > 0):
        return float(FAR_SCORE)
    return 100.0 * half_km / (trail_km + half_km)


def _area_score(grid, half):
    """Mirror of the grocery/healthcare scorer: saturate, null below 3."""

    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= NULL_BELOW else None

    return score_of


def _quiet_score_fn(grid, half_km, land_cells):
    """Inverted scorer for trailprivacy (see quiet_score). Cells the foot
    graph never reaches (open water) stay null -- red means honestly
    unknown there, like every other layer."""

    def score_of(k):
        s = grid.acc.get(k)
        if s:
            return quiet_score(s, half_km)
        if k in land_cells:
            return float(FAR_SCORE)
        return None

    return score_of


def build_points_layer(graph, grid, half, sigma, poi_path, name, derived=None):
    """Unweighted count kernel over POI points (mailbox/postal)."""
    raw, stats = wr.resolve_pois(poi_path, LAYER_PRED[name])
    feats = dedupe_points(raw)
    print(
        "%s: %d point features (%d raw, %d co-located merged)"
        % (name, len(feats), stats["kept"], stats["kept"] - len(feats)),
        flush=True,
    )
    if derived:
        import json as _json

        with open(derived, "w", encoding="utf-8") as f:
            # Unit weights: the area-kind Euclidean fallback splats these
            # with the layer half.
            _json.dump([{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats], f)
        print("%s: wrote %d fallback points to %s" % (name, len(feats), derived))
    stamp = [(lon, lat, 1.0, None) for lon, lat, _ in feats]
    snapped, euclid = wr.stamp_sum(grid, graph, stamp, sigma, 4 * sigma)
    print("%s: snapped=%d euclid=%d" % (name, snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def _cell_feats(pts, grid):
    """Aggregate per-vertex km onto grid cells (conserves total km)."""
    cells = {}
    for lon, lat, w in pts:
        k = grid.cell_of(lon, lat)
        if k is not None:
            cells[k] = cells.get(k, 0.0) + w
    return [(grid.center_of(k)[0], grid.center_of(k)[1], w, None) for k, w in cells.items()]


def build_way_layer(graph, grid, half, sigma, hwy_path, name, resolver, derived=None):
    """Way-km density kernel (alley: area kind over service=alley km)."""
    pts, stats = resolver(hwy_path)
    print("%s: %s" % (name, stats), flush=True)
    total_km = sum(w for _, _, w in pts)
    feats = _cell_feats(pts, grid)
    print("%s: %.3f km over %d cells" % (name, total_km, len(feats)), flush=True)
    if derived:
        import json as _json

        with open(derived, "w", encoding="utf-8") as f:
            # Way midpoints for the overlay (unit scroll sample; the
            # raster holds the full field).
            _json.dump(
                [{"lon": lon, "lat": lat, "a": round(w, 4)} for lon, lat, w, _ in feats], f
            )
        print("%s: wrote %d fallback points to %s" % (name, len(feats), derived))
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("%s: snapped=%d euclid=%d" % (name, snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def land_cells_of(graph, grid):
    """Grid cells the foot network reaches (land mask for the quiet
    background: trail-free land reads FAR_SCORE, open water stays null)."""
    cells = set()
    for vk in graph.adj:
        lon, lat = lonlat_of(vk)
        k = grid.cell_of(lon, lat)
        if k is not None:
            cells.add(k)
    return cells


def build_trailprivacy(graph, grid, half_km, wire_half, sigma, hwy_path, derived=None):
    """Inverted way-km kernel over highway=path (see quiet_score)."""
    pts, stats = wr.resolve_length_km(hwy_path, {"path"})
    print("trailprivacy: %s" % (stats,), flush=True)
    total_km = sum(w for _, _, w in pts)
    feats = _cell_feats(pts, grid)
    print("trailprivacy: %.3f km over %d cells" % (total_km, len(feats)), flush=True)
    if derived:
        import json as _json

        # Overlay sample: deterministic stride over stamped cells (the
        # full vertex set would be ~100k points of JSON).
        stride = max(1, len(feats) // 15000)
        sample = feats[::stride]
        with open(derived, "w", encoding="utf-8") as f:
            _json.dump(
                [{"lon": lon, "lat": lat, "a": round(w, 4)} for lon, lat, w, _ in sample],
                f,
            )
        print("trailprivacy: wrote %d fallback points to %s" % (len(sample), derived))
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("trailprivacy: snapped=%d euclid=%d" % (snapped, euclid))
    land = land_cells_of(graph, grid)
    print("trailprivacy: land cells=%d" % len(land), flush=True)
    return _quiet_score_fn(grid, half_km, land), {"half": wire_half, "sigma": sigma}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=G11D_LAYERS)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--snap", required=True)
    ap.add_argument("--poi", default=None, help="amenity GeoJSON (mailbox/postal)")
    ap.add_argument("--hwy", default=None, help="way GeoJSON (alley/trailprivacy)")
    ap.add_argument("--derived", default=None, help="write fallback points here")
    ap.add_argument("--stamp-cache", default=None)
    ap.add_argument("--half", type=float, default=None)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--step-m", type=float, default=75.0)
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--bbox", nargs=4, type=float, default=[23.3, 58.4, 25.5, 59.65])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    defs = LAYER_DEFAULTS[args.layer]
    sigma = args.sigma if args.sigma is not None else defs["sigma"]

    t0 = time.time()
    graph = load_graph(args.graph)
    print("graph: %d verts (%.1fs)" % (len(graph), time.time() - t0), flush=True)
    grid = wr.Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    cache = args.stamp_cache or (args.out + ".stamp.pkl")
    cached = os.path.exists(cache)
    if cached:
        grid.acc, grid.bits = wr.load_stamp(cache)
        print("stamp: loaded %s (skipped Dijkstra)" % cache, flush=True)

    if args.layer in LAYER_PRED:
        if not args.poi and not cached:
            ap.error("--poi is required for point layers")
        half = args.half if args.half is not None else defs["half"]
        if cached:
            score_of, contract = _area_score(grid, half), {"half": half, "sigma": sigma}
        else:
            score_of, contract = build_points_layer(
                graph, grid, half, sigma, args.poi, args.layer, args.derived
            )
    elif args.layer == "alley":
        if not args.hwy and not cached:
            ap.error("--hwy is required for alley")
        half = args.half if args.half is not None else defs["half"]
        if cached:
            score_of, contract = _area_score(grid, half), {"half": half, "sigma": sigma}
        else:
            score_of, contract = build_way_layer(
                graph,
                grid,
                half,
                sigma,
                args.hwy,
                "alley",
                resolve_service_km,
                args.derived,
            )
    else:
        if not args.hwy and not cached:
            ap.error("--hwy is required for trailprivacy")
        half_km = args.half if args.half is not None else defs["half_km"]
        if cached:
            land = land_cells_of(graph, grid)
            score_of = _quiet_score_fn(grid, half_km, land)
            contract = {"half": defs["wire_half"], "sigma": sigma}
        else:
            score_of, contract = build_trailprivacy(
                graph, grid, half_km, defs["wire_half"], sigma, args.hwy, args.derived
            )
    if cached:
        print("stamp: reusing cached accumulation", flush=True)
    else:
        wr.save_stamp(cache, grid.acc, grid.bits)
        print("stamp: saved %s" % cache, flush=True)
    per, cap = 0, 0
    half_c, sigma_c = contract["half"], contract["sigma"]
    doc = wr.encode_raster(grid, score_of, per=per, cap=cap, half=half_c, sigma=sigma_c)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    import base64

    raw = base64.b64decode(doc["data"])
    known = sum(1 for v in raw if v != 255)
    print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
    print("wrote %s (%.1f MB, %.1fs)" % (args.out, os.path.getsize(args.out) / 1e6, time.time() - t0))


if __name__ == "__main__":
    main()
