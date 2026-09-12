"""Batch B1 walk-access rasters: Group 11 amenity-proximity layers (issue #98).

Layers (parameters3.md section 5.11, all absolute 0-100, Harjumaa scope):
  pets       p86  pet-friendliness (leisure=dog_park, amenity=veterinary, shop=pet)
  community  p87  shared community amenities (amenity=community_centre/social_facility/townhall)
  culture    p89  cultural and community hubs (amenity=arts_centre/theatre/studio, tourism=museum/gallery)
  nightlife  p108 nightlife and culture (amenity=bar/pub/nightclub/cinema/casino)
  libraries  p313 local library system quality (amenity=library/public_bookcase)

Point-kernel layers in the grocery/healthcare style: unweighted counts from
the 2026-09-12 snapshot, stamped through the shared foot graph
(walk_raster.stamp_sum -- per-feature LOCAL Dijkstra, never a new
full-Harjumaa Dijkstra per layer), score = 100*S/(S+half), null below 3
(unknown stays 255, renders red, honest). County 75 m + metro 9.375 m
uint8 masters; the wire doc carries half/sigma so the server rejects stale
rasters (matchesContract in snapshot.ts).

Every tag above was verified present in
~/hf-data/2026-09-12/osm/harju-amenities.geojson before use (counts in
test_batch_b1_group11.py). No live Overpass/network anywhere here.

Rebuild (rasters are gitignored build artifacts; commit this builder +
tests + fixtures, never the .json/.u8 outputs):
  SNAP=~/hf-data/2026-09-12
  POI=$SNAP/osm/harju-amenities.geojson
  GRAPH=$SNAP/osm/harju-foot-graph.json
  for L in pets community culture nightlife libraries; do
    python3 scripts/build/batch_b1_group11.py --layer $L \\
      --graph $GRAPH --snap $SNAP --poi $POI \\
      --derived $SNAP/osm/derived-$L.json \\
      --out $SNAP/osm/$L-walk-raster.json \\
      --stamp-cache /tmp/b1-$L-county.stamp.pkl
    python3 scripts/build/batch_b1_group11.py --layer $L \\
      --graph $GRAPH --snap $SNAP --poi $POI \\
      --step-m 9.375 --bbox 24.3 59.28 25.2 59.56 --format split \\
      --out $SNAP/osm/$L-metro.json \\
      --stamp-cache /tmp/b1-$L-metro.stamp.pkl
  done
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

# tourism=museum/gallery disambiguation (documented judgment call): one
# snapshot feature -- Tallinna Opetajate Maja (amenity=community_centre +
# tourism=museum) -- matches both community and culture predicates. A museum
# is the stronger cultural signal, so culture claims tourism-tagged features
# and community explicitly excludes them. Layers stay disjoint (tested).
_CULTURE_TOURISM = ("museum", "gallery")

COMMUNITY_AMENITIES = ("community_centre", "social_facility", "townhall")
CULTURE_AMENITIES = ("arts_centre", "theatre", "studio")
NIGHTLIFE_AMENITIES = ("bar", "pub", "nightclub", "cinema", "casino")
LIBRARY_AMENITIES = ("library", "public_bookcase")


def is_pets(tags):
    """Dog parks, vets, pet shops. Unweighted: OSM has no reliable size/
    quality signal, so tiering would be fake precision (as grocery)."""
    return (
        isinstance(tags, dict)
        and (
            tags.get("leisure") == "dog_park"
            or tags.get("amenity") == "veterinary"
            or tags.get("shop") == "pet"
        )
    )


def is_community(tags):
    """Shared neighbourhood amenities. Excludes tourism=museum/gallery --
    those read as culture (see module docstring)."""
    return (
        isinstance(tags, dict)
        and tags.get("amenity") in COMMUNITY_AMENITIES
        and tags.get("tourism") not in _CULTURE_TOURISM
    )


def is_culture(tags):
    """Arts venues + museums/galleries. tourism= claims double-tagged
    features (e.g. Opetajate Maja) so community never double-counts."""
    return (
        isinstance(tags, dict)
        and (
            tags.get("amenity") in CULTURE_AMENITIES
            or tags.get("tourism") in _CULTURE_TOURISM
        )
    )


def is_nightlife(tags):
    """Evening-out venues. Deliberately NOT restaurants/cafes (dining is
    another group's scope) and not theatres/museums (p89 culture)."""
    return isinstance(tags, dict) and tags.get("amenity") in NIGHTLIFE_AMENITIES


def is_library(tags):
    """Libraries + public bookcases (both free book access; bookcases are
    too sparse to score alone: 23 county-wide)."""
    return isinstance(tags, dict) and tags.get("amenity") in LIBRARY_AMENITIES


PREDS = {
    "pets": is_pets,
    "community": is_community,
    "culture": is_culture,
    "nightlife": is_nightlife,
    "libraries": is_library,
}

# Tag keys kept on derived fallback points (bounded, debuggable; scoring
# ignores them -- area-kind counts need no weights). Superset of the
# split_layers.py ALLOW list, which predates shop/tourism layers.
DERIVED_TAG_KEYS = ("amenity", "leisure", "shop", "tourism")

# sigma: destination trips (culture/nightlife/libraries) read at the
# healthcare scale (0.8); neighbourhood amenities (pets/community) at a
# tighter 0.5. halves: anchor-calibrated 2026-09-12 so one adjacent feature
# reads ~70-85 while city medians stay in the 8-25 band of the built
# grocery/healthcare/parks rasters (see PR evidence). These numbers are
# locked with bonusSpecFor() in apps/web/lib/layers_batch1.ts -- the wire
# doc carries them and the server rejects mismatches.
LAYER_DEFAULTS = {
    # halves histogram-locked 2026-09-12: Tallinn known-cell median ~15
    # (libraries ~18), matching the built grocery (17) / healthcare (16) /
    # parks (17) / transit (15) rasters. Same unweighted-count semantics:
    # singletons read low-teens, clusters green (as grocery half=6).
    "pets": {"sigma": 0.5, "half": 5.7},
    "community": {"sigma": 0.5, "half": 3.3},
    "culture": {"sigma": 0.8, "half": 4.5},
    "nightlife": {"sigma": 0.8, "half": 7.5},
    "libraries": {"sigma": 0.8, "half": 3.0},
}


def resolve_with_tags(geojson_path, pred):
    """Like walk_raster.resolve_pois but keeps bounded tags on each point
    for the derived fallback file (scoring still uses unit weights)."""
    import json as _json

    out = []
    seen = set()
    feats = kept = 0
    with open(geojson_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line.startswith("{"):
                continue
            try:
                feat = _json.loads(line)
            except ValueError:
                continue
            if feat.get("type") != "Feature":
                continue
            feats += 1
            fid = feat.get("id")
            if fid is not None:
                if fid in seen:
                    continue
                seen.add(fid)
            props = feat.get("properties", {})
            if not pred(props):
                continue
            pt = wr._feature_point(feat.get("geometry"))
            if pt is None:
                continue
            kept += 1
            tags = {k: props[k] for k in DERIVED_TAG_KEYS if isinstance(props.get(k), str)}
            out.append((pt[0], pt[1], tags))
    return out, {"features": feats, "kept": kept}


def build_layer(graph, grid, half, sigma, poi_path, name, derived=None):
    pts, stats = resolve_with_tags(poi_path, PREDS[name])
    print("%s: %s" % (name, stats), flush=True)
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {"lon": lon, "lat": lat, "a": 1, **({"tags": tags} if tags else {})}
                    for lon, lat, tags in pts
                ],
                f,
            )
        print("%s: wrote %d fallback points to %s" % (name, len(pts), derived))
    feats = [(lon, lat, 1.0, None) for lon, lat, _ in pts]
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("%s: snapped=%d euclid=%d" % (name, snapped, euclid))

    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= 3 else None

    return score_of, {"half": half, "sigma": sigma}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=sorted(LAYER_DEFAULTS))
    ap.add_argument("--graph", required=True)
    ap.add_argument("--snap", required=True)
    ap.add_argument("--poi", required=True, help="shop/amenity GeoJSON (snapshot)")
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
    half = args.half if args.half is not None else defs["half"]
    sigma = args.sigma if args.sigma is not None else defs["sigma"]

    t0 = time.time()
    graph = load_graph(args.graph)
    print("graph: %d verts (%.1fs)" % (len(graph), time.time() - t0), flush=True)
    grid = wr.Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    cache = args.stamp_cache or (args.out + ".stamp.pkl")
    if os.path.exists(cache):
        grid.acc, grid.bits = wr.load_stamp(cache)
        print("stamp: loaded %s (skipped Dijkstra)" % cache, flush=True)

        def score_of(k, _half=half):
            s = grid.acc.get(k)
            if not s:
                return None
            sc = wr.saturate(s, _half)
            return sc if sc >= 3 else None

        contract = {"half": half, "sigma": sigma}
    else:
        score_of, contract = build_layer(
            graph, grid, half, sigma, args.poi, args.layer, args.derived
        )
        wr.save_stamp(cache, grid.acc, grid.bits)
        print("stamp: saved %s" % cache, flush=True)
    per, cap = 0, 0
    half_c, sigma_c = contract["half"], contract["sigma"]
    if args.format == "split":
        prefix = args.out[:-5] if args.out.endswith(".json") else args.out
        wr.save_master(prefix, grid, score_of, half_c, sigma_c, per, cap)
        raw = open(prefix + ".u8", "rb").read()
        known = sum(1 for v in raw if v != 255)
        print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
        print(
            "wrote %s.json + .u8 (%.1f MB, %.1fs)"
            % (prefix, os.path.getsize(prefix + ".u8") / 1e6, time.time() - t0)
        )
    else:
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
