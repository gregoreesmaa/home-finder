"""Hermetic unit tests for the Group 7C vector-habitat builder (issue #142).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g07c.py -q
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g07c_envhealth as H


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return H.Grid([24.74, 59.43, 24.74 + n * step / 1000 / H.LON_KM,
                   59.43 + n * step / 1000 / H.LAT_KM], step)


def test_quiet_from_half():
    assert H.quiet_from_half(0.0, 300.0) == 0.0
    assert H.quiet_from_half(300.0, 300.0) == 50.0
    assert H.quiet_from_half(float("inf"), 300.0) == 100.0
    assert H.quiet_from_half(1e9, 300.0) > 99.9


def square_ring(cx=24.745, cy=59.4335, half=0.002):
    return [(cx - half, cy - half), (cx + half, cy - half),
            (cx + half, cy + half), (cx - half, cy + half),
            (cx - half, cy - half)]


def test_ring_area_m2_and_min_area_drop():
    # 0.004° square ≈ 229 m × 442 m ≈ 101 000 m².
    assert H.ring_area_m2(square_ring()) == abs(H.ring_area_m2(square_ring()))
    assert 90000 < H.ring_area_m2(square_ring()) < 115000
    tiny = [(24.74, 59.43), (24.74005, 59.43), (24.74005, 59.43005),
            (24.74, 59.43005), (24.74, 59.43)]
    assert H.ring_area_m2(tiny) < H.MIN_AREA_M2


def test_ring_scan_fills_interior_not_exterior():
    g = tiny_grid()
    ring = square_ring()
    cells = H.ring_scan_cells(g, ring)
    assert len(cells) > 0
    cx, cy = 24.745, 59.4335
    assert g.cell_of(cx, cy) in cells  # centre: inside
    assert g.cell_of(24.74, 59.43) not in cells  # grid corner: outside


def test_habitat_cells_union_edge_and_interior():
    g = tiny_grid()
    ring = square_ring()
    cells = H.habitat_cells(g, [ring], [((24.74, 59.43), {})])
    assert g.cell_of(24.745, 59.4335) in cells  # interior via fill
    assert g.cell_of(24.74, 59.43) in cells  # lone edge vertex
    assert g.cell_of(24.74 + 8 * 75 / 1000 / H.LON_KM, 59.43) not in cells


def test_read_habitat_geoms_predicate_and_shapes(tmp_path):
    ring = square_ring()
    feats = [
        {"type": "Feature",
         "properties": {"natural": "wood"},
         "geometry": {"type": "Polygon", "coordinates": [ring]}},
        {"type": "Feature",
         "properties": {"landuse": "meadow"},
         "geometry": {"type": "LineString",
                      "coordinates": [ring[0], ring[1], ring[2],
                                      ring[3], ring[0]]}},  # closed way
        {"type": "Feature",
         "properties": {"natural": "wood"},
         "geometry": {"type": "LineString",
                      "coordinates": [[24.74, 59.43],
                                      [24.75, 59.44]]}},  # open row
        {"type": "Feature",
         "properties": {"natural": "water"},  # not habitat: dropped
         "geometry": {"type": "Point", "coordinates": [24.745, 59.4335]}},
        {"type": "Feature",
         "properties": {"landuse": "residential"},  # not habitat: dropped
         "geometry": {"type": "Point", "coordinates": [24.745, 59.4335]}},
        {"type": "Feature",
         "properties": {"natural": "scrub"},  # micro-fragment: dropped
         "geometry": {"type": "Polygon", "coordinates": [[
             [24.74, 59.43], [24.74005, 59.43], [24.74005, 59.43005],
             [24.74, 59.43005], [24.74, 59.43]]]}},
    ]
    p = tmp_path / "hab.geojson"
    p.write_text("\n".join(json.dumps(f) for f in feats), encoding="utf-8")
    rings, verts, stats = H.read_habitat_geoms(str(p))
    assert stats["features"] == 6
    assert stats["kept"] == 3
    assert stats["dropped_tags"] == 2
    assert stats["dropped_small"] == 1
    assert len(rings) == 2  # polygon + closed way
    assert len(verts) > 2  # ring samples + densified open row


def test_score_distance_half_and_wire_contract():
    g = tiny_grid(5)
    dist = H.dijkstra_km(g, {12})  # centre source on a 5x5 grid
    vals = H.score_distance(dist, 300)
    assert vals[12] == 0
    assert set(vals) - {0}  # calm rises away from the source
    assert max(vals) <= 100
    doc = H.encode_wire(g, vals, "vectorhabitat")
    assert doc["half"] == 300 and doc["sigma"] == 0.3
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    import base64
    assert len(base64.b64decode(doc["data"])) == g.cols * g.rows


def test_honesty_strings():
    src = open(os.path.abspath(__file__.replace(
        "test_batch_g07c.py", "batch_g07c_envhealth.py")),
        encoding="utf-8").read()
    for word in ("proksi", "hinnang", "seire",
                 "no pest-surveillance registry"):
        assert word in src
    assert "dBA" not in src  # never a measured-level claim


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G07C_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group07c.ts"), encoding="utf-8").read()
    m = re.search(r"G07C_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G07C_CAL block not found in layers_group07c.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = H.G07C_CAL["vectorhabitat"]
    assert flat["vectorhabitat"]["halfM"] == py["half_m"]
    assert flat["vectorhabitat"]["sigma"] == py["sigma"]
