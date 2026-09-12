"""Routable street graphs for Harjumaa from OSM data (stdlib only).

Builds walking ("foot") and driving ("car") webs from `osmium export`
GeoJSON: ways become edges between consecutive vertices, so railways,
water and motorways sever the graph exactly where no walkable/drivable
way crosses them -- only real bridges, tunnels and level crossings
connect across. No hand-drawn barriers, no invented crossings.

Profiles
--------
FOOT (undirected; one-ways do not apply to pedestrians):
  highway in {footway, path, pedestrian, steps, cycleway, living_street,
  residential, service, unclassified, tertiary, secondary, primary,
  trunk, track, corridor, crossing} plus station platforms
  (railway=platform / public_transport=platform ways and polygons).
  Excluded: anything with access=no or foot=no, and motorway/*_link,
  proposed, construction, raceway, bus_guideway. Pedestrian plazas
  mapped as (multi)polygons contribute their outer rings (a small
  overestimate of the true shortcut, documented, never an undercut).
  Trunk/primary streets are assumed walkable (sidewalks): erring toward
  Euclidean where mapping is thin is honest; inventing severance is not.

CAR (directed; oneways and roundabouts respected):
  highway in {motorway, trunk, primary, secondary, tertiary,
  unclassified, residential, living_street, service, track} plus *_link.
  Excluded: foot-only ways, access=no, construction/proposed/raceway.
  access=private is IGNORED for both profiles (tagging is too spotty to
  sever on; documented).

Public-transit-as-a-network (travel times from timetables, RAPTOR and
friends) is deliberately NOT built here: tracks alone do not give travel
times. The transit layer consumes GTFS weekday departures as weights on
the foot graph instead (see build-walk-raster.py).

Node identity: integer micro-degree keys (lossless for OSM 7-decimal
coordinates); shared OSM nodes yield identical floats from one export,
so topology joins exactly.
"""

import heapq
import json
import math

PREC = 10_000_000


def key_of(lon, lat):
    return (int(round(lon * PREC)) << 32) | (int(round(lat * PREC)) & 0xFFFFFFFF)


def lonlat_of(key):
    lon = key >> 32
    lat = key & 0xFFFFFFFF
    if lon >= 2**31:
        lon -= 2**32
    if lat >= 2**31:
        lat -= 2**32
    return lon / PREC, lat / PREC


def hav_km(lon1, lat1, lon2, lat2):
    # Equirectangular degrees-to-km at Harjumaa latitude. Callers must
    # pass (lon, lat) order — swapped args stretch N-S by ~2x (rural
    # school capsules); see test_hav_km_scales_degrees_to_km.
    return math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57)


FOOT_HIGHWAY = {
    "footway", "path", "pedestrian", "steps", "cycleway", "living_street",
    "residential", "service", "unclassified", "tertiary", "secondary",
    "primary", "trunk", "track", "corridor", "crossing",
}

FOOT_EXCLUDE_HIGHWAY = {
    "motorway", "motorway_link", "trunk_link", "primary_link",
    "secondary_link", "tertiary_link", "proposed", "construction",
    "raceway", "bus_guideway", "busway",
}

CAR_HIGHWAY = {
    "motorway", "motorway_link", "trunk", "trunk_link", "primary",
    "primary_link", "secondary", "secondary_link", "tertiary",
    "tertiary_link", "unclassified", "residential", "living_street",
    "service", "track",
}


def _tags(props):
    return props if isinstance(props, dict) else {}


def foot_ok(props):
    """True when a way/polygon is walkable under the FOOT profile."""
    p = _tags(props)
    if p.get("access") == "no" or p.get("foot") == "no":
        return False
    hw = p.get("highway")
    if hw in FOOT_EXCLUDE_HIGHWAY:
        return False
    if hw in FOOT_HIGHWAY:
        return True
    # Station platforms are walkable even without a highway tag.
    if p.get("railway") == "platform" or p.get("public_transport") == "platform":
        return True
    return False


def car_ok(props):
    """True when a way is drivable under the CAR profile."""
    p = _tags(props)
    if p.get("access") == "no":
        return False
    hw = p.get("highway")
    if not isinstance(hw, str):
        return False
    if hw in ("proposed", "construction", "raceway"):
        return False
    return hw in CAR_HIGHWAY


def _rings_of(geom):
    """Walkable rings from a GeoJSON geometry (lines as-is, polygon outers)."""
    if not isinstance(geom, dict):
        return
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "LineString" and isinstance(c, list):
        yield c
    elif t == "MultiLineString" and isinstance(c, list):
        for line in c:
            yield line
    elif t == "Polygon" and isinstance(c, list) and c:
        yield c[0]
    elif t == "MultiPolygon" and isinstance(c, list):
        for poly in c:
            if poly:
                yield poly[0]


def _oneway(props):
    p = _tags(props)
    if p.get("junction") == "roundabout":
        return 1
    ow = p.get("oneway")
    if ow in ("yes", "true", "1"):
        return 1
    if ow == "-1":
        return -1
    return 0


class Graph:
    """Adjacency over integer micro-degree keys. Foot: undirected."""

    def __init__(self, directed=False):
        self.adj = {}
        self.directed = directed
        self.edge_count = 0

    def add_edge(self, a, b, w):
        if a == b or not (w > 0):
            return
        self.adj.setdefault(a, []).append((b, w))
        if not self.directed:
            self.adj.setdefault(b, []).append((a, w))
        else:
            self.adj.setdefault(b, self.adj.get(b, []))
        self.edge_count += 1

    def add_ring(self, ring, directed_ok):
        pts = [(float(x), float(y)) for x, y in ring if isinstance(x, (int, float))]
        if len(pts) < 2:
            return
        keys = [key_of(x, y) for x, y in pts]
        for i in range(len(keys) - 1):
            a, b = keys[i], keys[i + 1]
            (x1, y1), (x2, y2) = pts[i], pts[i + 1]
            w = hav_km(x1, y1, x2, y2)
            if not self.directed:
                self.add_edge(a, b, w)
            elif directed_ok == 0:
                self.add_edge(a, b, w)
                self.add_edge(b, a, w)
            elif directed_ok == 1:
                self.add_edge(a, b, w)
            else:
                self.add_edge(b, a, w)

    def __len__(self):
        return len(self.adj)


def build_graph(geojson_path, profile):
    """Stream an osmium-export FeatureCollection into a Graph + stats."""
    ok = foot_ok if profile == "foot" else car_ok
    directed = profile == "car"
    g = Graph(directed=directed)
    feats = kept = 0
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
            feats += 1
            props = feat.get("properties", {})
            if not ok(props):
                continue
            kept += 1
            ow = _oneway(props) if directed else 0
            for ring in _rings_of(feat.get("geometry")):
                g.add_ring(ring, ow)
    return g, {"features": feats, "kept": kept}


def dijkstra(g, source, cutoff_km):
    """Single-source shortest paths capped at cutoff_km. Returns {key: km}."""
    dist = {source: 0.0}
    pq = [(0.0, source)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):
            continue
        if d > cutoff_km:
            continue
        for v, w in g.adj.get(u, ()):  # type: ignore[union-attr]
            nd = d + w
            if nd < dist.get(v, float("inf")) and nd <= cutoff_km:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist


class SnapIndex:
    """Uniform-grid nearest-vertex lookup for snapping stops to the graph."""

    CELL = 0.005

    def __init__(self, graph):
        self.cells = {}
        for k in graph.adj:
            lon, lat = lonlat_of(k)
            c = (int(math.floor(lon / self.CELL)), int(math.floor(lat / self.CELL)))
            self.cells.setdefault(c, []).append(k)

    def nearest(self, lon, lat, max_km):
        cx = int(math.floor(lon / self.CELL))
        cy = int(math.floor(lat / self.CELL))
        best, bestd = None, max_km
        # 0.005 deg ~ 0.3 km; rings of 1..3 cover max_km <= ~1 km.
        for r in range(4):
            for dx in range(-r, r + 1):
                for dy in (-r, r) if r else (0,):
                    for k in self.cells.get((cx + dx, cy + dy), ()):  # noqa
                        x, y = lonlat_of(k)
                        d = hav_km(lon, lat, x, y)
                        if d < bestd:
                            best, bestd = k, d
            for dy in range(-r + 1, r):
                for dx in (-r, r) if r else ():
                    for k in self.cells.get((cx + dx, cy + dy), ()):  # noqa
                        x, y = lonlat_of(k)
                        d = hav_km(lon, lat, x, y)
                        if d < bestd:
                            best, bestd = k, d
            if best is not None and bestd <= r * 0.3:
                break
        return (best, bestd) if best is not None else (None, None)


def save_graph(graph, path):
    """Compact JSON artifact: indexed nodes + meter-weighted edges."""
    idx = {k: i for i, k in enumerate(graph.adj)}
    nodes = [[round(lon, 7), round(lat, 7)] for lon, lat in (lonlat_of(k) for k in graph.adj)]
    edges = []
    for a, nbs in graph.adj.items():
        i = idx[a]
        for b, w in nbs:
            j = idx.get(b)
            if j is None:
                continue
            if not graph.directed and j < i:
                continue
            edges.append([i, j, round(w * 1000)])
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"directed": graph.directed, "nodes": nodes, "edges": edges}, f)


def load_graph(path):
    """Reload a saved graph (keys rebuilt losslessly from 7-decimal nodes)."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    g = Graph(directed=bool(data.get("directed")))
    keys = [key_of(lon, lat) for lon, lat in data["nodes"]]
    for i, j, m in data["edges"]:
        a, b = keys[i], keys[j]
        g.adj.setdefault(a, []).append((b, m / 1000.0))
        g.edge_count += 1
        if not g.directed:
            g.adj.setdefault(b, []).append((a, m / 1000.0))
        else:
            g.adj.setdefault(b, g.adj.get(b, []))
    return g


def components(graph, limit=0):
    """Union-find connected components; returns sizes desc (truncated)."""
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, nbs in graph.adj.items():
        parent.setdefault(a, a)
        for b, _ in nbs:
            parent.setdefault(b, b)
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb
    sizes = {}
    for a in parent:
        r = find(a)
        sizes[r] = sizes.get(r, 0) + 1
    out = sorted(sizes.values(), reverse=True)
    return out[:limit] if limit else out
