"""Network walk-access rasters for place layers (stdlib only).

Offline snapshot build shared by transit / parks / schools: resolve
weighted features from snapshot files, stamp network walksheds from the
foot graph (see walk_graph.py), bake FINAL 0..100 scores into a uint8
county raster the client renders and samples but never recomputes.

Scoring mirrors apps/web/lib/{layers,distanceField}.ts and
lib/server/snapshot.ts exactly (same constants, same formulas):
  transit  S = sum trips*K(d_walk); score = 100*S/(S+half) + 10 if >=2
           modes within 0.45 km network. Null below 3 (unknown).
  parks    S = sum hectares*K(d_walk); score = 100*S/(S+half).
           Null below 3 (unknown).
  schools  base = 100*e^(-dmin/0.8) over NETWORK nearest distance;
           bonus = 12*min(3, distinct-1) where a class counts when some
           stop of that class is within 0.9 km network (mirror of the
           PRESENT>0.5 kernel rule). Far field: Euclidean nearest takes
           over past the network cutoff (error only where scores are
           already deep red; documented), and past 3.2 km stores 0 --
           mirroring the TS spec, whose base+bonus path never reads
           null in-bbox (far = bad, not unknown).

Deliberate divergences from the TS Euclidean path (all sub-75 m):
  * No 22 m dedupeSum: addition commutes, so per-cell sums are
    identical; only feature-list shape differs (unused by the raster).
  * No round3 on coordinates: sub-cell rounding cannot move a stamp.
"""

import base64
import heapq
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from walk_graph import SnapIndex, dijkstra, hav_km, key_of, lonlat_of  # noqa: E402

MIDLAT = 59.0
KX = 111.32 * math.cos(math.radians(MIDLAT))
KY = 110.57
STEP_M_DEFAULT = 75.0
JOIN_KM = 0.1
SNAP_KM = 0.3
KICKER_KM = 0.45
DEFAULT_TRIPS = 100
POLY_CUTOFF_HA = 0.5

NOMINAL_AREA = {"playground": 0.1, "garden": 0.15, "park": 2.0}
NOMINAL_DEFAULT = 0.3

SCHOOL_VALUES = ["school", "kindergarten", "university", "college"]
SCHOOL_PER = 12
SCHOOL_CAP = 36
SCHOOL_PRESENT_KM = 0.9
SCHOOL_FAR_KM = 3.2

MODE_BIT = {"bus": 1, "tram": 2, "train": 4}


def nominal_area(tags):
    """Mirror of nominalArea() in snapshot.ts."""
    v = (tags or {}).get("leisure") if isinstance(tags, dict) else None
    return NOMINAL_AREA.get(v, NOMINAL_DEFAULT)


def stop_mode(tags):
    """Mirror of stopMode() in layers.ts."""
    if not isinstance(tags, dict):
        return None
    if tags.get("railway") == "tram_stop":
        return "tram"
    if tags.get("railway") in ("station", "stop"):
        return "train"
    if tags.get("public_transport") == "station":
        return "train"
    if tags.get("highway") == "bus_stop" or tags.get("public_transport") in (
        "platform", "stop_position",
    ):
        return "bus"
    return None


def saturate(s, half):
    return (100.0 * s / (s + half)) if s > 0 else 0.0


def school_bonus(distinct):
    """Mirror of the variety branch: per=12, cap=36."""
    return SCHOOL_PER * min(SCHOOL_CAP // SCHOOL_PER, max(0, distinct - 1))


def ring_contains(ring, lon, lat):
    """Mirror of ringContains() in snapshot.ts (ray cast, same tests)."""
    inside = False
    n = len(ring)
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[n - 1] if i == 0 else ring[i - 1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
    return inside


def _inside_big_poly(lon, lat, areas):
    for pa in areas:
        if pa["a"] < POLY_CUTOFF_HA:
            continue
        b = pa["b"]
        if lon < b[0] or lon > b[2] or lat < b[1] or lat > b[3]:
            continue
        if any(ring_contains(ring, lon, lat) for ring in pa["r"]):
            return True
    return False


def resolve_parks(points, areas, sigma):
    """Mirror of parksAreas(): subdivided polygons + nominal points.

    Returns [(lon, lat, hectares)]. Dedupe/round3 skipped (sub-75 m,
    sums commute; see module docstring). Two divergences, both
    documented: (1) weight splits over PLACED centers (conservation --
    the TS path does the same since the Pirita fix); (2) subdivision is
    kernel-resolution-adequate (subcell ~sigma/2, cap 2000) instead of
    the TS 25-cap client perf hack -- coarse subcells leave interior
    holes under narrow kernels. Same total hectares either way.
    """
    target_ha = 25 * sigma * sigma
    feats = []
    for pa in areas:
        n = max(1, min(2000, math.ceil(pa["a"] / target_ha)))
        w = pa["b"][2] - pa["b"][0]
        h = pa["b"][3] - pa["b"][1]
        nx = max(1, math.ceil(math.sqrt(n * w / (h + 1e-9))))
        ny = max(1, math.ceil(n / nx))
        centers = []
        for ix in range(nx):
            for iy in range(ny):
                lon = pa["b"][0] + w * (ix + 0.5) / nx
                lat = pa["b"][1] + h * (iy + 0.5) / ny
                if any(ring_contains(ring, lon, lat) for ring in pa["r"]):
                    centers.append((lon, lat))
        if not centers:
            feats.append(((pa["b"][0] + pa["b"][2]) / 2, (pa["b"][1] + pa["b"][3]) / 2, pa["a"]))
        else:
            wgt = pa["a"] / len(centers)
            feats.extend((lon, lat, wgt) for lon, lat in centers)
    for p in points:
        if _inside_big_poly(p["lon"], p["lat"], areas):
            continue
        tags = p.get("tags") if isinstance(p.get("tags"), dict) else None
        feats.append((p["lon"], p["lat"], nominal_area(tags)))
    return feats


def resolve_schools(points):
    """Schools pass through with their amenity tag (or None)."""
    out = []
    for p in points:
        tags = p.get("tags") if isinstance(p.get("tags"), dict) else None
        amenity = tags.get("amenity") if tags else None
        out.append((p["lon"], p["lat"], amenity if amenity in SCHOOL_VALUES else None))
    return out


GROCERY_SHOPS = {"supermarket", "convenience", "greengrocer", "grocery", "marketplace"}
MEDICAL_EVERYDAY = {"pharmacy", "doctors", "dentist"}
# Hospitals/clinics are p124 (specialized medical), not everyday p20.

PED_HIGHWAY = {"footway", "path", "pedestrian", "steps", "crossing", "corridor"}
CYCLE_LANES = {"lane", "track", "opposite_lane", "opposite_track"}


def is_grocery(tags):
    """Everyday food retail. Unweighted counts: OSM has no reliable floor
    area, so hypermarket-vs-kiosk tiering would be fake precision."""
    return isinstance(tags, dict) and tags.get("shop") in GROCERY_SHOPS


def is_medical(tags):
    return isinstance(tags, dict) and tags.get("amenity") in MEDICAL_EVERYDAY


def is_cycleway(tags):
    if not isinstance(tags, dict):
        return False
    if tags.get("highway") == "cycleway":
        return True
    return tags.get("cycleway") in CYCLE_LANES


def _feature_point(geom):
    """Point / line-midpoint / polygon-bbox-center representative."""
    if not isinstance(geom, dict):
        return None
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point" and isinstance(c, list) and len(c) >= 2:
        return (float(c[0]), float(c[1]))
    if t == "LineString" and isinstance(c, list) and c:
        mid = c[len(c) // 2]
        return (float(mid[0]), float(mid[1]))
    if t in ("Polygon", "MultiPolygon") and isinstance(c, list):
        rings = [c[0]] if t == "Polygon" else [p[0] for p in c if p]
        xs = [x for r in rings for x, _ in r]
        ys = [y for r in rings for _, y in r]
        if xs and ys:
            return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    return None


def resolve_pois(geojson_path, pred):
    """Deduped (by OSM id) POI points passing pred(tags). Returns (pts, stats).

    Same place mapped as node + building keeps ONE entry (first seen):
    kernel smoothing absorbs the ~meter offset either way.
    """
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
            pt = _feature_point(feat.get("geometry"))
            if pt is None:
                continue
            kept += 1
            out.append((pt[0], pt[1], 1.0))
    return out, {"features": feats, "kept": kept}


def resolve_walkability(graph):
    """Junction points (distinct neighbors >= 3) for p14.

    Shape points have degree 2 and never count; parallel twin edges share
    one neighbor and count once.
    """
    out = []
    for k, nbs in graph.adj.items():
        if len({b for b, _ in nbs}) >= 3:
            lon, lat = lonlat_of(k)
            out.append((lon, lat, 1.0))
    return out


def resolve_length_km(geojson_path, highway_set):
    """Per-vertex incident km for dedicated-infra density (p84/p102).

    Each edge's length splits half/half over its endpoints, so the vertex
    weights sum to the network's total km (conserved, tested).
    """
    import json as _json
    weights = {}
    kept = feats = 0
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
            props = feat.get("properties", {})
            if props.get("highway") not in highway_set and not (
                highway_set is CYCLE_SET and is_cycleway(props)
            ):
                continue
            kept += 1
            for ring in _rings_of(feat.get("geometry")):
                pts = [(float(x), float(y)) for x, y in ring if isinstance(x, (int, float))]
                for i in range(len(pts) - 1):
                    (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                    half = hav_km(x1, y1, x2, y2) / 2
                    if half <= 0:
                        continue
                    a, b = key_of(x1, y1), key_of(x2, y2)
                    weights[a] = weights.get(a, 0.0) + half
                    weights[b] = weights.get(b, 0.0) + half
    out = [(lonlat_of(k)[0], lonlat_of(k)[1], w) for k, w in weights.items()]
    return out, {"features": feats, "kept": kept}


def _rings_of(geom):
    if not isinstance(geom, dict):
        return
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "LineString" and isinstance(c, list):
        yield c
    elif t == "MultiLineString" and isinstance(c, list):
        for line in c:
            yield line


#: Sentinel so resolve_length_km can tell the cycle profile apart.
CYCLE_SET = frozenset({"__cycle__"})


def join_trips(stops, freq):
    """Winner-takes-all GTFS join (mirrors snapshot.ts)."""
    claim = [-1] * len(stops)
    dist = [float("inf")] * len(stops)
    for i, p in enumerate(stops):
        for j, f in enumerate(freq):
            if abs(f["lon"] - p["lon"]) > 0.002 or abs(f["lat"] - p["lat"]) > 0.001:
                continue
            d = hav_km(p["lon"], p["lat"], f["lon"], f["lat"])
            if d < dist[i]:
                dist[i] = d
                claim[i] = j
    won = {}
    for i in range(len(stops)):
        if claim[i] < 0 or dist[i] > JOIN_KM:
            continue
        if claim[i] not in won or dist[i] < dist[won[claim[i]]]:
            won[claim[i]] = i
    out = []
    for i in range(len(stops)):
        if claim[i] < 0 or dist[i] > JOIN_KM:
            out.append(DEFAULT_TRIPS)
        elif won[claim[i]] == i:
            out.append(freq[claim[i]]["trips"])
        else:
            out.append(0)
    return out


def multi_source_dist(graph, sources, cutoff_km):
    """One Dijkstra from many sources: vertex -> km to the NEAREST source.

    sources: [(vertex_key, start_gap_km)] -- the gap (snap distance) seeds
    the label so labels read as walk-from-feature, not walk-from-vertex.
    Bare keys are accepted with gap 0.
    """
    dist = {}
    pq = []
    for src in sources:
        v, gap = src if isinstance(src, tuple) else (src, 0.0)
        if gap < dist.get(v, float("inf")):
            dist[v] = gap
            heapq.heappush(pq, (gap, v))
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):
            continue
        if d > cutoff_km:
            continue
        for v, w in graph.adj.get(u, ()):
            nd = d + w
            if nd < dist.get(v, float("inf")) and nd <= cutoff_km:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


def kernel(d, sigma):
    return math.exp(-d * d / (2 * sigma * sigma))


class Grid:
    """75 m county accumulator: sparse S sums + bit masks + min distances."""

    def __init__(self, bbox, step_m=STEP_M_DEFAULT):
        self.bbox = bbox
        self.step = step_m
        minlon, minlat, maxlon, maxlat = bbox
        self.cols = int(round((maxlon - minlon) * KX * 1000 / self.step))
        self.rows = int(round((maxlat - minlat) * KY * 1000 / self.step))
        self.acc = {}
        self.bits = {}
        self.mind = {}

    def cell_of(self, lon, lat):
        minlon, minlat, _, _ = self.bbox
        ix = int((lon - minlon) * KX * 1000 / self.step)
        iy = int((lat - minlat) * KY * 1000 / self.step)
        if 0 <= ix < self.cols and 0 <= iy < self.rows:
            return iy * self.cols + ix
        return None

    def add(self, lon, lat, s=0.0, bit=0, dmin=None):
        k = self.cell_of(lon, lat)
        if k is None:
            return
        if s:
            self.acc[k] = self.acc.get(k, 0.0) + s
        if bit:
            self.bits[k] = self.bits.get(k, 0) | bit
        if dmin is not None and dmin < self.mind.get(k, float("inf")):
            self.mind[k] = dmin

    def center_of(self, k):
        minlon, minlat, _, _ = self.bbox
        ix, iy = k % self.cols, k // self.cols
        return (minlon + (ix + 0.5) * self.step / 1000 / KX,
                minlat + (iy + 0.5) * self.step / 1000 / KY)


def stamp_sum(grid, graph, feats, sigma, cutoff_km, bit_of=None, present_km=0.0):
    """Per-feature local Dijkstra; stamps weight*K(d_walk) + presence bits.

    feats: [(lon, lat, weight, aux)] where aux feeds bit_of(aux) -> bit.
    Returns (snapped, euclid_fallback) counts; fallback stamps Euclidean.
    """
    idx = SnapIndex(graph)
    snapped = euclid = 0
    for lon, lat, w, aux in feats:
        if w <= 0:
            continue
        bit = bit_of(aux) if bit_of else 0
        v, gap = idx.nearest(lon, lat, SNAP_KM)
        if v is None:
            euclid += 1
            r = cutoff_km
            x0, y0 = (lon - grid.bbox[0]) * KX, (lat - grid.bbox[1]) * KY
            for iy in range(max(0, int((y0 - r) * 1000 / grid.step)),
                             min(grid.rows, int((y0 + r) * 1000 / grid.step) + 1)):
                for ix in range(max(0, int((x0 - r) * 1000 / grid.step)),
                                 min(grid.cols, int((x0 + r) * 1000 / grid.step) + 1)):
                    clon = grid.bbox[0] + (ix + 0.5) * grid.step / 1000 / KX
                    clat = grid.bbox[1] + (iy + 0.5) * grid.step / 1000 / KY
                    d = hav_km(lon, lat, clon, clat)
                    if d > cutoff_km:
                        continue
                    grid.add(clon, clat, w * kernel(d, sigma),
                             bit if bit and d <= present_km else 0)
            continue
        snapped += 1
        # One field sample per cell: reduce the tree to min distance per
        # cell first. Accumulating per node would multiply the field by
        # the local graph density (dense paths score higher for the same
        # green/service). Presence keeps OR-semantics over the cell.
        best: dict = {}
        for vk, dn in dijkstra(graph, v, cutoff_km).items():
            d = dn + gap
            if d > cutoff_km:
                continue
            k = grid.cell_of(*lonlat_of(vk))
            if k is None:
                continue
            prev = best.get(k)
            if prev is None:
                best[k] = [d, bool(bit and d <= present_km), vk]
            else:
                if d < prev[0]:
                    prev[0] = d
                if bit and d <= present_km:
                    prev[1] = True
        for k, (d, present, vk) in best.items():
            x, y = lonlat_of(vk)
            grid.add(x, y, w * kernel(d, sigma), bit if present else 0)
    return snapped, euclid


def euclid_nearest_fill(grid, stops, max_km):
    """For cells lacking a network label: min Euclidean stop distance.

    Bounded O(stops * range^2) sweep; cells past max_km keep +inf.
    """
    cell_km = grid.step / 1000
    out = {}
    for lon, lat in stops:
        x0, y0 = (lon - grid.bbox[0]) * KX, (lat - grid.bbox[1]) * KY
        span = int(max_km / cell_km) + 1
        cx, cy = int(x0 * 1000 / grid.step), int(y0 * 1000 / grid.step)
        for iy in range(max(0, cy - span), min(grid.rows, cy + span + 1)):
            for ix in range(max(0, cx - span), min(grid.cols, cx + span + 1)):
                clon, clat = grid.center_of(iy * grid.cols + ix)
                d = hav_km(lon, lat, clon, clat)
                if d > max_km:
                    continue
                k = iy * grid.cols + ix
                if d < out.get(k, float("inf")):
                    out[k] = d
    return out


def save_stamp(path, acc, bits):
    """Cache a stamp (S sums + bits) so H-calibration loops skip Dijkstra."""
    import pickle as _pk
    with open(path, "wb") as f:
        _pk.dump({"acc": acc, "bits": bits}, f, protocol=4)


def load_stamp(path):
    import pickle as _pk
    with open(path, "rb") as f:
        d = _pk.load(f)
    return d["acc"], d["bits"]


def score_bytes(grid, score_of):
    """Per-cell FINAL uint8 scores (255 = unknown), as raw bytes."""
    vals = bytearray(255 for _ in range(grid.cols * grid.rows))
    for k in range(grid.cols * grid.rows):
        s = score_of(k)
        if s is not None:
            vals[k] = int(round(min(100.0, s)))
    return bytes(vals)


def doc_meta(grid, half=None, sigma=None, per=0, cap=0):
    return {
        "bbox": {"minlon": grid.bbox[0], "minlat": grid.bbox[1],
                 "maxlon": grid.bbox[2], "maxlat": grid.bbox[3]},
        "step_m": grid.step,
        "cols": grid.cols,
        "rows": grid.rows,
        "half": half,
        "sigma": sigma,
        "per": per,
        "cap": cap,
        "unknown": 255,
        "dtype": "uint8",
    }


def encode_raster(grid, score_of, half=None, sigma=None, per=0, cap=0):
    """Bake per-cell FINAL scores to the uint8 wire doc (255 = unknown)."""
    doc = doc_meta(grid, half, sigma, per, cap)
    doc["data"] = base64.b64encode(score_bytes(grid, score_of)).decode("ascii")
    return doc


def save_master(prefix, grid, score_of, half=None, sigma=None, per=0, cap=0):
    """Split master for tiled serving: tiny meta JSON + raw uint8 bytes."""
    import json as _json
    with open(prefix + ".json", "w", encoding="utf-8") as f:
        _json.dump(doc_meta(grid, half, sigma, per, cap), f)
    with open(prefix + ".u8", "wb") as f:
        f.write(score_bytes(grid, score_of))
