"""Hermetic unit tests for the GENV environmental-exposure builder (issue #124).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_genv.py -q
"""

import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_genv_exposure as E


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return E.Grid([24.74, 59.43, 24.74 + n * step / 1000 / E.LON_KM,
                   59.43 + n * step / 1000 / E.LAT_KM], step)


def test_hav_km_lon_scale():
    assert abs(E.hav_km(0.0, 0.0, 1.0, 0.0) - 57.29) < 1e-9
    assert abs(E.hav_km(0.0, 0.0, 0.0, 1.0) - 110.57) < 1e-9


def test_quiet_from_half():
    assert E.quiet_from_half(0.0, 300.0) == 0.0
    assert E.quiet_from_half(300.0, 300.0) == 50.0
    assert E.quiet_from_half(float("inf"), 300.0) == 100.0


def test_dijkstra_exact_on_tiny_grid():
    g = tiny_grid()
    src = g.cell_of(*g.center_of(40))
    d = E.dijkstra_km(g, {src})
    assert d[src] == 0.0
    assert abs(d[src + 1] - g.step / 1000.0) < 1e-9
    row = [d[40 + i] for i in range(5)]
    assert row == sorted(row)


def test_scores_endpoint_behaviour():
    n = 81
    s0 = [0.0] * n
    inf = [float("inf")] * n
    cal = E.GENV_CAL
    # Nothing mapped -> fully calm/dark/cool (absence in-bbox IS evidence).
    assert all(v == 100 for v in E.score_distance(inf, 300.0))
    assert all(v == 100 for v in E.score_density(s0, 120.0))
    assert all(v == 100 for v in E.score_flightcorr(inf, inf, cal["flightcorr"]))
    q = E.score_coolisland(s0, inf, cal["coolisland"])
    assert all(v == 100 for v in q)  # 100 base + green bonus caps
    # On the source -> known-exposed 0 (never 255/unknown).
    s_big = [1e9] * n
    d0 = [0.0] * n
    assert all(v == 0 for v in E.score_distance(d0, 300.0))
    assert all(v == 0 for v in E.score_density(s_big, 120.0))
    assert all(v == 0 for v in E.score_flightcorr(d0, inf, cal["flightcorr"]))
    assert all(v == 0 for v in E.score_flightcorr(inf, d0, cal["flightcorr"]))
    # Half distance reads 50.
    assert all(v == 50 for v in E.score_distance([0.3] * n, 300.0))
    assert all(v == 50 for v in E.score_distance([0.5] * n, 500.0))
    assert all(v == 50 for v in E.score_flightcorr([1.5] * n, inf, cal["flightcorr"]))
    assert all(v == 50 for v in E.score_flightcorr(inf, [0.4] * n, cal["flightcorr"]))
    # Worst tier wins: major-calm + minor-exposed -> exposed.
    assert all(v == 0 for v in E.score_flightcorr([10.0] * n, d0, cal["flightcorr"]))
    # Green ramp: +8 inside, +0 at range, capped at 100.
    q2 = E.score_coolisland([120.0] * n, [0.5] * n, cal["coolisland"])
    assert all(v == 50 for v in q2)  # base 50, bonus 0 at exactly 500 m


def test_axis_extension_geometry():
    # 1 km E-W runway at the equator-ish scale: extensions march both ways.
    ext = E.runway_axis_extension([(0.0, 0.0), (0.01, 0.0)], 0.6, 200.0)
    assert len(ext) == 6  # 3 steps x 2 ends
    lons = sorted(p[0] for p in ext)
    assert lons[0] < 0.0 < lons[-1]
    assert abs(ext[0][1]) < 1e-12  # on-axis
    # Degenerate (zero-length) runway -> no extension, no crash.
    assert E.runway_axis_extension([(1.0, 1.0), (1.0, 1.0)], 8.0, 200.0) == []


def test_dedupe_cells_merges_twins():
    # Second point ~1 m away (same 20 m cell, not straddling a boundary).
    pts = [(24.75, 59.435), (24.75001, 59.43501), (24.76, 59.44)]
    out = E.dedupe_cells(pts)
    assert len(out) == 2


def _snap_dir(tmp_path):
    osm = tmp_path / "osm"
    osm.mkdir()
    (osm / "derived-buildings.json").write_text(json.dumps([
        {"lon": 24.75, "lat": 59.435}, {"lon": 24.751, "lat": 59.436},
    ]), encoding="utf-8")
    (osm / "derived-lit.json").write_text(json.dumps([
        {"lon": 24.75, "lat": 59.435},
    ]), encoding="utf-8")
    (osm / "derived-streetlamps.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"highway": "street_lamp"},
             "geometry": {"type": "Point", "coordinates": [24.75001, 59.43501]}},
        ]}), encoding="utf-8")
    (osm / "derived-heavyroads.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"highway": "primary"},
             "geometry": {"type": "LineString", "coordinates": [
                 [24.70, 59.43], [24.72, 59.43]]}},
        ]}), encoding="utf-8")
    (osm / "derived-aeroway.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"aeroway": "runway",
                                              "surface": "asphalt"},
             "geometry": {"type": "LineString", "coordinates": [
                 [24.80, 59.413], [24.83, 59.413]]}},
            {"type": "Feature", "properties": {"aeroway": "runway",
                                              "surface": "grass"},
             "geometry": {"type": "LineString", "coordinates": [
                 [24.60, 59.20], [24.61, 59.20]]}},
            {"type": "Feature", "properties": {"aeroway": "aerodrome",
                                              "name": "Testi"},
             "geometry": {"type": "Point", "coordinates": [24.60, 59.21]}},
        ]}), encoding="utf-8")
    (osm / "harju-amenities.geojson").write_text(
        "\n".join([
            json.dumps({"type": "Feature", "properties": {"railway": "rail"},
                        "geometry": {"type": "LineString", "coordinates": [
                            [24.70, 59.44], [24.72, 59.44]]}}),
            json.dumps({"type": "Feature", "properties": {"landuse": "industrial"},
                        "geometry": {"type": "Polygon", "coordinates": [[
                            [24.78, 59.44], [24.79, 59.44], [24.79, 59.45],
                            [24.78, 59.45], [24.78, 59.44]]]}}),
        ]), encoding="utf-8")
    (osm / "derived-parks.json").write_text(
        json.dumps([{"lon": 24.755, "lat": 59.437}]), encoding="utf-8")
    (osm / "park-areas.json").write_text(json.dumps([{
        "b": [24.754, 59.436, 24.756, 59.438], "a": 2.0,
        "r": [[[24.754, 59.436], [24.756, 59.436], [24.756, 59.438],
               [24.754, 59.438], [24.754, 59.436]]]}]), encoding="utf-8")
    return str(tmp_path)


def test_readers_on_fixtures(tmp_path):
    snap = _snap_dir(tmp_path)
    bld = E.read_derived_points(snap, "buildings")
    assert len(bld) == 2
    # Lit node + lamp in the same 20 m cell dedupe to ONE (twin guard).
    lit, stats = E.read_lit_points(snap)
    assert stats["raw"] == 2 and stats["cells"] == 1
    heavy, stats = E.read_heavy_points(snap)
    assert stats["ways"] == 1
    assert len(heavy) > 2  # ~1.1 km carriageway densified to ~50 m steps
    rail, stats = E.read_rail_points(snap)
    assert stats["kept"] == 1
    ind, stats = E.read_industrial_points(snap)
    assert stats["kept"] == 1 and len(ind) > 0
    # Runway tiers: asphalt -> major (+axis extensions), grass -> minor,
    # aerodrome point -> minor.
    major, minor, stats = E.read_runway_sources(snap, E.GENV_CAL["flightcorr"])
    assert stats == {"major_seg": 1, "minor_seg": 1, "airfields": 1}
    assert len(major) > len(minor)  # extensions sampled +-8 km


def test_nature_cells_on_fixtures(tmp_path):
    snap = _snap_dir(tmp_path)
    g = E.Grid([24.74, 59.43, 24.80, 59.45], 75.0)
    cells = E.read_nature_cells(g, snap)
    assert len(cells) > 0
    assert g.cell_of(24.755, 59.437) in cells


def test_wire_doc_shape():
    g = tiny_grid()
    vals = bytes([50] * (g.cols * g.rows))
    doc = E.encode_wire(g, vals, "vibration")
    assert doc["cols"] == g.cols and doc["rows"] == g.rows
    assert doc["bbox"] == {"minlon": g.bbox[0], "minlat": g.bbox[1],
                           "maxlon": g.bbox[2], "maxlat": g.bbox[3]}
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    assert doc["half"] == 300.0 and doc["sigma"] == 0.3
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}
    # flightcorr carries the MAJOR half on the wire (worst-tier contract).
    assert E.contract_of("flightcorr") == (1500.0, 0.3)
    assert E.contract_of("darksky") == (120.0, 0.3)


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse GENV_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_genv.ts"), encoding="utf-8").read()
    m = re.search(r"GENV_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "GENV_CAL block not found in layers_genv.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = E.GENV_CAL
    assert flat["vibration"]["halfM"] == py["vibration"]["half_m"]
    assert flat["vibration"]["sigma"] == py["vibration"]["sigma"]
    assert flat["lowspec"]["halfM"] == py["lowspec"]["half_m"]
    assert flat["lowspec"]["sigma"] == py["lowspec"]["sigma"]
    assert flat["flightcorr"]["majorHalfM"] == py["flightcorr"]["major_half_m"]
    assert flat["flightcorr"]["minorHalfM"] == py["flightcorr"]["minor_half_m"]
    assert flat["flightcorr"]["sigma"] == py["flightcorr"]["sigma"]
    assert flat["darksky"]["half"] == py["darksky"]["half"]
    assert flat["darksky"]["sigma"] == py["darksky"]["sigma"]
    assert flat["coolisland"]["half"] == py["coolisland"]["half"]
    assert flat["coolisland"]["greenBonus"] == py["coolisland"]["green_bonus"]
    assert flat["coolisland"]["greenRangeM"] == py["coolisland"]["green_range_m"]
