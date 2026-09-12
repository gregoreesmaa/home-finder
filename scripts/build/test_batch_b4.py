"""Hermetic unit tests for batch 4 builders (no network, no snapshot, no
walk_raster/walk_graph imports -- fixtures are inline). Run from repo root:
  python3 -m pytest scripts/build/test_batch_b4.py -q
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_b4_common as C
import batch_b4_parcel as P
import batch_b4_rideshare as R
import batch_b4_transit as T


def test_hav_km_lon_scale():
    # 1 degree of longitude at Harjumaa latitude ~57.29 km; latitude ~110.57.
    assert abs(C.hav_km(0.0, 0.0, 1.0, 0.0) - 57.29) < 1e-9
    assert abs(C.hav_km(0.0, 0.0, 0.0, 1.0) - 110.57) < 1e-9


def test_kernel_and_saturate():
    assert C.kernel(0.0, 0.2) == 1.0
    assert 0.0 < C.kernel(0.2, 0.2) < 1.0
    assert C.saturate(0.0, 800.0) == 0.0
    assert C.saturate(800.0, 800.0) == 50.0
    assert C.saturate(1e9, 800.0) > 99.9


def test_service_ids_union_and_intersection():
    cal = [
        {"service_id": "wd", "wednesday": "1", "saturday": "0", "sunday": "0"},
        {"service_id": "sa", "wednesday": "0", "saturday": "1", "sunday": "0"},
        {"service_id": "su", "wednesday": "0", "saturday": "0", "sunday": "1"},
    ]
    assert C.service_ids_for(cal, "wednesday") == {"wd"}
    assert C.service_ids_for_any(cal, "saturday", "sunday") == {"sa", "su"}


def _gtfs():
    cal = [
        {"service_id": "wd", "wednesday": "1", "saturday": "0", "sunday": "0"},
        {"service_id": "sa", "wednesday": "0", "saturday": "1", "sunday": "0"},
        {"service_id": "su", "wednesday": "0", "saturday": "0", "sunday": "1"},
    ]
    trips = [
        {"trip_id": "t1", "route_id": "rA", "service_id": "wd"},
        {"trip_id": "t2", "route_id": "rB", "service_id": "wd"},
        {"trip_id": "t3", "route_id": "rA", "service_id": "sa"},
        {"trip_id": "t4", "route_id": "rA", "service_id": "su"},
    ]
    stop_times = [
        {"trip_id": "t1", "stop_id": "AP"},   # airport stop, route rA
        {"trip_id": "t1", "stop_id": "S1"},
        {"trip_id": "t2", "stop_id": "S1"},   # route rB, not airport-serving
        {"trip_id": "t3", "stop_id": "S1"},
        {"trip_id": "t3", "stop_id": "S2"},
        {"trip_id": "t4", "stop_id": "S2"},
    ]
    stops = [
        {"stop_id": "AP", "stop_lon": "24.80", "stop_lat": "59.42"},
        {"stop_id": "S1", "stop_lon": "24.74", "stop_lat": "59.44"},
        {"stop_id": "S2", "stop_lon": "24.66", "stop_lat": "59.41"},
    ]
    routes = [{"route_id": "rA"}, {"route_id": "rB"}]
    return {"calendar.txt": cal, "trips.txt": trips,
            "stop_times.txt": stop_times, "stops.txt": stops,
            "routes.txt": routes}


def test_weekend_counts_sum_sat_sun():
    cnt = T.weekend_counts(_gtfs())
    assert cnt == {"S1": 1, "S2": 2}  # t3 sat + t4 sun


def test_airport_counts_only_airport_routes():
    routes, cnt = T.airport_counts(_gtfs(), airport_stop_ids=("AP",))
    assert routes == ["rA"]  # only rA calls at the Lennujaam fixture stop AP
    # t1 (rA, wed) serves AP + S1; t2 (rB) is excluded entirely.
    assert cnt == {"AP": 1, "S1": 1}


def test_join_trips_winner_default_zero():
    stops = [{"lon": 0.0, "lat": 0.0},       # claimant A (nearer)
             {"lon": 0.0005, "lat": 0.0},    # claimant B (co-claimant -> 0)
             {"lon": 5.0, "lat": 5.0}]       # unmatched -> default
    freq = [{"lon": 0.0001, "lat": 0.0, "trips": 42}]
    assert T.join_trips(stops, freq) == [42, 0, T.DEFAULT_TRIPS]
    # Airport layer passes default=0: unserved stops contribute nothing.
    assert T.join_trips(stops, freq, default=0) == [42, 0, 0]


def test_feature_point_geometries():
    assert C.feature_point({"type": "Point", "coordinates": [1.0, 2.0]}) == (1.0, 2.0)
    assert C.feature_point({"type": "LineString",
                            "coordinates": [[0, 0], [2, 0], [4, 0]]}) == (2.0, 0.0)
    assert C.feature_point({"type": "Polygon",
                            "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 0]]]}) == (1.0, 1.0)
    assert C.feature_point({"type": "MultiPoint", "coordinates": []}) is None
    assert C.feature_point(None) is None


def _parcel_lines():
    feats = [
        {"type": "Feature", "id": 1, "properties": {"amenity": "parcel_locker"},
         "geometry": {"type": "Point", "coordinates": [24.75, 59.44]}},
        {"type": "Feature", "id": 1, "properties": {"amenity": "parcel_locker"},
         "geometry": {"type": "Point", "coordinates": [24.75001, 59.44001]}},
        {"type": "Feature", "id": 2, "properties": {"amenity": "post_office"},
         "geometry": {"type": "LineString", "coordinates": [[24.7, 59.4], [24.72, 59.4]]}},
        {"type": "Feature", "id": 3, "properties": {"amenity": "cafe"},
         "geometry": {"type": "Point", "coordinates": [24.7, 59.4]}},
        {"type": "Feature", "id": 4, "properties": {"amenity": "parcel_locker"},
         "geometry": {"type": "Point", "coordinates": []}},
    ]
    return "\n".join(json.dumps(f) for f in feats) + "\n"


def test_resolve_parcels_weights_dedupe(tmp_path):
    p = tmp_path / "amen.geojson"
    p.write_text(_parcel_lines(), encoding="utf-8")
    pts, stats = P.resolve_parcels(str(p))
    assert stats["lockers"] == 1  # duplicate OSM id kept once
    assert stats["postoffices"] == 1
    assert stats["features"] == 5
    by_amenity = {a: w for _, _, w, a in pts}
    assert by_amenity == {"parcel_locker": 1.0, "post_office": 2.0}
    # LineString midpoint representative.
    po = [pt for pt in pts if pt[3] == "post_office"][0]
    assert po[0] == 24.72 and po[1] == 59.4


def test_wait_mapping_explicit_boundaries():
    assert R.wait_from_norms(1.0, 1.0) == 2.0
    assert R.wait_from_norms(0.0, 0.0) == 15.0
    assert R.score_from_wait(2.0) == 100.0
    assert R.score_from_wait(15.0) == 0.0
    # Linear midpoint: 8.5 min -> 50.
    assert R.score_from_wait(8.5) == 50.0
    # Clamping, never outside [2, 15].
    assert R.wait_from_norms(2.0, 2.0) == 2.0
    assert R.wait_from_norms(-1.0, -1.0) == 15.0


def test_build_scores_ordering_and_unknown():
    bbox = [24.70, 59.40, 24.75, 59.43]
    stops = [(24.725, 59.415, 2000.0)]  # strong transit at the middle
    cars = [(24.725 + dx * 0.0005, 59.415 + dy * 0.0005)
            for dx in range(-10, 11) for dy in range(-10, 11)]
    scores, stats = R.build_scores(bbox, 75.0, stops, cars)
    assert stats["cells"] > 0
    cols, rows = stats["cols"], stats["rows"]
    center = R.cell_of(bbox, 75.0, cols, rows, 24.725, 59.415)
    corner = R.cell_of(bbox, 75.0, cols, rows, 24.701, 59.401)
    assert center is not None and corner is not None
    # One 2000-trip stop + a 441-node street grid: Tn~0.57, Rn~0.3, so the
    # center reads mid-ramp (~40); real hubs sum MANY stops and read 70+.
    assert scores[center] > 35
    assert corner not in scores  # past both signals: unknown, never zero-filled


def test_build_scores_road_only_is_known_bad():
    bbox = [24.70, 59.40, 24.75, 59.43]
    cars = [(24.725, 59.415)]  # one road node, no transit anywhere
    scores, _ = R.build_scores(bbox, 75.0, [], cars)
    assert len(scores) > 0
    assert all(0 <= v <= 100 for v in scores.values())
    assert max(scores.values()) < 50  # transit-free can never read good


def test_ts_calibration_matches():
    """layers_batch4.ts mirrors CAL exactly (parsed, not imported)."""
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_batch4.ts"), encoding="utf-8").read()
    for token, value in [("half: 800", None), ("half: 150", None),
                         ("half: 4", None), ("half: 6", None),
                         ("waitMin: 2", None), ("waitMax: 15", None),
                         ("transitHalf: 1500", None), ("roadHalf: 800", None)]:
        assert token in ts, token
    assert '"teens"' in ts and '"airport"' in ts and '"lockers"' in ts
    assert '"securepickup"' in ts and '"rideshare"' in ts
