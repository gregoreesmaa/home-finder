"""Batch G11C walk-access rasters: Group 11 amenity leftovers A (issue #134).

Layers (parameters3.md section 5.11, all absolute 0-100, Harjumaa scope):
  schoolbus   p88   school-bus access, HONEST PROXY (route=school_bus has ~2
                    uses globally -- real routes are unmapped; this stamps
                    amenity=school gated on a transit stop within 500 m,
                    the exact dim_school_bus scorer logic)
  recspecial  p101  specialized recreation (leisure=sports_centre/sports_hall/
                    stadium/swimming_pool/water_park/ice_rink/golf_course/
                    fitness_centre; generic parks/playgrounds stay in p19)
  medspecial  p124  specialized medical (amenity=hospital/dentist; GP-level
                    pharmacy/doctors stay in the p20 healthcare layer)
  worship     p169  philosophical/religious proximity
                    (amenity=place_of_worship/monastery)
  forage      p190  foraging/natural resources (landuse=forest,
                    natural=wood/scrub/heath polygon centroids + nodes)

Point-kernel layers in the grocery/healthcare/B1 style: unweighted counts
from the 2026-09-12 snapshot, stamped through the shared foot graph
(walk_raster.stamp_sum -- per-feature LOCAL Dijkstra, never a new
full-Harjumaa Dijkstra per layer), score = 100*S/(S+half), null below 3
(unknown stays 255, renders red, honest). County 75 m masters only (no
metro -- smooth kernels need no 9 m cells; the window route serves county
everywhere, B5 precedent); the wire doc carries half/sigma so the server
rejects stale rasters (matchesContract in snapshot.ts).

Every tag above was verified present in the snapshot before use (counts in
test_batch_g11c.py). No live Overpass/network anywhere here.

Rebuild (rasters are gitignored build artifacts; commit this builder +
tests, never the .json outputs):
  SNAP=~/hf-data/2026-09-12
  POI=$SNAP/osm/harju-amenities.geojson
  GRAPH=$SNAP/osm/harju-foot-graph.json
  # one-time forest source export (amenities sweep drops forest polygons):
  osmium tags-filter $SNAP/osm/harjumaa-260911.osm.pbf nwr/landuse=forest \\
      nwr/natural=wood nwr/natural=scrub nwr/natural=heath \\
      -o $SNAP/osm/derived-forest.geojson --overwrite
  for L in schoolbus recspecial medspecial worship forage; do
    python3 scripts/build/batch_g11c_amenity.py --layer $L \\
      --graph $GRAPH --snap $SNAP --poi $POI \\
      --derived $SNAP/osm/derived-$L.json \\
      --out $SNAP/osm/$L-walk-raster.json \\
      --stamp-cache /tmp/g11c-$L-county.stamp.pkl
  done
"""

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from walk_graph import load_graph  # noqa: E402

REC_LEISURE = (
    "sports_centre",
    "sports_hall",
    "stadium",
    "swimming_pool",
    "water_park",
    "ice_rink",
    "golf_course",
    "fitness_centre",
)

MED_AMENITIES = ("hospital", "dentist")

WORSHIP_AMENITIES = ("place_of_worship", "monastery")

# Transit-stop predicate for the p88 school gate (any scheduled-stop kind:
# bus, tram, train all serve school trips; mirrors the transit TAGS scope).
STOP_PUBLIC_TRANSPORT = ("platform", "stop_position", "station")
STOP_RAILWAY = ("tram_stop", "station", "halt")


def is_school(tags):
    """amenity=school only (kindergartens run no school bus)."""
    return isinstance(tags, dict) and tags.get("amenity") == "school"


def is_stop(tags):
    """Any scheduled transit stop (bus/tram/train)."""
    return isinstance(tags, dict) and (
        tags.get("highway") == "bus_stop"
        or tags.get("public_transport") in STOP_PUBLIC_TRANSPORT
        or tags.get("railway") in STOP_RAILWAY
    )


def is_recspecial(tags):
    """Specialised sports tier only (generic parks/playgrounds excluded)."""
    return isinstance(tags, dict) and tags.get("leisure") in REC_LEISURE


def is_medspecial(tags):
    """Hospital or dentist (sparse specialist tier, not GP-level care)."""
    return isinstance(tags, dict) and tags.get("amenity") in MED_AMENITIES


def is_worship(tags):
    """Churches, chapels, monasteries (all faiths, one kind)."""
    return isinstance(tags, dict) and tags.get("amenity") in WORSHIP_AMENITIES


def is_forage_tags(tags):
    """Forest/scrub/heath tags (node features; polygons come from the PBF
    export via read_forest_points)."""
    return isinstance(tags, dict) and (
        tags.get("landuse") == "forest" or tags.get("natural") in ("wood", "scrub", "heath")
    )


PREDS = {
    "recspecial": is_recspecial,
    "medspecial": is_medspecial,
    "worship": is_worship,
}

# Tag keys kept on derived fallback points (bounded, debuggable; scoring
# ignores them -- area-kind counts need no weights). natural/landuse ride
# along for forage provenance; the web allowlist filters at serve time.
DERIVED_TAG_KEYS = ("amenity", "leisure", "healthcare", "religion", "natural", "landuse")

# sigma: destination trips (recspecial/medspecial/worship) read at the
# healthcare scale (0.8); neighbourhood access (schoolbus/forage) at a
# tighter 0.5. halves: anchor-calibrated 2026-09-12 so one adjacent feature
# reads low-teens-to-30s while city medians sit mid-ramp (see build probes
# in the PR). Locked with G11C_BONUS in apps/web/lib/layers_group11c.ts --
# the wire doc carries them and the server rejects mismatches.
LAYER_DEFAULTS = {
    "schoolbus": {"sigma": 0.5, "half": 4.0},
    "recspecial": {"sigma": 0.8, "half": 8.0},
    "medspecial": {"sigma": 0.8, "half": 5.0},
    "worship": {"sigma": 0.8, "half": 2.5},
    "forage": {"sigma": 0.5, "half": 12.0},
}

LAYER_IDS = tuple(sorted(LAYER_DEFAULTS))

# p88 gate: crow-flies km within which a school counts as stop-served
# (mirrors dims_group11.dim_school_bus: bus_stop kind within 500 m).
SCHOOLBUS_GATE_KM = 0.5


def _hav_km(lon1, lat1, lon2, lat2):
    return math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57)


def _iter_features(geojson_path):
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
            yield feat


def resolve_with_tags(geojson_path, pred):
    """Like batch_b1 resolve_with_tags: centroid points + bounded tags."""
    out = []
    seen = set()
    feats = kept = 0
    for feat in _iter_features(geojson_path):
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


def resolve_schoolbus(geojson_path):
    """Schools gated on a transit stop within SCHOOLBUS_GATE_KM.

    Returns (gated_points, stats). The gate is crow-flies at build time
    (documented); the walk kernel then measures true walking distance.
    """
    schools = []
    stops = []
    feats = 0
    for feat in _iter_features(geojson_path):
        feats += 1
        props = feat.get("properties", {})
        want_s = is_school(props)
        want_t = is_stop(props)
        if not (want_s or want_t):
            continue
        pt = wr._feature_point(feat.get("geometry"))
        if pt is None:
            continue
        tags = {k: props[k] for k in DERIVED_TAG_KEYS if isinstance(props.get(k), str)}
        if want_s:
            schools.append((pt[0], pt[1], tags))
        if want_t:
            stops.append((pt[0], pt[1]))
    gated = [
        (lon, lat, tags)
        for lon, lat, tags in schools
        if any(_hav_km(lon, lat, slon, slat) <= SCHOOLBUS_GATE_KM for slon, slat in stops)
    ]
    stats = {"features": feats, "schools": len(schools), "stops": len(stops), "kept": len(gated)}
    return gated, stats


def read_forest_points(forest_path):
    """Forest/scrub/heath source points from the PBF export: polygon
    centroids + bare nodes, deduped by rounded coords (a forest reads as
    one foraging unit per mapped polygon -- honest centroid-density
    semantics, NOT area; see module docstring)."""
    out = []
    seen = set()
    feats = kept = 0
    for feat in _iter_features(forest_path):
        feats += 1
        props = feat.get("properties", {})
        if not is_forage_tags(props):
            continue
        pt = wr._feature_point(feat.get("geometry"))
        if pt is None:
            continue
        key = (round(pt[0], 5), round(pt[1], 5))
        if key in seen:
            continue
        seen.add(key)
        kept += 1
        tags = {k: props[k] for k in DERIVED_TAG_KEYS if isinstance(props.get(k), str)}
        out.append((pt[0], pt[1], tags))
    return out, {"features": feats, "kept": kept}


def resolve_layer(poi_path, forest_path, name):
    if name == "schoolbus":
        return resolve_schoolbus(poi_path)
    if name == "forage":
        if not forest_path:
            raise SystemExit("forage needs --forest <derived-forest.geojson>")
        return read_forest_points(forest_path)
    return resolve_with_tags(poi_path, PREDS[name])


def build_layer(graph, grid, half, sigma, pts, name, derived=None):
    print("%s: %d source points" % (name, len(pts)), flush=True)
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


def write_master(args, grid, score_of, half, sigma):
    per, cap = 0, 0
    doc = wr.encode_raster(grid, score_of, per=per, cap=cap, half=half, sigma=sigma)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    import base64

    raw = base64.b64decode(doc["data"])
    known = sum(1 for v in raw if v != 255)
    print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
    print("wrote %s (%.1f MB)" % (args.out, os.path.getsize(args.out) / 1e6))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=sorted(LAYER_DEFAULTS) + ["all"])
    ap.add_argument("--graph", required=True)
    ap.add_argument("--snap", required=True)
    ap.add_argument("--poi", required=True, help="amenity sweep GeoJSON (snapshot)")
    ap.add_argument("--forest", default=None, help="forest PBF export GeoJSON (forage)")
    ap.add_argument("--derived", default=None, help="write fallback points here")
    ap.add_argument("--stamp-cache", default=None)
    ap.add_argument("--half", type=float, default=None)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--step-m", type=float, default=75.0)
    ap.add_argument("--bbox", nargs=4, type=float, default=[23.3, 58.4, 25.5, 59.65])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    t0 = time.time()
    graph = load_graph(args.graph)
    print("graph: loaded (%.1fs)" % (time.time() - t0), flush=True)

    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    for i, name in enumerate(layers):
        defs = LAYER_DEFAULTS[name]
        half = args.half if args.half is not None else defs["half"]
        sigma = args.sigma if args.sigma is not None else defs["sigma"]
        grid = wr.Grid(args.bbox, args.step_m)
        cache = args.stamp_cache or (args.out + ".stamp.pkl")
        if len(layers) > 1:
            cache = "%s.%s.pkl" % (cache, name)
        out = args.out if len(layers) == 1 else args.out.replace(".json", ".%s.json" % name)
        derived = args.derived
        if derived and len(layers) > 1:
            derived = derived.replace(".json", ".%s.json" % name)
        if os.path.exists(cache):
            grid.acc, grid.bits = wr.load_stamp(cache)
            print("%s: stamp loaded %s (skipped Dijkstra)" % (name, cache), flush=True)

            def score_of(k, _half=half):
                s = grid.acc.get(k)
                if not s:
                    return None
                sc = wr.saturate(s, _half)
                return sc if sc >= 3 else None
        else:
            t1 = time.time()
            pts, stats = resolve_layer(args.poi, args.forest, name)
            print("%s: %s" % (name, stats), flush=True)
            score_of, _ = build_layer(graph, grid, half, sigma, pts, name, derived)
            wr.save_stamp(cache, grid.acc, grid.bits)
            print("%s: stamp saved %s (%.1fs)" % (name, cache, time.time() - t1))

        class _A:
            pass

        a = _A()
        a.out = out
        write_master(a, grid, score_of, half, sigma)
        print("%s: done (%.1fs total)" % (name, time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
