"""Group 17 municipal-services-A builder tests (issue #177): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group17a.ts.
"""

import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g17_a as G


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


def test_keep_compost_stations_not_bottle_banks():
    assert G.keep_compost({"amenity": "recycling", "recycling_type": "centre",
                           "recycling:green_waste": "yes"})
    assert G.keep_compost({"amenity": "recycling", "recycling_type": "centre",
                           "recycling:garden_waste": "yes"})
    assert G.keep_compost({"amenity": "recycling",
                           "recycling:food_waste": "yes"})
    assert G.keep_compost({"amenity": "recycling",
                           "recycling:organic": "yes"})
    # Plain paper/glass/plastic containers stay p54's, not composting.
    assert not G.keep_compost({"amenity": "recycling",
                               "recycling:paper": "yes"})
    assert not G.keep_compost({"amenity": "recycling"})
    assert not G.keep_compost({"amenity": "recycling",
                               "recycling_type": "centre"})
    assert not G.keep_compost({"amenity": "waste_disposal",
                               "recycling:green_waste": "yes"})
    assert not G.keep_compost({})
    assert not G.keep_compost(None)


def test_keep_grit_is_grit_bin_only():
    assert G.keep_grit({"amenity": "grit_bin"})
    # Road class is p446's, never re-scored here.
    assert not G.keep_grit({"highway": "primary"})
    assert not G.keep_grit({"amenity": "recycling",
                            "recycling:green_waste": "yes"})
    assert not G.keep_grit({})
    assert not G.keep_grit(None)


def test_keep_leaf_drops_litter_bins():
    assert G.keep_leaf({"amenity": "recycling",
                        "recycling:green_waste": "yes"})
    assert G.keep_leaf({"amenity": "recycling",
                        "recycling:garden_waste": "yes"})
    assert G.keep_leaf({"amenity": "waste_disposal",
                        "recycling:green_waste": "yes"})
    # A litter bin is not yard-waste collection.
    assert not G.keep_leaf({"amenity": "waste_disposal"})
    assert not G.keep_leaf({"amenity": "recycling",
                            "recycling:paper": "yes"})
    assert not G.keep_leaf({})
    assert not G.keep_leaf(None)


def test_read_compost_points(tmp_path):
    p = write_geojson(str(tmp_path / "waste.geojson"), [
        pt(24.75, 59.44, {"amenity": "recycling",
                           "recycling_type": "centre",
                           "recycling:green_waste": "yes"}),
        pt(24.751, 59.441, {"amenity": "recycling",
                             "recycling:food_waste": "yes"}),
        pt(24.76, 59.45, {"amenity": "recycling",
                           "recycling:paper": "yes"}),  # p54's, not compost
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_compost_points(p)
    assert stats["stations"] == 2
    assert stats["dropped"] == 2
    assert len(pts) == 2


def test_read_grit_points(tmp_path):
    p = write_geojson(str(tmp_path / "waste.geojson"), [
        pt(24.75, 59.44, {"amenity": "grit_bin"}),
        pt(24.76, 59.45, {"highway": "primary"}),  # p446's, not gritbin
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_grit_points(p)
    assert stats["bins"] == 1
    assert stats["dropped"] == 2
    assert pts == [(24.75, 59.44)]


def test_read_leaf_points(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "waste.geojson"), [
        pt(24.75, 59.44, {"amenity": "recycling",
                           "recycling:green_waste": "yes"}),
        poly(ring, {"amenity": "recycling",
                     "recycling:green_waste": "yes"}),
        pt(24.76, 59.45, {"amenity": "waste_disposal"}),  # litter, out
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_leaf_points(p)
    assert stats["drops"] == 2
    assert stats["dropped"] == 2
    assert len(pts) >= 2


def test_area_score_saturates_like_viewshed():
    assert G.area_score(0, 1) == 0
    assert G.area_score(1, 1) == 50
    assert G.area_score(3, 1) == 75


def test_kernel_field_scores_near_high_far_unknown():
    # 4-sigma cutoff is 1.2 km: the desert probe sits 1.5 km out.
    g = tiny_grid(30)
    lon0, lat0 = 24.74, 59.44
    for layer in G.LAYER_IDS:
        acc = G.count_kernel_field(g, [(lon0, lat0)],
                                   G.G17A_CAL[layer]["sigma"])
        vals = G.score_area_cells(g, acc, G.G17A_CAL[layer]["half"])
        k = g.cell_of(lon0, lat0)
        assert vals[k] >= 50  # on the station reads serviced-green
        desert = g.cell_of(lon0 + 1500.0 / 1000 / G.LON_KM, lat0)
        assert vals[desert] == 255  # desert stays honestly unknown


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    for layer in G.LAYER_IDS:
        half, sigma = G.contract_of(layer)
        assert half == 1.0 and sigma == 0.3
        doc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), layer)
        assert doc["half"] == 1.0 and doc["sigma"] == 0.3
        assert doc["per"] == 0 and doc["cap"] == 0
        assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
        raw = base64.b64decode(doc["data"])
        assert len(raw) == g.cols * g.rows
        assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G17A_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group17a.ts"), encoding="utf-8").read()
    m = re.search(r"G17A_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G17A_CAL block not found in layers_group17a.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G17A_CAL
    for layer in ("compost", "gritbin", "leafdrop"):
        assert flat[layer]["half"] == py[layer]["half"]
        assert flat[layer]["sigma"] == py[layer]["sigma"]
