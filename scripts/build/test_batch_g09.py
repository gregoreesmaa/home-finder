"""Hermetic unit tests for the Group 9 noise-proxy builder (issue #104).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g09.py -q
"""

import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g09_noise as N


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return N.Grid([24.74, 59.43, 24.74 + n * step / 1000 / N.LON_KM,
                   59.43 + n * step / 1000 / N.LAT_KM], step)


def test_hav_km_lon_scale():
    # 1 degree of longitude at Harjumaa latitude ~57.29 km; latitude ~110.57.
    assert abs(N.hav_km(0.0, 0.0, 1.0, 0.0) - 57.29) < 1e-9
    assert abs(N.hav_km(0.0, 0.0, 0.0, 1.0) - 110.57) < 1e-9


def test_quiet_from_half():
    assert N.quiet_from_half(0.0, 300.0) == 0.0
    assert N.quiet_from_half(300.0, 300.0) == 50.0
    assert N.quiet_from_half(float("inf"), 300.0) == 100.0
    assert N.quiet_from_half(1e9, 300.0) > 99.9


def test_kernel_and_grid_roundtrip():
    assert N.kernel(0.0, 0.3) == 1.0
    assert 0.0 < N.kernel(0.3, 0.3) < 1.0
    g = tiny_grid()
    k = g.cell_of(24.745, 59.432)
    assert k is not None
    lon, lat = g.center_of(k)
    assert g.cell_of(lon, lat) == k


def test_dijkstra_exact_on_tiny_grid():
    g = tiny_grid()
    src = g.cell_of(*g.center_of(40))  # centre cell
    d = N.dijkstra_km(g, {src})
    assert d[src] == 0.0
    # Orthogonal neighbour reads exactly one cell step.
    assert abs(d[src + 1] - g.step / 1000.0) < 1e-9
    # Monotone along the row away from the source.
    row = [d[40 + i] for i in range(5)]
    assert row == sorted(row)
    # Far corner within one diagonal slack of straight-line haversine
    # (1e-9 floors float rounding: the 8-conn path may sit a hair below).
    lon0, lat0 = g.center_of(src)
    lon1, lat1 = g.center_of(80)
    assert d[80] >= N.hav_km(lon0, lat0, lon1, lat1) - 1e-9
    assert d[80] <= N.hav_km(lon0, lat0, lon1, lat1) + g.step / 1000 * 1.5


def test_stamp_density_unit():
    g = tiny_grid()
    lon, lat = g.center_of(40)
    acc = N.stamp_density(g, [(lon, lat, 1.0)], 0.3)
    assert 0.99 < acc[40] <= 1.0
    # Kernel support is bounded: narrow sigma leaves the far cell at 0,
    # wide sigma reaches it with exactly the kernel value.
    acc_narrow = N.stamp_density(g, [(lon, lat, 1.0)], 0.05)
    assert acc_narrow[0] == 0.0
    lon0, lat0 = g.center_of(0)
    assert abs(acc[0] - N.kernel(N.hav_km(lon, lat, lon0, lat0), 0.3)) < 1e-9


def test_scores_endpoint_behaviour():
    n = 81
    s0 = [0.0] * n
    inf = [float("inf")] * n
    # Nothing mapped -> fully quiet (absence in-bbox IS the evidence).
    assert all(v == 100 for v in N.score_trafficnoise(s0, inf, N.G09_CAL["trafficnoise"]))
    assert all(v == 100 for v in N.score_braking(s0, N.G09_CAL["braking"]))
    assert all(v == 100 for v in N.score_distance(inf, 300.0))
    # On the source -> known-loud 0 (never 255/unknown).
    s_big = [1e9] * n
    d0 = [0.0] * n
    assert all(v == 0 for v in N.score_trafficnoise(s_big, d0, N.G09_CAL["trafficnoise"]))
    assert all(v == 0 for v in N.score_distance(d0, 300.0))
    assert all(v == 0 for v in N.score_braking(s_big, N.G09_CAL["braking"]))
    # Half distance reads 50.
    d_half = [0.3] * n
    assert all(v == 50 for v in N.score_distance(d_half, 300.0))
    # Nature ramp: +10 inside, +0 at range, capped at 100.
    q = N.score_quietnature(s0, inf, d0, N.G09_CAL["quietnature"])
    assert all(v == 100 for v in q)  # 100 base + bonus would cap
    q2 = N.score_quietnature([400.0] * n, inf, [0.6] * n, N.G09_CAL["quietnature"])
    assert all(v == 50 for v in q2)  # base 50, bonus 0 at exactly 600 m


def _snap_dir(tmp_path):
    osm = tmp_path / "osm"
    osm.mkdir()
    geo = [
        {"type": "Feature", "properties": {"amenity": "bar"},
         "geometry": {"type": "Point", "coordinates": [24.75, 59.435]}},
        {"type": "Feature", "properties": {"amenity": "cinema"},
         "geometry": {"type": "Point", "coordinates": [24.76, 59.436]}},
        {"type": "Feature", "properties": {"landuse": "industrial"},
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.78, 59.44], [24.79, 59.44], [24.79, 59.45], [24.78, 59.45],
             [24.78, 59.44]]]}},
        {"type": "Feature", "properties": {"railway": "rail"},
         "geometry": {"type": "LineString", "coordinates": [
             [24.70, 59.43], [24.72, 59.43]]}},  # ~1.1 km: densified
    ]
    (osm / "harju-amenities.geojson").write_text(
        "\n".join(json.dumps(f) for f in geo), encoding="utf-8")
    (osm / "derived-nightlife.json").write_text(json.dumps([
        {"lon": 24.75, "lat": 59.435, "tags": {"amenity": "bar"}},
        {"lon": 24.76, "lat": 59.436, "tags": {"amenity": "cinema"}},
    ]), encoding="utf-8")
    (osm / "derived-parks.json").write_text(
        json.dumps([{"lon": 24.755, "lat": 59.437}]), encoding="utf-8")
    (osm / "derived-transit.json").write_text(
        json.dumps([{"lon": 24.751, "lat": 59.434}]), encoding="utf-8")
    (osm / "park-areas.json").write_text(json.dumps([{
        "b": [24.754, 59.436, 24.756, 59.438], "a": 2.0,
        "r": [[[24.754, 59.436], [24.756, 59.436], [24.756, 59.438],
               [24.754, 59.438], [24.754, 59.436]]]}]), encoding="utf-8")
    return str(tmp_path)


def test_readers_on_fixtures(tmp_path):
    snap = _snap_dir(tmp_path)
    # Cinema excluded from the nuisance kind (seated culture, not nuisance).
    pts, stats = N.read_nuisance_points(snap)
    assert stats["nightlife"] == 1
    assert len(pts) > 1  # bar + industrial ring points
    rail, stats = N.read_rail_points(snap)
    assert stats["kept"] == 1
    assert len(rail) > 2  # 1.1 km segment densified to ~40 m steps
    cross, _ = N.read_crossing_points(snap)
    assert cross == []


def test_nature_cells_on_fixtures(tmp_path):
    snap = _snap_dir(tmp_path)
    g = N.Grid([24.74, 59.43, 24.80, 59.45], 75.0)
    cells = N.read_nature_cells(g, snap)
    assert len(cells) > 0
    # The parks point cell is covered.
    assert g.cell_of(24.755, 59.437) in cells


def test_wire_doc_shape():
    g = tiny_grid()
    vals = bytes([50] * (g.cols * g.rows))
    doc = N.encode_wire(g, vals, "nuisance")
    assert doc["cols"] == g.cols and doc["rows"] == g.rows
    assert doc["bbox"] == {"minlon": g.bbox[0], "minlat": g.bbox[1],
                           "maxlon": g.bbox[2], "maxlat": g.bbox[3]}
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    assert doc["half"] == 300.0 and doc["sigma"] == 0.3
    import base64
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse GROUP09_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group09.ts"), encoding="utf-8").read()
    m = re.search(r"GROUP09_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "GROUP09_CAL block not found in layers_group09.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = N.G09_CAL
    assert flat["trafficnoise"]["sigma"] == py["trafficnoise"]["sigma"]
    assert flat["trafficnoise"]["roadHalf"] == py["trafficnoise"]["road_half"]
    assert flat["trafficnoise"]["railSigma"] == py["trafficnoise"]["rail_sigma"]
    assert flat["quietnature"]["natureBonus"] == py["quietnature"]["nature_bonus"]
    assert flat["quietnature"]["natureRangeM"] == py["quietnature"]["nature_range_m"]
    assert flat["nuisance"]["halfM"] == py["nuisance"]["half_m"]
    assert flat["nuisance"]["sigma"] == py["nuisance"]["sigma"]
    assert flat["lowfreq"]["halfM"] == py["lowfreq"]["half_m"]
    assert flat["lowfreq"]["sigma"] == py["lowfreq"]["sigma"]
    assert flat["braking"]["sigma"] == py["braking"]["sigma"]
    assert flat["braking"]["half"] == py["braking"]["half"]
