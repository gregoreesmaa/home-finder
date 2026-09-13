"""Hermetic unit tests for the Group 3 cadastre-D builder (issue #154).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g03d.py -q
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402

import batch_g03d_cadastre as D


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return D.Grid([24.74, 59.43, 24.74 + n * step / 1000 / D.LON_KM,
                   59.43 + n * step / 1000 / D.LAT_KM], step)


def hydro_doc(features):
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": p,
                          "geometry": g} for p, g in features]}


def write_shore(tmp_path, features):
    p = str(tmp_path / "shore.geojson")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(hydro_doc(features), f)
    return p


# ---------------------------------------------------------------------------
# Moorage predicate.
# ---------------------------------------------------------------------------

def test_moorage_predicate():
    # Marinas, seamark moorings/harbours, harbour/mooring=yes are sources.
    assert D.is_moorage({"leisure": "marina"})
    assert D.is_moorage({"leisure": "marina", "seamark:type": "harbour"})
    assert D.is_moorage({"seamark:type": "mooring"})
    assert D.is_moorage({"seamark:type": "harbour"})
    assert D.is_moorage({"harbour": "yes"})
    assert D.is_moorage({"mooring": "yes"})
    assert D.is_moorage({"mooring": "yacht"})
    assert D.is_moorage({"mooring": "private"})
    # Bare piers (cargo/industrial/private), breakwaters, quays are OUT:
    # they answer p331 condition, not p332 opportunity.
    assert not D.is_moorage({"man_made": "pier"})
    assert not D.is_moorage({"man_made": "breakwater"})
    assert not D.is_moorage({"man_made": "quay"})
    assert not D.is_moorage({"man_made": "pier", "mooring": "no"})
    assert not D.is_moorage({"mooring": "no"})
    assert not D.is_moorage({"leisure": "slipway"})
    assert not D.is_moorage({"natural": "water"})
    assert not D.is_moorage({})
    assert not D.is_moorage(None)


def test_moorage_poi_resolution(tmp_path):
    p = str(tmp_path / "moor.geojson")
    feats = [
        {"type": "Feature", "id": "n1", "properties": {"leisure": "marina"},
         "geometry": {"type": "Point", "coordinates": [24.755, 59.438]}},
        {"type": "Feature", "id": "n2", "properties": {"mooring": "yes"},
         "geometry": {"type": "Point", "coordinates": [24.760, 59.440]}},
        {"type": "Feature", "id": "n3", "properties": {"man_made": "pier"},
         "geometry": {"type": "Point", "coordinates": [24.770, 59.445]}},
        {"type": "Feature", "id": "n4", "properties": {"mooring": "no"},
         "geometry": {"type": "Point", "coordinates": [24.780, 59.450]}},
    ]
    with open(p, "w", encoding="utf-8") as f:
        for feat in feats:
            f.write(json.dumps(feat) + "\n")
    pts, stats = wr.resolve_pois(p, D.is_moorage)
    assert len(pts) == 2  # marina + mooring=yes; bare pier + mooring=no out
    assert stats["kept"] == 2


def _moor_geojson(path, coords_props):
    with open(path, "w", encoding="utf-8") as f:
        for i, (lon, lat, props) in enumerate(coords_props):
            f.write(json.dumps(
                {"type": "Feature", "id": "n%d" % i, "properties": props,
                 "geometry": {"type": "Point",
                              "coordinates": [lon, lat]}}) + "\n")
    return path


def test_moorage_field_end_to_end_on_tiny_grid(tmp_path):
    # One marina at the grid centre: the facility cell stacks kernel ~1
    # (centroid offset only), scoring 100*1/2 = 50 at half 1 — no
    # water-centroid hole. Neighbours decay, far cells stay unknown
    # (255), never zero.
    g = tiny_grid(25)
    clon, clat = g.center_of(12 * g.cols + 12)
    p = _moor_geojson(str(tmp_path / "moor.geojson"),
                      [(clon, clat, {"leisure": "marina"})])
    acc, feats = D.build_moorage_field(g, 1, 0.3, p)
    assert len(feats) == 1
    score_of = D._area_score(acc, 1)
    k = g.cell_of(clon, clat)
    assert k is not None
    assert score_of(k) == pytest.approx(50.0, abs=3.0)
    vals = D.score_bytes(g, score_of)
    assert vals[k] == round(score_of(k))
    # ~1.3 km out (grid corner, past the 4-sigma cutoff) the field is
    # unknown, never zero…
    assert vals[0] == 255
    # …while ~150 m out the field still reads high but decayed
    # (Gaussian monotone falloff: kernel(0.15, 0.3) ~= 0.88 -> 47).
    near = g.cell_of(clon + 0.0026, clat)
    assert near is not None and vals[near] not in (255,)
    assert vals[near] >= 40
    assert vals[near] <= vals[k]


def test_moorage_two_facilities_stack(tmp_path):
    # Two co-located marinas (distinct cells >20 m apart) stack S ~2,
    # scoring 100*2/3 = 67 — a harbour basin reads denser.
    g = tiny_grid(25)
    clon, clat = g.center_of(12 * g.cols + 12)
    p = _moor_geojson(str(tmp_path / "moor2.geojson"),
                      [(clon, clat, {"leisure": "marina"}),
                       (clon + 0.0006, clat, {"mooring": "yes"})])
    acc, feats = D.build_moorage_field(g, 1, 0.3, p)
    assert len(feats) == 2
    score_of = D._area_score(acc, 1)
    k = g.cell_of(clon, clat)
    assert score_of(k) == pytest.approx(67.0, abs=5.0)


# ---------------------------------------------------------------------------
# Shore predicate + Dijkstra field.
# ---------------------------------------------------------------------------

def test_keep_shore_predicate():
    # Sea shore + standing water are shore; rivers/wetlands are p50's.
    assert D.keep_shore({"natural": "coastline"})
    assert D.keep_shore({"natural": "water"})
    assert D.keep_shore({"natural": "water", "water": "lake"})
    assert D.keep_shore({"natural": "water", "water": "pond"})
    assert D.keep_shore({"natural": "water", "water": "reservoir"})
    assert not D.keep_shore({"natural": "water", "water": "wastewater"})
    assert not D.keep_shore({"natural": "water", "water": "basin"})
    assert not D.keep_shore({"natural": "water", "water": "fountain"})
    assert not D.keep_shore({"waterway": "river"})
    assert not D.keep_shore({"waterway": "stream"})
    assert not D.keep_shore({"natural": "wetland"})
    assert not D.keep_shore({"natural": "scrub"})
    assert not D.keep_shore({"man_made": "pier"})
    assert not D.keep_shore({})
    assert not D.keep_shore(None)


def test_quiet_from_half():
    assert D.quiet_from_half(0.0, 100.0) == 0.0
    assert D.quiet_from_half(100.0, 100.0) == 50.0
    assert D.quiet_from_half(float("inf"), 100.0) == 100.0
    assert D.quiet_from_half(1e9, 100.0) > 99.9


def test_polygon_interior_is_source(tmp_path):
    # A lake polygon fills its interior cells (d=0 -> score 0), not just
    # the ring: the centre must read at-shore, never green.
    g = tiny_grid(21)
    lon0, lat0 = g.center_of(0)
    lon1, lat1 = g.center_of(g.cols * g.rows - 1)
    ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1],
            [lon0, lat1], [lon0, lat0]]
    path = write_shore(tmp_path, [({"natural": "water", "water": "lake"},
                                   {"type": "Polygon", "coordinates": [ring]})])
    cells, stats = D.read_shore_sources(g, path)
    assert stats["kept"] == 1
    mid = g.cell_of(*g.center_of((g.rows // 2) * g.cols + g.cols // 2))
    assert mid in cells
    d = D.dijkstra_km(g, cells)
    vals = D.score_distance(d, D.G03D_CAL["shoredist"]["half_m"])
    assert vals[mid] == 0


def test_river_excluded_end_to_end(tmp_path):
    # A river through the grid is NOT shore: no source cells at all.
    g = tiny_grid()
    clon, clat = g.center_of(40)
    path = write_shore(tmp_path, [
        ({"waterway": "river"},
         {"type": "LineString", "coordinates": [[clon, clat],
                                                [clon + 0.001, clat]]}),
    ])
    cells, stats = D.read_shore_sources(g, path)
    assert stats["kept"] == 0
    assert len(cells) == 0


def test_coastline_line_is_source(tmp_path):
    g = tiny_grid()
    clon, clat = g.center_of(40)
    path = write_shore(tmp_path, [
        ({"natural": "coastline"},
         {"type": "LineString", "coordinates": [[clon, clat],
                                                [clon + 0.001, clat]]}),
    ])
    cells, stats = D.read_shore_sources(g, path)
    assert stats["kept"] == 1
    assert g.cell_of(clon, clat) in cells


def test_score_distance_endpoints():
    g = tiny_grid()
    src = g.cell_of(*g.center_of(40))
    d = D.dijkstra_km(g, {src})
    vals = D.score_distance(d, 100.0)
    assert vals[src] == 0  # at the shore
    assert vals[0] > vals[40]  # freer with distance
    assert 0 <= vals[0] <= 100


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.43), (24.75001, 59.43001), (24.76, 59.44)]
    out = D.thin_overlay(pts, cap=1500)
    assert len(out) == 2
    assert out[0] == {"lon": 24.75, "lat": 59.43}
    many = [(24.0 + i * 0.001, 59.0) for i in range(3000)]
    out = D.thin_overlay(many, cap=1500)
    assert len(out) == 1500
    assert out[0]["lon"] == 24.0


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = D.contract_of("shoredist")
    assert half == 100.0 and sigma == 0.3
    half_m, sigma_m = D.contract_of("moorage")
    assert half_m == 1 and sigma_m == 0.3
    doc = D.encode_wire(g, bytearray([90]) * (g.cols * g.rows))
    assert doc["half"] == 100.0 and doc["sigma"] == 0.3
    mdoc = D.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "moorage")
    assert mdoc["half"] == 1 and mdoc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {90}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G03D_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group03d.ts"), encoding="utf-8").read()
    m = re.search(r"G03D_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G03D_CAL block not found in layers_group03d.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = D.G03D_CAL
    assert flat["moorage"]["half"] == py["moorage"]["half"]
    assert flat["moorage"]["sigma"] == py["moorage"]["sigma"]
    assert flat["shoredist"]["halfM"] == py["shoredist"]["half_m"]
    assert flat["shoredist"]["sigma"] == py["shoredist"]["sigma"]
