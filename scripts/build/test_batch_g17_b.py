"""Group 17 municipal-services-B builder tests (issue #178): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group17b.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g17_b as G


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


def poly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def mpoly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "MultiPolygon",
                         "coordinates": [[ring]]}}


def test_keep_lawn_is_mown_grass_only():
    assert G.keep_lawn({"landuse": "grass"})
    assert G.keep_lawn({"landuse": "grass;meadow"})
    # A meadow is unmown by design, not a mowing-duty lawn.
    assert not G.keep_lawn({"landuse": "meadow"})
    assert not G.keep_lawn({"landuse": "residential"})
    # Footways stay pedinfra's, never re-scored here.
    assert not G.keep_lawn({"highway": "footway"})
    assert not G.keep_lawn({"footway": "sidewalk"})
    assert not G.keep_lawn({"leisure": "garden"})
    assert not G.keep_lawn({})
    assert not G.keep_lawn(None)


def test_read_lawn_points_centroid_per_feature(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "lawn.geojson"), [
        pt(24.75, 59.44, {"landuse": "grass"}),
        poly(ring, {"landuse": "grass"}),
        mpoly(ring, {"landuse": "grass"}),
        pt(24.76, 59.45, {"landuse": "meadow"}),  # unmown, out
        pt(24.76, 59.45, {"highway": "footway"}),  # pedinfra's, out
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_lawn_points(p)
    assert stats["lawns"] == 3
    assert stats["dropped"] == 3
    # One upkeep unit per feature: point + polygon centroid + multipolygon.
    assert len(pts) == 3
    assert (24.75, 59.44) in pts
    # Polygon bbox centre, not stride-sampled rings.
    assert any(abs(lon - 24.751) < 1e-9 and abs(lat - 59.441) < 1e-9
               for lon, lat in pts)


def test_bbox_center_handles_nesting():
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    assert G._bbox_center([ring]) == pytest.approx((24.751, 59.441))
    assert G._bbox_center([]) is None


def test_area_score_saturates_with_density_half():
    assert G.area_score(0, 20) == 0
    assert G.area_score(20, 20) == 50
    assert G.area_score(60, 20) == 75


def test_kernel_field_scores_near_high_far_unknown():
    # 4-sigma cutoff is 1.2 km: the desert probe sits 1.5 km out.
    # Density half (20): a lone lawn reads low, a dense pocket green.
    g = tiny_grid(30)
    lon0, lat0 = 24.74, 59.44
    acc = G.count_kernel_field(g, [(lon0, lat0)],
                               G.G17B_CAL["lawncare"]["sigma"])
    vals = G.score_area_cells(g, acc, G.G17B_CAL["lawncare"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] < 50  # one lawn does not paint the street green
    dense = G.count_kernel_field(g, [(lon0, lat0)] * 25,
                                 G.G17B_CAL["lawncare"]["sigma"])
    dvals = G.score_area_cells(g, dense, G.G17B_CAL["lawncare"]["half"])
    assert dvals[k] >= 50  # a lawn-lined pocket reads upkeep-visible
    desert = g.cell_of(lon0 + 1500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 255  # desert stays honestly unknown


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("lawncare")
    assert half == 20.0 and sigma == 0.3
    doc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "lawncare")
    assert doc["half"] == 20.0 and doc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G17B_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group17b.ts"), encoding="utf-8").read()
    m = re.search(r"G17B_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G17B_CAL block not found in layers_group17b.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G17B_CAL
    assert flat["lawncare"]["half"] == py["lawncare"]["half"]
    assert flat["lawncare"]["sigma"] == py["lawncare"]["sigma"]
