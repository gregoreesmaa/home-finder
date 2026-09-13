"""Hermetic unit tests for the Group 7 env-health batch-B builder (issue #141).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g07b.py -q
"""

import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g07b_envhealth as G


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return G.Grid([24.74, 59.43, 24.74 + n * step / 1000 / G.LON_KM,
                   59.43 + n * step / 1000 / G.LAT_KM], step)


def test_hav_km_lon_scale():
    assert abs(G.hav_km(0.0, 0.0, 1.0, 0.0) - 57.29) < 1e-9
    assert abs(G.hav_km(0.0, 0.0, 0.0, 1.0) - 110.57) < 1e-9


def test_quiet_from_half():
    assert G.quiet_from_half(0.0, 500.0) == 0.0
    assert G.quiet_from_half(500.0, 500.0) == 50.0
    assert G.quiet_from_half(float("inf"), 500.0) == 100.0


def test_dijkstra_exact_on_tiny_grid():
    g = tiny_grid()
    src = g.cell_of(*g.center_of(40))
    d = G.dijkstra_km(g, {src})
    assert d[src] == 0.0
    assert abs(d[src + 1] - g.step / 1000.0) < 1e-9
    row = [d[40 + i] for i in range(5)]
    assert row == sorted(row)


def test_scores_endpoint_behaviour():
    n = 81
    inf = [float("inf")] * n
    d0 = [0.0] * n
    # Nothing mapped -> fully clean (absence in-bbox IS evidence).
    assert all(v == 100 for v in G.score_distance(inf, 500.0))
    # On the source -> known-exposed 0 (never 255/unknown).
    assert all(v == 0 for v in G.score_distance(d0, 500.0))
    # Half distance reads 50.
    assert all(v == 50 for v in G.score_distance([0.5] * n, 500.0))
    # Agriland halves at the 800 m spray-drift scale.
    assert all(v == 50 for v in G.score_distance([0.8] * n, 800.0))


def test_dedupe_cells_merges_twins():
    # Second point ~1 m away (same 20 m cell, not straddling a boundary).
    pts = [(24.75, 59.435), (24.75001, 59.43501), (24.76, 59.44)]
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def _snap_dir(tmp_path):
    osm = tmp_path / "osm"
    osm.mkdir()
    (osm / "derived-soil.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"landuse": "brownfield"},
             "geometry": {"type": "MultiPolygon", "coordinates": [[[
                 [24.70, 59.44], [24.71, 59.44], [24.71, 59.45],
                 [24.70, 59.45], [24.70, 59.44]]]]}},
            # Closed-way twin of the same site: dropped, not doubled.
            {"type": "Feature", "properties": {"landuse": "brownfield"},
             "geometry": {"type": "LineString", "coordinates": [
                 [24.70, 59.44], [24.71, 59.44], [24.71, 59.45],
                 [24.70, 59.45], [24.70, 59.44]]}},
            # Untagged member pulled in for relation completeness: dropped.
            {"type": "Feature", "properties": {},
             "geometry": {"type": "Point", "coordinates": [24.61, 59.31]}},
        ]}), encoding="utf-8")
    (osm / "derived-tanks.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"man_made": "storage_tank"},
             "geometry": {"type": "Point", "coordinates": [24.72, 59.45]}},
            # A slurry tank is still mapped tank stock: kept (no content
            # allowlist — buried vs above-ground is unmapped).
            {"type": "Feature",
             "properties": {"man_made": "storage_tank", "content": "slurry"},
             "geometry": {"type": "Point", "coordinates": [24.73, 59.46]}},
        ]}), encoding="utf-8")
    (osm / "derived-agri.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"landuse": "farmland"},
             "geometry": {"type": "MultiPolygon", "coordinates": [[[
                 [24.70, 59.44], [24.71, 59.44], [24.71, 59.45],
                 [24.70, 59.45], [24.70, 59.44]]]]}},
            {"type": "Feature", "properties": {"landuse": "farmyard"},
             "geometry": {"type": "Point", "coordinates": [24.60, 59.30]}},
            # Meadow is deliberately excluded (hay/pasture, low spray
            # relevance): dropped by the keeper, not the geometry path.
            {"type": "Feature", "properties": {"landuse": "meadow"},
             "geometry": {"type": "Point", "coordinates": [24.61, 59.31]}},
        ]}), encoding="utf-8")
    return str(tmp_path)


def test_readers_on_fixtures(tmp_path):
    snap = _snap_dir(tmp_path)
    soil, stats = G.read_brownfield_points(snap)
    assert stats["areas"] == 1  # twin merged: one brownfield object
    assert stats["twins_dropped"] == 1
    assert stats["untagged_dropped"] == 1
    assert len(soil) > 0
    tanks, stats = G.read_tank_points(snap)
    assert stats["tanks"] == 2  # slurry tank kept: no content allowlist
    assert len(tanks) == 2
    agri, stats = G.read_agri_points(snap)
    assert stats["farmland"] == 1
    assert stats["farmyard"] == 1
    assert stats["untagged_dropped"] == 1  # the meadow
    assert len(agri) > 0


def test_write_points_shape(tmp_path):
    doc = G.write_points(str(tmp_path), "oiltank",
                         [(24.70, 59.44), (24.70001, 59.44001)])
    assert len(doc) == 1  # 20 m twins merge
    assert set(doc[0]) == {"lon", "lat"}
    back = json.loads((tmp_path / "derived-oiltank.json").read_text(encoding="utf-8"))
    assert back == doc


def test_wire_doc_shape():
    g = tiny_grid()
    vals = bytes([50] * (g.cols * g.rows))
    doc = G.encode_wire(g, vals, "brownsoil")
    assert doc["cols"] == g.cols and doc["rows"] == g.rows
    assert doc["bbox"] == {"minlon": g.bbox[0], "minlat": g.bbox[1],
                           "maxlon": g.bbox[2], "maxlat": g.bbox[3]}
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    assert doc["half"] == 500.0 and doc["sigma"] == 0.5
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}
    assert G.contract_of("agriland") == (800.0, 0.8)


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G07B_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group07b.ts"), encoding="utf-8").read()
    m = re.search(r"G07B_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G07B_CAL block not found in layers_group07b.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G07B_CAL
    assert flat["brownsoil"]["halfM"] == py["brownsoil"]["half_m"]
    assert flat["brownsoil"]["sigma"] == py["brownsoil"]["sigma"]
    assert flat["oiltank"]["halfM"] == py["oiltank"]["half_m"]
    assert flat["oiltank"]["sigma"] == py["oiltank"]["sigma"]
    assert flat["agriland"]["halfM"] == py["agriland"]["half_m"]
    assert flat["agriland"]["sigma"] == py["agriland"]["sigma"]
