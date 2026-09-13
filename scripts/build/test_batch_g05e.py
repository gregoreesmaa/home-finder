"""Group 5 plans-E builder tests (issue #165): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group05e.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g05e_plans as G


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


def test_keep_equi_centres_arenas_stables_trails():
    assert G.keep_equi({"leisure": "horse_riding"})
    assert G.keep_equi({"leisure": "horse_riding", "building": "yes"})
    assert G.keep_equi({"sport": "equestrian"})
    assert G.keep_equi({"leisure": "pitch", "sport": "equestrian"})
    assert G.keep_equi({"highway": "bridleway"})
    assert G.keep_equi({"building": "stable"})
    # A plain football pitch is not an arena.
    assert not G.keep_equi({"leisure": "pitch"})
    assert not G.keep_equi({"leisure": "pitch", "sport": "soccer"})
    assert not G.keep_equi({"building": "yes"})
    assert not G.keep_equi({"landuse": "farmyard"})
    assert not G.keep_equi({})  # untagged member drops out
    assert not G.keep_equi(None)


def test_read_equi_points(tmp_path):
    ring = [[24.75, 59.44], [24.751, 59.44], [24.751, 59.441],
            [24.75, 59.441], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "equi.geojson"), [
        pt(24.75, 59.44, {"leisure": "horse_riding"}),
        mpoly(ring, {"leisure": "pitch", "sport": "equestrian"}),
        line([[24.75, 59.44], [24.752, 59.4405]], {"highway": "bridleway"}),
        pt(24.76, 59.45, {"building": "stable"}),
        pt(24.76, 59.45, {"leisure": "pitch"}),  # football, not arena
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_equi_points(p)
    assert stats["sites"] == 4
    assert stats["dropped"] == 2
    assert len(pts) >= 4


def test_area_score_saturates_like_viewshed():
    assert G.area_score(0, 1) == 0
    assert G.area_score(1, 1) == 50
    assert G.area_score(3, 1) == 75


def test_kernel_scores_near_high_far_unknown():
    # 4-sigma cutoff is 1.2 km: the desert probe sits 1.5 km out.
    g = tiny_grid(30)
    lon0, lat0 = 24.74, 59.44
    acc = G.count_kernel_field(g, [(lon0, lat0)], G.G05E_CAL["equestrian"]["sigma"])
    vals = G.score_area_cells(g, acc, G.G05E_CAL["equestrian"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] >= 50  # on the campus reads access-green
    desert = g.cell_of(lon0 + 1500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 255  # desert stays honestly unknown


def test_thin_overlay_dedupes_twins():
    # osmium export doubles closed ways as LineString + MultiPolygon
    # twins with identical coordinates — they collapse to one dot.
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("equestrian")
    assert half == 1.0 and sigma == 0.3
    doc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows))
    assert doc["half"] == 1.0 and doc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G05E_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group05e.ts"), encoding="utf-8").read()
    m = re.search(r"G05E_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G05E_CAL block not found in layers_group05e.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G05E_CAL
    assert flat["equestrian"]["half"] == py["equestrian"]["half"]
    assert flat["equestrian"]["sigma"] == py["equestrian"]["sigma"]
