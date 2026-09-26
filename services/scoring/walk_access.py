# 814-HOOK (#814): foot-graph walk distance source for per-listing scorer legs.
"""Walk-graph distance source for pedestrian-access scorer legs (issue #814).

Follow-up to the #808 audit finding: the map measures pedestrian access
on the foot graph (walk-raster masters stamped via scripts/walk_raster.py)
while every per-listing scorer leg measured bird-flight haversine. This
module gives the scorer legs a walk-graph distance without a database.

SOURCE CHOICE (documented per #814 scope.1 — sidecar, not pgRouting):
per-listing walk distance comes from a foot-graph SIDECAR lookup (snap
origin + POI to the nearest graph nodes, Dijkstra shortest path), reusing
the exact sidecar file the map build already ships
(snapshot ``osm/harju-foot-graph.json``: ``{"nodes": [[lon, lat], ...],
"edges": [[i, j, metres], ...]}`` — the scripts/walk_graph.save_graph
shape, also read by apps/web/lib/server/graphSample.ts). pgRouting was
the alternative and is REJECTED here: it needs PostGIS + the pgRouting
extension + a DB-loaded OSM graph, while every scorer in this tree is
pure and offline-tested by contract (network lives only in
livability.fetch_pois; hermetic tests by default per AGENTS.md 7.6).
A DB round-trip per listing per POI would break that contract; a local
snap + Dijkstra over the shipped sidecar keeps it.

The snap + Dijkstra below is the scorer twin of scripts/walk_graph.py
(Graph/dijkstra/SnapIndex — same algorithm, same edge weights in
metres). It is a deliberate local copy, not an import: cross-tree
imports are not the repo precedent (dims_group12.py and dims_p4_peatus.py
both keep local haversine copies to avoid cycles and path surgery).
Parity with the map side holds because both sides route the SAME
sidecar file with the same algorithm — and because the walk BANDS in
each migrated leg are the legacy haversine bands rescaled by
WALK_DETOUR (see below), so a listing scored with the sidecar agrees
with the walk-raster map cell it sits in up to snap granularity.

WALK_DETOUR = 1.3 is the recalibration factor (scope.3): mean
walk/haversine detour for urban pedestrian trips (standard 1.2–1.4
planning range; 1.3 is the documented judgment call, reviewable per
AGENTS.md 7.5). It rescales BAND EDGES ONLY (walk_bands) — it is never
multiplied into a distance and presented as a measurement. A leg with
no graph still scores bird-flight on the legacy bands (bit-identical
reasons); a leg with a graph scores routed metres on the rescaled
bands; a leg with a graph that cannot route (snap miss, disconnected
component, over cutoff) falls back to the legacy measurement —
haversine metres on the LEGACY bands, reason unchanged (bands_for
encodes this rule in one place). Fallback output is therefore
identical to the no-graph output: an explicitly labelled legacy
estimate, never a fake route.

OSMDAILY separation (scope.4): the OSMDAILY walk masters ride their own
documented follow-up in apps/web/lib/layers_osmdaily.ts and are NOT
touched here; this module serves the core + amenity + dbands legs only.

pgRouting seam: there is deliberately no pgRouting code in this tree.
If a future deployment wants DB routing, it should inject a graph-like
object (anything with snap_m/route_m, see FootGraph) — the legs never
touch the sidecar directly, only the injected object. No integration
test is added for that seam: without a live PostGIS there is nothing
honest to assert.
"""

import heapq
import json
import math
from typing import Dict, List, Optional, Tuple

#: Mean walk/haversine detour (recalibration factor for band edges; see
#: module docstring). Judgment call inside the standard 1.2–1.4 range.
WALK_DETOUR = 1.3

#: Snap radius: origin/POI must find a graph node within this many metres
#: or the leg falls back to the estimate path (never a fake route).
SNAP_MAX_M = 300.0

#: Max routed candidates per nearest lookup (haversine-prefiltered,
#: nearest first). Bounds per-listing Dijkstra cost on dense POI sets.
ROUTE_CANDIDATES = 8

#: Reason suffix marking a routed walk measurement (repo vocabulary:
#: "jalgsikäik" is the word dims_group12 LAYER_META already uses for
#: the walk leg). Legacy/fallback reasons never carry it.
WALK_TAG = " (jalgsikäik)"


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (scorer (lat, lon) convention)."""
    r = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (lat1, lon1, lat2, lon2))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(
        (lo2 - lo1) / 2
    ) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def walk_bands(bands: List[Tuple[float, int]],
               factor: float = WALK_DETOUR) -> List[Tuple[float, int]]:
    """Rescale band edges by the walk detour factor (recalibration).

    ``inf`` edges pass through untouched. Integer-valued edges that stay
    integral are returned as ints so reason/table literals stay neat.

    Parity identity (pinned by test): scoring ``h * factor`` on
    ``walk_bands(bands, factor)`` gives the same score as scoring ``h``
    on ``bands`` — a listing whose true detour equals the factor keeps
    its legacy score exactly.
    """
    out: List[Tuple[float, int]] = []
    for limit, pts in bands:
        if limit == float("inf"):
            out.append((limit, pts))
            continue
        scaled = limit * factor
        if float(scaled).is_integer():
            scaled = int(scaled)
        out.append((scaled, pts))
    return out


def walk_cutoff(window_hav_m: float,
                factor: float = WALK_DETOUR) -> float:
    """Walk-equivalent of a haversine window (recalibrated cutoff).

    A leg that gated POIs on haversine <= window gates routed metres on
    walk_cutoff(window) instead, so the same places roughly pass under
    both measurements (detour compensation, same judgment call as
    WALK_DETOUR). Never multiplied into a distance.
    """
    return window_hav_m * factor


def bands_for(method: str,
              legacy_bands: List[Tuple[float, int]]) -> List[Tuple[float, int]]:
    """Band table for a lookup method ("walk" or "haversine").

    Walk-routed metres score on the rescaled bands; every other method
    (legacy no-graph path AND the unroutable-graph fallback) scores on
    the legacy bands, so fallback output is identical to no-graph
    output. Legs must branch only through this helper, never inline.
    """
    if method == "walk":
        return walk_bands(legacy_bands)
    return legacy_bands


class FootGraph:
    """Routable foot graph over the shipped sidecar shape.

    Nodes are (lon, lat); edges carry metre weights. Undirected (oneways
    do not apply to pedestrians — same FOOT profile as
    scripts/walk_graph.py).
    """

    def __init__(self) -> None:
        self.nodes: List[Tuple[float, float]] = []
        self.adj: Dict[int, List[Tuple[int, float]]] = {}

    def __len__(self) -> int:
        return len(self.nodes)

    def add_edge(self, i: int, j: int, metres: float) -> None:
        if i == j or not (metres > 0):
            return
        self.adj.setdefault(i, []).append((j, metres))
        self.adj.setdefault(j, []).append((i, metres))

    def snap_m(self, lon: float, lat: float,
               max_m: float = SNAP_MAX_M) -> Optional[Tuple[int, float]]:
        """(node, snap_metres) of the nearest node within max_m, else None."""
        best: Optional[int] = None
        best_d = max_m
        for i, (nlon, nlat) in enumerate(self.nodes):
            d = _haversine_m(lat, lon, nlat, nlon)
            if d <= best_d:
                best, best_d = i, d
        if best is None:
            return None
        return best, best_d

    def route_m(self, src: int, dst: int, cutoff_m: float) -> Optional[float]:
        """Shortest-path metres from src to dst within cutoff_m, else None."""
        if src == dst:
            return 0.0
        dist: Dict[int, float] = {src: 0.0}
        pq: List[Tuple[float, int]] = [(0.0, src)]
        while pq:
            d, u = heapq.heappop(pq)
            if d > dist.get(u, float("inf")):
                continue
            if d > cutoff_m:
                continue
            if u == dst:
                return d
            for v, w in self.adj.get(u, ()):
                nd = d + w
                if nd < dist.get(v, float("inf")) and nd <= cutoff_m:
                    dist[v] = nd
                    heapq.heappush(pq, (nd, v))
        return None


def load_foot_graph(path: str) -> Optional[FootGraph]:
    """Load a sidecar graph file. None when missing/unreadable — never throws.

    Callers degrade to the legacy haversine path, never an error
    presented as data (same None-on-missing contract as
    graphSample.loadFootGraph on the map side).
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        nodes = data["nodes"]
        edges = data["edges"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    try:
        g = FootGraph()
        for lon, lat in nodes:
            g.nodes.append((float(lon), float(lat)))
        n = len(g.nodes)
        for i, j, m in edges:
            i, j = int(i), int(j)
            if 0 <= i < n and 0 <= j < n:
                g.add_edge(i, j, float(m))
    except (TypeError, ValueError):
        return None
    return g if len(g) else None


def walk_dist_m(graph: FootGraph,
                origin: Tuple[float, float],
                lat: float, lon: float,
                cutoff_m: float) -> Optional[float]:
    """Routed walk metres from origin (lat, lon) to a POI, else None.

    None means "cannot route" (snap miss either end, disconnected, over
    cutoff) — the caller falls back to the estimate path, never zero.
    """
    olat, olon = origin
    s = graph.snap_m(olon, olat)
    t = graph.snap_m(lon, lat)
    if s is None or t is None:
        return None
    return graph.route_m(s[0], t[0], cutoff_m)


def _valid_kind_pois(origin: Tuple[float, float],
                       pois: List[dict],
                       kinds: set) -> List[Tuple[float, float, float]]:
    """All well-formed kind POIs as (hav_m, lat, lon), nearest first."""
    cands: List[Tuple[float, float, float]] = []
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") not in kinds:
            continue
        lat, lon = p.get("lat"), p.get("lon")
        if isinstance(lat, bool) or isinstance(lon, bool):
            continue
        try:
            latf, lonf = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(latf) and math.isfinite(lonf)):
            continue
        cands.append((_haversine_m(origin[0], origin[1], latf, lonf),
                      latf, lonf))
    cands.sort(key=lambda c: c[0])
    return cands


def nearest_walk_m(origin: Tuple[float, float],
                   pois: List[dict],
                   kinds: set,
                   window_hav_m: float,
                   graph: Optional[FootGraph] = None,
                   ) -> Tuple[Optional[float], str]:
    """Nearest POI distance in walk-aware metres + method flag.

    Returns ((metres, method)); method is "walk" when the metres are
    graph-routed, "haversine" otherwise.

    Legacy equivalence (pinned by test): None is returned iff no
    well-formed kind POI exists — the window only bounds ROUTING work,
    never the fallback. So graph None -> global haversine minimum
    (bit-identical to the old _nearest_m loops, default-path reasons
    never change); graph given but nothing routable -> global
    haversine minimum ("haversine", legacy bands via bands_for).

    * graph None -> legacy haversine minimum over all kind POIs.
    * graph given -> route the nearest-by-haversine candidates within
      window_hav_m (capped at ROUTE_CANDIDATES, walk cutoff
      walk_cutoff(window_hav_m)); best routed distance wins ("walk").
    """
    cands = _valid_kind_pois(origin, pois, kinds)
    if not cands:
        return None, "haversine"
    if graph is None:
        return cands[0][0], "haversine"
    cutoff = walk_cutoff(window_hav_m)
    best: Optional[float] = None
    routed = 0
    for d, lat, lon in cands:
        if d > window_hav_m or routed >= ROUTE_CANDIDATES:
            break
        r = walk_dist_m(graph, origin, lat, lon, cutoff)
        routed += 1
        if r is not None and (best is None or r < best):
            best = r
    if best is not None:
        return best, "walk"
    return cands[0][0], "haversine"


def count_within_walk_m(origin: Tuple[float, float],
                        pois: List[dict],
                        kinds: set,
                        radius_hav_m: float,
                        graph: Optional[FootGraph] = None,
                        ) -> Tuple[int, str]:
    """POI count inside the walk-equivalent radius + method flag.

    graph None -> legacy haversine count (identical to the old
    _count_within_m loops). graph given -> a POI counts when its routed
    walk distance is within radius_hav_m * WALK_DETOUR ("walk"); POIs
    that cannot route count on haversine <= radius ("haversine" mixed
    path — the count, not the method, is what scores, so the flag is
    informational only).
    """
    if graph is None:
        n = 0
        for p in pois:
            if not isinstance(p, dict) or p.get("kind") not in kinds:
                continue
            lat, lon = p.get("lat"), p.get("lon")
            if isinstance(lat, bool) or isinstance(lon, bool):
                continue
            try:
                latf, lonf = float(lat), float(lon)
            except (TypeError, ValueError):
                continue
            if _haversine_m(origin[0], origin[1], latf, lonf) <= radius_hav_m:
                n += 1
        return n, "haversine"
    window = walk_cutoff(radius_hav_m)
    cands: List[Tuple[float, float, float]] = []
    for p in pois:
        if not isinstance(p, dict) or p.get("kind") not in kinds:
            continue
        lat, lon = p.get("lat"), p.get("lon")
        if isinstance(lat, bool) or isinstance(lon, bool):
            continue
        try:
            latf, lonf = float(lat), float(lon)
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(latf) and math.isfinite(lonf)):
            continue
        d = _haversine_m(origin[0], origin[1], latf, lonf)
        if d <= window:
            cands.append((d, latf, lonf))
    n = 0
    routed_any = False
    for d, lat, lon in cands:
        r = walk_dist_m(graph, origin, lat, lon, window)
        if r is not None:
            routed_any = True
            if r <= window:
                n += 1
        elif d <= radius_hav_m:
            n += 1
    return n, ("walk" if routed_any else "haversine")
