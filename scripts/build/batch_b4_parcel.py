"""Batch 4 Group 13 parcel builders: p141 delivery logistics, p282 security.

p141 (Pakiautomaadid): walk access to carrier parcel lockers. Snapshot
OSM amenity=parcel_locker (517 verified) is the cross-carrier physical
truth (Omniva/SmartPOST/DPD APIs are live-only; the spec's alternates are
unusable offline, so OSM is the honest primary here). Unweighted counts
(OSM has no locker-bank size), saturating sum half=4, sigma=0.3: Balti
~64, Oismae ~62, Lasnamae ~30, lockerless countryside unknown.

p282 (Pakikindlus): secure pickup = locker (weight 1, PIN box) or staffed
post office counter (weight 2: human handoff + ID check + holding time).
38 post_office tags verified in-snapshot. half=6, sigma=0.3. The 2x post
office weight is a judgment call -- documented here and in reviewer notes.

Both reuse the walk-graph kernel via lazy imports. Rebuild:
  python3 scripts/build/batch_b4_parcel.py --which lockers --snap S --out D
  python3 scripts/build/batch_b4_parcel.py --which securepickup --snap S --out D
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from batch_b4_common import (  # noqa: E402
    COUNTY_BBOX,
    SCORE_FLOOR,
    feature_point,
    saturate,
)

LOCKER_WEIGHT = 1.0
POSTOFFICE_WEIGHT = 2.0


def resolve_parcels(geojson_path):
    """Deduped (by OSM id) locker/post-office points with weights.

    Returns (pts, stats) where pts = [(lon, lat, weight, amenity)].
    Same place mapped as node + building keeps ONE entry (first seen):
    kernel smoothing absorbs the ~meter offset either way.
    """
    pts = []
    seen = set()
    stats = {"features": 0, "lockers": 0, "postoffices": 0, "skipped": 0}
    with open(geojson_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip().rstrip(",")
            if not line.startswith("{"):
                continue
            try:
                feat = json.loads(line)
            except ValueError:
                stats["skipped"] += 1
                continue
            if feat.get("type") != "Feature":
                continue
            stats["features"] += 1
            fid = feat.get("id")
            if fid is not None:
                if fid in seen:
                    continue
                seen.add(fid)
            amenity = (feat.get("properties") or {}).get("amenity")
            if amenity == "parcel_locker":
                weight = LOCKER_WEIGHT
            elif amenity == "post_office":
                weight = POSTOFFICE_WEIGHT
            else:
                continue
            pt = feature_point(feat.get("geometry"))
            if pt is None:
                stats["skipped"] += 1
                continue
            # Count only kept points (an unlocatable feature is skipped,
            # not kept): stats must match the stamped feature list.
            stats["lockers" if amenity == "parcel_locker" else "postoffices"] += 1
            pts.append((pt[0], pt[1], weight, amenity))
    return pts, stats


def _build_weighted(graph, grid, feats, half, sigma, name):
    import walk_raster as wr  # lazy: hermetic unit tests never reach here
    stamp = [(lon, lat, w, None) for lon, lat, w, _ in feats]
    snapped, euclid = wr.stamp_sum(grid, graph, stamp, sigma, 4 * sigma)

    def score_of(k):
        s = grid.acc.get(k)
        if not s:
            return None
        sc = saturate(s, half)
        return sc if sc >= SCORE_FLOOR else None

    print("%s: %d feats snapped=%d euclid=%d" % (name, len(feats), snapped, euclid))
    return score_of, {"half": half, "sigma": sigma}


def build_lockers(graph, snap, grid, half, sigma, hwy=None, poi=None, derived=None):
    pts, stats = resolve_parcels(os.path.join(snap, "osm", "harju-amenities.geojson"))
    print("lockers: %s" % (stats,))
    feats = [(lon, lat, w, a) for lon, lat, w, a in pts if a == "parcel_locker"]
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            json.dump([{"lon": lon, "lat": lat, "a": 1} for lon, lat, _, _ in feats], f)
        print("lockers: wrote %d fallback points to %s" % (len(feats), derived))
    return _build_weighted(graph, grid, feats, half, sigma, "lockers")


def build_securepickup(graph, snap, grid, half, sigma, hwy=None, poi=None,
                       derived=None):
    pts, stats = resolve_parcels(os.path.join(snap, "osm", "harju-amenities.geojson"))
    print("securepickup: %s" % (stats,))
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            # Weighted fallback points: the area-kind Euclidean splat reads
            # `a`, so weights ride along (unlike the unit-weight POI precedent).
            json.dump([{"lon": lon, "lat": lat, "a": w}
                       for lon, lat, w, _ in pts], f)
        print("securepickup: wrote %d fallback points to %s" % (len(pts), derived))
    return _build_weighted(graph, grid, pts, half, sigma, "securepickup")


BUILDERS = {"lockers": build_lockers, "securepickup": build_securepickup}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", required=True, choices=sorted(BUILDERS))
    ap.add_argument("--snap", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--derived", default=None)
    ap.add_argument("--step-m", type=float, default=75.0)
    ap.add_argument("--format", choices=["combined", "split"], default="combined")
    ap.add_argument("--half", type=float, default=None)
    ap.add_argument("--sigma", type=float, default=None)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    args = ap.parse_args()

    from batch_b4_common import CAL
    half = args.half if args.half is not None else CAL[args.which]["half"]
    sigma = args.sigma if args.sigma is not None else CAL[args.which]["sigma"]

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    import walk_raster as wr
    from walk_graph import load_graph
    graph = load_graph(args.graph)
    grid = wr.Grid(args.bbox, args.step_m)
    score_of, contract = BUILDERS[args.which](
        graph, args.snap, grid, half, sigma, derived=args.derived)
    if args.format == "split":
        wr.save_master(os.path.join(args.out, args.which + "-metro"),
                       grid, score_of, contract["half"], contract["sigma"])
    else:
        doc = wr.encode_raster(grid, score_of, half=contract["half"],
                               sigma=contract["sigma"])
        with open(os.path.join(args.out, args.which + "-walk-raster.json"), "w",
                  encoding="utf-8") as f:
            json.dump(doc, f)
    print("wrote %s raster half=%s sigma=%s" % (args.which, half, sigma))


if __name__ == "__main__":
    main()
