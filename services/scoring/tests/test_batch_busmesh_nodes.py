"""Batch bus-mesh nodes builder (issue #769): hermetic builder tests.

No network, no snapshot: build_window runs on a synthetic two-route
crossing (same fixture shape as test_dims_p4_busmesh) and asserts the
full chain — window derivation, clustering, chain collapse, stop snap,
sidecar point shape.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

import batch_busmesh_nodes as bbn  # noqa: E402
import dims_p4_busmesh as bm  # noqa: E402

CAL = [{"service_id": "W", "monday": "1", "tuesday": "1",
        "wednesday": "1", "thursday": "1", "friday": "1",
        "saturday": "0", "sunday": "0"},
       {"service_id": "S", "monday": "0", "tuesday": "0",
        "wednesday": "0", "thursday": "0", "friday": "0",
        "saturday": "1", "sunday": "0"}]

TRIPS = [{"trip_id": "a", "route_id": "A", "service_id": "W",
          "shape_id": "sA"},
         {"trip_id": "b", "route_id": "B", "service_id": "W",
          "shape_id": "sB"},
         {"trip_id": "c", "route_id": "C", "service_id": "S",
          "shape_id": "sC"}]

SHAPES = [{"shape_id": "sA", "shape_pt_lat": "59.4400",
           "shape_pt_lon": "24.7400", "shape_pt_sequence": "1"},
          {"shape_id": "sA", "shape_pt_lat": "59.4400",
           "shape_pt_lon": "24.7600", "shape_pt_sequence": "2"},
          {"shape_id": "sB", "shape_pt_lat": "59.4350",
           "shape_pt_lon": "24.7500", "shape_pt_sequence": "1"},
          {"shape_id": "sB", "shape_pt_lat": "59.4450",
           "shape_pt_lon": "24.7500", "shape_pt_sequence": "2"},
          {"shape_id": "sC", "shape_pt_lat": "59.4300",
           "shape_pt_lon": "24.7000", "shape_pt_sequence": "1"},
          {"shape_id": "sC", "shape_pt_lat": "59.4300",
           "shape_pt_lon": "24.7200", "shape_pt_sequence": "2"}]

STOPS = [{"stop_id": "hub", "stop_lat": "59.4401",
          "stop_lon": "24.7501"},
         {"stop_id": "far", "stop_lat": "59.4500",
          "stop_lon": "24.7800"}]

GTFS = {"calendar.txt": CAL, "trips.txt": TRIPS, "shapes.txt": SHAPES,
        "stops.txt": STOPS,
        "routes.txt": [{"route_id": "A"}, {"route_id": "B"},
                       {"route_id": "C"}]}


def test_build_window_wednesday_snaps_one_node():
    points, stats = bbn.build_window(GTFS, bm.WINDOWS["wd"])
    assert stats["snapped"] == 1
    assert stats["dropped"] == 0
    assert points == [{"lon": 24.7501, "lat": 59.4401, "t": 2}]


def test_build_window_saturday_uses_own_services():
    # Saturday runs route C only: no crossings, no nodes, no crash.
    points, stats = bbn.build_window(GTFS, bm.WINDOWS["sat"])
    assert stats["snapped"] == 0
    assert points == []


def test_splat_weights_route_counts():
    points, _ = bbn.build_window(GTFS, bm.WINDOWS["wd"])
    on_node = bbn.splat(points, 24.7501, 59.4401)
    assert abs(on_node - 2.0) < 1e-6
    rural = bbn.splat(points, 24.50, 59.20)
    assert rural == 0.0
