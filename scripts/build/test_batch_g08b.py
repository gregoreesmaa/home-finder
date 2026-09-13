"""Group 8 flood/climate-B builder tests (issue #168): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group08b.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g08b_flood as G


def tiny_grid(n=9, step=75.0):
    # ~0.675 km square near Tallinn.
    return G.Grid([24.74, 59.44, 24.74 + n * step / 1000 / G.LON_KM,
                   59.44 + n * step / 1000 / G.LAT_KM], step)


def write_geojson(path, features):
    doc = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


def pt(lon, lat, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Point", "coordinates": [lon, lat]}}


def line(coords, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords}}


def mpoly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "MultiPolygon",
                         "coordinates": [[ring]]}}


def test_first_levels_parses_first_semi_value():
    assert G.first_levels("5") == 5.0
    assert G.first_levels("9;9") == 9.0
    assert G.first_levels(" 4 ") == 4.0
    assert G.first_levels(None) is None
    assert G.first_levels("abc") is None
    assert G.first_levels("") is None


def test_keep_tall_threshold():
    assert G.keep_tall({"building:levels": "5"})
    assert G.keep_tall({"building:levels": "9"})
    assert G.keep_tall({"building:levels": "5;4"})
    assert not G.keep_tall({"building:levels": "4"})
    assert not G.keep_tall({"building:levels": "1"})
    assert not G.keep_tall({"building": "yes"})  # untagged member drops out
    assert not G.keep_tall({})
    assert not G.keep_tall(None)
    # Metres confound villas with towers: height alone never keeps.
    assert not G.keep_tall({"building:levels": "2", "height": "30"})


def test_keep_sea_is_coastline_only():
    assert G.keep_sea({"natural": "coastline"})
    # Lake spray is not salty; lakes already feed p340 shoredist (#154).
    assert not G.keep_sea({"natural": "water"})
    assert not G.keep_sea({"natural": "water", "water": "lake"})
    assert not G.keep_sea({})
    assert not G.keep_sea(None)


def test_read_tall_points_keeps_rings_and_points(tmp_path):
    ring = [[24.75, 59.44], [24.751, 59.44], [24.751, 59.441],
            [24.75, 59.441], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "levels.geojson"), [
        pt(24.75, 59.44, {"building:levels": "9"}),
        line(ring, {"building:levels": "5"}),  # footprint ring, not a twin
        mpoly(ring, {"building:levels": "5"}),
        pt(24.76, 59.45, {"building:levels": "2"}),  # too low
        pt(24.76, 59.45, {"building": "yes"}),  # untagged member
    ])
    pts, stats = G.read_tall_points(p)
    assert stats["towers"] == 3
    assert stats["dropped"] == 2
    assert len(pts) >= 3


def test_read_sea_points_keeps_island_rings(tmp_path):
    # Closed coastline rings are REAL island shores, never twins.
    ring = [[24.75, 59.44], [24.751, 59.44], [24.751, 59.441],
            [24.75, 59.441], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "coast.geojson"), [
        line([[24.74, 59.44], [24.75, 59.44]], {"natural": "coastline"}),
        line(ring, {"natural": "coastline"}),  # island ring: kept
        mpoly(ring, {"natural": "coastline", "place": "islet"}),
        line([[24.74, 59.44], [24.75, 59.44]], {"natural": "water"}),
    ])
    pts, stats = G.read_sea_points(p)
    assert stats["shore"] == 3
    assert stats["dropped"] == 1
    assert len(pts) >= 3


def test_quiet_from_half():
    assert G.quiet_from_half(0, 200) == 0
    assert G.quiet_from_half(200, 200) == 50
    assert G.quiet_from_half(500, 500) == 50
    assert G.quiet_from_half(float("inf"), 200) == 100
    assert G.quiet_from_half(1e9, 200) > 99.9


def test_field_end_to_end_on_tiny_grid(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "levels.geojson"), [
        pt(lon0, 59.44 + 150 / 110570.0, {"building:levels": "9"}),
    ])
    raw, _ = G.read_tall_points(p)
    dist = G.dijkstra_km(g, G.cells_of_points(g, raw))
    vals = G.score_distance(dist, G.G08B_CAL["windtunnel"]["half_m"])
    k = g.cell_of(lon0, 59.44 + 150 / 110570.0)
    assert vals[k] <= 45  # ~150 m from a tower reads low-calm
    far = g.cell_of(lon0, 59.44)
    assert vals[far] > vals[k]


def test_score_distance_endpoints():
    g = tiny_grid()
    n = g.cols * g.rows
    dist = [0.0] * n
    vals = G.score_distance(dist, 200.0)
    assert set(vals) == {0}
    dist = [float("inf")] * n
    vals = G.score_distance(dist, 200.0)
    assert set(vals) == {100}


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("saltspray")
    assert half == 500.0 and sigma == 0.5
    half_w, sigma_w = G.contract_of("windtunnel")
    assert half_w == 200.0 and sigma_w == 0.2
    doc = G.encode_wire(g, bytearray([90]) * (g.cols * g.rows))
    assert doc["half"] == 500.0 and doc["sigma"] == 0.5
    wdoc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "windtunnel")
    assert wdoc["half"] == 200.0 and wdoc["sigma"] == 0.2
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {90}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G08B_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group08b.ts"), encoding="utf-8").read()
    m = re.search(r"G08B_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G08B_CAL block not found in layers_group08b.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G08B_CAL
    assert flat["windtunnel"]["halfM"] == py["windtunnel"]["half_m"]
    assert flat["windtunnel"]["sigma"] == py["windtunnel"]["sigma"]
    assert flat["saltspray"]["halfM"] == py["saltspray"]["half_m"]
    assert flat["saltspray"]["sigma"] == py["saltspray"]["sigma"]
