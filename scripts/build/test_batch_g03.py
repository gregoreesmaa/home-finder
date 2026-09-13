"""Hermetic unit tests for the Group 3 cadastre-A builder (issue #151).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g03.py -q
"""

import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g03_cadastre as C


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return C.Grid([24.74, 59.43, 24.74 + n * step / 1000 / C.LON_KM,
                   59.43 + n * step / 1000 / C.LAT_KM], step)


def hydro_doc(features):
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": p,
                          "geometry": g} for p, g in features]}


def write_hydro(tmp_path, features):
    p = str(tmp_path / "hydro.geojson")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(hydro_doc(features), f)
    return p


def test_quiet_from_half():
    assert C.quiet_from_half(0.0, 300.0) == 0.0
    assert C.quiet_from_half(300.0, 300.0) == 50.0
    assert C.quiet_from_half(float("inf"), 300.0) == 100.0
    assert C.quiet_from_half(1e9, 300.0) > 99.9


def test_keep_hydro_predicate():
    # Sea shore, inland water, wetland and flowing lines are sources.
    assert C.keep_hydro({"natural": "coastline"})
    assert C.keep_hydro({"natural": "water"})
    assert C.keep_hydro({"natural": "water", "water": "lake"})
    assert C.keep_hydro({"natural": "water", "water": "pond"})
    assert C.keep_hydro({"natural": "water", "water": "reservoir"})
    assert C.keep_hydro({"natural": "wetland"})
    assert C.keep_hydro({"waterway": "river"})
    assert C.keep_hydro({"waterway": "stream"})
    assert C.keep_hydro({"waterway": "ditch"})
    # Fenced/ornamental infra is NOT open water.
    assert not C.keep_hydro({"natural": "water", "water": "wastewater"})
    assert not C.keep_hydro({"natural": "water", "water": "basin"})
    assert not C.keep_hydro({"natural": "water", "water": "fountain"})
    # Bank vegetation, mills, slipways and untagged leftovers are out.
    assert not C.keep_hydro({"natural": "scrub"})
    assert not C.keep_hydro({"natural": "wood"})
    assert not C.keep_hydro({"man_made": "watermill"})
    assert not C.keep_hydro({"leisure": "slipway"})
    assert not C.keep_hydro({"created_by": "almien_LA2_coastlines"})
    assert not C.keep_hydro({})
    assert not C.keep_hydro(None)


def test_polygon_interior_is_source(tmp_path):
    # A lake polygon fills its interior cells (d=0 -> score 0), not just
    # the ring: the centre must read on-water, never green.
    g = tiny_grid(21)
    lon0, lat0 = g.center_of(0)
    lon1, lat1 = g.center_of(g.cols * g.rows - 1)
    ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1],
            [lon0, lat1], [lon0, lat0]]
    path = write_hydro(tmp_path, [({"natural": "water", "water": "lake"},
                                   {"type": "Polygon", "coordinates": [ring]})])
    cells, stats = C.read_hydro_sources(g, path)
    assert stats["kept"] == 1
    mid = g.cell_of(*g.center_of((g.rows // 2) * g.cols + g.cols // 2))
    assert mid in cells
    d = C.dijkstra_km(g, cells)
    vals = C.score_distance(d, C.G03_CAL["drainage"]["half_m"])
    assert vals[mid] == 0


def test_line_and_point_sources(tmp_path):
    g = tiny_grid()
    clon, clat = g.center_of(40)
    path = write_hydro(tmp_path, [
        ({"waterway": "stream"},
         {"type": "LineString", "coordinates": [[clon, clat],
                                                [clon + 0.001, clat]]}),
        ({"natural": "water"},
         {"type": "Point", "coordinates": [clon, clat]}),
    ])
    cells, stats = C.read_hydro_sources(g, path)
    assert stats["kept"] == 2
    assert g.cell_of(clon, clat) in cells


def test_wastewater_excluded_end_to_end(tmp_path):
    g = tiny_grid()
    clon, clat = g.center_of(40)
    path = write_hydro(tmp_path, [
        ({"natural": "water", "water": "wastewater"},
         {"type": "Point", "coordinates": [clon, clat]}),
    ])
    cells, stats = C.read_hydro_sources(g, path)
    assert stats["kept"] == 0
    assert len(cells) == 0


def test_score_distance_endpoints():
    g = tiny_grid()
    src = g.cell_of(*g.center_of(40))
    d = C.dijkstra_km(g, {src})
    vals = C.score_distance(d, 300.0)
    assert vals[src] == 0  # on the water
    assert vals[0] > vals[40]  # drier with distance
    assert 0 <= vals[0] <= 100


def test_thin_overlay_dedupes_twins():
    # Polygon/LineString export twins (same vertex twice) collapse.
    pts = [(24.75, 59.43), (24.75001, 59.43001), (24.76, 59.44)]
    out = C.thin_overlay(pts, cap=1500)
    assert len(out) == 2
    assert out[0] == {"lon": 24.75, "lat": 59.43}
    # Cap keeps spatial spread deterministically.
    many = [(24.0 + i * 0.001, 59.0) for i in range(3000)]
    out = C.thin_overlay(many, cap=1500)
    assert len(out) == 1500
    assert out[0]["lon"] == 24.0


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = C.contract_of("drainage")
    assert half == 300.0 and sigma == 0.3
    doc = C.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "drainage")
    assert doc["half"] == 300.0 and doc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G03_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group03.ts"), encoding="utf-8").read()
    m = re.search(r"G03_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G03_CAL block not found in layers_group03.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = C.G03_CAL
    assert flat["drainage"]["halfM"] == py["drainage"]["half_m"]
    assert flat["drainage"]["sigma"] == py["drainage"]["sigma"]
