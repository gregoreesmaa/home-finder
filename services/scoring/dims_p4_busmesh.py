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

#: Chain-collapse radius: clustered nodes with IDENTICAL route sets within
#: this merge (shared-corridor chains, build #769 — measured, never guessed).
CHAIN_M = 300.0

#: Transfer-score saturating half: score = 100*n/(n+half) over the route
#: count at the node (client trips-kernel parity, see node_score).
TRANSFER_HALF = 5

#: GTFS calendar weekday columns per served window. Wednesday is the
#: commuter-peak window (densest network); Saturday/Sunday are derived
#: INDEPENDENTLY from their own services (never copied from Wednesday).
WINDOWS = {
    "wd": ("monday", "tuesday", "wednesday", "thursday", "friday"),
    "sat": ("saturday",),
    "sun": ("sunday",),
}


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


def window_shape_routes(trip_rows, calendar_rows, days):
    """shape_id -> {route_id} over trips running on ALL of the given days.

    days are calendar.txt weekday columns, e.g. ("saturday",) or the full
    WINDOWS["wd"] commuter set. ALL semantics (commuter core): a service
    must run every listed day, so Friday-only extras never leak into the
    Wednesday window (and vice versa).
    """
    wanted = {c["service_id"] for c in calendar_rows
              if all(c.get(d) == "1" for d in days)}
    out = {}
    for trip in trip_rows:
        if trip.get("service_id") not in wanted:
            continue
        sid = trip.get("shape_id")
        rid = trip.get("route_id")
        if not sid or not rid:
            continue
        out.setdefault(sid, set()).add(rid)
    return out


def wed_shape_routes(trip_rows, calendar_rows):
    """shape_id -> {route_id} over Wednesday-running trips."""
    return window_shape_routes(trip_rows, calendar_rows, ("wednesday",))


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


def collapse_chains(nodes, radius_m=CHAIN_M):
    """Merge corridor chains: nodes with IDENTICAL route sets within radius_m.

    Shared corridors produce crossing CHAINS (probe #764: 253 396 raw ->
    1922 clusters); plotting every link is noise, so equal-route-set
    neighbours collapse into one node (hits summed, centroid kept).
    Distinct hubs less than radius_m apart with DIFFERENT route sets are
    never merged. Greedy in input order, deterministic for a fixed input.
    Returns (kept, collapsed_count).
    """
    kept = []
    collapsed = 0
    for node in nodes:
        for keep in kept:
            if (keep["routes"] == node["routes"] and
                    math.hypot(keep["x"] - node["x"],
                               keep["y"] - node["y"]) <= radius_m):
                keep["hits"] += node["hits"]
                collapsed += 1
                break
        else:
            kept.append({"x": node["x"], "y": node["y"],
                         "routes": set(node["routes"]),
                         "hits": node["hits"]})
    return kept, collapsed


def snap_to_stops(nodes, stop_rows, radius_m=STOP_M):
    """Snap nodes to their nearest stop within radius_m; drop the stopless.

    Nodes snapping to the SAME stop merge (route sets union — one
    boarding point, one transfer record). Returns (snapped, dropped):
    snapped entries carry stop_id + stop lat/lon (the plotted position),
    dropped counts geometry without a usable transfer.
    """
    stops = []
    for row in stop_rows:
        try:
            lat = float(row["stop_lat"])
            lon = float(row["stop_lon"])
            sid = row["stop_id"]
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(lat) and math.isfinite(lon) and sid:
            stops.append((sid, lat, lon))
    by_stop = {}
    dropped = 0
    for node in nodes:
        best = None
        for sid, lat, lon in stops:
            x, y = project(lat, lon)
            d = math.hypot(node["x"] - x, node["y"] - y)
            if d <= radius_m and (best is None or d < best[0]):
                best = (d, sid, lat, lon)
        if best is None:
            dropped += 1
            continue
        _, sid, lat, lon = best
        slot = by_stop.get(sid)
        if slot is None:
            by_stop[sid] = {"stop_id": sid, "lat": lat, "lon": lon,
                            "routes": set(node["routes"]),
                            "hits": node["hits"]}
        else:
            slot["routes"].update(node["routes"])
            slot["hits"] += node["hits"]
    return list(by_stop.values()), dropped


def node_score(n_routes, half=TRANSFER_HALF):
    """Transfer score 0-100 over the route count (client trips-kernel parity).

    The client splats point t = route count with { kind: "trips", half }
    and scores 100*S/(S+half); an isolated node reads its own count, so
    node_score pins the anchor: 2 routes -> ~29, 5 -> 50, 10 -> 67,
    30 -> ~86. Single-route clusters never reach here (crossings need two
    routes by construction) — a lone route is "üksikteenus", not a node.
    """
    if n_routes <= 0:
        return 0.0
    return 100.0 * n_routes / (n_routes + half)


def busmesh_points(snapped_nodes):
    """Snapped nodes -> bare LayerPoint array for derived-busmesh*.json.

    t = route count at the stop (transfer richness, scheduled service —
    never occupancy). Points are classless BY HONESTY (no invented OSM
    tags, gtfsstops #483 precedent), so the client multi-mode kicker
    stays off (modeBonus 0).
    """
    return [{"lon": n["lon"], "lat": n["lat"], "t": len(n["routes"])}
            for n in snapped_nodes]


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
