"""Group 18 rest-A builder tests (issue #172): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group18resta.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g18_resta as G


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


def test_keep_tall_is_levels4_plus():
    assert G.keep_tall({"building:levels": "4"})
    assert G.keep_tall({"building:levels": "9"})
    assert G.keep_tall({"building:levels": "16"})
    # Low-rise reads as low-rise: absence is weak evidence, never tall.
    assert not G.keep_tall({"building:levels": "3"})
    assert not G.keep_tall({"building:levels": "1"})
    assert not G.keep_tall({"building": "apartments"})  # untagged: low-rise
    assert not G.keep_tall({"building:levels": "tall"})
    assert not G.keep_tall({})
    assert not G.keep_tall(None)


def test_keep_glass_is_glass_or_mirror():
    assert G.keep_glass({"building:material": "glass"})
    assert G.keep_glass({"building:material": "mirror"})
    # Plaster/wood/brick/concrete are not reflective — out by design.
    assert not G.keep_glass({"building:material": "plaster"})
    assert not G.keep_glass({"building:material": "wood"})
    assert not G.keep_glass({"building:material": "brick"})
    assert not G.keep_glass({"building:material": "concrete"})
    assert not G.keep_glass({})  # untagged member drops out
    assert not G.keep_glass(None)


def test_read_tall_fills_polygons(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "tall.geojson"), [
        pt(24.75, 59.44, {"building:levels": "5"}),
        poly(ring, {"building:levels": "9"}),
        pt(24.76, 59.45, {"building:levels": "2"}),  # low-rise, not a mass
        pt(24.76, 59.45, {"building": "house"}),  # untagged: low-rise
    ])
    pts, polys, stats = G.read_tall_points(p)
    assert stats["masses"] == 2
    assert stats["dropped"] == 2
    assert len(polys) == 1
    assert len(pts) >= 2


def test_fill_tall_cells_covers_interior(tmp_path):
    g = tiny_grid(12)
    ring = [[24.741, 59.4405], [24.743, 59.4405], [24.743, 59.4415],
            [24.741, 59.4415], [24.741, 59.4405]]
    cells = G.fill_tall_cells(g, [ring])
    assert len(cells) > 0
    # A cell far outside the ring is not filled.
    far = g.cell_of(24.74, 59.44)
    assert far not in cells


def test_read_glass_points_rings_not_filled(tmp_path):
    # Glare is an outside-view fact: polygons feed rings only, and the
    # reader returns NO fill hint (unlike read_tall_points' 3-tuple).
    ring = [[24.75, 59.44], [24.751, 59.44], [24.751, 59.441],
            [24.75, 59.441], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "glass.geojson"), [
        pt(24.75, 59.44, {"building:material": "glass"}),
        poly(ring, {"building:material": "mirror"}),
        pt(24.76, 59.45, {"building:material": "plaster"}),
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_glass_points(p)
    assert stats["facades"] == 2
    assert stats["dropped"] == 2
    assert len(pts) >= 2


def test_quiet_from_half():
    assert G.quiet_from_half(0, 150) == 0
    assert G.quiet_from_half(150, 150) == 50
    assert G.quiet_from_half(200, 200) == 50
    assert G.quiet_from_half(float("inf"), 150) == 100
    assert G.quiet_from_half(1e9, 150) > 99.9


def test_field_end_to_end_on_tiny_grid(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "tall.geojson"), [
        poly([[lon0, lat0 + 150 / 110570.0], [lon0 + 0.001, lat0 + 150 / 110570.0],
              [lon0 + 0.001, lat0 + 160 / 110570.0], [lon0, lat0 + 160 / 110570.0],
              [lon0, lat0 + 150 / 110570.0]], {"building:levels": "5"}),
    ])
    raw, polys, _ = G.read_tall_points(p)
    cells = G.cells_of_points(g, raw) | G.fill_tall_cells(g, polys)
    dist = G.dijkstra_km(g, cells)
    vals = G.score_distance(dist, G.G18A_CAL["dayopen"]["half_m"])
    assert min(vals) <= 55  # ~150 m from a mass reads half-calm
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
    half, sigma = G.contract_of("dayopen")
    assert half == 150.0 and sigma == 0.3
    half_g, sigma_g = G.contract_of("glassglare")
    assert half_g == 200.0 and sigma_g == 0.3
    doc = G.encode_wire(g, bytearray([90]) * (g.cols * g.rows))
    assert doc["half"] == 150.0 and doc["sigma"] == 0.3
    gdoc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "glassglare")
    assert gdoc["half"] == 200.0 and gdoc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {90}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G18A_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group18resta.ts"), encoding="utf-8").read()
    m = re.search(r"G18A_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G18A_CAL block not found in layers_group18resta.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G18A_CAL
    assert flat["dayopen"]["halfM"] == py["dayopen"]["half_m"]
    assert flat["dayopen"]["sigma"] == py["dayopen"]["sigma"]
    assert flat["glassglare"]["halfM"] == py["glassglare"]["half_m"]
    assert flat["glassglare"]["sigma"] == py["glassglare"]["sigma"]
