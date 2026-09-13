"""Hermetic unit tests for the Group 8 flood/climate-C builder (issue #169).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g08c_flood.py -q
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g08c_flood as D


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return D.Grid([24.74, 59.43, 24.74 + n * step / 1000 / D.LON_KM,
                   59.43 + n * step / 1000 / D.LAT_KM], step)


def write_doc(tmp_path, name, features):
    p = str(tmp_path / name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection",
                   "features": [{"type": "Feature", "properties": p,
                                 "geometry": g} for p, g in features]}, f)
    return p


# ---------------------------------------------------------------------------
# Predicates.
# ---------------------------------------------------------------------------

def test_slide_predicate():
    assert D.is_slide_source({"natural": "cliff"})
    assert D.is_slide_source({"natural": "earth_bank"})
    # Rivers/wetlands/water are p50 drainage's signal, not slopes.
    assert not D.is_slide_source({"natural": "water"})
    assert not D.is_slide_source({"natural": "wetland"})
    assert not D.is_slide_source({"waterway": "river"})
    assert not D.is_slide_source({"man_made": "embankment"})
    assert not D.is_slide_source({})
    assert not D.is_slide_source(None)


def test_surge_road_predicate():
    for v in ("motorway", "trunk", "primary", "secondary", "tertiary",
              "unclassified", "residential", "living_street", "service",
              "road"):
        assert D.is_surge_road({"highway": v}), v
    # Trails and footways are OUT: the param asks about STREETS.
    for v in ("track", "path", "footway", "cycleway", "steps",
              "pedestrian", "crossing", "traffic_signals"):
        assert not D.is_surge_road({"highway": v}), v
    # flood_prone tags add nothing: forest tracks stay out.
    assert not D.is_surge_road({"highway": "track", "flood_prone": "yes"})
    assert not D.is_surge_road({})
    assert not D.is_surge_road(None)


# ---------------------------------------------------------------------------
# slidebuf field on a tiny grid.
# ---------------------------------------------------------------------------

def test_slidebuf_field_end_to_end_on_tiny_grid(tmp_path):
    # One cliff line across the grid centre: centre cells read 0,
    # halfM (100 m) out reads 50, far corners stay high (Dijkstra has
    # no cutoff — every cell knows its distance, unlike count kernels).
    g = tiny_grid(25)
    clon, clat = g.center_of(12 * g.cols + 12)
    half = D.G08C_CAL["slidebuf"]["half_m"] / 1000.0
    line = {"type": "LineString",
            "coordinates": [[clon - half / D.LON_KM, clat],
                            [clon + half / D.LON_KM, clat]]}
    p = write_doc(tmp_path, "cliff.geojson", [({"natural": "cliff"}, line)])
    cells, stats = D.read_line_sources(g, p, D.is_slide_source)
    assert stats["kept"] == 1
    assert len(cells) > 0
    vals, _ = D.build_layer("slidebuf", g, cells, stats)
    k = g.cell_of(clon, clat)
    assert k is not None
    assert vals[k] == 0
    # One halfM (100 m) north of the line: grid quantization puts the
    # query cell centre exactly one 75 m row above the source row, so
    # the exact-grid field reads round(100*75/175) = 43, not 50.
    q = g.cell_of(clon, clat + half / D.LAT_KM)
    assert q is not None
    assert vals[q] == 43
    # Far corner reads high (distant, never unknown for Dijkstra).
    assert vals[0] > 90


def test_slidebuf_river_excluded(tmp_path):
    g = tiny_grid()
    clon, clat = g.center_of(4 * g.cols + 4)
    pt = {"type": "Point", "coordinates": [clon, clat]}
    p = write_doc(tmp_path, "x.geojson",
                  [({"waterway": "river"}, pt),
                   ({"natural": "wetland"}, pt)])
    _, stats = D.read_line_sources(g, p, D.is_slide_source)
    assert stats["kept"] == 0


# ---------------------------------------------------------------------------
# Surge gate: only band carriageways become sources.
# ---------------------------------------------------------------------------

def _pt(lon, lat):
    return {"type": "Point", "coordinates": [lon, lat]}


def test_surge_gate_keeps_only_band_carriageways(tmp_path):
    g = tiny_grid(25)
    clon, clat = g.center_of(12 * g.cols + 12)
    shore = write_doc(tmp_path, "shore.geojson",
                      [({"natural": "coastline"}, _pt(clon, clat))])
    near_lon = clon + 100.0 / 1000.0 / D.LON_KM   # 100 m east: in band
    edge_lon = clon + 149.0 / 1000.0 / D.LON_KM   # 149 m east: band edge
    far_lon = clon + 500.0 / 1000.0 / D.LON_KM    # 500 m east: out
    roads = write_doc(tmp_path, "roads.geojson", [
        ({"highway": "secondary", "name": "in-band"}, _pt(near_lon, clat)),
        ({"highway": "residential", "name": "band-edge"}, _pt(edge_lon, clat)),
        ({"highway": "secondary", "name": "out-band"}, _pt(far_lon, clat)),
        ({"highway": "track", "name": "trail"}, _pt(near_lon, clat)),
        ({"natural": "water"}, _pt(near_lon, clat)),
    ])
    cells, stats = D.gate_roads_to_surge_band(g, shore, roads)
    # In-band + band-edge carriageways gate; the 149 m-east vertex pins
    # the anisotropic bucket fix (lon-degrees are ~77 m at 59N, so a
    # naive square-degree hash misses it).
    assert stats["kept"] == 2
    assert stats["kept_verts"] == 2
    assert stats["shore_verts"] == 1
    k = g.cell_of(near_lon, clat)
    assert k is not None and k in cells
    kf = g.cell_of(far_lon, clat)
    assert kf is None or kf not in cells


def test_surge_gate_lakes_do_not_gate(tmp_path):
    g = tiny_grid()
    clon, clat = g.center_of(4 * g.cols + 4)
    shore = write_doc(tmp_path, "shore.geojson",
                      [({"natural": "water"}, _pt(clon, clat))])
    roads = write_doc(tmp_path, "roads.geojson",
                      [({"highway": "residential"}, _pt(clon, clat))])
    cells, stats = D.gate_roads_to_surge_band(g, shore, roads)
    assert stats["kept_verts"] == 0
    assert len(cells) == 0


def test_surgeroad_field_scores_zero_on_exposed_street(tmp_path):
    g = tiny_grid(25)
    clon, clat = g.center_of(12 * g.cols + 12)
    shore = write_doc(tmp_path, "shore.geojson",
                      [({"natural": "coastline"}, _pt(clon, clat))])
    roads = write_doc(tmp_path, "roads.geojson",
                      [({"highway": "residential"}, _pt(clon, clat))])
    cells, stats = D.gate_roads_to_surge_band(g, shore, roads)
    vals, _ = D.build_layer("surgeroad", g, cells, stats)
    k = g.cell_of(clon, clat)
    assert k is not None
    assert vals[k] == 0
    # One halfM (150 m = exactly two 75 m rows) out reads 50.
    q = g.cell_of(clon, clat + 150.0 / 1000.0 / D.LAT_KM)
    assert q is not None
    assert vals[q] == 50


# ---------------------------------------------------------------------------
# Wire contract + TS drift guard.
# ---------------------------------------------------------------------------

def test_wire_contract_and_encoding(tmp_path):
    g = tiny_grid()
    assert D.contract_of("surgeroad") == (150.0, 0.3)
    assert D.contract_of("slidebuf") == (100.0, 0.3)
    doc = D.encode_wire(g, bytearray([0, 50, 100] + [255] * (g.cols * g.rows - 3)),
                        "slidebuf")
    assert doc["half"] == 100.0 and doc["sigma"] == 0.3
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert raw[0] == 0 and raw[1] == 50 and raw[2] == 100


def test_quiet_formula_and_overlay_thin():
    assert D.quiet_from_half(0.0, 150.0) == 0.0
    assert D.quiet_from_half(150.0, 150.0) == 50.0
    assert D.quiet_from_half(float("inf"), 100.0) == 100.0
    pts = [(24.0 + i * 0.001, 59.0) for i in range(5000)]
    th = D.thin_overlay(pts)
    assert len(th) == D.OVERLAY_CAP
    assert th[0] == {"lon": pts[0][0], "lat": pts[0][1]}
    # Twins collapse: identical points dedupe before the cap.
    assert len(D.thin_overlay([(24.8, 59.44)] * 3000)) == 1


def test_ts_calibration_drift_guard():
    # Parse G08C_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group08c.ts"), encoding="utf-8").read()
    m = re.search(r"G08C_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G08C_CAL block not found in layers_group08c.ts"
    pairs = {a: (b, c) for a, b, c in
               re.findall(r"(\w+): \{ halfM: (\d+), sigma: ([\d.]+) \}", m.group(1))}
    assert set(pairs) == {"surgeroad", "slidebuf"}
    py = D.G08C_CAL
    for layer, (half, sigma) in pairs.items():
        assert float(half) == py[layer]["half_m"], layer
        assert float(sigma) == py[layer]["sigma"], layer
