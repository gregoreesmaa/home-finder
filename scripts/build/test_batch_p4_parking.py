"""P4 OSM parking builder tests (issue #479): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_p4_parking.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_p4_parking as G


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


def poly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "Polygon", "coordinates": [ring]}}


def mpoly(ring, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "MultiPolygon",
                         "coordinates": [[ring]]}}


def line(coords, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords}}


def test_keep_parking_is_bays_plus_lots():
    # Bays + lots BOTH count (p4_osm.md verdict) — the on-street
    # subtype split lives in the scorer mapping, never here.
    assert G.keep_parking({"amenity": "parking"})
    assert G.keep_parking({"amenity": "parking", "parking": "street_side"})
    assert G.keep_parking({"amenity": "parking", "parking": "surface"})
    assert G.keep_parking({"amenity": "parking;garage"})
    assert not G.keep_parking({"amenity": "garage"})
    assert not G.keep_parking({"highway": "footway"})
    assert not G.keep_parking({})
    assert not G.keep_parking(None)


def test_read_parking_points_centroid_per_lot(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "parking.geojson"), [
        pt(24.75, 59.44, {"amenity": "parking"}),
        poly(ring, {"amenity": "parking"}),
        mpoly(ring, {"amenity": "parking", "parking": "street_side"}),
        pt(24.76, 59.45, {"amenity": "garage"}),  # not parking, out
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_parking_points(p)
    assert stats["lots"] == 3
    assert stats["dropped"] == 2
    # One parking unit per feature: point + polygon centroid + multipolygon.
    assert len(pts) == 3
    assert (24.75, 59.44) in pts
    # Polygon bbox centre, not stride-sampled rings.
    assert any(abs(lon - 24.751) < 1e-9 and abs(lat - 59.441) < 1e-9
               for lon, lat in pts)


def test_read_parking_points_densifies_bay_lines(tmp_path):
    # A 100 m street bay is several bays, not one dot.
    p = write_geojson(str(tmp_path / "bay.geojson"), [
        line([[24.74, 59.44], [24.7415, 59.44]], {"amenity": "parking"}),
    ])
    pts, stats = G.read_parking_points(p)
    assert stats["lots"] == 1
    assert len(pts) > 1  # densified, not a single centroid


def test_bbox_center_handles_nesting():
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    assert G._bbox_center([ring]) == pytest.approx((24.751, 59.441))
    assert G._bbox_center([]) is None


def test_area_score_saturates_with_density_half():
    assert G.area_score(0, 75) == 0
    assert G.area_score(75, 75) == 50
    assert G.area_score(225, 75) == 75


def test_kernel_field_scores_near_high_far_unknown():
    # 4-sigma cutoff is 3.2 km: the desert probe sits 3.5 km out.
    # Density half (75): a lone lot reads ~0, a dense pocket green.
    g = tiny_grid(60)
    lon0, lat0 = 24.74, 59.44
    acc = G.count_kernel_field(g, [(lon0, lat0)],
                               G.P4PARK_CAL["parking"]["sigma"])
    vals = G.score_area_cells(g, acc, G.P4PARK_CAL["parking"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] < 50  # one lot does not paint the street green
    dense = G.count_kernel_field(g, [(lon0, lat0)] * 200,
                                 G.P4PARK_CAL["parking"]["sigma"])
    dvals = G.score_area_cells(g, dense, G.P4PARK_CAL["parking"]["half"])
    assert dvals[k] >= 50  # a lot-lined pocket reads dense-mapped
    desert = g.cell_of(lon0 + 3500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 255  # desert stays honestly unknown


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("parking")
    assert half == 75.0 and sigma == 0.8
    doc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "parking")
    assert doc["half"] == 75.0 and doc["sigma"] == 0.8
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse P4PARK_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_p4_parking.ts"), encoding="utf-8").read()
    m = re.search(r"P4PARK_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "P4PARK_CAL block not found in layers_p4_parking.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.P4PARK_CAL
    assert flat["parking"]["half"] == py["parking"]["half"]
    assert flat["parking"]["sigma"] == py["parking"]["sigma"]
