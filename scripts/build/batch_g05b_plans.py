"""Group 5 plans-B county masters (issue #162): p106 gardens + p146 buildout.

Stdlib only (+ sibling scripts/walk_raster.py, same as batch_g03d).
Offline, snapshot-only (NO network): garden and construction vectors
come from the LOCAL Harjumaa PBF via the documented osmium pre-steps,
never from a live service. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; full-county builds run only
via the documented rebuild commands.

SCOPE (two layers, honest): this builder serves ONLY p106 (urban
farming capability) as a mapped-garden proximity hinnang and p146
(future neighborhood density) as a mapped-construction proximity
hinnang. The sibling params are documented no-map (see
apps/web/lib/layers_group05b.ts): p107 livestock/equestrian zoning,
p186 gray-water legality and p188 dark sky compliance are
per-parcel/per-register facts with no honest area signal in the
snapshot — they ship as scorer dims only
(services/scoring/dims_group05b.py), OTA PR #131 precedent.

HONESTY (load-bearing): the PLANK WFS (planeeringud.ee) and the
Tallinna Planeeringute Register are NOT in the 2026-09-12 snapshot,
so neither master is a planning-register readout. gardens scores
nearness to MAPPED community gardens + allotments (growing happens
at mapped gardens — the gardens are the mapped cause, not a soil
measurement); buildout scores nearness to MAPPED construction sites
(sites under construction ARE the density being added — the
param's densification shape, never the plan's target density).
Titles, legends and sources say "hinnang" (pinned by
layers_group05b.test.ts).

Models (locked 2026-09-12):
* gardens (p106): EUCLIDEAN count kernel over kept garden points
  (Gaussian sigma 0.3 km, 4-sigma stamp cutoff; graph-free on
  purpose — garden beds sit where the foot graph has no vertices,
  so walk stamping leaves holes AT the gardens, same story as
  moorage #154), score = 100*S/(S+1). half=1: facilities are
  sparse (76 deduped Tallinn sites), so ONE mapped garden already
  reads 50 on its own cell instead of vanishing.
* buildout (p146): same kernel, score = 100*S/(S+2). half=2:
  construction polygons are denser (138 deduped Tallinn sites)
  and cluster (one development maps several polygons), so TWO
  nearby sites read 50 — a single fenced pit does not paint the
  block green alone.
* green = developing/growing (opportunity framing, moorage
  precedent). A buyer wanting stillness reads red as calm — the
  legend says "valmis/rahulik piirkond", never "bad".

Sources (predicates verified on the snapshot extract):
* garden: landuse=allotments OR (leisure=garden AND
  (garden:type=community OR garden:style=kitchen)) (verified
  2026-09-12: 353 kept county-wide = 155 community/kitchen + 198
  allotments; 115 of them in the Tallinn window, 76 after the
  20 m dedupe). leisure=garden WITHOUT garden:type (2988
  residential backyards in the window) is OUT by design (a
  private backyard is not growing opportunity);
  landuse=orchard is OUT by design (p409 agrifield #143 already
  scores farmland/meadow/orchard — keeping it here would
  re-skin that layer). Untagged relation members (addr:*,
  barrier=gate fragments) carry no garden tags, so they drop
  out in keep_garden.
* construction: landuse=construction (verified 2026-09-12: 332
  kept county-wide; 177 in the Tallinn window, 138 after the
  20 m dedupe: Hipodroomi kvartal, City Plaza 2, Reaalkooli
  juurdeehitus...). Untagged construction-relation members drop
  out in keep_buildout.

Computation: both masters are graph-free Euclidean count kernels
on the 75 m county grid (57.29/110.57 scales) — sparse Gaussian
stamps, 255 = unknown beyond the 4-sigma cutoff. NO metro masters
(documented): sparse count kernels at 9.375 m cells would be fake
precision — the window route serves county everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/leisure=garden nwr/landuse=allotments \\
      -o /tmp/hf-g05b-gardens.pbf --overwrite
  osmium export -u type_id /tmp/hf-g05b-gardens.pbf -o /tmp/hf-g05b-gardens.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      nwr/landuse=construction \\
      -o /tmp/hf-g05b-construction.pbf --overwrite
  osmium export -u type_id /tmp/hf-g05b-construction.pbf -o /tmp/hf-g05b-construction.geojson
  python3 scripts/build/batch_g05b_plans.py --layer gardens \\
      --poi /tmp/hf-g05b-gardens.geojson \\
      --out ~/hf-data/2026-09-12/osm/gardens-walk-raster.json \\
      --write-points --probe
  python3 scripts/build/batch_g05b_plans.py --layer buildout \\
      --poi /tmp/hf-g05b-construction.geojson \\
      --out ~/hf-data/2026-09-12/osm/buildout-walk-raster.json \\
      --write-points --probe
Outputs: gardens-walk-raster.json (Euclidean count-kernel master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-gardens.json
(fallback points for the Euclidean route + overlay) and
buildout-walk-raster.json (same wire shape) + derived-buildout.json
overlay sample. Restart the web server afterwards — the server caches
masters per process.
"""

import argparse
import base64
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_g03d_cadastre scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group05b.ts G05B_CAL mirrors these numbers
# exactly — test_batch_g05b.py parses that file and fails on drift.
G05B_CAL = {
    "gardens": {"half": 1, "sigma": 0.3},
    "buildout": {"half": 2, "sigma": 0.3},
}

LAYER_IDS = ("gardens", "buildout")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Kalamaja": (24.74131, 59.44757), "Hipodroom": (24.70261, 59.43249),
    "Viru": (24.7611, 59.4278), "Nomme": (24.68, 59.39),
    "Lasnamae": (24.82, 59.44), "Pirita": (24.821, 59.468),
    "Raadiku": (24.88473, 59.44107), "rural": (24.5, 59.2),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


# ---------------------------------------------------------------------------
# Source predicates (p106/p107 hinnang source sets).
# ---------------------------------------------------------------------------

def keep_garden(tags):
    """True when OSM tags mark a community growing site (NOT a backyard).

    landuse=allotments (aiandusühistud) or leisure=garden refined to
    garden:type=community / garden:style=kitchen. Bare leisure=garden
    (private residential backyards) is OUT — a backyard is not growing
    opportunity; landuse=orchard/farmland/meadow is OUT (p409
    agrifield's signal — keeping it here would re-skin that layer).
    Never throws.
    """
    if not isinstance(tags, dict):
        return False
    if tags.get("landuse") == "allotments":
        return True
    if tags.get("leisure") == "garden" and (
        tags.get("garden:type") == "community" or tags.get("garden:style") == "kitchen"
    ):
        return True
    return False


def keep_buildout(tags):
    """True when OSM tags mark an active construction site.

    landuse=construction ONLY (Hipodroomi kvartal, City Plaza 2...).
    Finished buildings, brownfields without the construction tag and
    untagged relation members are OUT. Never throws.
    """
    if not isinstance(tags, dict):
        return False
    return tags.get("landuse") == "construction"


LAYER_PRED = {
    "gardens": keep_garden,
    "buildout": keep_buildout,
}

# ~20 m spatial dedupe cells (mirrors snapshot.ts DEDUPE_LON/LAT).
DEDUPE_LON = 0.0004
DEDUPE_LAT = 0.0002


def dedupe_points(feats):
    """Collapse co-located points (~20 m cells, first wins).

    Needed because osmium export emits closed-way rings twice
    (LineString + MultiPolygon for the same garden): OSM-id dedupe
    in resolve_pois cannot see those pairs, and double-counting one
    garden would double its kernel weight. Distinct beds >20 m
    apart (e.g. Raadiku peenrad rows) stay separate — a garden
    cluster reads as more growing-dense.
    """
    seen = {}
    for lon, lat, w in feats:
        k = (round(lon / DEDUPE_LON), round(lat / DEDUPE_LAT))
        if k not in seen:
            seen[k] = (lon, lat, w)
    return list(seen.values())


def _area_score(acc, half):
    """Mirror of the grocery/healthcare scorer: saturate, null below 3."""

    def score_of(k):
        s = acc.get(k)
        if not s:
            return None
        sc = wr.saturate(s, half)
        return sc if sc >= 3 else None

    return score_of


def build_count_field(grid, half, sigma, poi_path, pred, name):
    """Euclidean Gaussian count kernel over kept source points.

    Bounded O(points * range^2) sweep: each site stamps
    kernel(d, sigma) into cells within 4 sigma. Returns (acc, stats).
    Graph-free on purpose (see module docstring: garden beds and
    fenced pits sit where the foot graph has no vertices — walk
    stamping leaves holes AT the facilities, moorage #154 story).
    """
    raw, stats = wr.resolve_pois(poi_path, pred)
    feats = dedupe_points(raw)
    cutoff_km = 4.0 * sigma
    acc = {}
    minlon, minlat, _, _ = grid.bbox
    for lon, lat, _ in feats:
        x0 = (lon - minlon) * LON_KM
        y0 = (lat - minlat) * LAT_KM
        ix_lo = max(0, int((x0 - cutoff_km) * 1000 / grid.step))
        ix_hi = min(grid.cols - 1, int((x0 + cutoff_km) * 1000 / grid.step))
        iy_lo = max(0, int((y0 - cutoff_km) * 1000 / grid.step))
        iy_hi = min(grid.rows - 1, int((y0 + cutoff_km) * 1000 / grid.step))
        for iy in range(iy_lo, iy_hi + 1):
            for ix in range(ix_lo, ix_hi + 1):
                clon = minlon + (ix + 0.5) * grid.step / 1000 / LON_KM
                clat = minlat + (iy + 0.5) * grid.step / 1000 / LAT_KM
                d = hav_km(lon, lat, clon, clat)
                if d > cutoff_km:
                    continue
                k = iy * grid.cols + ix
                acc[k] = acc.get(k, 0.0) + wr.kernel(d, sigma)
    print("%s: %d point features (%d raw, %d co-located merged), "
          "%d stamped cells"
          % (name, len(feats), stats["kept"], stats["kept"] - len(feats), len(acc)),
          flush=True)
    return acc, feats


# ---------------------------------------------------------------------------
# Grid (local copy for self-containment, mirrors batch_g03d_cadastre).
# ---------------------------------------------------------------------------

class Grid:
    """75 m county grid (mirrors walk_raster.Grid indexing)."""

    def __init__(self, bbox, step_m=STEP_M):
        self.bbox = list(bbox)
        self.step = step_m
        minlon, minlat, maxlon, maxlat = bbox
        self.cols = int(round((maxlon - minlon) * LON_KM * 1000 / step_m))
        self.rows = int(round((maxlat - minlat) * LAT_KM * 1000 / step_m))

    def cell_of(self, lon, lat):
        minlon, minlat, _, _ = self.bbox
        ix = int((lon - minlon) * LON_KM * 1000 / self.step)
        iy = int((lat - minlat) * LAT_KM * 1000 / self.step)
        if 0 <= ix < self.cols and 0 <= iy < self.rows:
            return iy * self.cols + ix
        return None

    def center_of(self, k):
        minlon, minlat, _, _ = self.bbox
        ix, iy = k % self.cols, k // self.cols
        return (minlon + (ix + 0.5) * self.step / 1000 / LON_KM,
                minlat + (iy + 0.5) * self.step / 1000 / LAT_KM)


# ---------------------------------------------------------------------------
# Wire output + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G05B_CAL[layer]
    return cal["half"], cal["sigma"]


def encode_wire(grid, values, layer="gardens"):
    half, sigma = contract_of(layer)
    return {
        "cols": grid.cols, "rows": grid.rows,
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step, "half": half, "sigma": sigma,
        "per": 0, "cap": 0, "unknown": 255, "dtype": "uint8",
        "data": base64.b64encode(bytes(values)).decode("ascii"),
    }


def score_bytes(grid, score_of):
    """Per-cell FINAL uint8 scores (255 = unknown), as raw bytes."""
    vals = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k in range(grid.cols * grid.rows):
        s = score_of(k)
        if s is not None:
            vals[k] = int(round(min(100.0, s)))
    return bytes(vals)


def probe_field(vals, grid, name):
    print("probe (%s goodness 0..100, high = sites near):" % name, flush=True)
    for pname, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-9s outside grid" % pname, flush=True)
            continue
        v = vals[k]
        print("  %-9s %s" % (pname, "unknown" if v == 255 else v), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True, choices=list(LAYER_IDS))
    ap.add_argument("--poi", default=None,
                    help="garden/construction geojson from the docstring osmium pre-step")
    ap.add_argument("--out", default=None,
                    help="raster output path")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-*.json overlay/fallback sample")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args()
    if not args.poi or not args.out:
        ap.error("--poi and --out are required")
    t0 = time.time()
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    defs = G05B_CAL[args.layer]
    acc, feats = build_count_field(grid, defs["half"], defs["sigma"],
                                   args.poi, LAYER_PRED[args.layer], args.layer)
    vals = score_bytes(grid, _area_score(acc, defs["half"]))
    doc = encode_wire(grid, vals, args.layer)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    raw = base64.b64decode(doc["data"])
    known = sum(1 for v in raw if v != 255)
    print("cells: %d known=%d (%.1f%%)" % (len(raw), known, 100 * known / len(raw)))
    print("wrote %s (%.1f MB, %.1fs)"
          % (args.out, os.path.getsize(args.out) / 1e6, time.time() - t0))
    if args.write_points:
        pts = [{"lon": lon, "lat": lat, "a": 1} for lon, lat, _ in feats]
        derived = os.path.join(os.path.dirname(args.out), "derived-%s.json" % args.layer)
        with open(derived, "w", encoding="utf-8") as f:
            json.dump(pts, f)
        print("wrote derived-%s.json (%d fallback points)" % (args.layer, len(pts)),
              flush=True)
    if args.probe:
        probe_field(vals, grid, args.layer)


if __name__ == "__main__":
    main()
