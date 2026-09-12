"""Build a network walk-access raster for one place layer (offline snapshot).

Usage:
  python3 scripts/build-walk-raster.py --layer transit --graph .../harju-foot-graph.json \\
      --snap /Users/gregoreesmaa/hf-data/2026-09-12 --out .../transit-walk-raster.json
  python3 scripts/build-walk-raster.py --layer parks --graph ... [same]
  python3 scripts/build-walk-raster.py --layer schools --graph ... [same]

Layers share the foot graph and 75 m county grid; only features, kernel
and scoring differ (see walk_raster.py). Calibration flags default to the
numbers locked in apps/web/lib/layers.ts bonusSpecFor(); the wire doc
carries them so the server rejects stale rasters (loadLayerRaster).
"""

import argparse
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import walk_raster as wr  # noqa: E402
from walk_graph import SnapIndex, load_graph, lonlat_of  # noqa: E402

LAYER_DEFAULTS = {
    "transit": {"sigma": 0.2, "half": 1500},
    "parks": {"sigma": 0.25, "half": 15},
    "schools": {"sigma": 0.8},
    # Daily errands read at block scale; healthcare trips are rarer, like schools.
    # Walkability runs narrow (135k junctions county-wide: cheaper cutoff,
    # and hyper-local texture is the point).
    "walkability": {"sigma": 0.2, "half": None},
    "pedinfra": {"sigma": 0.25, "half": None},
    "cycling": {"sigma": 0.3, "half": None},
    "grocery": {"sigma": 0.3, "half": None},
    "healthcare": {"sigma": 0.8, "half": None},
}


def build_transit(graph, snap, grid, half, sigma):
    stops = json.load(open(os.path.join(snap, "osm", "derived-transit.json")))
    freq = json.load(open(os.path.join(snap, "osm", "transit-frequency.json")))["stops"]
    trips = wr.join_trips(stops, freq)
    feats = [(p["lon"], p["lat"], t, (p.get("tags") or {}))
             for p, t in zip(stops, trips) if t > 0]

    def bit_of(tags):
        return wr.MODE_BIT.get(wr.stop_mode(tags) or "", 0)

    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma, bit_of, wr.KICKER_KM)

    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        if bin(grid.bits.get(k, 0)).count("1") >= 2:
            sc = min(100.0, sc + 10)
        return sc if sc >= 3 else None

    print("transit: %d feats snapped=%d euclid=%d" % (len(feats), snapped, euclid))
    return score_of, {"half": half, "sigma": sigma}


def build_parks(graph, snap, grid, half, sigma):
    points = json.load(open(os.path.join(snap, "osm", "derived-parks.json")))
    areas = json.load(open(os.path.join(snap, "osm", "park-areas.json")))
    feats = [(lon, lat, a, None) for lon, lat, a in wr.resolve_parks(points, areas, sigma)]
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)

    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= 3 else None

    print("parks: %d feats snapped=%d euclid=%d" % (len(feats), snapped, euclid))
    return score_of, {"half": half, "sigma": sigma}


def build_schools(graph, snap, grid, sigma):
    points = json.load(open(os.path.join(snap, "osm", "derived-schools.json")))
    feats = wr.resolve_schools(points)
    idx = SnapIndex(graph)
    # One multi-source run for nearest-any + one per class for presence.
    by_class = {c: [] for c in wr.SCHOOL_VALUES}
    sources = []
    euclid_pool = []
    for lon, lat, amenity in feats:
        euclid_pool.append((lon, lat))
        v, gap = idx.nearest(lon, lat, wr.SNAP_KM)
        if v is None:
            continue
        sources.append((v, gap))
        if amenity in by_class:
            by_class[amenity].append((v, gap))
    net_cut = 2 * sigma
    dmin = wr.multi_source_dist(graph, sources, net_cut)
    cell_min = {}
    for vk, d in dmin.items():
        k = grid.cell_of(*lonlat_of(vk))
        if k is not None and d < cell_min.get(k, float("inf")):
            cell_min[k] = d
    present = {}
    for c, src in by_class.items():
        if not src:
            continue
        for vk, d in wr.multi_source_dist(graph, src, wr.SCHOOL_PRESENT_KM).items():
            k = grid.cell_of(*lonlat_of(vk))
            if k is not None:
                present.setdefault(k, set()).add(c)
    # Euclid tier on a coarse grid when stamping fine: far-field only,
    # where +-40 m inheritance costs about a point.
    coarse = grid if grid.step >= 75 else wr.Grid(grid.bbox)
    euc = wr.euclid_nearest_fill(coarse, euclid_pool, wr.SCHOOL_FAR_KM)

    def euc_at(k):
        if coarse is grid:
            return euc.get(k, float("inf"))
        lon, lat = grid.center_of(k)
        ck = coarse.cell_of(lon, lat)
        return euc.get(ck, float("inf")) if ck is not None else float("inf")

    def score_of(k):
        d = cell_min.get(k, euc_at(k))
        if d == float("inf"):
            return 0.0  # past 3.2 km of any school: known-bad, mirrors TS wash
        base = 100.0 * math.exp(-d / sigma)
        distinct = len(present.get(k, ()))
        if k not in cell_min:
            distinct = 0  # euclid tier: no network presence info
        return min(100.0, base + wr.school_bonus(distinct))

    print("schools: %d feats network-labeled=%d cells" % (len(feats), len(cell_min)))
    return score_of, {"sigma": sigma, "per": wr.SCHOOL_PER, "cap": wr.SCHOOL_CAP}


def _area_score(grid, half):
    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= 3 else None
    return score_of


def build_walkability(graph, snap, grid, half, sigma, hwy, poi):
    feats = [(lon, lat, 1.0, None) for lon, lat, _ in wr.resolve_walkability(graph)]
    print("walkability: %d junctions" % len(feats), flush=True)
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("walkability: snapped=%d euclid=%d" % (snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def _length_feats(hwy, grid, kind):
    pts, stats = wr.resolve_length_km(hwy, wr.PED_HIGHWAY if kind == "pedinfra" else wr.CYCLE_SET)
    print("%s: %s" % (kind, stats), flush=True)
    # Aggregate vertex-km onto 75 m cells (conserves total km; <=54 m error).
    cells = {}
    for lon, lat, w in pts:
        k = grid.cell_of(lon, lat)
        if k is not None:
            cells[k] = cells.get(k, 0.0) + w
    feats = []
    for k, w in cells.items():
        lon, lat = grid.center_of(k)
        feats.append((lon, lat, w, None))
    print("%s: %d cell-sources" % (kind, len(feats)), flush=True)
    return feats


def build_pedinfra(graph, snap, grid, half, sigma, hwy, poi):
    feats = _length_feats(hwy, grid, "pedinfra")
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("pedinfra: snapped=%d euclid=%d" % (snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def build_cycling(graph, snap, grid, half, sigma, hwy, poi):
    feats = _length_feats(hwy, grid, "cycling")
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("cycling: snapped=%d euclid=%d" % (snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def build_poi_layer(graph, snap, grid, half, sigma, hwy, poi, pred, name, derived):
    pts, stats = wr.resolve_pois(poi, pred)
    print("%s: %s" % (name, stats), flush=True)
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            # Unit weights: the area-kind fallback splats these with half.
            json.dump([{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in pts], f)
        print("%s: wrote %d fallback points to %s" % (name, len(pts), derived))
    feats = [(lon, lat, 1.0, None) for lon, lat, _ in pts]
    snapped, euclid = wr.stamp_sum(grid, graph, feats, sigma, 4 * sigma)
    print("%s: snapped=%d euclid=%d" % (name, snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def build_grocery(graph, snap, grid, half, sigma, hwy, poi, derived=None):
    return build_poi_layer(graph, snap, grid, half, sigma, hwy, poi,
                           wr.is_grocery, "grocery", derived)


def build_healthcare(graph, snap, grid, half, sigma, hwy, poi, derived=None):
    return build_poi_layer(graph, snap, grid, half, sigma, hwy, poi,
                           wr.is_medical, "healthcare", derived)


BUILDERS = {
    "transit": build_transit,
    "parks": build_parks,
    "schools": build_schools,
    "walkability": build_walkability,
    "pedinfra": build_pedinfra,
    "cycling": build_cycling,
    "grocery": build_grocery,
    "healthcare": build_healthcare,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=sorted(LAYER_DEFAULTS))
    ap.add_argument("--graph", required=True)
    ap.add_argument("--snap", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--half", type=float, default=None)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--hwy", default=None, help="highway GeoJSON (pedinfra/cycling)")
    ap.add_argument("--poi", default=None, help="shop/amenity GeoJSON (grocery/healthcare)")
    ap.add_argument("--derived", default=None, help="write fallback points here (grocery/healthcare)")
    ap.add_argument("--stamp-cache", default=None, help="pickle S-stamp here to skip Dijkstra on reruns")
    ap.add_argument("--step-m", type=float, default=75.0, help="raster cell size in meters")
    ap.add_argument("--format", choices=["combined", "split"], default="combined",
                    help="combined: single wire JSON; split: meta JSON + raw .u8 master")
    ap.add_argument("--bbox", nargs=4, type=float, default=[23.3, 58.4, 25.5, 59.65])
    args = ap.parse_args()
    defs = LAYER_DEFAULTS[args.layer]
    half = args.half if args.half is not None else defs.get("half") or 0
    sigma = args.sigma if args.sigma is not None else defs["sigma"]
    if half <= 0 and args.layer != "schools":
        ap.error("--half is required for this layer (no default locked yet)")

    t0 = time.time()
    graph = load_graph(args.graph)
    print("graph: %d verts (%.1fs)" % (len(graph), time.time() - t0), flush=True)
    grid = wr.Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    cache = args.stamp_cache or (args.out + ".stamp.pkl")
    score_of, contract = None, None
    if os.path.exists(cache) and args.layer != "schools":
        grid.acc, grid.bits = wr.load_stamp(cache)
        print("stamp: loaded %s (skipped Dijkstra)" % cache, flush=True)
        # Stamp cache holds S sums only: rebuild the scorer identically.
        score_of, contract = _area_score(grid, half), {"half": half, "sigma": sigma}
    else:
        builder = BUILDERS[args.layer]
        if args.layer == "schools":
            score_of, contract = builder(graph, args.snap, grid, sigma)
        elif args.layer == "walkability":
            score_of, contract = builder(graph, args.snap, grid, half, sigma, args.hwy, args.poi)
        elif args.layer in ("pedinfra", "cycling"):
            if not args.hwy:
                ap.error("--hwy is required for this layer")
            score_of, contract = builder(graph, args.snap, grid, half, sigma, args.hwy, args.poi)
        elif args.layer in ("grocery", "healthcare"):
            if not args.poi:
                ap.error("--poi is required for this layer")
            score_of, contract = builder(graph, args.snap, grid, half, sigma,
                                         args.hwy, args.poi, args.derived)
        else:
            score_of, contract = builder(graph, args.snap, grid, half, sigma)
        if args.layer != "schools":
            wr.save_stamp(cache, grid.acc, grid.bits)
            print("stamp: saved %s" % cache, flush=True)
    per, cap = contract.get("per", 0), contract.get("cap", 0)
    half, sigma_c = contract.get("half"), contract.get("sigma")
    if args.format == "split":
        prefix = args.out[:-5] if args.out.endswith(".json") else args.out
        wr.save_master(prefix, grid, score_of, half, sigma_c, per, cap)
        raw = open(prefix + ".u8", "rb").read()
        known = sum(1 for v in raw if v != 255)
        print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
        print("wrote %s.json + .u8 (%.1f MB, %.1fs)"
              % (prefix, os.path.getsize(prefix + ".u8") / 1e6, time.time() - t0))
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
