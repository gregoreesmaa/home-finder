"""Group 15 education + Group 11 leftover county masters (issue #116).

Layers (parameters3.md sections 5.15/5.11, all absolute 0-100):
  schoolchoice  p130  school-choice density (amenity=school count /1.5km)
  redistrict    p314  redistricting-exposure proxy (school count /2km)
  weedwater     p338  inland-water proximity (natural=water et al.)
  festival      p442  event-venue quiet, INVERTED (events/market/attraction)
  stadium       p462  stadium quiet, INVERTED (leisure=stadium)

Stdlib only. Offline, snapshot-only (NO network): all vectors come from
the local 2026-09-12 snapshot. Pure logic + snapshot readers live at
module top so unit tests stay hermetic; the full-county build runs only
via the documented rebuild command.

HONESTY (load-bearing): EHIS lottery/redistricting internals, aquatic
weed-management activity and the festival calendar are NOT in the
snapshot, so these are OSM PROXIMITY proxies — titles, legends and
sources say "proksi", never official odds/measured activity. Green/red
directions are explicit per layer (schoolchoice/weedwater green-near;
festival/stadium green-far/red-near). In-bbox absence of a mapped
source IS the evidence (0 = known-bad on that proxy, never 255);
out-of-coverage stays 255 server-side (cover mask).

Model (locked 2026-09-12 from snapshot probes at Balti/Viru/Kadriorg/
Oismae/Lasnamae/Viimsi/rural/airport/Lauluvaljak):
* schoolchoice (p130): EXACT deduped amenity=school counts within
  1.5 km per cell -> 100*S/(S+6), the same formula as the scorer, so
  raster and listing scores agree. Probe S: Balti ~35 -> ~85,
  Lasnamäe ~8 -> ~57, Viimsi ~6 -> 50, rural 0 -> 0.
* redistrict (p314): same points counted within 2 km -> 100*S/(S+2);
  discriminates the sparse end (Viimsi ~75, rural 0). Correlates with
  schoolchoice by construction (documented judgment call: both ARE
  school-density framings — choice vs dependency).
* weedwater (p338): exact full-grid Dijkstra to rasterized inland-water
  cells (natural=water polygons/lines + water=pond|lake|reservoir|basin|
  river, densified <= 50 m) -> 100*600/(d+600). Green-near waterfront
  amenity; management activity unknown (said in legend/source).
* festival (p442): Dijkstra to event venues (amenity=events_venue|
  marketplace + tourism=attraction, 177 features, points + centroids)
  -> quiet 100*d/(d+500). Red-near (disruption), green-far.
* stadium (p462): Dijkstra to stadium grounds (leisure=stadium 55,
  densified ring vertices <= 50 m) -> quiet 100*d/(d+800). Red-near
  (event traffic), green-far. leisure=pitch excluded (2723 pitches
  would paint the county red; pitches draw no event traffic).

Computation: count layers count sources exactly within the calibration
radius per cell; distance layers run exact full-grid 8-connectivity
Dijkstra from rasterized source cells (no cutoff, no cliffs). Grid
mirrors walk_raster (75 m county, 57.29/110.57 scales). Euclidean
throughout; walk-graph refinement is a central follow-up.

NO metro masters (documented): a count/distance-decay proxy is smooth
at 75 m; 9.375 m cells would be fake precision. The window route serves
county everywhere (metro slot stays empty).

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored).
Water polygons come from the snapshot PBF (the amenities extract drops
all but 12 small ponds, so a one-time osmium export is required):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \\
      natural=water water=pond water=lake water=reservoir \\
      water=basin water=river -o /tmp/g15-water.osm.pbf
  osmium export /tmp/g15-water.osm.pbf \\
      -o ~/hf-data/2026-09-12/osm/derived-water.geojson
  python3 scripts/build/batch_g15_edu.py --layer all \\
      --snap ~/hf-data/2026-09-12 --outdir ~/hf-data/2026-09-12/osm
  # single layer, small test bbox:
  python3 scripts/build/batch_g15_edu.py --layer festival \\
      --snap ~/hf-data/2026-09-12 --outdir /tmp/g15 \\
      --bbox 24.6 59.35 24.9 59.5 --probe
Outputs per layer: <id>-walk-raster.json (combined wire, WalkRasterDoc
shape so cleanRaster accepts it); --format split writes <id>-walk-raster.json
(meta, data stubbed) + <id>-walk-raster.u8 (raw master).
"""

import argparse
import base64
import heapq
import json
import math
import os
import sys
import time

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster scales; G15_CAL mirrors dims_group15.py +
# apps/web/lib/layers_group15.ts GROUP15_CAL — drift-checked by tests).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 50.0  # polygon/line vertex spacing for distance sources

# NOTE: apps/web/lib/layers_group15.ts GROUP15_CAL mirrors these numbers
# exactly — test_batch_g15.py parses that file and fails on drift, as it
# does for services/scoring/dims_group15.py constants.
G15_CAL = {
    "schoolchoice": {"sigma": 0.5, "radius_m": 1500.0, "half": 6.0},
    "redistrict": {"sigma": 0.8, "radius_m": 2000.0, "half": 2.0},
    "weedwater": {"half_m": 600.0, "sigma": 0.5},
    "festival": {"half_m": 500.0, "sigma": 0.5},
    "stadium": {"half_m": 800.0, "sigma": 0.8},
}

LAYER_IDS = ("schoolchoice", "redistrict", "weedwater", "festival", "stadium")

VENUE_AMENITIES = ("events_venue", "marketplace")
WATER_VALUES = ("pond", "lake", "reservoir", "basin", "river")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "rural": (24.5, 59.2), "airport": (24.79659, 59.41646),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def saturate(count, half):
    """Unweighted count -> 0..100: 100*S/(S+half); 0 stays 0 (evidence)."""
    return 100.0 * count / (count + half)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> calmness 0..100: 0 on the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


def shore_from_half(d_m, half_m):
    """Distance (m) -> waterfront amenity: 100 at shore, 50 at half_m."""
    return 100.0 * half_m / (d_m + half_m) if d_m < float("inf") else 0.0


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


def count_within(grid, points, radius_m):
    """Exact hard-radius counts per cell (matches the scorer formula).

    For each source point every cell centre within radius_m gains one.
    radius_m / step_m bounds the neighbourhood, so the full-county cost
    stays trivial (~301 schools x ~1300 cells).
    """
    acc = [0] * (grid.cols * grid.rows)
    reach = int(math.ceil(radius_m / grid.step)) + 1
    for lon, lat in points:
        c = grid.cell_of(lon, lat)
        if c is None:
            continue
        cx, cy = c % grid.cols, c // grid.cols
        for dy in range(-reach, reach + 1):
            iy = cy + dy
            if iy < 0 or iy >= grid.rows:
                continue
            for dx in range(-reach, reach + 1):
                ix = cx + dx
                if ix < 0 or ix >= grid.cols:
                    continue
                k = iy * grid.cols + ix
                clon, clat = grid.center_of(k)
                if hav_km(lon, lat, clon, clat) * 1000.0 <= radius_m:
                    acc[k] += 1
    return acc


def dijkstra_km(grid, sources):
    """Exact 8-connectivity distances (km) from source cells, no cutoff."""
    n = grid.cols * grid.rows
    dist = [float("inf")] * n
    pq = []
    for s in sources:
        if 0 <= s < n and dist[s] > 0.0:
            dist[s] = 0.0
            heapq.heappush(pq, (0.0, s))
    step_lon = grid.step / 1000 / LON_KM
    step_lat = grid.step / 1000 / LAT_KM
    diag = math.hypot(step_lon * LON_KM, step_lat * LAT_KM)
    ortho_lon = step_lon * LON_KM
    ortho_lat = step_lat * LAT_KM
    while pq:
        d, k = heapq.heappop(pq)
        if d > dist[k]:
            continue
        ix, iy = k % grid.cols, k // grid.cols
        for dx, dy, w in ((1, 0, ortho_lon), (-1, 0, ortho_lon),
                          (0, 1, ortho_lat), (0, -1, ortho_lat),
                          (1, 1, diag), (1, -1, diag),
                          (-1, 1, diag), (-1, -1, diag)):
            jx, jy = ix + dx, iy + dy
            if 0 <= jx < grid.cols and 0 <= jy < grid.rows:
                j = jy * grid.cols + jx
                nd = d + w
                if nd < dist[j]:
                    dist[j] = nd
                    heapq.heappush(pq, (nd, j))
    return dist


# ---------------------------------------------------------------------------
# Snapshot readers (offline files only — never the network).
# ---------------------------------------------------------------------------

def _rings_of(geom):
    t = (geom or {}).get("type")
    if t == "Point":
        return [[geom["coordinates"]]]
    if t == "LineString":
        return [geom["coordinates"]]
    if t == "Polygon":
        return geom["coordinates"]
    if t == "MultiPolygon":
        return [r for poly in geom["coordinates"] for r in poly]
    return []


def _centroid(rings):
    xs = [x for r in rings for x, _ in r]
    ys = [y for r in rings for _, y in r]
    return (sum(xs) / len(xs), sum(ys) / len(ys)) if xs else None


def _densify(rings, max_m=DENSIFY_M):
    """Ring vertices subdivided so no gap exceeds max_m (metres)."""
    out = []
    for r in rings:
        for a, b in zip(r, r[1:] + r[:1]):
            out.append(a)
            d_km = hav_km(a[0], a[1], b[0], b[1])
            steps = int(d_km * 1000 / max_m)
            for i in range(1, steps + 1):
                f = i / (steps + 1)
                out.append([a[0] + (b[0] - a[0]) * f,
                            a[1] + (b[1] - a[1]) * f])
    return out


def _iter_geojson(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        feats = data["features"]
    elif isinstance(data, list):
        feats = data
    else:
        feats = []
    for ft in feats:
        if not isinstance(ft, dict):
            continue
        props = ft.get("properties") or {}
        geom = ft.get("geometry") or {}
        if not isinstance(props, dict):
            continue
        yield props, geom


def is_school_tags(tags):
    return isinstance(tags, dict) and tags.get("amenity") == "school"


def is_stadium_tags(tags):
    return isinstance(tags, dict) and tags.get("leisure") == "stadium"


def is_venue_tags(tags):
    """Event/festival-capable venues. theatre/museum/gallery stay p89
    culture and community_centre/townhall stay p87 community (#98)."""
    return (isinstance(tags, dict)
            and (tags.get("amenity") in VENUE_AMENITIES
                 or tags.get("tourism") == "attraction"))


def is_water_tags(tags):
    """Inland water where weed management applies. Fountains, pools and
    water parks excluded (no weed habitat); the sea is coastline, not
    water here."""
    return (isinstance(tags, dict)
            and tags.get("amenity") != "fountain"
            and tags.get("leisure") not in ("swimming_pool", "water_park")
            and (tags.get("natural") == "water"
                 or tags.get("water") in WATER_VALUES))


def read_school_points(snap):
    """Deduped amenity=school lon/lat from derived-schools.json.

    The snapshot carries node+way-centre dupes (41 pairs county-wide);
    identical coords collapse to one so counts never double-book.
    """
    path = os.path.join(snap, "osm", "derived-schools.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    seen = set()
    pts = []
    for feat in data:
        tags = (feat or {}).get("tags") or {}
        if not is_school_tags(tags):
            continue
        key = (round(feat["lon"], 6), round(feat["lat"], 6))
        if key not in seen:
            seen.add(key)
            pts.append((feat["lon"], feat["lat"]))
    return pts


def _iter_amenities(snap):
    yield from _iter_geojson(
        os.path.join(snap, "osm", "harju-amenities.geojson"))


def read_polygon_points(snap, pred, stats_key, stats):
    """Centroid per matching amenity feature (stadiums, venues)."""
    pts = []
    for props, geom in _iter_amenities(snap):
        if not pred(props):
            continue
        stats[stats_key] = stats.get(stats_key, 0) + 1
        if geom.get("type") == "Point":
            pts.append(tuple(geom["coordinates"][:2]))
        else:
            c = _centroid(_rings_of(geom))
            if c is not None:
                pts.append(c)
    return pts


def read_edge_cells(grid, feats, pred, stats_key, stats):
    """Raster cells on densified water/stadium edges (distance sources).

    `feats` is an iterable of (props, geom) pairs, so water can come
    from the PBF export while stadiums use the amenities extract.
    """
    cells = set()
    for props, geom in feats:
        if not pred(props):
            continue
        stats[stats_key] = stats.get(stats_key, 0) + 1
        if geom.get("type") == "Point":
            lon, lat = geom["coordinates"][:2]
            k = grid.cell_of(lon, lat)
            if k is not None:
                cells.add(k)
        else:
            for lon, lat in _densify(_rings_of(geom)):
                k = grid.cell_of(lon, lat)
                if k is not None:
                    cells.add(k)
    return cells


# ---------------------------------------------------------------------------
# Layer builders -> uint8 value lists.
# ---------------------------------------------------------------------------

def build_count_layer(grid, snap, cal, stats):
    """Exact hard-radius choice/dependency score from school points.

    Same formula as the scorer (100*n/(n+half) on deduped counts), so
    raster and listing scores agree up to walk-vs-Euclidean geometry.
    """
    pts = read_school_points(snap)
    stats["schools"] = len(pts)
    acc = count_within(grid, pts, cal["radius_m"])
    return [max(0, min(100, int(round(saturate(s, cal["half"])))))
            for s in acc]


def build_distance_layer(grid, feats, pred, stats_key, score_fn, half_m,
                         stats, kind_label):
    """Exact-Dijkstra distance score from polygon-edge source cells."""
    cells = read_edge_cells(grid, feats, pred, stats_key, stats)
    stats[kind_label + "_cells"] = len(cells)
    dist = dijkstra_km(grid, cells)
    return [max(0, min(100, int(round(score_fn(d * 1000.0, half_m)))))
            if d < float("inf") else 255 for d in dist]


def default_water_path(snap):
    return os.path.join(snap, "osm", "derived-water.geojson")


def build_layer(grid, snap, layer, stats, water_path=None):
    cal = G15_CAL[layer]
    if layer in ("schoolchoice", "redistrict"):
        return build_count_layer(grid, snap, cal, stats)
    if layer == "weedwater":
        path = water_path or default_water_path(snap)
        if not os.path.exists(path):
            raise FileNotFoundError(
                "water export missing: %s — build it once with:\n"
                "  osmium tags-filter %s harjumaa-260911.osm.pbf \\\n"
                "      natural=water water=pond water=lake water=reservoir \\\n"
                "      water=basin water=river -o /tmp/g15-water.osm.pbf\n"
                "  osmium export /tmp/g15-water.osm.pbf -o %s"
                % (path, os.path.join(snap, "osm"), path))
        return build_distance_layer(grid, _iter_geojson(path), is_water_tags,
                                    "water", shore_from_half, cal["half_m"],
                                    stats, "water")
    if layer == "festival":
        venues = read_polygon_points(snap, is_venue_tags, "venues", stats)
        cells = set()
        for lon, lat in venues:
            k = grid.cell_of(lon, lat)
            if k is not None:
                cells.add(k)
        stats["venue_cells"] = len(cells)
        dist = dijkstra_km(grid, cells)
        return [max(0, min(100, int(round(quiet_from_half(d * 1000.0,
                                                        cal["half_m"])))))
                if d < float("inf") else 255 for d in dist]
    if layer == "stadium":
        return build_distance_layer(grid, _iter_amenities(snap),
                                    is_stadium_tags, "stadiums",
                                    quiet_from_half, cal["half_m"], stats,
                                    "stadium")
    raise ValueError("unknown layer: %s" % layer)


# ---------------------------------------------------------------------------
# Wire encoding (WalkRasterDoc shape so cleanRaster accepts it).
# ---------------------------------------------------------------------------

def spec_for(layer):
    """(half, sigma) carried in the wire doc — must match the TS spec
    (group15MatchesContract): area layers carry the count half,
    distance layers carry halfM in metres."""
    cal = G15_CAL[layer]
    sigma = {"schoolchoice": 0.5, "redistrict": 0.8, "weedwater": 0.5,
             "festival": 0.5, "stadium": 0.8}[layer]
    half = cal["half"] if layer in ("schoolchoice", "redistrict") \
        else cal["half_m"]
    return half, sigma


def encode_wire(grid, vals, layer):
    half, sigma = spec_for(layer)
    return {
        "cols": grid.cols, "rows": grid.rows,
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step, "half": half, "sigma": sigma,
        "per": 0, "cap": 0, "unknown": 255, "dtype": "uint8",
        "data": base64.b64encode(bytes(vals)).decode("ascii"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--layer", default="all",
                    choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--snap", required=True, help="snapshot root dir")
    ap.add_argument("--outdir", required=True, help="output dir for masters")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"),
                    help="override bbox (default: county)")
    ap.add_argument("--water", default=None,
                    help="water export geojson (default: "
                         "<snap>/osm/derived-water.geojson)")
    ap.add_argument("--format", default="combined", choices=["combined", "split"])
    ap.add_argument("--probe", action="store_true",
                    help="print calibration probe values after building")
    args = ap.parse_args(argv)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    bbox = args.bbox or COUNTY_BBOX
    os.makedirs(args.outdir, exist_ok=True)
    t0 = time.time()
    for layer in layers:
        grid = Grid(bbox)
        stats = {}
        vals = build_layer(grid, args.snap, layer, stats,
                           water_path=args.water)
        doc = encode_wire(grid, vals, layer)
        base = os.path.join(args.outdir, "%s-walk-raster" % layer)
        if args.format == "split":
            meta = dict(doc, data="")
            with open(base + ".json", "w", encoding="utf-8") as f:
                json.dump(meta, f)
            with open(base + ".u8", "wb") as f:
                f.write(bytes(vals))
        else:
            with open(base + ".json", "w", encoding="utf-8") as f:
                json.dump(doc, f)
        known = sum(1 for v in vals if v != 255)
        print("%s: %d cells (%d known), stats=%s" % (layer, len(vals),
                                                    known, stats),
              file=sys.stderr)
        if args.probe:
            for name, (lon, lat) in PROBE_POINTS.items():
                k = grid.cell_of(lon, lat)
                print("  probe %s -> %s" % (name, vals[k] if k is not None
                                            else "out-of-bbox"))
    print("done in %.1fs" % (time.time() - t0), file=sys.stderr)


if __name__ == "__main__":
    main()
