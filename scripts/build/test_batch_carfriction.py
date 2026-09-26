"""Car-friction builder tests (issue #829): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_p4_carfriction.ts.
"""

import base64
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_carfriction as G


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


def test_keep_restriction_is_no_private_permit_destination_customers():
    # Only genuinely car-restrictive motor-vehicle values count —
    # permissive values and untagged filter artefacts are dropped.
    assert G.keep_restriction({"motor_vehicle": "no"})
    assert G.keep_restriction({"motor_vehicle": "private"})
    assert G.keep_restriction({"motor_vehicle": "permit"})
    assert G.keep_restriction({"motor_vehicle": "destination"})
    assert G.keep_restriction({"motor_vehicle": "customers"})
    assert G.keep_restriction({"vehicle": "no"})
    assert G.keep_restriction({"vehicle": "private"})
    assert G.keep_restriction({"motorcar": "no"})
    assert not G.keep_restriction({"motor_vehicle": "yes"})
    assert not G.keep_restriction({"motor_vehicle": "designated"})
    assert not G.keep_restriction({"motor_vehicle": "permissive"})
    assert not G.keep_restriction({"motor_vehicle": "delivery"})
    assert not G.keep_restriction({"amenity": "parking"})
    assert not G.keep_restriction({"highway": "footway"})
    assert not G.keep_restriction({})
    assert not G.keep_restriction(None)


def test_read_restriction_points_centroid_per_closure(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "restr.geojson"), [
        pt(24.75, 59.44, {"motor_vehicle": "no"}),
        poly(ring, {"motor_vehicle": "private"}),
        mpoly(ring, {"vehicle": "destination"}),
        pt(24.76, 59.45, {"motor_vehicle": "yes"}),  # permissive, out
        pt(24.76, 59.45, {}),
    ])
    pts, stats = G.read_restriction_points(p)
    assert stats["closures"] == 3
    assert stats["dropped"] == 2
    # One friction unit per feature: point + polygon centroid + multipolygon.
    assert len(pts) == 3
    assert (24.75, 59.44) in pts
    # Polygon bbox centre, not stride-sampled rings.
    assert any(abs(lon - 24.751) < 1e-9 and abs(lat - 59.441) < 1e-9
               for lon, lat in pts)


def test_read_restriction_points_densifies_closed_streets(tmp_path):
    # A 100 m no-entry street is more friction than a 10 m gate.
    p = write_geojson(str(tmp_path / "street.geojson"), [
        line([[24.74, 59.44], [24.7415, 59.44]], {"motor_vehicle": "no"}),
    ])
    pts, stats = G.read_restriction_points(p)
    assert stats["closures"] == 1
    assert len(pts) > 1  # densified, not a single centroid


def test_bbox_center_handles_nesting():
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    assert G._bbox_center([ring]) == pytest.approx((24.751, 59.441))
    assert G._bbox_center([]) is None


def test_sparse_score_falls_with_density_half():
    assert G.sparse_score(0, 60) == 100  # measured open, honestly known
    assert G.sparse_score(60, 60) == 50
    assert G.sparse_score(180, 60) == 25


def test_kernel_field_scores_dense_low_open_high_desert_unknown():
    # 4-sigma cutoff is 1.2 km: the desert probe sits 1.5 km out.
    # Friction half (60): a lone barrier still reads ~open, a dense
    # old-town-like pocket reads bad.
    g = tiny_grid(60)
    lon0, lat0 = 24.74, 59.44
    acc = G.count_kernel_field(g, [(lon0, lat0)],
                               G.CARFRICTION_CAL["carfriction"]["sigma"])
    vals = G.score_sparse_cells(g, acc,
                                G.CARFRICTION_CAL["carfriction"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] > 90  # one barrier does not paint the street red
    dense = G.count_kernel_field(g, [(lon0, lat0)] * 200,
                                 G.CARFRICTION_CAL["carfriction"]["sigma"])
    dvals = G.score_sparse_cells(g, dense,
                                 G.CARFRICTION_CAL["carfriction"]["half"])
    assert dvals[k] < 50  # a closure-lined pocket reads high friction
    desert = g.cell_of(lon0 + 1500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 255  # desert stays honestly unknown


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = G.contract_of("carfriction")
    assert half == 60.0 and sigma == 0.3
    doc = G.encode_wire(g, bytearray([28]) * (g.cols * g.rows), "carfriction")
    assert doc["half"] == 60.0 and doc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {28}


def test_main_writes_outdir_master_and_points(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    src = write_geojson(str(tmp_path / "restr.geojson"), [
        pt(24.75, 59.44, {"motor_vehicle": "no"}),
        poly(ring, {"motor_vehicle": "private"}),
    ])
    outdir = str(tmp_path / "snap")
    G.main(["--layer", "carfriction", "--restrictions", src,
            "--bbox", "24.7", "59.4", "24.8", "59.5",
            "--outdir", outdir, "--write-points"])
    master = os.path.join(outdir, "carfriction-walk-raster.json")
    assert os.path.isfile(master)
    doc = json.load(open(master, encoding="utf-8"))
    assert doc["half"] == 60.0 and doc["sigma"] == 0.3
    assert doc["unknown"] == 255
    derived = os.path.join(outdir, "derived-carfriction.json")
    assert os.path.isfile(derived)
    assert len(json.load(open(derived, encoding="utf-8"))) > 0


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse CARFRICTION_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_p4_carfriction.ts"), encoding="utf-8").read()
    m = re.search(r"CARFRICTION_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "CARFRICTION_CAL block not found in layers_p4_carfriction.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.CARFRICTION_CAL
    assert flat["carfriction"]["half"] == py["carfriction"]["half"]
    assert flat["carfriction"]["sigma"] == py["carfriction"]["sigma"]
