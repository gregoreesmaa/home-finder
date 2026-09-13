"""Group 18 rest-B builder tests (issue #173): hermetic tests.

No network, no snapshot: readers run on tiny fixture files, fields on
a tiny grid, and the TS calibration drift guard parses the checked-in
layers_group18restb.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g18_restb as G


def tiny_grid(n=9, step=75.0):
    # ~0.675 km square near Tallinn.
    return G.Grid([24.74, 59.44, 24.74 + n * step / 1000 / G.LON_KM,
                   59.44 + n * step / 1000 / G.LAT_KM], step)


def write_geojson(path, features):
    doc = {"type": "FeatureCollection", "features": features}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


def write_json(path, doc):
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


def test_keep_forest_stands_not_street_trees():
    assert G.keep_forest({"natural": "wood"})
    assert G.keep_forest({"landuse": "forest"})
    assert G.keep_forest({"natural": "wood", "leaf_type": "needleleaved"})
    # A street tree is not a moss stand (map excludes trees by design).
    assert not G.keep_forest({"natural": "tree"})
    assert not G.keep_forest({"natural": "scrub"})
    assert not G.keep_forest({"landuse": "residential"})
    assert not G.keep_forest({})  # untagged member drops out
    assert not G.keep_forest(None)


def test_read_forest_fills_polygons(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "forest.geojson"), [
        pt(24.75, 59.44, {"natural": "wood"}),
        poly(ring, {"landuse": "forest"}),
        line([[24.75, 59.44], [24.751, 59.4405]], {"natural": "wood"}),
        pt(24.76, 59.45, {"natural": "tree"}),  # a tree, not a stand
        pt(24.76, 59.45, {"landuse": "residential"}),
    ])
    pts, polys, stats = G.read_forest_points(p)
    assert stats["stands"] == 3
    assert stats["dropped"] == 2
    assert len(polys) == 1
    assert len(pts) >= 3


def test_fill_poly_cells_covers_interior(tmp_path):
    g = tiny_grid(12)
    ring = [[24.741, 59.4405], [24.743, 59.4405], [24.743, 59.4415],
            [24.741, 59.4415], [24.741, 59.4405]]
    cells = G.fill_poly_cells(g, [ring])
    assert len(cells) > 0
    # A cell far outside the ring is not filled.
    far = g.cell_of(24.74, 59.44)
    assert far not in cells


def test_graph_junctions_keep_settled_only(tmp_path):
    # Star at node 0 (deg 3: a junction) near buildings; star at node
    # 4 (deg 3) in empty forest; chain 7-8 (deg 1: not a junction).
    lon0, lat0 = 24.74, 59.44
    far = (24.9, 59.5)
    nodes = [[lon0, lat0], [lon0 + 0.001, lat0], [lon0, lat0 + 0.001],
             [lon0 - 0.001, lat0],
             [far[0], far[1]], [far[0] + 0.001, far[1]],
             [far[0], far[1] + 0.001], [far[0] - 0.001, far[1]],
             [lon0 + 0.01, lat0 + 0.01], [lon0 + 0.011, lat0 + 0.01]]
    edges = [[0, 1, 10], [0, 2, 10], [0, 3, 10],
             [4, 5, 10], [4, 6, 10], [4, 7, 10],
             [8, 9, 10]]
    gp = write_json(str(tmp_path / "graph.json"),
                    {"directed": False, "nodes": nodes, "edges": edges})
    jun, stats = G.read_graph_junctions(gp)
    assert stats["junctions"] == 2
    bp = write_json(str(tmp_path / "buildings.json"),
                    [{"lon": lon0, "lat": lat0}])
    bcells, nbuild = G.read_building_cells(bp)
    assert nbuild == 1
    settled = G.settled_junctions(jun, bcells)
    # The forest star drops out (no house nearby); the settled star stays.
    assert len(settled) == 1
    assert abs(settled[0][0] - lon0) < 1e-9


def test_read_building_points_skips_junk(tmp_path):
    bp = write_json(str(tmp_path / "buildings.json"), [
        {"lon": 24.75, "lat": 59.44},
        {"lon": 24.76},  # coordless junk drops out
        {"lat": 59.44},
    ])
    assert G.read_building_points(bp) == [(24.75, 59.44)]


def test_quiet_from_half():
    assert G.quiet_from_half(0, 150) == 0
    assert G.quiet_from_half(150, 150) == 50
    assert G.quiet_from_half(250, 250) == 50
    assert G.quiet_from_half(float("inf"), 150) == 100
    assert G.quiet_from_half(1e9, 250) > 99.9


def test_sparse_score_inverts_like_daylight():
    assert G.sparse_score(0, 150) == 100
    assert G.sparse_score(150, 150) == 50
    assert G.sparse_score(450, 150) == 25


def test_field_end_to_end_on_tiny_grid(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "forest.geojson"), [
        poly([[lon0, lat0 + 150 / 110570.0], [lon0 + 0.001, lat0 + 150 / 110570.0],
              [lon0 + 0.001, lat0 + 160 / 110570.0], [lon0, lat0 + 160 / 110570.0],
              [lon0, lat0 + 150 / 110570.0]], {"natural": "wood"}),
    ])
    raw, polys, _ = G.read_forest_points(p)
    cells = G.cells_of_points(g, raw) | G.fill_poly_cells(g, polys)
    dist = G.dijkstra_km(g, cells)
    vals = G.score_distance(dist, G.G18B_CAL["mossrisk"]["half_m"])
    assert min(vals) <= 45  # ~150 m from a stand reads low-calm
    far = g.cell_of(lon0, lat0)
    assert vals[far] > min(vals)


def test_sparse_cells_open_high_dense_low():
    # 4-sigma cutoff is 1.2 km: the desert probe sits 1.5 km out but
    # still reads measured-open 100 (never 255 — buildings ARE the
    # obstruction and the inventory is near-complete).
    g = tiny_grid(30)
    lon0, lat0 = 24.74, 59.44
    acc = G.count_kernel_field(g, [(lon0, lat0)], G.G18B_CAL["daylight"]["sigma"])
    vals = G.score_sparse_cells(g, acc, G.G18B_CAL["daylight"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] == 99  # one house barely shades: 100*150/151
    desert = g.cell_of(lon0 + 1500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 100
    # A dense cluster reads low: 600 stacked houses -> 100*150/750 = 20.
    acc2 = G.count_kernel_field(g, [(lon0, lat0)] * 600,
                                G.G18B_CAL["daylight"]["sigma"])
    vals2 = G.score_sparse_cells(g, acc2, G.G18B_CAL["daylight"]["half"])
    assert vals2[k] == 20


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


def test_window_counts_tallinn_box():
    pts = [(24.75, 59.44), (24.9, 59.5), (25.0, 59.5)]
    assert G.window_counts(pts) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("fishbowl")
    assert half == 150.0 and sigma == 0.3
    half_m, sigma_m = G.contract_of("mossrisk")
    assert half_m == 250.0 and sigma_m == 0.3
    half_d, sigma_d = G.contract_of("daylight")
    assert half_d == 150.0 and sigma_d == 0.3
    doc = G.encode_wire(g, bytearray([90]) * (g.cols * g.rows))
    assert doc["half"] == 150.0 and doc["sigma"] == 0.3
    mdoc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "mossrisk")
    assert mdoc["half"] == 250.0 and mdoc["sigma"] == 0.3
    ddoc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "daylight")
    assert ddoc["half"] == 150.0 and ddoc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {90}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G18B_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group18restb.ts"), encoding="utf-8").read()
    m = re.search(r"G18B_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G18B_CAL block not found in layers_group18restb.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G18B_CAL
    assert flat["fishbowl"]["halfM"] == py["fishbowl"]["half_m"]
    assert flat["fishbowl"]["sigma"] == py["fishbowl"]["sigma"]
    assert flat["mossrisk"]["halfM"] == py["mossrisk"]["half_m"]
    assert flat["mossrisk"]["sigma"] == py["mossrisk"]["sigma"]
    assert flat["daylight"]["half"] == py["daylight"]["half"]
    assert flat["daylight"]["sigma"] == py["daylight"]["sigma"]
