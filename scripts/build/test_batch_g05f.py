"""Group 5 plans-F builder tests (issue #166): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group05f.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g05f_plans as G


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


def test_keep_upcycle_stock_not_junk():
    assert G.keep_upcycle({"abandoned": "yes", "building": "yes"})
    assert G.keep_upcycle({"abandoned": "yes", "building": "industrial"})
    assert G.keep_upcycle({"disused": "yes", "building": "yes"})
    assert G.keep_upcycle({"abandoned:building": "yes"})
    assert G.keep_upcycle({"abandoned:building": "garage"})
    assert G.keep_upcycle({"abandoned:building": "school"})
    # A forest bunker is not rezoning stock — out even with flags.
    assert not G.keep_upcycle({"building": "bunker", "abandoned": "yes"})
    assert not G.keep_upcycle({"abandoned:building": "bunker"})
    assert not G.keep_upcycle({"abandoned:building": "roof"})
    assert not G.keep_upcycle({"abandoned:building": "level_crossing"})
    # Stale flags: bare lifecycle keys without a building key stay out
    # (the ACTIVE ferry terminal carries disused=yes).
    assert not G.keep_upcycle({"disused": "yes"})
    assert not G.keep_upcycle({"abandoned": "yes"})
    # Infrastructure, not buildings; quarries/landfills score elsewhere.
    assert not G.keep_upcycle({"abandoned": "tunnel"})
    assert not G.keep_upcycle({"abandoned:landuse": "quarry"})
    assert not G.keep_upcycle({"landuse": "industrial"})  # industprox's own
    assert not G.keep_upcycle({"landuse": "brownfield"})  # brownsoil's own
    assert not G.keep_upcycle({})  # untagged member drops out
    assert not G.keep_upcycle(None)


def test_read_upcycle_points_centroids(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "aband.geojson"), [
        pt(24.75, 59.44, {"abandoned": "yes", "building": "yes"}),
        line([[24.751, 59.441], [24.753, 59.441]],
             {"disused": "yes", "building": "warehouse"}),
        poly(ring, {"abandoned:building": "school"}),
        pt(24.76, 59.45, {"building": "bunker", "abandoned": "yes"}),
        pt(24.76, 59.45, {"disused": "yes"}),  # stale flag, no building
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_upcycle_points(p)
    assert stats == {"stock": 3, "dropped": 3}
    # ONE point per kept feature (count kernels must not multi-count).
    assert len(pts) == 3
    assert pts[0] == (24.75, 59.44)
    assert pts[1] == pytest.approx((24.752, 59.441))
    assert pts[2][0] == pytest.approx(24.751, abs=1e-3)


def test_feature_point_shapes():
    assert G.feature_point({"type": "Point",
                            "coordinates": [24.7, 59.4]}) == (24.7, 59.4)
    assert G.feature_point({"type": "LineString",
                            "coordinates": [[24.7, 59.4],
                                            [24.702, 59.4]]}) == (24.701, 59.4)
    ring = [[24.7, 59.4], [24.702, 59.4], [24.702, 59.402],
            [24.7, 59.402], [24.7, 59.4]]
    lon, _ = G.feature_point({"type": "Polygon", "coordinates": [ring]})
    assert lon == pytest.approx(24.7008, abs=1e-3)
    assert G.feature_point({"type": "MultiPolygon",
                            "coordinates": [[ring]]})[0] == pytest.approx(
        24.7008, abs=1e-3)
    assert G.feature_point({}) is None
    assert G.feature_point({"type": "Point", "coordinates": []}) is None


def test_area_score_saturates_like_buildout():
    assert G.area_score(0, 2) == 0
    assert G.area_score(2, 2) == 50
    assert G.area_score(6, 2) == 75


def test_upcycle_kernel_scores_near_high_far_unknown():
    # 4-sigma cutoff is 1.2 km: the desert probe sits 1.5 km out.
    g = tiny_grid(30)
    lon0, lat0 = 24.74, 59.44
    acc = G.count_kernel_field(g, [(lon0, lat0)], G.G05F_CAL["upcycle"]["sigma"])
    vals = G.score_area_cells(g, acc, G.G05F_CAL["upcycle"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] == 33  # one dot reads 33 (half 2: TWO nearby read 50)
    acc2 = G.count_kernel_field(g, [(lon0, lat0)] * 2,
                                G.G05F_CAL["upcycle"]["sigma"])
    vals2 = G.score_area_cells(g, acc2, G.G05F_CAL["upcycle"]["half"])
    assert vals2[k] == 50  # a pair reads opportunity-green
    desert = g.cell_of(lon0 + 1500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 255  # desert stays honestly unknown


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("upcycle")
    assert half == 2.0 and sigma == 0.3
    doc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "upcycle")
    assert doc["half"] == 2.0 and doc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G05F_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group05f.ts"), encoding="utf-8").read()
    m = re.search(r"G05F_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G05F_CAL block not found in layers_group05f.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G05F_CAL
    assert flat["upcycle"]["half"] == py["upcycle"]["half"]
    assert flat["upcycle"]["sigma"] == py["upcycle"]["sigma"]
