"""Build network walk-access rasters for Group 10 batch-C utility layers (B10C).

Usage (local 2026-09-12 snapshot ONLY — no network; inputs are local files):
  # 1. Extract Batch-10C features from the snapshot PBF (osmium reads local data).
  # MUST be nwr/ (nodes+ways+relations): collection points and antennas are
  # frequently way-mapped, and a node-only (n/) filter silently drops them
  # (PR #118 family). resolve_pois centroids every geometry and
  # dedupe_points merges node+area pairs in ~20 m cells.
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/man_made=mast nwr/man_made=tower nwr/man_made=communications_tower \\
      nwr/man_made=antenna nwr/man_made=water_well nwr/natural=spring \\
      nwr/amenity=drinking_water nwr/amenity=waste_disposal \\
      nwr/amenity=recycling -o /tmp/hf-b10c-utility.pbf --overwrite
  osmium export -u type_id /tmp/hf-b10c-utility.pbf -o /tmp/hf-b10c-utility.geojson
  # communication:radio/television=yes tags ride along on matched objects;
  # objects carrying ONLY those tags (no man_made/amenity match) are missed
  # — recount at extraction time; the scorer docstring counted 6 TV + 1
  # radio uses, all on masts/antennas.
  # 2. Stamp one county raster per layer (75 m master; metro tiling is
  #    optional — the window endpoint falls back to county-only windows):
  python3 scripts/build/batch_b10c_utility.py --layer waste \\
      --graph ~/hf-data/2026-09-12/osm/harju-foot-graph.json \\
      --poi /tmp/hf-b10c-utility.geojson \\
      --derived ~/hf-data/2026-09-12/osm/derived-waste.json \\
      --out ~/hf-data/2026-09-12/osm/waste-walk-raster.json

Layers share the foot graph and 75 m county grid; only features, kernel
and scoring differ (see walk_raster.py). Calibration flags default to the
numbers locked in apps/web/lib/layers_batch10c.ts (BATCH10C_BONUS/DECAY);
the wire doc carries them so the server rejects stale rasters
(loadLayerRaster/matchesContract).

HONESTY: every layer is an OSM-derived PROXY, never registry data —
internet is mast proximity, not measured broadband (TTJA/KKIS absent);
water is mapped-public-point proximity, not the house's tap source (ÜVK
absent); waste is collection-point proximity, not measured service;
redundancy is mast depth, not measured failover; OTA is broadcast-mast
proximity, not field strength. Titles/legends/sources say so (pinned by
layers_batch10c.test.ts).

Scoring mirrors apps/web/lib/layers_batch10c.ts exactly: unweighted
count kernels, area-kind saturating scores 100*S/(S+half), null below 3
(unknown -> 255 -> red). Internet and redundancy share sources but ask
different questions: any nearby feed (half 1, sigma 0.8 — one mast
within ~1.6 km reads 50) versus feed depth across a wider area (half 3,
sigma 1.5 ≈ the scorer's 3 km count radius at 2σ — one nearby mast
reads only ~25 here).
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

# Locked calibration — must match BATCH10C_BONUS / BATCH10C_DECAY in
# apps/web/lib/layers_batch10c.ts (BONUS is the single source of halves;
# pinned by test_batch_b10c.py).
# SCOPE: only the two amenity-framed layers survive as maps (buyer
# review cut p51/p262/p265 — mast proximity cannot show fiber/mobile
# coverage). The telecom/broadcast predicates below stay, tested, as the
# documented tag reference for the per-listing scorer dims.
LAYER_DEFAULTS = {
    "water": {"sigma": 0.5, "half": 1, "kind": "area"},  # p53 (~157)
    "waste": {"sigma": 0.3, "half": 6, "kind": "area"},  # p54 (~1740)
    # p51 FIBER (real coverage, not masts): ~160k TTJA-reported >=1000
    # Mbit/s addresses — half/size set so Tallinn saturates green
    # (truth: coverage IS universal there) while the fringe discriminates.
    "fiber": {"sigma": 0.3, "half": 50, "kind": "area"},
    # p51 MOBILE (real crowdsourced cells, not masts): ~4.2k OpenCellID
    # LTE footprints (samples>=3) — contributor bias (Elisa
    # over-represented vs Telia) means absence is softer evidence than
    # presence; the legend must say so. Self-scaling (no half): the
    # measured ranges ARE the calibration.
    "mobile": {"sigma": 1.0, "half": None, "kind": "cover"},
}

B10C_LAYERS = sorted(LAYER_DEFAULTS)


def _first(tags, key):
    """First ;-separated tag value (multi-values never smuggle a match)."""
    return str(tags.get(key, "")).split(";")[0]


def _is_broadcast_tagged(tags):
    return _first(tags, "communication:radio") == "yes" or (
        _first(tags, "communication:television") == "yes"
    )


def is_broadcast(tags):
    """p265 OTA proxy: antennas and broadcast-tagged radiators.

    Checked before the mast rule (a TV-tagged mast scores as broadcast,
    not telecom) — mirrors kinds_from_tags in dims_group10c.py.
    """
    if not isinstance(tags, dict):
        return False
    if _is_broadcast_tagged(tags):
        return True
    return _first(tags, "man_made") == "antenna"


def is_telecom(tags):
    """p51/p262 proxy: CONFIRMED telecom use only (NOT every mast).

    communications_tower is telecom by definition; mast/tower need
    tower:type=communication (church/clock/observation towers excluded —
    sibling p52 owns generic masts). Broadcast-tagged masts belong to
    p265, never here.
    """
    if not isinstance(tags, dict):
        return False
    if _is_broadcast_tagged(tags):
        return False
    mm = _first(tags, "man_made")
    if mm == "communications_tower":
        return True
    if mm in ("mast", "tower"):
        return _first(tags, "tower:type") == "communication"
    return False


def is_waterpoint(tags):
    """p53 proxy: mapped public water points (wells, springs, taps)."""
    if not isinstance(tags, dict):
        return False
    if _first(tags, "man_made") == "water_well":
        return True
    if _first(tags, "natural") == "spring":
        return True
    return _first(tags, "amenity") == "drinking_water"


def is_wastepoint(tags):
    """p54 proxy: collection points (NOT street litter bins, NOT plants)."""
    if not isinstance(tags, dict):
        return False
    return _first(tags, "amenity") in ("waste_disposal", "recycling")


LAYER_PRED = {
    "internet": is_telecom,
    "water": is_waterpoint,
    "waste": is_wastepoint,
    "redundancy": is_telecom,
    "ota": is_broadcast,
}

# ~20 m spatial dedupe cells (mirrors snapshot.ts DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def dedupe_points(feats):
    """Collapse co-located points (~20 m cells, first wins).

    osmium export emits untagged member nodes (skipped by the
    predicates) AND node+area pairs for the same mast/shelter: OSM-id
    dedupe in resolve_pois cannot see those pairs, and double-counting
    one mast would double its kernel weight.
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
    """Unweighted count kernel over POI points (all five B10C layers)."""
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


# Overlay sample cap (fiber has ~160k addresses; the raster holds the
# full field, dots mark a thinned honest sample — see GENV precedent).
FIBER_OVERLAY_CAP = 8000


def build_fiber_layer(graph, grid, half, sigma, fiber_path, derived=None):
    """Count kernel over TTJA-reported >=1000 Mbit/s addresses (p51 fiber).

    Points come from derived-fiber.json (batch_fiber_import.py), not the
    osmium extract — real operator-reported coverage, not mast proximity.
    """
    with open(fiber_path, encoding="utf-8") as f:
        pts = json.load(f)
    feats = [(p["lon"], p["lat"], 1.0) for p in pts
             if isinstance(p.get("lon"), (int, float))
             and isinstance(p.get("lat"), (int, float))]
    print("fiber: %d covered addresses" % len(feats), flush=True)
    if derived:
        step = max(1, len(feats) // FIBER_OVERLAY_CAP)
        sample = feats[::step][:FIBER_OVERLAY_CAP]
        with open(derived, "w", encoding="utf-8") as f:
            json.dump([{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in sample], f)
        print("fiber: wrote %d thinned overlay points to %s" % (len(sample), derived))
    stamp = [(lon, lat, 1.0, None) for lon, lat, _ in feats]
    snapped, euclid = wr.stamp_sum(grid, graph, stamp, sigma, 4 * sigma)
    print("fiber: snapped=%d euclid=%d" % (snapped, euclid))
    return _area_score(grid, half), {"half": half, "sigma": sigma}


def stamp_cover(grid, discs):
    """Max-merge linear coverage discs (measured footprints, not density).

    discs: [(lon, lat, r_km)]. Cell value v = max over covering discs of
    (1 - d/r): 100 at the centroid where fixes cluster, ~0 at the
    observed edge, missing (unknown) outside every disc. Overlapping
    coverage max-merges — covered is covered, never stacked. Direct
    (Euclidean) distance throughout: radio does not walk footpaths.
    Returns the stamped disc count.
    """
    n = 0
    for lon, lat, r in discs:
        if not r > 0:
            continue
        n += 1
        x0, y0 = (lon - grid.bbox[0]) * wr.KX, (lat - grid.bbox[1]) * wr.KY
        for iy in range(max(0, int((y0 - r) * 1000 / grid.step)),
                        min(grid.rows, int((y0 + r) * 1000 / grid.step) + 1)):
            for ix in range(max(0, int((x0 - r) * 1000 / grid.step)),
                            min(grid.cols, int((x0 + r) * 1000 / grid.step) + 1)):
                clon = grid.bbox[0] + (ix + 0.5) * grid.step / 1000 / wr.KX
                clat = grid.bbox[1] + (iy + 0.5) * grid.step / 1000 / wr.KY
                # Direct Euclidean (equirectangular, same geometry as the
                # web client's cover discs): radio does not walk footpaths.
                d = math.hypot((lon - clon) * wr.KX, (lat - clat) * wr.KY)
                if d > r:
                    continue
                k = iy * grid.cols + ix
                v = 1.0 - d / r
                if v > grid.acc.get(k, 0.0):
                    grid.acc[k] = v
    return n


def cover_scores(grid):
    """Direct 0..100 percent from stamped cover fractions (self-scaling).

    No half, no floor: the measured ranges ARE the calibration. Cells
    outside every disc stay missing (unknown -> 255 -> red); the ~0
    observed boundary is kept (measured edge, informative red).
    """

    def score_of(k):
        if k not in grid.acc:
            return None
        return round(100.0 * grid.acc[k])

    return score_of


def _disc_range_m(tags):
    """Measured footprint radius in metres, or None (no measurement)."""
    if not isinstance(tags, dict):
        return None
    try:
        r = float(tags.get("ulatus_m", ""))
    except (ValueError, TypeError):
        return None
    return r if r > 0 else None


def build_mobile_layer(graph, grid, half, sigma, mobile_path, derived=None):
    """Measured-coverage discs over OpenCellID LTE cells (p51 mobile).

    Points come from derived-mobile.json (batch_mobile_import.py); each
    carries its MEASURED range (ulatus_m) driving one coverage disc.
    Points without a range carry no usable measurement and are skipped
    for the raster (never zero-filled) but kept as overlay dots: the
    dots mark measurement sites, the raster models coverage. The half
    argument is accepted for call-shape parity and ignored (cover is
    self-scaling); the graph argument likewise (direct distance).
    """
    with open(mobile_path, encoding="utf-8") as f:
        pts = json.load(f)
    feats, dots, skipped = [], [], 0
    for p in pts:
        if not (isinstance(p.get("lon"), (int, float))
                and isinstance(p.get("lat"), (int, float))):
            skipped += 1
            continue
        tags = p.get("tags") if isinstance(p.get("tags"), dict) else None
        dots.append({"lon": p["lon"], "lat": p["lat"],
                     **({"tags": tags} if tags else {}), "a": 1})
        r = _disc_range_m(tags)
        if r is None:
            skipped += 1
            continue
        feats.append((p["lon"], p["lat"], r / 1000.0))
    print("mobile: %d discs (%d skipped: no range/junk)" % (len(feats), skipped),
          flush=True)
    if derived:
        with open(derived, "w", encoding="utf-8") as f:
            json.dump(dots, f)
        print("mobile: wrote %d overlay points to %s" % (len(dots), derived))
    n = stamp_cover(grid, feats)
    print("mobile: cover-stamped=%d discs" % n)
    return cover_scores(grid), {"half": None, "sigma": sigma}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=B10C_LAYERS)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--poi", default=None, help="utility geojson (all layers)")
    ap.add_argument("--fiber-points", default=None,
                    help="derived-fiber.json (fiber layer only)")
    ap.add_argument("--mobile-points", default=None,
                    help="derived-mobile.json (mobile layer only)")
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
    # Mobile stamps direct distance (radio physics) — no graph needed.
    graph = None if args.layer == "mobile" else load_graph(args.graph)
    if graph is not None:
        print("graph: %d verts (%.1fs)" % (len(graph), time.time() - t0), flush=True)
    grid = wr.Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    if args.layer == "fiber":
        if not args.fiber_points:
            ap.error("--fiber-points is required for the fiber layer")
        score_of, contract = build_fiber_layer(
            graph, grid, half, sigma, args.fiber_points, args.derived
        )
    elif args.layer == "mobile":
        if not args.mobile_points:
            ap.error("--mobile-points is required for the mobile layer")
        score_of, contract = build_mobile_layer(
            graph, grid, half, sigma, args.mobile_points, args.derived
        )
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
