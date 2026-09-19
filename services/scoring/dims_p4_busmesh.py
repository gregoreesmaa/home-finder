"""P4 bus-mesh probe (issue #764): granular transfer nodes where GTFS
static route shapes cross.

Pure offline derivation (single source of truth), stdlib only. A node is
a place where the SHAPES of two different routes geometrically cross —
a candidate transfer point. Stops do not define nodes (shape crossings
do); stops only VALIDATE them (a crossing with no stop nearby is not a
usable transfer).

Network lives NOWHERE in this module: the vintage zip is snapshot data
read by scripts/build/batch_busmesh_probe.py, and the tests below run on
in-file fixtures. Method, vintage and measured counts are dated in
docs/p4_busmesh.md (verdict 2026-09-19: POSITIVE).

Judgment calls (reviewable per AGENTS.md section 7.5):
* Wednesday service defines the route set (commuter peak ⇒ densest
  network; weekend-only crossings are a documented non-goal).
* Crossings cluster at 60 m: shared corridors produce crossing CHAINS,
  and the build issue must collapse corridor chains (or snap to stops),
  not plot every chain link. The probe counts clusters, never raw
  crossings, as nodes.
* Stop validation at 100 m: a node without a stop in 100 m is counted
  separately (unusable as a transfer until a stop is mapped).
"""

import math

#: Local equirectangular projection origin (Tallinn centre).
LAT0 = math.radians(59.44)

#: Clustering radius: raw crossings within this merge into one node.
CLUSTER_M = 60.0

#: Stop-validation radius: a node needs a stop within this to count as usable.
STOP_M = 100.0


def project(lat, lon):
    """(lat, lon) degrees -> local (x, y) metres."""
    return (lon * 111320.0 * math.cos(LAT0), lat * 110540.0)


def shape_polylines(shape_rows):
    """shape_id -> [(lat, lon)] in shape_pt_sequence order."""
    grouped = {}
    for row in shape_rows:
        try:
            sid = row["shape_id"]
            lat = float(row["shape_pt_lat"])
            lon = float(row["shape_pt_lon"])
            seq = int(row["shape_pt_sequence"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(lat) and math.isfinite(lon)):
            continue
        grouped.setdefault(sid, []).append((seq, lat, lon))
    out = {}
    for sid, pts in grouped.items():
        pts.sort(key=lambda p: p[0])
        line = [(lat, lon) for _, lat, lon in pts]
        if len(line) >= 2:
            out[sid] = line
    return out


def wed_shape_routes(trip_rows, calendar_rows):
    """shape_id -> {route_id} over Wednesday-running trips."""
    wed = {c["service_id"] for c in calendar_rows
           if c.get("wednesday") == "1"}
    out = {}
    for trip in trip_rows:
        if trip.get("service_id") not in wed:
            continue
        sid = trip.get("shape_id")
        rid = trip.get("route_id")
        if not sid or not rid:
            continue
        out.setdefault(sid, set()).add(rid)
    return out


def seg_intersection(p1, p2, p3, p4):
    """Proper segment intersection of p1p2 x p3p4 in metres, else None.

    Collinear/parallel overlaps return None (shared corridors are chains
    of proper crossings at their ends, not overlaps — the builder must
    still collapse chains, see module docstring).
    """
    x1, y1, x2, y2 = p1[0], p1[1], p2[0], p2[1]
    x3, y3, x4, y4 = p3[0], p3[1], p4[0], p4[1]
    denom = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(denom) < 1e-9:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / denom
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def segment_crossings(polylines, shape_routes):
    """Raw crossings between shapes of DIFFERENT route sets.

    Returns [(x, y, frozenset(routes))]. Same-shape and same-route-set
    pairs are skipped (a route crossing itself is not a transfer).
    Shapes with no Wednesday routes are skipped (unknown, never guessed).
    """
    sids = sorted(polylines)
    projected = {sid: [project(la, lo) for la, lo in polylines[sid]]
                 for sid in sids}
    # Grid index so city scale stays tractable.
    cell = 300.0
    grid = {}
    for idx, sid in enumerate(sids):
        line = projected[sid]
        for a, b in zip(line, line[1:]):
            key_range = (
                range(int(min(a[0], b[0]) // cell),
                      int(max(a[0], b[0]) // cell) + 1),
                range(int(min(a[1], b[1]) // cell),
                      int(max(a[1], b[1]) // cell) + 1),
            )
            for cx in key_range[0]:
                for cy in key_range[1]:
                    grid.setdefault((cx, cy), []).append((idx, a, b))
    raw = []
    for members in grid.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                (ai, a1, a2), (bi, b1, b2) = members[i], members[j]
                if ai == bi:
                    continue
                ra = shape_routes.get(sids[ai], set())
                rb = shape_routes.get(sids[bi], set())
                if not ra or not rb or ra == rb:
                    continue
                pt = seg_intersection(a1, a2, b1, b2)
                if pt is None:
                    continue
                raw.append((pt[0], pt[1], frozenset(ra | rb)))
    return raw


def cluster_nodes(raw_crossings, radius_m=CLUSTER_M):
    """Merge raw crossings within radius_m into nodes.

    Returns [{"x", "y", "routes": set, "hits": n}]. Route sets UNION on
    merge (a corridor chain accumulates every route touching it).
    """
    nodes = []
    for x, y, routes in raw_crossings:
        for node in nodes:
            if math.hypot(node["x"] - x, node["y"] - y) <= radius_m:
                node["routes"].update(routes)
                node["hits"] += 1
                break
        else:
            nodes.append({"x": x, "y": y,
                          "routes": set(routes), "hits": 1})
    return nodes


def stop_overlap(nodes, stop_rows, radius_m=STOP_M):
    """(nodes within radius_m of a stop, stops within radius_m of a node)."""
    pts = []
    for row in stop_rows:
        try:
            lat = float(row["stop_lat"])
            lon = float(row["stop_lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(lat) and math.isfinite(lon):
            pts.append(project(lat, lon))
    near_nodes = sum(
        1 for node in nodes
        if any(math.hypot(node["x"] - x, node["y"] - y) <= radius_m
               for x, y in pts))
    near_stops = sum(
        1 for x, y in pts
        if any(math.hypot(node["x"] - x, node["y"] - y) <= radius_m
               for node in nodes))
    return near_nodes, near_stops
