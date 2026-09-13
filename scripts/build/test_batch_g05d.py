"""Group 5 plans-D builder tests (issue #164): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group05d.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g05d_plans as G


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


def test_first_tourism_parses_first_semi_value():
    assert G.first_tourism("hotel") == "hotel"
    assert G.first_tourism("apartment;yes") == "apartment"
    assert G.first_tourism("  hostel ") == "hostel"
    assert G.first_tourism(None) == ""
    assert G.first_tourism("") == ""


def test_keep_strstay_threshold():
    assert G.keep_strstay({"tourism": "apartment"})
    assert G.keep_strstay({"tourism": "guest_house"})
    assert G.keep_strstay({"tourism": "hostel"})
    assert G.keep_strstay({"tourism": "hotel"})
    assert G.keep_strstay({"tourism": "motel"})
    assert G.keep_strstay({"tourism": "hotel;apartments"})
    # Food/drink foot traffic is not overnight-guest signal.
    assert not G.keep_strstay({"tourism": "restaurant"})
    assert not G.keep_strstay({"amenity": "bar"})
    assert not G.keep_strstay({"tourism": "museum"})
    assert not G.keep_strstay({"building": "yes"})  # untagged member drops out
    assert not G.keep_strstay({})
    assert not G.keep_strstay(None)


def test_read_stay_points_keeps_rings_and_points(tmp_path):
    ring = [[24.75, 59.44], [24.751, 59.44], [24.751, 59.441],
            [24.75, 59.441], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "stay.geojson"), [
        pt(24.75, 59.44, {"tourism": "apartment"}),
        line(ring, {"tourism": "hotel"}),  # footprint ring, not a twin
        mpoly(ring, {"tourism": "hostel"}),
        pt(24.76, 59.45, {"tourism": "restaurant"}),  # no beds
        pt(24.76, 59.45, {"building": "yes"}),  # untagged member
    ])
    pts, stats = G.read_stay_points(p)
    assert stats["beds"] == 3
    assert stats["dropped"] == 2
    assert len(pts) >= 3


def test_avoid_from_half():
    assert G.avoid_from_half(0, 0.35) == 0
    assert G.avoid_from_half(0.35, 0.35) == 50
    assert G.avoid_from_half(float("inf"), 0.35) == 100
    assert G.avoid_from_half(1e9, 0.35) > 99.99


def test_field_end_to_end_on_tiny_grid(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "stay.geojson"), [
        pt(lon0, 59.44 + 150 / 110570.0, {"tourism": "hotel"}),
    ])
    raw, _ = G.read_stay_points(p)
    dist = G.dijkstra_km(g, G.cells_of_points(g, raw))
    vals = G.score_avoid(dist, G.G05D_CAL["strsat"]["half"])
    k = g.cell_of(lon0, 59.44 + 150 / 110570.0)
    assert vals[k] <= 30  # ~150 m from mapped beds reads saturated
    far = g.cell_of(lon0, 59.44)
    assert vals[far] > vals[k]


def test_score_avoid_endpoints():
    g = tiny_grid()
    n = g.cols * g.rows
    dist = [0.0] * n
    vals = G.score_avoid(dist, 0.35)
    assert set(vals) == {0}
    dist = [float("inf")] * n
    vals = G.score_avoid(dist, 0.35)
    assert set(vals) == {100}


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("strsat")
    assert half == 0.35 and sigma == 0.5
    doc = G.encode_wire(g, bytearray([12]) * (g.cols * g.rows))
    assert doc["half"] == 0.35 and doc["sigma"] == 0.5
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {12}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G05D_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group05d.ts"), encoding="utf-8").read()
    m = re.search(r"G05D_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G05D_CAL block not found in layers_group05d.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G05D_CAL
    assert flat["strsat"]["half"] == py["strsat"]["half"]
    assert flat["strsat"]["sigma"] == py["strsat"]["sigma"]


def test_builder_is_hermetic_no_network_imports():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "batch_g05d_plans.py")).read()
    for mod in ("urllib", "requests", "socket", "http.client", "overpass"):
        assert mod not in src
