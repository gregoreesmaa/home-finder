"""P4 bus-mesh probe (issue #764): hermetic guard tests.

No network: every case below runs on in-file shape/stop fixtures around
a synthetic crossing. Pins: proper crossings found, same-shape and
same-route pairs ignored, parallel lines never cross, degenerate rows
dropped, 60 m clustering unions route sets, stop join honours the
100 m radius.
"""

import dims_p4_busmesh as bm

CAL = [
    {"service_id": "W", "wednesday": "1"},
    {"service_id": "E", "wednesday": "0"},
]

# Route A runs east along lat 59.44; route B runs north across it at
# lon 24.75; route C runs parallel to A 200 m north (never crosses).
TRIPS = [
    {"trip_id": "a1", "route_id": "A", "service_id": "W", "shape_id": "sA"},
    {"trip_id": "b1", "route_id": "B", "service_id": "W", "shape_id": "sB"},
    {"trip_id": "c1", "route_id": "C", "service_id": "W", "shape_id": "sC"},
    {"trip_id": "e1", "route_id": "A", "service_id": "E", "shape_id": "sE"},
]

SHAPES = [
    {"shape_id": "sA", "shape_pt_lat": "59.4400", "shape_pt_lon": "24.7400",
     "shape_pt_sequence": "1"},
    {"shape_id": "sA", "shape_pt_lat": "59.4400", "shape_pt_lon": "24.7600",
     "shape_pt_sequence": "2"},
    {"shape_id": "sB", "shape_pt_lat": "59.4350", "shape_pt_lon": "24.7500",
     "shape_pt_sequence": "1"},
    {"shape_id": "sB", "shape_pt_lat": "59.4450", "shape_pt_lon": "24.7500",
     "shape_pt_sequence": "2"},
    {"shape_id": "sC", "shape_pt_lat": "59.4418", "shape_pt_lon": "24.7400",
     "shape_pt_sequence": "1"},
    {"shape_id": "sC", "shape_pt_lat": "59.4418", "shape_pt_lon": "24.7600",
     "shape_pt_sequence": "2"},
    # Degenerate rows: unparseable + single-point shape (never a node).
    {"shape_id": "sX", "shape_pt_lat": "NaN", "shape_pt_lon": "24.7500",
     "shape_pt_sequence": "1"},
    {"shape_id": "s1", "shape_pt_lat": "59.4400", "shape_pt_lon": "24.7500",
     "shape_pt_sequence": "1"},
]

STOPS = [
    {"stop_id": "near", "stop_lat": "59.4402", "stop_lon": "24.7503"},
    {"stop_id": "far", "stop_lat": "59.4500", "stop_lon": "24.7800"},
]


def _mesh():
    polys = bm.shape_polylines(SHAPES)
    routes = bm.wed_shape_routes(TRIPS, CAL)
    raw = bm.segment_crossings(polys, routes)
    return polys, routes, bm.cluster_nodes(raw)


def test_crossing_found_between_different_routes():
    _, _, nodes = _mesh()
    # B crosses both A and C: two nodes, {A,B} south and {B,C} north.
    assert len(nodes) == 2
    route_sets = sorted((sorted(n["routes"]) for n in nodes))
    assert route_sets == [["A", "B"], ["B", "C"]]


def test_parallel_routes_never_share_a_node():
    _, _, nodes = _mesh()
    assert all(not ({"A", "C"} <= node["routes"]) for node in nodes)


def test_weekend_only_shape_has_no_wednesday_routes():
    _, routes, _ = _mesh()
    assert "sE" not in routes


def test_degenerate_shapes_dropped():
    polys, _, _ = _mesh()
    assert "sX" not in polys
    assert "s1" not in polys


def test_same_route_pair_ignored():
    polys = {"s1": [(59.44, 24.74), (59.44, 24.76)],
             "s2": [(59.435, 24.75), (59.445, 24.75)]}
    routes = {"s1": {"A"}, "s2": {"A"}}
    assert bm.cluster_nodes(bm.segment_crossings(polys, routes)) == []


def test_clustering_unions_route_sets():
    raw = [(0.0, 0.0, frozenset({"A", "B"})),
           (30.0, 40.0, frozenset({"C", "D"})),
           (500.0, 0.0, frozenset({"E", "F"}))]
    nodes = bm.cluster_nodes(raw, radius_m=60.0)
    assert len(nodes) == 2
    big = next(n for n in nodes if n["hits"] == 2)
    assert big["routes"] == {"A", "B", "C", "D"}


def test_stop_join_radius():
    _, _, nodes = _mesh()
    near_nodes, near_stops = bm.stop_overlap(nodes, STOPS)
    assert near_nodes == 1
    assert near_stops == 1


def test_collinear_overlap_is_not_a_crossing():
    assert bm.seg_intersection((0, 0), (10, 0), (3, 0), (7, 0)) is None
    assert bm.seg_intersection((0, 0), (10, 0), (0, 5), (10, 5)) is None
    pt = bm.seg_intersection((0, 0), (10, 0), (5, -5), (5, 5))
    assert pt is not None and abs(pt[0] - 5.0) < 1e-6


# -- Build #769: chains, snap, windows, transfer score. ----------------------

def _node(x, y, routes, hits=1):
    return {"x": x, "y": y, "routes": set(routes), "hits": hits}


def test_collapse_chains_merges_identical_route_sets():
    nodes = [_node(0, 0, {"A", "B"}), _node(200, 0, {"A", "B"}),
             _node(1000, 0, {"A", "B"}), _node(100, 0, {"A", "C"})]
    kept, collapsed = bm.collapse_chains(nodes, radius_m=300.0)
    assert collapsed == 1
    assert len(kept) == 3
    assert kept[0]["hits"] == 2
    # Different route sets never merge, however close.
    assert {len(n["routes"]) for n in kept} == {2}


def test_snap_to_stops_merges_same_stop_and_drops_stopless():
    proj = bm.project(59.44, 24.75)
    stops = [{"stop_id": "s1", "stop_lat": "59.4400", "stop_lon": "24.7500"},
             {"stop_id": "bad", "stop_lat": "NaN", "stop_lon": "24.75"}]
    nodes = [_node(proj[0] + 20, proj[1], {"A", "B"}),
             _node(proj[0] - 20, proj[1], {"B", "C"}),
             _node(proj[0] + 5000, proj[1], {"D", "E"})]
    snapped, dropped = bm.snap_to_stops(nodes, stops)
    assert dropped == 1
    assert len(snapped) == 1
    assert snapped[0]["stop_id"] == "s1"
    assert snapped[0]["routes"] == {"A", "B", "C"}
    assert snapped[0]["lat"] == 59.44 and snapped[0]["lon"] == 24.75


def test_window_routes_use_all_day_semantics():
    cal = [{"service_id": "WD", "monday": "1", "tuesday": "1",
            "wednesday": "1", "thursday": "1", "friday": "1",
            "saturday": "0", "sunday": "0"},
           {"service_id": "FRI", "monday": "0", "tuesday": "0",
            "wednesday": "0", "thursday": "0", "friday": "1",
            "saturday": "0", "sunday": "0"},
           {"service_id": "SAT", "monday": "0", "tuesday": "0",
            "wednesday": "0", "thursday": "0", "friday": "0",
            "saturday": "1", "sunday": "0"}]
    trips = [{"trip_id": "a", "route_id": "A", "service_id": "WD",
              "shape_id": "s"},
             {"trip_id": "b", "route_id": "B", "service_id": "FRI",
              "shape_id": "s"},
             {"trip_id": "c", "route_id": "C", "service_id": "SAT",
              "shape_id": "s"}]
    wd = bm.window_shape_routes(trips, cal, bm.WINDOWS["wd"])
    assert wd == {"s": {"A"}}
    assert bm.window_shape_routes(trips, cal, ("wednesday",)) == {"s": {"A"}}
    assert bm.window_shape_routes(trips, cal, bm.WINDOWS["sat"]) == {"s": {"C"}}
    assert bm.wed_shape_routes(trips, cal) == {"s": {"A"}}


def test_node_score_anchors():
    assert bm.node_score(0) == 0.0
    assert round(bm.node_score(2), 1) == 28.6
    assert bm.node_score(5) == 50.0
    assert round(bm.node_score(10), 1) == 66.7
    assert round(bm.node_score(30), 1) == 85.7


def test_busmesh_points_carry_route_counts_classless():
    pts = bm.busmesh_points([{"stop_id": "s", "lat": 59.44, "lon": 24.75,
                              "routes": {"A", "B", "C"}, "hits": 4}])
    assert pts == [{"lon": 24.75, "lat": 59.44, "t": 3}]
