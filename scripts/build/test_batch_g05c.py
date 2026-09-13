"""Group 5 plans-C builder tests (issue #163): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group05c.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g05c_plans as G


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


def poly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def test_keep_comm_zones_not_errands():
    assert G.keep_comm({"landuse": "commercial"})
    assert G.keep_comm({"landuse": "retail"})
    assert G.keep_comm({"shop": "mall"})
    assert G.keep_comm({"landuse": "retail", "shop": "garden_centre"})
    # Plain supermarkets stay grocery's (#98), not bleed pressure.
    assert not G.keep_comm({"shop": "supermarket"})
    assert not G.keep_comm({"shop": "convenience"})
    assert not G.keep_comm({"landuse": "residential"})
    assert not G.keep_comm({})  # untagged member drops out
    assert not G.keep_comm(None)


def test_keep_farm_scale_not_panels():
    assert G.keep_farm({"power": "generator", "generator:source": "wind"})
    assert G.keep_farm({"power": "generator", "generator:source": "wind",
                        "location": "roof"})
    assert G.keep_farm({"power": "generator", "generator:source": "solar",
                        "location": "ground"})
    assert G.keep_farm({"power": "generator", "generator:source": "solar",
                        "location": "surface"})
    # A rooftop panel is not a farm; unknown location stays out too.
    assert not G.keep_farm({"power": "generator", "generator:source": "solar",
                            "location": "roof"})
    assert not G.keep_farm({"power": "generator",
                            "generator:source": "solar"})
    # Not wind/solar at all.
    assert not G.keep_farm({"power": "generator",
                            "generator:source": "diesel"})
    assert not G.keep_farm({"power": "generator",
                            "generator:source": "hydro"})
    assert not G.keep_farm({})
    assert not G.keep_farm(None)


def test_keep_view_is_viewpoint_only():
    assert G.keep_view({"tourism": "viewpoint"})
    assert not G.keep_view({"tourism": "museum"})
    assert not G.keep_view({"tourism": "attraction"})
    assert not G.keep_view({})
    assert not G.keep_view(None)


def test_read_comm_fills_polygons(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "comm.geojson"), [
        pt(24.75, 59.44, {"shop": "mall"}),
        poly(ring, {"landuse": "retail"}),
        pt(24.76, 59.45, {"shop": "supermarket"}),  # grocery's, not bleed
        pt(24.76, 59.45, {"landuse": "residential"}),
    ])
    pts, polys, stats = G.read_comm_points(p)
    assert stats["zones"] == 2
    assert stats["dropped"] == 2
    assert len(polys) == 1
    assert len(pts) >= 2


def test_fill_comm_cells_covers_interior(tmp_path):
    g = tiny_grid(12)
    ring = [[24.741, 59.4405], [24.743, 59.4405], [24.743, 59.4415],
            [24.741, 59.4415], [24.741, 59.4405]]
    cells = G.fill_comm_cells(g, [ring])
    assert len(cells) > 0
    # A cell far outside the ring is not filled.
    far = g.cell_of(24.74, 59.44)
    assert far not in cells


def test_read_farm_points_keeps_scale(tmp_path):
    ring = [[24.75, 59.44], [24.751, 59.44], [24.751, 59.441],
            [24.75, 59.441], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "gen.geojson"), [
        pt(24.75, 59.44, {"power": "generator",
                           "generator:source": "wind"}),
        mpoly(ring, {"power": "generator", "generator:source": "solar",
                      "location": "ground"}),
        pt(24.76, 59.45, {"power": "generator", "generator:source": "solar",
                           "location": "roof"}),  # a panel, not a farm
        pt(24.76, 59.45, {"power": "generator",
                           "generator:source": "diesel"}),
    ])
    pts, stats = G.read_farm_points(p)
    assert stats["farms"] == 2
    assert stats["dropped"] == 2
    assert len(pts) >= 2


def test_read_view_points(tmp_path):
    p = write_geojson(str(tmp_path / "view.geojson"), [
        pt(24.75, 59.44, {"tourism": "viewpoint"}),
        pt(24.76, 59.45, {"tourism": "museum"}),
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_view_points(p)
    assert stats["views"] == 1
    assert stats["dropped"] == 2
    assert pts == [(24.75, 59.44)]


def test_quiet_from_half():
    assert G.quiet_from_half(0, 300) == 0
    assert G.quiet_from_half(300, 300) == 50
    assert G.quiet_from_half(800, 800) == 50
    assert G.quiet_from_half(float("inf"), 300) == 100
    assert G.quiet_from_half(1e9, 300) > 99.9


def test_area_score_saturates_like_moorage():
    assert G.area_score(0, 1) == 0
    assert G.area_score(1, 1) == 50
    assert G.area_score(3, 1) == 75


def test_field_end_to_end_on_tiny_grid(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "comm.geojson"), [
        poly([[lon0, lat0 + 150 / 110570.0], [lon0 + 0.001, lat0 + 150 / 110570.0],
              [lon0 + 0.001, lat0 + 160 / 110570.0], [lon0, lat0 + 160 / 110570.0],
              [lon0, lat0 + 150 / 110570.0]], {"landuse": "commercial"}),
    ])
    raw, polys, _ = G.read_comm_points(p)
    cells = G.cells_of_points(g, raw) | G.fill_comm_cells(g, polys)
    dist = G.dijkstra_km(g, cells)
    vals = G.score_distance(dist, G.G05C_CAL["commbleed"]["half_m"])
    assert min(vals) <= 45  # ~150 m from a zone reads low-calm
    far = g.cell_of(lon0, lat0)
    assert vals[far] > min(vals)


def test_viewshed_kernel_scores_near_high_far_unknown(tmp_path):
    # 4-sigma cutoff is 1.2 km: the desert probe sits 1.5 km out.
    g = tiny_grid(30)
    lon0, lat0 = 24.74, 59.44
    acc = G.count_kernel_field(g, [(lon0, lat0)], G.G05C_CAL["viewshed"]["sigma"])
    vals = G.score_area_cells(g, acc, G.G05C_CAL["viewshed"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] >= 50  # on the viewpoint reads protected-green
    desert = g.cell_of(lon0 + 1500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 255  # desert stays honestly unknown


def test_score_distance_endpoints():
    g = tiny_grid()
    n = g.cols * g.rows
    dist = [0.0] * n
    vals = G.score_distance(dist, 300.0)
    assert set(vals) == {0}
    dist = [float("inf")] * n
    vals = G.score_distance(dist, 300.0)
    assert set(vals) == {100}


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("windsolar")
    assert half == 800.0 and sigma == 0.3
    half_c, sigma_c = G.contract_of("commbleed")
    assert half_c == 300.0 and sigma_c == 0.3
    half_v, sigma_v = G.contract_of("viewshed")
    assert half_v == 1.0 and sigma_v == 0.3
    doc = G.encode_wire(g, bytearray([90]) * (g.cols * g.rows))
    assert doc["half"] == 300.0 and doc["sigma"] == 0.3
    wdoc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "windsolar")
    assert wdoc["half"] == 800.0 and wdoc["sigma"] == 0.3
    vdoc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "viewshed")
    assert vdoc["half"] == 1.0 and vdoc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {90}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G05C_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group05c.ts"), encoding="utf-8").read()
    m = re.search(r"G05C_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G05C_CAL block not found in layers_group05c.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G05C_CAL
    assert flat["commbleed"]["halfM"] == py["commbleed"]["half_m"]
    assert flat["commbleed"]["sigma"] == py["commbleed"]["sigma"]
    assert flat["windsolar"]["halfM"] == py["windsolar"]["half_m"]
    assert flat["windsolar"]["sigma"] == py["windsolar"]["sigma"]
    assert flat["viewshed"]["half"] == py["viewshed"]["half"]
    assert flat["viewshed"]["sigma"] == py["viewshed"]["sigma"]
