"""Group 5 plans-A builder tests (issue #161): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group05a.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g05a_plans as G


def tiny_grid(n=17, step=75.0):
    # ~1.275 km square near Tallinn.
    return G.wr.Grid([24.74, 59.44, 24.74 + n * step / 1000 / G.LON_KM,
                      59.44 + n * step / 1000 / G.LAT_KM], step)


def write_geojson(path, features):
    # Line-delimited features (what read_site_points consumes — the
    # real osmium exports are multi-GB, never loaded whole).
    with open(path, "w", encoding="utf-8") as f:
        for feat in features:
            f.write(json.dumps(feat) + "\n")
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


def test_is_devsite_predicate():
    assert G.is_devsite({"landuse": "construction"})
    assert G.is_devsite({"building": "construction"})
    assert not G.is_devsite({"building": "apartments"})
    assert not G.is_devsite({"landuse": "residential"})
    assert not G.is_devsite({})
    assert not G.is_devsite(None)


def test_is_apartstock_predicate():
    assert G.is_apartstock({"building": "apartments"})
    # Entrances / addresses carry no building tag: no multi-count.
    assert not G.is_apartstock({"entrance": "staircase"})
    assert not G.is_apartstock({"addr:housenumber": "1"})
    assert not G.is_apartstock({"building": "construction"})
    assert not G.is_apartstock({"building": "dormitory"})
    assert not G.is_apartstock({})
    assert not G.is_apartstock(None)


def test_read_site_points_merges_ring_duals(tmp_path):
    # One closed way exports as a LineString ring + a MultiPolygon:
    # both collapse to the same bbox center, so the 20 m dedupe
    # merges them into a single site vote.
    ring = [[24.75, 59.44], [24.751, 59.44], [24.751, 59.441],
            [24.75, 59.441], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "dev.geojson"), [
        line(ring, {"building": "construction"}),
        mpoly(ring, {"building": "construction"}),
        pt(24.76, 59.45, {"landuse": "construction"}),
        pt(24.76, 59.45, {"building": "yes"}),  # untagged member
        pt(24.76, 59.45, {"building": "apartments"}),  # wrong layer
    ])
    pts, stats = G.read_site_points(p, G.is_devsite)
    assert stats["kept"] == 3
    assert stats["dropped"] == 2
    assert len(G.dedupe_points(pts)) == 2  # ring duals merge


def test_read_site_points_open_line_feeds_midpoint(tmp_path):
    p = write_geojson(str(tmp_path / "open.geojson"), [
        line([[24.74, 59.44], [24.745, 59.44], [24.75, 59.44]],
             {"landuse": "construction"}),
    ])
    pts, stats = G.read_site_points(p, G.is_devsite)
    assert stats["kept"] == 1
    assert pts[0][0] == pytest.approx(24.745)


def test_count_field_scores_near_high_far_null(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "apt.geojson"), [
        pt(lon0, lat0, {"landuse": "construction"}),
    ])
    acc, feats = G.build_count_field(g, 1, 0.3, p, "ehitus")
    assert len(feats) == 1
    vals = G.score_bytes(g, G._area_score(acc, 1))
    k = g.cell_of(lon0, lat0)
    assert vals[k] == 50  # one site reads half-saturation on its cell
    far = g.cell_of(24.74 + 16 * 75 / 1000 / G.LON_KM, 59.44)
    assert vals[far] == 255  # beyond 4 sigma: unknown, never faked


def test_area_score_null_below_three():
    g = tiny_grid()
    score_of = G._area_score({7: 0.01}, 1)
    assert score_of(7) is None  # saturate(0.01, 1) < 3 -> unknown
    assert score_of(999) is None  # missing cell -> unknown
    score_of = G._area_score({7: 1.0}, 1)
    assert score_of(7) == 50.0


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("ehitus")
    assert half == 1 and sigma == 0.3
    half_k, sigma_k = G.contract_of("korterstock")
    assert half_k == 15 and sigma_k == 0.3
    doc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "ehitus")
    assert doc["half"] == 1 and doc["sigma"] == 0.3
    kdoc = G.encode_wire(g, bytearray([70]) * (g.cols * g.rows), "korterstock")
    assert kdoc["half"] == 15 and kdoc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G05A_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group05a.ts"), encoding="utf-8").read()
    m = re.search(r"G05A_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G05A_CAL block not found in layers_group05a.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G05A_CAL
    assert flat["ehitus"]["half"] == py["ehitus"]["half"]
    assert flat["ehitus"]["sigma"] == py["ehitus"]["sigma"]
    assert flat["korterstock"]["half"] == py["korterstock"]["half"]
    assert flat["korterstock"]["sigma"] == py["korterstock"]["sigma"]
