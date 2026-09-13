"""Hermetic unit tests for the Group 8 flood batch-D builder (issue #170).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g08d.py -q
"""

import base64
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g08d_flood as G


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return G.Grid([24.74, 59.43, 24.74 + n * step / 1000 / G.LON_KM,
                   59.43 + n * step / 1000 / G.LAT_KM], step)


def test_hav_km_lon_scale():
    assert abs(G.hav_km(0.0, 0.0, 1.0, 0.0) - 57.29) < 1e-9
    assert abs(G.hav_km(0.0, 0.0, 0.0, 1.0) - 110.57) < 1e-9


def test_quiet_from_half():
    assert G.quiet_from_half(0.0, 300.0) == 0.0
    assert G.quiet_from_half(300.0, 300.0) == 50.0
    assert G.quiet_from_half(float("inf"), 300.0) == 100.0


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
    # Nothing mapped -> fully dry (absence in-bbox IS evidence).
    assert all(v == 100 for v in G.score_distance(inf, 300.0))
    # On the pond -> known-exposed 0 (never 255/unknown).
    assert all(v == 0 for v in G.score_distance(d0, 300.0))
    # Half distance reads 50.
    assert all(v == 50 for v in G.score_distance([0.3] * n, 300.0))


def test_dedupe_cells_merges_twins():
    # Second point ~1 m away (same 20 m cell, not straddling a boundary).
    pts = [(24.75, 59.435), (24.75001, 59.43501), (24.76, 59.44)]
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def _snap_dir(tmp_path):
    osm = tmp_path / "osm"
    osm.mkdir()
    (osm / "derived-ephemeral.geojson").write_text(json.dumps({
        "type": "FeatureCollection", "features": [
            {"type": "Feature",
             "properties": {"natural": "water", "water": "pond",
                            "intermittent": "yes"},
             "geometry": {"type": "MultiPolygon", "coordinates": [[[
                 [24.70, 59.44], [24.71, 59.44], [24.71, 59.45],
                 [24.70, 59.45], [24.70, 59.44]]]]}},
            {"type": "Feature",
             "properties": {"natural": "water", "water": "basin",
                            "intermittent": "yes"},
             "geometry": {"type": "Point",
                          "coordinates": [24.72, 59.45]}},
            # Closed-way twin of the pond: dropped, not doubled.
            {"type": "Feature",
             "properties": {"natural": "water", "water": "pond",
                            "intermittent": "yes"},
             "geometry": {"type": "LineString", "coordinates": [
                 [24.70, 59.44], [24.71, 59.44], [24.71, 59.45],
                 [24.70, 59.45], [24.70, 59.44]]}},
            # Permanent pond (no intermittent): not ephemeral, dropped.
            {"type": "Feature",
             "properties": {"natural": "water", "water": "pond"},
             "geometry": {"type": "Point",
                          "coordinates": [24.73, 59.46]}},
            # Intermittent ditch: flow feature (p50's), dropped.
            {"type": "Feature",
             "properties": {"waterway": "ditch", "intermittent": "yes"},
             "geometry": {"type": "LineString", "coordinates": [
                 [24.74, 59.44], [24.75, 59.44]]}},
            # Intermittent wetland: p50/p257's, dropped.
            {"type": "Feature",
             "properties": {"natural": "wetland",
                            "intermittent": "yes"},
             "geometry": {"type": "Point",
                          "coordinates": [24.75, 59.46]}},
            # Untagged member pulled in for relation completeness: dropped.
            {"type": "Feature", "properties": {},
             "geometry": {"type": "Point", "coordinates": [24.61, 59.31]}},
        ]}), encoding="utf-8")
    return str(tmp_path)


def test_reader_on_fixture(tmp_path):
    snap = _snap_dir(tmp_path)
    pts, stats = G.read_vernalpool_points(snap)
    assert stats["ponds"] == 1
    assert stats["basins"] == 1
    assert stats["twins_dropped"] == 1
    # Permanent pond + ditch + wetland + untagged all dropped.
    assert stats["untagged_dropped"] == 4
    assert len(pts) > 0


def test_write_points_shape(tmp_path):
    doc = G.write_points(str(tmp_path), "vernalpool",
                         [(24.70, 59.44), (24.70001, 59.44001)])
    assert len(doc) == 1  # 20 m twins merge
    assert set(doc[0]) == {"lon", "lat"}
    back = json.loads((tmp_path / "derived-vernalpool.json").read_text(encoding="utf-8"))
    assert back == doc


def test_wire_doc_shape():
    g = tiny_grid()
    vals = bytes([50] * (g.cols * g.rows))
    doc = G.encode_wire(g, vals, "vernalpool")
    assert doc["cols"] == g.cols and doc["rows"] == g.rows
    assert doc["bbox"] == {"minlon": g.bbox[0], "minlat": g.bbox[1],
                           "maxlon": g.bbox[2], "maxlat": g.bbox[3]}
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    assert doc["half"] == 300.0 and doc["sigma"] == 0.3
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}
    assert G.contract_of("vernalpool") == (300.0, 0.3)


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G08D_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group08d.ts"), encoding="utf-8").read()
    m = re.search(r"G08D_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G08D_CAL block not found in layers_group08d.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G08D_CAL
    assert flat["vernalpool"]["halfM"] == py["vernalpool"]["half_m"]
    assert flat["vernalpool"]["sigma"] == py["vernalpool"]["sigma"]
