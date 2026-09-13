"""Group 17 HOA-rest builder tests (issue #196): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_group17rest.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_g17_rest as G


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


def poly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def test_keep_privroad_shared_not_parcels():
    assert G.keep_privroad({"highway": "service", "access": "private"})
    assert G.keep_privroad({"highway": "track", "access": "private"})
    assert G.keep_privroad({"highway": "unclassified", "access": "private"})
    assert G.keep_privroad({"highway": "residential", "access": "private"})
    assert G.keep_privroad({"highway": "living_street", "access": "private"})
    # A private driveway is not an agreement road; a parking aisle is
    # not a road at all.
    assert not G.keep_privroad({"highway": "service", "service": "driveway",
                                "access": "private"})
    assert not G.keep_privroad({"highway": "service",
                                "service": "parking_aisle",
                                "access": "private"})
    # Public streets carry no burden.
    assert not G.keep_privroad({"highway": "service"})
    assert not G.keep_privroad({"highway": "residential"})
    # A car park is not a road; a footway is not a maintained road.
    assert not G.keep_privroad({"amenity": "parking", "access": "private"})
    assert not G.keep_privroad({"leisure": "pitch", "access": "private"})
    assert not G.keep_privroad({"highway": "footway", "access": "private"})
    assert not G.keep_privroad({"highway": "cycleway", "access": "private"})
    assert not G.keep_privroad({})  # untagged member drops out
    assert not G.keep_privroad(None)


def test_read_priv_points_boundary_only(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "priv.geojson"), [
        pt(24.75, 59.44, {"highway": "service", "access": "private"}),
        line([[24.75, 59.44], [24.751, 59.441]],
             {"highway": "track", "access": "private"}),
        poly(ring, {"highway": "service", "access": "private"}),
        pt(24.76, 59.45, {"highway": "service", "service": "driveway",
                           "access": "private"}),  # single-parcel, out
        pt(24.76, 59.45, {"amenity": "parking",
                           "access": "private"}),  # a car park, not a road
        pt(24.76, 59.45, {"highway": "footway", "access": "private"}),
    ])
    pts, stats = G.read_priv_points(p)
    assert stats["roads"] == 3
    assert stats["dropped"] == 3
    assert len(pts) >= 3


def test_quiet_from_half():
    assert G.quiet_from_half(0, 200) == 0
    assert G.quiet_from_half(200, 200) == 50
    assert G.quiet_from_half(float("inf"), 200) == 100
    assert G.quiet_from_half(1e9, 200) > 99.9


def test_field_end_to_end_on_tiny_grid(tmp_path):
    g = tiny_grid()
    lon0, lat0 = 24.74, 59.44
    p = write_geojson(str(tmp_path / "priv.geojson"), [
        line([[lon0, lat0 + 100 / 110570.0],
              [lon0 + 0.001, lat0 + 100 / 110570.0]],
             {"highway": "service", "access": "private"}),
    ])
    raw, _ = G.read_priv_points(p)
    cells = G.cells_of_points(g, raw)
    dist = G.dijkstra_km(g, cells)
    vals = G.score_distance(dist, G.G17R_CAL["privroad"]["half_m"])
    assert min(vals) <= 40  # ~100 m from a private road reads low-calm
    far = g.cell_of(lon0, lat0)
    assert vals[far] > min(vals)


def test_score_distance_endpoints():
    g = tiny_grid()
    n = g.cols * g.rows
    dist = [0.0] * n
    vals = G.score_distance(dist, 200.0)
    assert set(vals) == {0}
    dist = [float("inf")] * n
    vals = G.score_distance(dist, 200.0)
    assert set(vals) == {100}


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("privroad")
    assert half == 200.0 and sigma == 0.3
    doc = G.encode_wire(g, bytearray([90]) * (g.cols * g.rows))
    assert doc["half"] == 200.0 and doc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {90}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G17R_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group17rest.ts"), encoding="utf-8").read()
    m = re.search(r"G17R_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G17R_CAL block not found in layers_group17rest.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.G17R_CAL
    assert flat["privroad"]["halfM"] == py["privroad"]["half_m"]
    assert flat["privroad"]["sigma"] == py["privroad"]["sigma"]
