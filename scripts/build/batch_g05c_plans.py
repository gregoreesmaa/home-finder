"""Group 5 plans-C county masters (issue #163): p223 commbleed + p224
windsolar + p225 viewshed.

Stdlib only. Offline, snapshot-only (NO network): commercial-zone
vectors, wind/solar-farm vectors and viewpoint vectors come from the
LOCAL Harjumaa PBF via the documented osmium pre-steps, never from a
live service. Pure logic + snapshot readers live at module top so unit
tests stay hermetic; full-county builds run only via the documented
rebuild commands.

SCOPE (three layers, honest): this builder serves ONLY p223
(commercial zoning bleed) as a mapped-commercial-zone proximity
hinnang, p224 (wind/solar farm proximity) as a mapped-farm distance
field, and p225 (view shedding ordinances) as a mapped-viewpoint
count hinnang. The sibling params are documented no-map (see
apps/web/lib/layers_group05c.ts): p221 eminent domain risk (a
per-parcel legal fact with no area signal) and p222 flight path
re-routing (a schedule fact already scored twice: flightcorr p445 +
droneclear p220) ship as scorer dims only
(services/scoring/dims_group05c.py), OTA PR #131 precedent.

HONESTY (load-bearing): the PLANK register, Tallinna Planeeringute
Register, KOV expropriation decisions, EANS schedules and the Elering
generation register are NOT in the 2026-09-12 snapshot, so no master
is registry data. commbleed scores nearness to MAPPED commercial /
retail landuse + malls (bleed pressure, not a zoning decision);
windsolar scores distance to MAPPED turbines + farm-scale solar (the
param's own ST_Distance shape, never a production ruling); viewshed
scores the COUNT of mapped scenic viewpoints nearby (area-kind,
moorage precedent — never a height-limit ruling). Titles, legends and
sources say "hinnang" (pinned by layers_group05c.test.ts).

Models (locked 2026-09-12):
* commbleed (p223): exact full-grid 8-connectivity Dijkstra distance
  to the nearest commercial-zone cell (same machinery as
  batch_g07b_envhealth.py, local Grid copy for self-containment),
  score = 100*d/(d+300). halfM=300 m: mall traffic/noise pressure is
  block-scale — Ülemiste/Rocca al Mare read honestly low, detached
  Nõmme reads calm. Commercial polygons are FILLED (a parcel inside
  the zone reads 0: inside IS the bleed); mall points/lines feed
  directly/densified.
* windsolar (p224): exact full-grid Dijkstra distance to the nearest
  farm cell, score = 100*d/(d+800). halfM=800 m tracks turbine
  setback literature (500-1000 m visual/noise; solar glare is local,
  turbines dominate). Rooftop panels are OUT by design (1734 roof +
  unknown-location small installs: a panel is not a farm);
  diesel/gas/biofuel/hydro are OUT (not wind/solar).
* viewshed (p225): Euclidean Gaussian count kernel over kept
  viewpoint dots (sigma 0.3, cutoff 4 sigma, saturating score
  100*S/(S+1), unstamped cells stay 255 unknown — same shape as
  moorage, batch_g03d_cadastre.py). half=1 (not 2): with 88 county
  viewpoints (44 Tallinn-window: Kohtuotsa/Patkuli/Piiskopi,
  klint edges) ONE mapped platform reads 50 on its own cell
  (mid-amber) instead of vanishing; viewpoint deserts read honestly
  unknown. Green sits NEAR the amenity (protection likely).

Sources (predicates verified on the snapshot extract):
* commercial: landuse in (commercial, retail) or shop=mall
  (verified 2026-09-12: 854 kept county-wide, 670 in the Tallinn
  window). Plain supermarkets are OUT by design (grocery's own,
  #98): malls/retail parks are bleed pressure, not errands.
  Untagged relation members carry no landuse/shop, so they drop out
  in keep_comm — no twin purge needed beyond the cell dedupe.
* farm: generator:source=wind (any location, 53) or
  generator:source=solar with location in (ground, surface,
  overground) (102). Verified 2026-09-12: 155 kept county-wide, 91
  in the Tallinn window (incl. a Nõmme turbine). Turbines feed as
  points; solar-farm polygons feed stride-sampled outer rings (a
  distance field only needs the boundary; interiors read near-zero
  through the ring Dijkstra at 75 m cells).
* viewpoint: tourism=viewpoint ONLY (verified 2026-09-12: 88 kept
  county-wide, 44 in the Tallinn window). Points feed directly;
  bog bird-towers dilute the rural field BY DESIGN (documented in
  the TS verdict, not hidden).

Computation: commbleed + windsolar are graph-free Euclidean fields
on the 75 m county grid (57.29/110.57 scales) — exact-grid Dijkstra
nearest-source distance; viewshed is a graph-free Gaussian count
kernel on the same grid. NO metro masters (documented): smooth
distance-decay fields and a sparse count kernel at 9.375 m cells
would be fake precision — the window route serves county
everywhere.

Rebuild (needs the snapshot dir, NOT committed — masters are gitignored):
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/landuse=commercial nwr/landuse=retail nwr/shop=mall \
      -o /tmp/hf-g05c-comm.pbf --overwrite
  osmium export /tmp/hf-g05c-comm.pbf -o /tmp/hf-g05c-comm.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/power=generator \
      -o /tmp/hf-g05c-gen.pbf --overwrite
  osmium export /tmp/hf-g05c-gen.pbf -o /tmp/hf-g05c-gen.geojson
  osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
      nwr/tourism=viewpoint \
      -o /tmp/hf-g05c-view.pbf --overwrite
  osmium export /tmp/hf-g05c-view.pbf -o /tmp/hf-g05c-view.geojson
  python3 scripts/build/batch_g05c_plans.py --layer all \
      --comm /tmp/hf-g05c-comm.geojson --gen /tmp/hf-g05c-gen.geojson \
      --view /tmp/hf-g05c-view.geojson \
      --outdir ~/hf-data/2026-09-12/osm --write-points --probe
Outputs: commbleed/windsolar-walk-raster.json (Dijkstra quiet
masters) + viewshed-walk-raster.json (count-kernel area master,
WalkRasterDoc shape so cleanRaster accepts it) + derived-<layer>.json
(fallback points for the Euclidean route + overlay). Restart the web
server afterwards — the server caches masters per process.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# ---------------------------------------------------------------------------
# Constants (mirrors walk_raster / batch_g07b_envhealth scales).
# ---------------------------------------------------------------------------

COUNTY_BBOX = [23.3, 58.4, 25.5, 59.65]
LON_KM = 57.29
LAT_KM = 110.57
STEP_M = 75.0
DENSIFY_M = 40.0  # line vertex spacing for source rasterisation
DEDUPE_M = 20.0  # node+area twin guard (mirrors scorer _count_cells_within_m)
OVERLAY_CAP = 1500  # thinned overlay sample (raster holds the field)

# Calibration locked 2026-09-12 (see module docstring).
# NOTE: apps/web/lib/layers_group05c.ts G05C_CAL mirrors these numbers
# exactly — test_batch_g05c.py parses that file and fails on drift.
G05C_CAL = {
    "commbleed": {"half_m": 300.0, "sigma": 0.3},
    "windsolar": {"half_m": 800.0, "sigma": 0.3},
    "viewshed": {"half": 1.0, "sigma": 0.3},
}

LAYER_IDS = ("commbleed", "windsolar", "viewshed")

#: landuse values that are bleed-pressure zones (plain shops stay grocery's).
KEEP_LANDUSE = ("commercial", "retail")

#: Solar locations that count as farm scale (rooftop + unknown OUT).
KEEP_SOLAR_LOC = ("ground", "surface", "overground")

PROBE_POINTS = {  # lon, lat — calibration witnesses, also --probe output
    "Balti": (24.7369, 59.4405), "Viru": (24.7611, 59.4278),
    "Kadriorg": (24.7912, 59.4386), "Oismae": (24.655, 59.412),
    "Lasnamae": (24.82, 59.44), "Viimsi": (24.83, 59.51),
    "Nomme": (24.66, 59.36), "Paljassaare": (24.698, 59.466),
    "Pirita": (24.821, 59.468), "rural": (24.5, 59.2),
    "Ulemiste": (24.7956, 59.4229), "Kohtuotsa": (24.7399, 59.4357),
}


def hav_km(lon1, lat1, lon2, lat2):
    """Equirectangular km (same 57.29/110.57 constants as walk_graph)."""
    return math.hypot((lon2 - lon1) * LON_KM, (lat2 - lat1) * LAT_KM)


def quiet_from_half(d_m, half_m):
    """Distance (m) -> calmness 0..100: 0 on the source, 50 at half_m."""
    return 100.0 * d_m / (d_m + half_m) if d_m < float("inf") else 100.0


def kernel(d_km, sigma):
    """Gaussian kernel weight (moorage precedent: exp(-d^2/2σ^2))."""
    return math.exp(-(d_km * d_km) / (2.0 * sigma * sigma))


def area_score(s, half):
    """Saturating count score 100*S/(S+half) (mirrors walk_raster.saturate)."""
    return 100.0 * s / (s + half)


# ---------------------------------------------------------------------------
# Grid (local copy for self-containment, mirrors batch_g07b_envhealth).
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
# Source predicates + readers (offline geojson extracts only).
# ---------------------------------------------------------------------------

def _first(value):
    try:
        return str(value).split(";")[0].strip()
    except (TypeError, AttributeError):
        return ""


def keep_comm(props):
    """True when a commercial-extract feature is a bleed-pressure zone.

    landuse commercial/retail or shop=mall. Plain supermarkets are OUT
    by design (grocery's own, #98): malls/retail parks are bleed
    pressure, not errands. Untagged relation members drop out here.
    """
    props = props or {}
    if _first(props.get("landuse")) in KEEP_LANDUSE:
        return True
    return _first(props.get("shop")) == "mall"


def keep_farm(props):
    """True when a generator-extract feature is farm scale.

    Wind turbines always count (any location); solar ONLY on
    ground/surface/overground. Rooftop + unknown-location panels are
    OUT by design (a panel is not a farm); diesel/gas/biofuel/hydro
    are OUT (not wind/solar).
    """
    props = props or {}
    if _first(props.get("power")) != "generator":
        return False
    src = _first(props.get("generator:source"))
    if src == "wind":
        return True
    if src == "solar" and _first(props.get("location")) in KEEP_SOLAR_LOC:
        return True
    return False


def keep_view(props):
    """True when a viewpoint-extract feature is a scenic viewpoint."""
    return _first((props or {}).get("tourism")) == "viewpoint"


def _densify_line(coords, step_km=DENSIFY_M / 1000.0):
    pts = []
    for i, (lon, lat) in enumerate(coords):
        pts.append((lon, lat))
        if i == 0:
            continue
        plon, plat = coords[i - 1]
        d = hav_km(plon, plat, lon, lat)
        if d > step_km:
            n = int(d / step_km)
            for k in range(1, n):
                t = k / n
                pts.append((plon + (lon - plon) * t, plat + (lat - plat) * t))
    return pts


def _stride_ring(ring, per=25):
    pts = [(c[0], c[1]) for c in ring]
    return pts[:: max(1, len(pts) // per)]


def _point_in_ring(lon, lat, ring):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        # NOTE: parenthesised on purpose — Python would CHAIN
        # `yi > lat != yj > lat` into different semantics (and divide
        # by zero on horizontal edges); the JS twin (ringContains in
        # snapshot.ts) groups as (yi > lat) !== (yj > lat).
        if (yi > lat) != (yj > lat) and \
                lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _iter_features(path):
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    feats = doc.get("features", doc) if isinstance(doc, dict) else doc
    return [x for x in feats if isinstance(x, dict)]


def read_comm_points(comm_path):
    """Commercial-zone source cells from a commercial geojson extract.

    Points feed directly; open lines are densified; polygons are
    boundary-sampled AND filled (a parcel inside the zone reads 0:
    inside IS the bleed). Returns ([(lon, lat)], fill_cells_hint,
    stats) — the fill runs on the caller grid via fill_comm_cells.
    """
    pts = []
    polys = []  # outer rings for the grid fill
    stats = {"zones": 0, "dropped": 0}
    for feat in _iter_features(comm_path):
        if not keep_comm(feat.get("properties") or {}):
            stats["dropped"] += 1
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            stats["dropped"] += 1
            continue
        gtype = geom.get("type")
        if gtype == "Point":
            pts.append((coords[0], coords[1]))
            stats["zones"] += 1
        elif gtype == "LineString":
            co = [(c[0], c[1]) for c in coords]
            if len(co) > 1 and co[0] == co[-1]:
                pts.extend(_stride_ring(co))
            else:
                pts.extend(_densify_line(co))
            stats["zones"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
                polys.append([(c[0], c[1]) for c in ring])
            stats["zones"] += 1
        else:
            stats["dropped"] += 1
    return pts, polys, stats


def fill_comm_cells(grid, polys):
    """Grid cells whose centre falls inside a commercial polygon."""
    cells = set()
    for ring in polys:
        lons = [c[0] for c in ring]
        lats = [c[1] for c in ring]
        minlon, minlat, _, _ = grid.bbox
        ix_lo = max(0, int((min(lons) - minlon) * LON_KM * 1000 / grid.step))
        ix_hi = min(grid.cols - 1,
                    int((max(lons) - minlon) * LON_KM * 1000 / grid.step))
        iy_lo = max(0, int((min(lats) - minlat) * LAT_KM * 1000 / grid.step))
        iy_hi = min(grid.rows - 1,
                    int((max(lats) - minlat) * LAT_KM * 1000 / grid.step))
        for iy in range(iy_lo, iy_hi + 1):
            for ix in range(ix_lo, ix_hi + 1):
                clon = minlon + (ix + 0.5) * grid.step / 1000 / LON_KM
                clat = minlat + (iy + 0.5) * grid.step / 1000 / LAT_KM
                if _point_in_ring(clon, clat, ring):
                    cells.add(iy * grid.cols + ix)
    return cells


def read_farm_points(gen_path):
    """Farm source points from a generator geojson extract.

    Turbines (points) feed directly; solar-farm polygons feed
    stride-sampled outer rings (a distance field only needs the
    boundary — interiors read near-zero through the ring Dijkstra at
    75 m cells). Returns ([(lon, lat)], stats).
    """
    pts = []
    stats = {"farms": 0, "dropped": 0}
    for feat in _iter_features(gen_path):
        if not keep_farm(feat.get("properties") or {}):
            stats["dropped"] += 1
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            stats["dropped"] += 1
            continue
        gtype = geom.get("type")
        if gtype == "Point":
            pts.append((coords[0], coords[1]))
            stats["farms"] += 1
        elif gtype == "LineString":
            pts.extend(_densify_line([(c[0], c[1]) for c in coords]))
            stats["farms"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
            stats["farms"] += 1
        else:
            stats["dropped"] += 1
    return pts, stats


def read_view_points(view_path):
    """Viewpoint dots from a tourism=viewpoint geojson extract."""
    pts = []
    stats = {"views": 0, "dropped": 0}
    for feat in _iter_features(view_path):
        if not keep_view(feat.get("properties") or {}):
            stats["dropped"] += 1
            continue
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            stats["dropped"] += 1
            continue
        gtype = geom.get("type")
        if gtype == "Point":
            pts.append((coords[0], coords[1]))
            stats["views"] += 1
        elif gtype in ("Polygon", "MultiPolygon"):
            rings = [coords[0]] if gtype == "Polygon" \
                else [p[0] for p in coords if p]
            for ring in rings:
                pts.extend(_stride_ring(ring))
            stats["views"] += 1
        else:
            stats["dropped"] += 1
    return pts, stats


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
# Fields: exact grid Dijkstra (quiet) + Gaussian count kernel (area).
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


def count_kernel_field(grid, points, sigma):
    """Gaussian count accumulation: cell -> S (moorage precedent).

    Bounded O(points * range^2) sweep: each viewpoint stamps
    kernel(d, sigma) into cells within 4 sigma. Unstamped cells stay
    absent (the scorer renders them 255 unknown, never a faked
    zero).
    """
    cutoff_km = 4.0 * sigma
    acc = {}
    minlon, minlat, _, _ = grid.bbox
    for lon, lat in points:
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
                acc[k] = acc.get(k, 0.0) + kernel(d, sigma)
    return acc


# ---------------------------------------------------------------------------
# Layer scores (high = calm; 0 = known-exposed, never 255 — except the
# unstamped viewshed desert, which stays honestly unknown).
# ---------------------------------------------------------------------------

def score_distance(d_km, half_m):
    """Nearest-source calmness 100*d/(d+half) for one distance field."""
    out = bytearray(len(d_km))
    for k in range(len(d_km)):
        d_m = d_km[k] * 1000.0
        out[k] = max(0, min(100, int(round(quiet_from_half(d_m, half_m)))))
    return out


def score_area_cells(grid, acc, half):
    """Saturating viewpoint score 100*S/(S+half); desert stays 255."""
    out = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k, s in acc.items():
        out[k] = max(0, min(100, int(round(area_score(s, half)))))
    return out


# ---------------------------------------------------------------------------
# Wire output (WalkRasterDoc shape: cleanRaster-compatible) + orchestration.
# ---------------------------------------------------------------------------

def contract_of(layer):
    """(half, sigma) carried on the wire for the matchesContract hook."""
    cal = G05C_CAL[layer]
    return cal.get("half_m", cal.get("half")), cal["sigma"]


def encode_wire(grid, values, layer="commbleed"):
    half, sigma = contract_of(layer)
    return {
        "cols": grid.cols, "rows": grid.rows,
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step, "half": half, "sigma": sigma,
        "per": 0, "cap": 0, "unknown": 255, "dtype": "uint8",
        "data": base64.b64encode(bytes(values)).decode("ascii"),
    }


def write_outputs(outdir, layer, grid, values, fmt):
    name = "%s-walk-raster" % layer
    if fmt == "split":
        with open(os.path.join(outdir, name + ".json"), "w",
                  encoding="utf-8") as f:
            doc = encode_wire(grid, values, layer)
            doc["data"] = "AA=="  # meta only; bytes live in the .u8 master
            json.dump(doc, f)
        with open(os.path.join(outdir, name + ".u8"), "wb") as f:
            f.write(bytes(values))
        print("wrote %s.json + .u8" % name, flush=True)
    else:
        with open(os.path.join(outdir, name + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(encode_wire(grid, values, layer), f)
        print("wrote %s.json" % name, flush=True)


def write_points(outdir, layer, points):
    """Thinned overlay/fallback points (loadSnapshotPoints reads these)."""
    pts = dedupe_cells(points)
    if len(pts) > OVERLAY_CAP:  # stride-thin huge ring samples, keep spread
        stride = len(pts) / OVERLAY_CAP
        pts = [pts[int(i * stride)] for i in range(OVERLAY_CAP)]
    doc = [{"lon": round(lon, 6), "lat": round(lat, 6)}
           for lon, lat in pts]
    with open(os.path.join(outdir, "derived-%s.json" % layer), "w",
              encoding="utf-8") as f:
        json.dump(doc, f)
    print("wrote derived-%s.json (%d pts)" % (layer, len(doc)), flush=True)
    return doc


def build_layer(grid, layer, comm_path=None, gen_path=None, view_path=None):
    """Source points -> master bytes for one layer. Returns (bytes, pts)."""
    t0 = time.time()
    if layer == "commbleed":
        if not comm_path:
            raise SystemExit("commbleed needs --comm commercial extract")
        raw, polys, stats = read_comm_points(comm_path)
        print("commbleed=%s raw_pts=%d polys=%d" % (stats, len(raw), len(polys)),
              flush=True)
        pts = dedupe_cells(raw)
        print("commbleed: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        cells = cells_of_points(grid, pts) | fill_comm_cells(grid, polys)
        dist = dijkstra_km(grid, cells)
        vals = score_distance(dist, G05C_CAL[layer]["half_m"])
    elif layer == "windsolar":
        if not gen_path:
            raise SystemExit("windsolar needs --gen generator extract")
        raw, stats = read_farm_points(gen_path)
        print("windsolar=%s raw_pts=%d" % (stats, len(raw)), flush=True)
        pts = dedupe_cells(raw)
        print("windsolar: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        dist = dijkstra_km(grid, cells_of_points(grid, pts))
        vals = score_distance(dist, G05C_CAL[layer]["half_m"])
    else:
        if not view_path:
            raise SystemExit("viewshed needs --view viewpoint extract")
        raw, stats = read_view_points(view_path)
        print("viewshed=%s raw_pts=%d" % (stats, len(raw)), flush=True)
        pts = dedupe_cells(raw)
        print("viewshed: deduped %d -> %d" % (len(raw), len(pts)), flush=True)
        acc = count_kernel_field(grid, pts, G05C_CAL[layer]["sigma"])
        vals = score_area_cells(grid, acc, G05C_CAL[layer]["half"])
    print("%s field ready (%.1fs)" % (layer, time.time() - t0), flush=True)
    return vals, pts


def probe_scores(masters, grid):
    print("probe (high = calm):", flush=True)
    for name, (lon, lat) in PROBE_POINTS.items():
        k = grid.cell_of(lon, lat)
        if k is None:
            print("  %-11s outside grid" % name, flush=True)
            continue
        print("  %-11s %s" % (name, {l: masters[l][k] for l in masters}),
              flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--layer", required=True,
                    choices=list(LAYER_IDS) + ["all"])
    ap.add_argument("--comm", default=None,
                    help="commercial geojson extract (commbleed)")
    ap.add_argument("--gen", default=None,
                    help="generator geojson extract (windsolar)")
    ap.add_argument("--view", default=None,
                    help="viewpoint geojson extract (viewshed)")
    ap.add_argument("--out", default=None,
                    help="single-layer master path (implies --outdir)")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--format", choices=["combined", "split"],
                    default="combined")
    ap.add_argument("--step-m", type=float, default=STEP_M)
    ap.add_argument("--bbox", nargs=4, type=float, default=COUNTY_BBOX)
    ap.add_argument("--write-points", action="store_true",
                    help="also write derived-<layer>.json overlay points")
    ap.add_argument("--probe", action="store_true",
                    help="print sample-point scores after building")
    args = ap.parse_args(argv)
    outdir = args.outdir or (os.path.dirname(args.out) if args.out else None)
    if not outdir:
        raise SystemExit("need --outdir (or --out)")
    os.makedirs(outdir, exist_ok=True)
    grid = Grid(args.bbox, args.step_m)
    print("grid: %d x %d @ %.2f m" % (grid.cols, grid.rows, grid.step),
          flush=True)
    layers = list(LAYER_IDS) if args.layer == "all" else [args.layer]
    masters = {}
    for layer in layers:
        vals, pts = build_layer(grid, layer, args.comm, args.gen, args.view)
        masters[layer] = vals
        if args.out and len(layers) == 1:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(encode_wire(grid, vals, layer), f)
            print("wrote %s" % args.out, flush=True)
        else:
            write_outputs(outdir, layer, grid, vals, args.format)
        if args.write_points:
            write_points(outdir, layer, pts)
        print("%s: cells=%d zeros(known-exposed)=%d" %
              (layer, len(vals), sum(1 for v in vals if v == 0)), flush=True)
    if args.probe:
        probe_scores(masters, grid)


if __name__ == "__main__":
    main()
