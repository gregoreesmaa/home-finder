"""Mobility/access leftover county masters (issue #133): droneclear (p220) /
droneviab (p270) / rentbleed (p386).

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; the full-county build runs only
via the documented rebuild command.

Per-param verdicts (documented in code + PR #133, OTA #131 precedent
for the no-map cases):

* p11 commute time (G12): DOCUMENTED NO-MAP. Reaffirms the issue #126
  delivery note ("scorer dims ONLY, no raster masters"): p11 is a
  per-listing minutes estimate with no destination, and a county kernel
  of GTFS frequency would duplicate the p15 transit layer under a new
  name. Scorer lives in services/scoring/dims_group12.py (untouched).
* p17 family/friends proximity (G12): DOCUMENTED NO-MAP. Where YOUR
  family lives is not a place attribute — no registry and no honest OSM
  proxy exists. New buyer-supplied scorer dim in
  services/scoring/dims_batch6.py (this batch).
* p220 drone delivery clearance (G13): REAL quiet layer. Disagrees with
  the #126 "no raster" note on the record: that note feared sparse
  point-kernel spikes, but a quiet-kind DISTANCE field has no spikes —
  every in-bbox cell reads its nearest-site distance (flightcorr/p445
  proves the shape for airspace-adjacent sources). Sources are
  aerodrome/helipad SITES (helipads included, no runway axis lobes —
  that is the honest split from flightcorr, which scores runway NOISE
  corridors and deliberately excludes helipads).
* p270 drone delivery viability (G13): REAL layer, min(clearance leg,
  yard leg) per cell — a drone needs BOTH likely-clear airspace AND
  somewhere to land, so min() is the honest combiner (same combiner as
  the services/scoring/dims_group13.py scorer, whose bands are mirrored
  exactly). The yard leg is raster-side + fallback-only for the wire
  contract (flightcorr minor-tier precedent): the wire half carries the
  clearance leg.
* p386 university-town rental bleed (G15): REAL quiet layer (hinnang).
  Student-rental pressure proxied by inverted nearest distance to
  mapped universities/colleges/dormitories. Red near campus = high
  pressure (owner-occupier framing, documented judgment call — the
  schools/p12 layer scores the same universities as variety GREEN, and
  buyer weights resolve the two views). Never euros: the EHIS/rental
  registries are not in the snapshot, so no EUR claim appears anywhere.

HONESTY (load-bearing): the EANS UTM DroneMap WFS, Maa-amet yard
clearances and any rental registry are NOT in the 2026-09-12 snapshot
(MANIFEST gaps), so every title/legend/source/reason says
"proksi (hinnang)" plus "mitte EANS DroneMap" where airspace is
claimed. Green = clear/viable/calm (far), red = restricted/unviable/
pressured (near). In-bbox absence of a mapped source IS the quiet
evidence, so masters emit no in-bbox unknowns (0 = known-exposed on
the source, never 255); out-of-coverage stays 255 server-side.

Model (locked 2026-09-12, candidate halves verified by --probe before
locking; witness table in PR #133):
* droneclear (p220): nearest aerodrome/helipad site: calm =
  100*d/(d+1300). Fits the scorer CLEARANCE_BANDS mid-range
  (1000 m -> 43 vs 40, 2000 m -> 61 vs 60, 4000 m -> 75 vs 75).
* droneviab (p270): min(100*d_aero/(d_aero+800), yard(d_park)) with the
  scorer YARD_BANDS step function (<=100: 100, <=300: 80, <=500: 60,
  <=1000: 40, else 25). Clear leg fits the scorer VIABILITY_CLEAR_BANDS
  mid-range (1000 m -> 56 vs 55, 2000 m -> 71 vs 75).
* rentbleed (p386): nearest university/college/dormitory: calm =
  100*d/(d+800). Tallinn probes sit mid-ramp (Balti ~43, Viru ~60).

Computation: exact full-grid 8-connectivity Dijkstra from rasterized
source cells (no cutoff, no cliffs) — the same kernel machinery as
batch_genv_exposure.py (grid scales 57.29/110.57, 75 m county step).
Air layers use direct (crow-flies-equivalent grid) distance BY DESIGN:
airspace zones are drawn as circles around sites (drones fly, they do
not walk) — walk-graph routing would speckle an airspace field with
footpath barriers. Rentbleed rides the same grid Dijkstra (a smooth
75 m proximity field; 9.375 m metro would be fake precision).

NO metro masters (documented, GENV precedent): smooth proxy fields at
the 75 m county step; the window route serves county everywhere.

One-time PBF export (snapshot dir input, NOT committed — same pattern
as batch_genv_exposure.py derived-aeroway.geojson; aeroway is reused):
  S=~/hf-data/2026-09-12/osm
  osmium tags-filter $S/harjumaa-260911.osm.pbf nwr/amenity=university \\
      nwr/amenity=college nwr/amenity=dormitory nwr/building=dormitory \\
      -o /tmp/b6-campus.pbf --overwrite
  osmium export -u type_id /tmp/b6-campus.pbf -o $S/derived-campus.geojson \\
      --overwrite
  # 104 features: university/college/dormitory objects (nodes + building
  # outlines) plus 32 untagged member nodes pulled in for way
  # completeness — the reader drops untagged junk (same twin/member rule
  # as batch_genv_noise_src.py).

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  python3 scripts/build/batch_b6_mobility.py --layer all \\
      --snap ~/hf-data/2026-09-12 --outdir ~/hf-data/2026-09-12/osm
  # single layer, small test bbox:
  python3 scripts/build/batch_b6_mobility.py --layer rentbleed \\
      --snap ~/hf-data/2026-09-12 --outdir /tmp/b6 \\
      --bbox 24.6 59.35 24.9 59.5 --probe
Outputs per layer: <id>-walk-raster.json (combined wire, WalkRasterDoc
shape so cleanRaster accepts it).
Overlay dots (vector layer above each raster, served via the generic
/api/layers/<layer> points route):
  python3 scripts/build/batch_b6_mobility.py --write-points \\
      --snap ~/hf-data/2026-09-12 --outdir /tmp/b6-ignore
# emits derived-droneclear/droneviab.json (scored airspace sites, twins
# included — dots show exactly what the raster scored) and
# derived-rentbleed.json (campus points with amenity/building/name tags).
# --outdir is unused in this mode.
"""

import argparse
import array
import base64
import heapq
import json
import math
import os
import sys
import time

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_genv_exposure.py scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DEDUPE_M = 20.0  # node+area twin guard (PR #118 family)

# Calibration locked 2026-09-12 (see module docstring probes).
# NOTE: apps/web/lib/layers_batch6.ts B6_CAL mirrors the scalars exactly
# — scripts/build/test_batch_b6.py parses that file and fails on drift.
# The yard step bands mirror services/scoring/dims_group13.py YARD_BANDS
# exactly (behavior-locked both sides, no parse).
B6_CAL = {
    "droneclear": {"half_m": 1300.0, "sigma": 0.3},
    "droneviab": {"clear_half_m": 800.0, "sigma": 0.3},
    "rentbleed": {"half_m": 800.0, "sigma": 0.3},
}

#: p270 yard leg: nearest open-landing proxy bands (== dims_group13 YARD_BANDS).
YARD_BANDS = ((100.0, 100), (300.0, 80), (500.0, 60), (1000.0, 40),
              (float("inf"), 25))

LAYER_IDS = ("droneclear", "droneviab", "rentbleed")

SITE_VALUES = ("aerodrome", "helipad")
CAMPUS_AMENITY = ("university", "college", "dormitory")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.68, 59.375),
    "rural": (24.5, 59.2), "airport": (24.79659, 59.41646),
    "TalTech": (24.6615, 59.3947),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> calmness 0..100: 0 on the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


def yard_score(d_m):
    """p270 yard leg: YARD_BANDS step function (== scorer bands)."""
    for limit, pts in YARD_BANDS:
        if d_m <= limit:
            return pts
    return YARD_BANDS[-1][1]


# ---------------------------------------------------------------------------
# Grid.
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
# Snapshot readers (offline files only).
# ---------------------------------------------------------------------------

def _need(snap, *parts):
    p = os.path.join(snap, *parts)
    if not os.path.exists(p):
        raise SystemExit(
            "missing %s — run the one-time osmium exports in this "
            "module's docstring (snapshot-only, no network)" % p)
    return p


def _geom_points(g):
    """One geometry -> representative points (twins kept: nearest-only
    fields are minimum-immune, PR #118 / dims_group13 convention)."""
    t = g.get("type")
    coords = g.get("coordinates")
    if not coords:
        return []
    if t == "Point":
        return [(coords[0], coords[1])]
    if t == "LineString":
        return [tuple(coords[len(coords) // 2])]
    if t == "Polygon":
        ring = coords[0] if coords else []
        if not ring:
            return []
        xs = [c[0] for c in ring]
        ys = [c[1] for c in ring]
        return [((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)]
    if t == "MultiPolygon":
        out = []
        for poly in coords:
            if not poly or not poly[0]:
                continue
            xs = [c[0] for c in poly[0]]
            ys = [c[1] for c in poly[0]]
            out.append(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
        return out
    return []


def _tagged_overlay_tags(p, keep):
    """Small honest tag subset for overlay dots (names kept, junk dropped)."""
    tags = {}
    for k in keep:
        v = p.get(k)
        if isinstance(v, str) and v:
            tags[k] = v
    name = p.get("name")
    if isinstance(name, str) and name:
        tags["name"] = name
    return tags


def read_air_sites(snap):
    """(points, overlay, stats): aerodrome/helipad SITES from the shared
    derived-aeroway.geojson export (no new PBF pass needed).

    Runways/taxiways/aprons/navigationaids are deliberately NOT sites:
    they are sub-parts of an airfield (flightcorr/p445 owns runway
    noise). Ways/polygons collapse to midpoint/bbox-center reps; the
    residual twin risk (Tallinna lennujaam as node + way + multipolygon
    ~2.1 km apart, Ämari likewise — dims_group13 convention) cannot move
    a nearest-only minimum. Overlay dots show every scored centroid.
    """
    d = json.load(open(_need(snap, "osm", "derived-aeroway.geojson"),
                       encoding="utf-8"))
    feats = d["features"] if isinstance(d, dict) else d
    pts, overlay = [], []
    stats = {"aerodrome": 0, "helipad": 0, "skipped": 0}
    for f in feats:
        p = f.get("properties") or {}
        if p.get("aeroway") not in SITE_VALUES:
            stats["skipped"] += 1
            continue
        reps = _geom_points(f.get("geometry") or {})
        if not reps:
            stats["skipped"] += 1
            continue
        stats[p["aeroway"]] += 1
        pts.extend(reps)
        tags = _tagged_overlay_tags(p, ("aeroway", "surface"))
        for lon, lat in reps:
            dot = {"lon": round(lon, 6), "lat": round(lat, 6)}
            if tags:
                dot["tags"] = dict(tags)
            overlay.append(dot)
    return pts, overlay, stats


def read_campus_points(snap):
    """(points, overlay, stats): universities/colleges/dormitories from
    the one-time derived-campus.geojson export.

    Points as-is; building outlines collapse to bbox-center reps (a dorm
    block is one pressure source, not a ring of them). Features with
    neither amenity=university|college|dormitory nor
    building=dormitory are untagged member nodes pulled in for way
    completeness — dropped (same rule as batch_genv_noise_src.py).
    Overlay dots keep amenity/building/name tags.
    """
    d = json.load(open(_need(snap, "osm", "derived-campus.geojson"),
                       encoding="utf-8"))
    feats = d["features"] if isinstance(d, dict) else d
    pts, overlay = [], []
    stats = {"university": 0, "college": 0, "dormitory": 0, "skipped": 0}
    for f in feats:
        p = f.get("properties") or {}
        amenity = p.get("amenity")
        building = p.get("building")
        if amenity in ("university", "college"):
            kind = amenity
        elif amenity == "dormitory" or building == "dormitory":
            kind = "dormitory"
        else:
            stats["skipped"] += 1
            continue
        reps = _geom_points(f.get("geometry") or {})
        if not reps:
            stats["skipped"] += 1
            continue
        stats[kind] += 1
        pts.extend(reps)
        tags = _tagged_overlay_tags(p, ("amenity", "building"))
        for lon, lat in reps:
            dot = {"lon": round(lon, 6), "lat": round(lat, 6)}
            if tags:
                dot["tags"] = dict(tags)
            overlay.append(dot)
    return pts, overlay, stats


def read_park_points(snap):
    """p270 yard leg: mapped open-space points (shared derived-parks.json)."""
    pts = json.load(open(_need(snap, "osm", "derived-parks.json")))
    return [(p["lon"], p["lat"]) for p in pts]


# ---------------------------------------------------------------------------
# Fields: exact grid Dijkstra (mirrors batch_genv_exposure.py).
# ---------------------------------------------------------------------------

def dijkstra_km(grid, source_cells):
    """Exact 8-connectivity distance (km) to the nearest source cell.

    No cutoff (sparse sources: no cliffs). Orthogonal step = cell km,
    diagonal = *sqrt(2); longitude scaled by LON_KM at cell latitude.
    Returns array('d') with +inf where unreachable (never in practice).
    """
    INF = float("inf")
    dist = array.array("d", [INF]) * (grid.cols * grid.rows)
    ortho = grid.step / 1000.0
    step_w = {1: ortho, 2: ortho * math.sqrt(2.0)}
    pq = []
    for k in source_cells:
        if 0 <= k < len(dist) and dist[k] > 0:
            dist[k] = 0.0
            heapq.heappush(pq, (0.0, k))
    cols, rows = grid.cols, grid.rows
    while pq:
        d, k = heapq.heappop(pq)
        if d > dist[k]:
            continue
        ix, iy = k % cols, k // cols
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1),
                       (-1, -1), (-1, 1), (1, -1), (1, 1)):
            jx, jy = ix + dx, iy + dy
            if not (0 <= jx < cols and 0 <= jy < rows):
                continue
            nd = d + step_w[dx * dx + dy * dy]
            j = jy * cols + jx
            if nd < dist[j]:
                dist[j] = nd
                heapq.heappush(pq, (nd, j))
    return dist


def cells_of_points(grid, points):
    out = set()
    for lon, lat in points:
        k = grid.cell_of(lon, lat)
        if k is not None:
            out.add(k)
    return out


def dedupe_cells(points, cell_m=DEDUPE_M):
    """Merge node+area twins falling in the same ~cell_m cell."""
    cells = {}
    for lon, lat in points:
        k = (round(lon * LON_KM * 1000 / cell_m),
             round(lat * LAT_KM * 1000 / cell_m))
        if k not in cells:
            cells[k] = (lon, lat)
    return list(cells.values())


# ---------------------------------------------------------------------------
# Layer scores (high = clear/viable/calm; 0 = known-exposed, never 255).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-source calmness 100*d/(d+half) for one distance field."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


def score_droneviab(d_aero_km, d_park_km, cal):
    """min(clearance leg, yard leg): the blocker binds, never an average
    (same combiner as the dims_group13.py scorer)."""
    out = bytearray(len(d_aero_km))
    for k in range(len(d_aero_km)):
        clear = quiet_from_half(d_aero_km[k] * 1000.0, cal["clear_half_m"])
        yard = yard_score(d_park_km[k] * 1000.0)
        out[k] = max(0, min(100, int(round(min(clear, yard)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook.

    droneviab carries the CLEARANCE leg half (the yard leg is
    raster-side + fallback-only — flightcorr minor-tier precedent).
    """
    cal = B6_CAL[layer]
    if layer == "droneviab":
        return cal["clear_half_m"], cal["sigma"]
    return cal["half_m"], cal["sigma"]


def encode_wire(grid, values, layer):
    half, sigma = contract_of(layer)
    return {
        "cols": grid.cols, "rows": grid.rows,
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step, "half": half, "sigma": sigma,
        "per": 0, "cap": 0, "unknown": 255, "dtype": "uint8",
        "data": base64.b64encode(bytes(values)).decode("ascii"),
    }


def write_outputs(outdir, layer, grid, values):
    name = "%s-walk-raster" % layer
    with open(os.path.join(outdir, name + ".json"), "w",
              encoding="utf-8") as f:
        json.dump(encode_wire(grid, values, layer), f)
    print("wrote %s.json" % name, flush=True)


def build_all(snap, grid, cache_path):
    """Shared fields once -> per-layer byte masters. Returns {layer: bytes}."""
    t0 = time.time()
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            import pickle
            fields = pickle.load(f)
        print("fields: loaded %s (skipped stamping)" % cache_path, flush=True)
    else:
        print("air sites: reading aeroway export...", flush=True)
        aero_pts, _, aero_stats = read_air_sites(snap)
        print("air=%s" % (aero_stats,), flush=True)
        print("campus: reading campus export...", flush=True)
        camp_pts, _, camp_stats = read_campus_points(snap)
        print("campus=%s" % (camp_stats,), flush=True)
        print("parks: reading derived-parks...", flush=True)
        park_pts = read_park_points(snap)
        print("parks: %d points" % len(park_pts), flush=True)

        cal = B6_CAL
        print("dijkstra: air sites (droneclear/droneviab)...", flush=True)
        d_aero = dijkstra_km(grid, cells_of_points(grid, aero_pts))
        print("dijkstra: campus (rentbleed)...", flush=True)
        d_camp = dijkstra_km(grid, cells_of_points(grid, camp_pts))
        print("dijkstra: parks (droneviab yard leg)...", flush=True)
        d_park = dijkstra_km(grid, cells_of_points(grid, park_pts))
        fields = {"d_aero": d_aero, "d_camp": d_camp, "d_park": d_park}
        if cache_path:
            with open(cache_path, "wb") as f:
                import pickle
                pickle.dump(fields, f, protocol=4)
            print("fields: saved %s" % cache_path, flush=True)
    print("fields ready (%.1fs)" % (time.time() - t0), flush=True)

    out = {}
    out["droneclear"] = score_distance(
        fields["d_aero"], B6_CAL["droneclear"]["half_m"])
    out["droneviab"] = score_droneviab(
        fields["d_aero"], fields["d_park"], B6_CAL["droneviab"])
    out["rentbleed"] = score_distance(
        fields["d_camp"], B6_CAL["rentbleed"]["half_m"])
    return out


# ---------------------------------------------------------------------------
# Overlay points (derived-<layer>.json): scored source sites for the
# vector dots above each raster (see apps/web/lib/overlays.ts). Served
# through the generic /api/layers/<layer> points route; the client
# stride-caps to 800 markers.
# ---------------------------------------------------------------------------

POINT_CAP = 8000  # per-layer overlay sample cap (client caps again at 800)


def stride_sample(pts, cap=POINT_CAP):
    """Deterministic stride thin to <= cap entries (keeps spatial spread)."""
    pts = list(pts)
    if len(pts) <= cap:
        return pts
    step = len(pts) / cap
    return [pts[int(i * step)] for i in range(cap)]


def write_points(snap):
    """Emit derived-<layer>.json overlay samples into <snap>/osm."""
    _, aero_overlay, _ = read_air_sites(snap)
    _, camp_overlay, _ = read_campus_points(snap)
    payloads = {
        "droneclear": stride_sample(aero_overlay),
        "droneviab": stride_sample(aero_overlay),
        "rentbleed": stride_sample(camp_overlay),
    }
    counts = {}
    for layer, pts in payloads.items():
        path = os.path.join(snap, "osm", "derived-%s.json" % layer)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(pts, f)
        counts[layer] = len(pts)
        print("points %s: %d" % (layer, len(pts)), flush=True)
    return counts


def probe_scores(masters, grid):
    print("probe (high = clear/viable/calm):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-9s outside grid" % name, flush=True)
            continue
        print("  %-9s %s" % (name, {l: masters[l][k] for l in LAYER_IDS}),
              flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=False, default="all",
                    choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--snap", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--stamp-cache", default=None)
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    ap.add_argument("--write-points", action="store_true",
                    help="emit derived-<layer>.json overlay samples and exit")
    args = ap.parse_args()
    if args.write_points:
        write_points(args.snap)
        return
    os.makedirs(args.outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step), flush=True)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    cache = args.stamp_cache or os.path.join(args.outdir, "b6-fields.pkl")
    masters = build_all(args.snap, grid, cache if args.layer == "all" else None)
    for layer in layers:
        write_outputs(args.outdir, layer, grid, masters[layer])
        vals = masters[layer]
        known = sum(1 for v in vals if v != 255)
        print("%s: cells=%d known=%d zeros(known-exposed)=%d" %
              (layer, len(vals), known, sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
