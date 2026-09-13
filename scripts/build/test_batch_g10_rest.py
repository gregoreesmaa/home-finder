"""Group 10 utilities-rest builder tests (issue #171): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group10rest.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g10_rest as G


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


def poly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def mpoly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "MultiPolygon",
                         "coordinates": [[ring]]}}


def test_is_tall_needs_five_storeys():
    assert G.is_tall({"building:levels": "5"})
    assert G.is_tall({"building:levels": "9"})
    assert G.is_tall({"building": "apartments", "building:levels": "16"})
    # A family house does not block the dish cone.
    assert not G.is_tall({"building:levels": "4"})
    assert not G.is_tall({"building:levels": "1"})
    # Guessing height would fake precision: level-less stays out.
    assert not G.is_tall({"building": "apartments"})
    assert not G.is_tall({"building:levels": "tower"})
    assert not G.is_tall({})
    assert not G.is_tall(None)


def test_is_forest_needs_canopy():
    assert G.is_forest({"natural": "wood"})
    assert G.is_forest({"landuse": "forest"})
    # A tree row is not a canopy; untagged members drop out.
    assert not G.is_forest({"natural": "tree_row"})
    assert not G.is_forest({"natural": "tree"})
    assert not G.is_forest({"landuse": "meadow"})
    assert not G.is_forest({})
    assert not G.is_forest(None)


def test_keep_sky_unions_tall_and_forest():
    assert G.keep_sky({"building:levels": "9"})
    assert G.keep_sky({"natural": "wood"})
    assert not G.keep_sky({"building:levels": "2"})
    assert not G.keep_sky({"shop": "mall"})
    assert not G.keep_sky({})


def test_read_sky_points_splits_tall_forest(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    forest = [[24.76, 59.45], [24.764, 59.45], [24.764, 59.454],
              [24.76, 59.454], [24.76, 59.45]]
    p = write_geojson(str(tmp_path / "sky.geojson"), [
        pt(24.75, 59.44, {"building": "apartments", "building:levels": "9"}),
        line(ring, {"building": "apartments", "building:levels": "5"}),
        poly(forest, {"natural": "wood"}),
        pt(24.77, 59.46, {"building": "house", "building:levels": "2"}),
        pt(24.77, 59.46, {"natural": "tree_row"}),
        pt(24.77, 59.46, {}),
    ])
    pts, polys, stats = G.read_sky_points(p)
    assert stats["tall"] == 2
    assert stats["forests"] == 1
    assert stats["dropped"] == 3
    assert len(polys) == 1  # only the forest polygon fills
    assert len(pts) >= 3


def test_fill_sky_cells_covers_forest_interior(tmp_path):
    g = tiny_grid(12)
    ring = [[24.741, 59.4405], [24.743, 59.4405], [24.743, 59.4415],
            [24.741, 59.4415], [24.741, 59.4405]]
    cells = G.fill_sky_cells(g, [ring])
    assert len(cells) > 0
    # A cell far outside the ring is not filled.
    far = g.cell_of(24.74, 59.44)
    assert far not in cells


def test_quiet_from_half():
    assert G.quiet_from_half(0, 150) == 0
    assert G.quiet_from_half(150, 150) == 50
    assert G.quiet_from_half(float("inf"), 150) == 100
    assert G.quiet_from_half(1e9, 150) > 99.9


def test_field_end_to_end_on_tiny_grid(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "sky.geojson"), [
        poly([[lon0, lat0 + 75 / 110570.0], [lon0 + 0.001, lat0 + 75 / 110570.0],
              [lon0 + 0.001, lat0 + 85 / 110570.0], [lon0, lat0 + 85 / 110570.0],
              [lon0, lat0 + 75 / 110570.0]], {"natural": "wood"}),
    ])
    raw, polys, _ = G.read_sky_points(p)
    cells = G.cells_of_points(g, raw) | G.fill_sky_cells(g, polys)
    dist = G.dijkstra_km(g, cells)
    vals = G.score_distance(dist, G.G10R_CAL["skyview"]["half_m"])
    assert min(vals) <= 45  # ~75 m from the forest edge reads low-calm
    far = g.cell_of(lon0, lat0)
    assert vals[far] > min(vals)


def test_score_distance_endpoints():
    g = tiny_grid()
    n = g.cols * g.rows
    dist = [0.0] * n
    vals = G.score_distance(dist, 150.0)
    assert set(vals) == {0}
    dist = [float("inf")] * n
    vals = G.score_distance(dist, 150.0)
    assert set(vals) == {100}


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("skyview")
    assert half == 150.0 and sigma == 0.3
    doc = G.encode_wire(g, bytearray([90]) * (g.cols * g.rows))
    assert doc["half"] == 150.0 and doc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {90}


def test_build_layer_needs_sky_extract():
    g = tiny_grid()
    with pytest.raises(SystemExit):
        G.build_layer(g, "skyview")
    with pytest.raises(SystemExit):
        G.build_layer(g, "nosuchlayer", sky_path="/tmp/x")


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G10R_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group10rest.ts"), encoding="utf-8").read()
    m = re.search(r"G10R_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G10R_CAL block not found in layers_group10rest.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G10R_CAL
    assert flat["skyview"]["halfM"] == py["skyview"]["half_m"]
    assert flat["skyview"]["sigma"] == py["skyview"]["sigma"]
