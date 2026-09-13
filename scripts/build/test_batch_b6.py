"""Hermetic unit tests for the B6 mobility/access builder (issue #133).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_b6.py -q
"""

import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_b6_mobility as B


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return B.Grid([24.74, 59.43, 24.74 + n * step / 1000 / B.LON_KM,
                   59.43 + n * step / 1000 / B.LAT_KM], step)


def test_hav_km_lon_scale():
    assert abs(B.hav_km(0.0, 0.0, 1.0, 0.0) - 57.29) < 1e-9
    assert abs(B.hav_km(0.0, 0.0, 0.0, 1.0) - 110.57) < 1e-9


def test_quiet_from_half():
    assert B.quiet_from_half(0.0, 1300.0) == 0.0
    assert B.quiet_from_half(1300.0, 1300.0) == 50.0
    assert B.quiet_from_half(float("inf"), 1300.0) == 100.0


def test_yard_bands_match_scorer():
    # Behaviour lock: these MUST equal services/scoring/dims_group13.py
    # YARD_BANDS exactly (the p270 scorer bands).
    assert B.yard_score(0.0) == 100
    assert B.yard_score(100.0) == 100
    assert B.yard_score(101.0) == 80
    assert B.yard_score(300.0) == 80
    assert B.yard_score(500.0) == 60
    assert B.yard_score(1000.0) == 40
    assert B.yard_score(1001.0) == 25
    assert B.yard_score(20000.0) == 25


def test_dijkstra_exact_on_tiny_grid():
    g = tiny_grid()
    src = g.cell_of(*g.center_of(40))
    d = B.dijkstra_km(g, {src})
    assert d[src] == 0.0
    assert abs(d[src + 1] - g.step / 1000.0) < 1e-9
    row = [d[40 + i] for i in range(5)]
    assert row == sorted(row)


def test_scores_endpoint_behaviour():
    n = 81
    inf = [float("inf")] * n
    d0 = [0.0] * n
    cal = B.B6_CAL
    # Nothing mapped -> fully clear/viable/calm (absence in-bbox IS evidence).
    assert all(v == 100 for v in B.score_distance(inf, 1300.0))
    assert all(v == 25 for v in B.score_droneviab(inf, inf, cal["droneviab"]))
    assert all(v == 100 for v in B.score_distance(inf, 800.0))
    # On the source -> known-exposed 0 (never 255/unknown).
    assert all(v == 0 for v in B.score_distance(d0, 1300.0))
    # p270 min() combiner: the blocker binds, never an average.
    assert all(v == 0 for v in B.score_droneviab(d0, inf, cal["droneviab"]))
    # Far from everything: clear leg 100, yard leg 25 -> min binds at 25.
    assert all(v == 25 for v in B.score_droneviab(inf, inf, cal["droneviab"]))
    far = B.score_droneviab(inf, [20000.0 / 1000.0] * n, cal["droneviab"])
    assert all(v == 25 for v in far)
    # Near a park but under the flight path: clearance binds.
    near_park = B.score_droneviab(d0, [0.05] * n, cal["droneviab"])
    assert all(v == 0 for v in near_park)


def test_geom_points_shapes():
    assert B._geom_points({"type": "Point", "coordinates": [24.7, 59.4]}) == [(24.7, 59.4)]
    line = {"type": "LineString", "coordinates": [[0.0, 0.0], [2.0, 0.0], [4.0, 0.0]]}
    assert B._geom_points(line) == [(2.0, 0.0)]
    poly = {"type": "Polygon", "coordinates": [[[0.0, 0.0], [4.0, 0.0],
                                                [4.0, 4.0], [0.0, 0.0]]]}
    assert B._geom_points(poly) == [(2.0, 2.0)]
    assert B._geom_points({"type": "Point", "coordinates": []}) == []
    assert B._geom_points({"type": "GeometryCollection"}) == []


def _write_snap(tmpdir, aero_feats, campus_feats, parks):
    os.makedirs(os.path.join(tmpdir, "osm"))
    with open(os.path.join(tmpdir, "osm", "derived-aeroway.geojson"), "w") as f:
        json.dump({"features": aero_feats}, f)
    with open(os.path.join(tmpdir, "osm", "derived-campus.geojson"), "w") as f:
        json.dump({"features": campus_feats}, f)
    with open(os.path.join(tmpdir, "osm", "derived-parks.json"), "w") as f:
        json.dump(parks, f)
    return tmpdir


def _pt(lon, lat, **tags):
    return {"type": "Feature", "properties": dict(tags),
            "geometry": {"type": "Point", "coordinates": [lon, lat]}}


def test_readers_keep_sites_drop_junk(tmp_path):
    snap = _write_snap(
        str(tmp_path),
        [_pt(24.80, 59.41, aeroway="aerodrome", name="Test Airport"),
         _pt(24.74, 59.43, aeroway="helipad"),
         _pt(24.75, 59.44, aeroway="runway"),  # sub-part, not a site
         _pt(24.76, 59.45, aeroway="taxiway"),  # sub-part, not a site
         {"type": "Feature", "properties": {},
          "geometry": {"type": "Point", "coordinates": [24.77, 59.46]}}],
        [_pt(24.66, 59.39, amenity="university", name="Test Uni"),
         {"type": "Feature",
          "properties": {"amenity": "university"},
          "geometry": {"type": "Polygon", "coordinates": [[[24.66, 59.39],
                         [24.67, 59.39], [24.67, 59.40], [24.66, 59.39]]]}},
         _pt(24.67, 59.40, building="dormitory"),
         {"type": "Feature", "properties": {},
          "geometry": {"type": "Point", "coordinates": [24.68, 59.41]}}],
        [{"lon": 24.70, "lat": 59.42}])
    aero_pts, aero_overlay, aero_stats = B.read_air_sites(snap)
    assert aero_stats == {"aerodrome": 1, "helipad": 1, "skipped": 3}
    assert len(aero_pts) == 2
    assert {d["tags"]["aeroway"] for d in aero_overlay} == {"aerodrome", "helipad"}
    camp_pts, camp_overlay, camp_stats = B.read_campus_points(snap)
    assert camp_stats == {"university": 2, "college": 0, "dormitory": 1,
                          "skipped": 1}
    assert len(camp_pts) == 3
    assert B.read_park_points(snap) == [(24.70, 59.42)]


def test_scores_never_emit_unknown():
    # In-bbox absence IS the quiet evidence: masters carry no 255s
    # (speckle-rescan guard — every cell reads a real distance).
    n = 81
    for vals in (B.score_distance([0.0] * n, 1300.0),
                 B.score_distance([float("inf")] * n, 1300.0),
                 B.score_droneviab([0.0] * n, [float("inf")] * n,
                                   B.B6_CAL["droneviab"]),
                 B.score_droneviab([float("inf")] * n, [float("inf")] * n,
                                   B.B6_CAL["droneviab"])):
        assert all(0 <= v <= 100 for v in vals)


def test_wire_contract_matches_registry():
    # Wire halves MUST equal B6_CAL (the matchesContract hook rejects drift).
    assert B.contract_of("droneclear") == (1300.0, 0.3)
    assert B.contract_of("droneviab") == (800.0, 0.3)  # clearance leg on wire
    assert B.contract_of("rentbleed") == (800.0, 0.3)
    g = tiny_grid()
    doc = B.encode_wire(g, bytearray(g.cols * g.rows), "droneclear")
    assert doc["half"] == 1300.0 and doc["sigma"] == 0.3
    assert doc["unknown"] == 255 and doc["per"] == 0 and doc["cap"] == 0
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows


def test_ts_cal_drift_lock():
    # Parse B6_CAL out of the TS source and fail on any drift.
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    ts = open(os.path.join(root, "apps", "web", "lib",
                           "layers_batch6.ts"), encoding="utf-8").read()
    m = re.search(r"B6_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "B6_CAL block not found in layers_batch6.ts"
    body = m.group(1)
    ts_key = {"half_m": "halfM", "clear_half_m": "clearHalfM",
              "sigma": "sigma"}
    for layer, cal in B.B6_CAL.items():
        for key in cal:
            pat = r"%s:\s*\{[^}]*%s:\s*([0-9.]+)" % (layer, ts_key[key])
            tm = re.search(pat, body)
            assert tm, "B6_CAL.%s.%s missing in TS" % (layer, key)
            assert abs(float(tm.group(1)) - cal[key]) < 1e-9, \
                "drift: TS B6_CAL.%s.%s=%s != py %s" % (
                    layer, key, tm.group(1), cal[key])


def test_write_points_shape(tmp_path):
    snap = _write_snap(
        str(tmp_path),
        [_pt(24.80, 59.41, aeroway="aerodrome"),
         _pt(24.74, 59.43, aeroway="helipad")],
        [_pt(24.66, 59.39, amenity="university", name="U")],
        [{"lon": 24.70, "lat": 59.42}])
    counts = B.write_points(snap)
    assert counts == {"droneclear": 2, "droneviab": 2, "rentbleed": 1}
    for layer in ("droneclear", "droneviab", "rentbleed"):
        pts = json.load(open(os.path.join(snap, "osm",
                                          "derived-%s.json" % layer)))
        assert isinstance(pts, list) and pts
        for p in pts:
            assert isinstance(p["lon"], float) and isinstance(p["lat"], float)
