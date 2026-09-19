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
