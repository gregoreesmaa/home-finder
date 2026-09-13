"""P4 OSM walkability + darkness builder tests (issue #480): hermetic tests.

No network, no snapshot: readers run on tiny fixture geojson files,
fields on a tiny grid, and the TS calibration drift guard parses the
checked-in layers_p4osm.ts.
"""

import base64
import json
import math
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_p4_osmwalk as G


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


def line(coords, props):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": "LineString", "coordinates": coords}}


def test_keep_evidence_is_verified_tags_only():
    assert G.keep_evidence("footway", {"highway": "footway"})
    assert G.keep_evidence("footway", {"highway": "footway;path"})
    assert not G.keep_evidence("footway", {"highway": "residential"})
    assert G.keep_evidence("sidewalk", {"sidewalk": "both"})
    assert G.keep_evidence("sidewalk", {"sidewalk": "left"})
    # sidewalk=no is evidence of ABSENCE, never of presence.
    assert not G.keep_evidence("sidewalk", {"sidewalk": "no"})
    assert not G.keep_evidence("sidewalk", {"sidewalk": ""})
    assert not G.keep_evidence("sidewalk", {})
    assert G.keep_evidence("asphalt", {"surface": "asphalt"})
    assert G.keep_evidence("asphalt", {"surface": "asphalt;paving_stones"})
    assert not G.keep_evidence("asphalt", {"surface": "gravel"})
    assert G.keep_evidence("lit", {"lit": "yes"})
    assert not G.keep_evidence("lit", {"lit": "no"})
    assert not G.keep_evidence("lit", {"highway": "street_lamp"})
    assert not G.keep_evidence("lit", None)
    assert not G.keep_evidence("footway", None)


def test_read_evidence_points_feeding_rules(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "lit.geojson"), [
        pt(24.75, 59.44, {"lit": "yes"}),  # mapped lamp feeds directly
        poly(ring, {"lit": "yes"}),  # one centroid per area, not rings
        pt(24.76, 59.45, {"lit": "no"}),  # out
        pt(24.76, 59.45, {}),  # untagged relation member, out
    ])
    pts, stats = G.read_evidence_points(p, "lit")
    assert stats == {"kept": 2, "dropped": 2}
    assert len(pts) == 2
    assert (24.75, 59.44) in pts
    assert any(abs(lon - 24.751) < 1e-9 and abs(lat - 59.441) < 1e-9
               for lon, lat in pts)


def test_read_evidence_points_downsamples_dense_lines(tmp_path):
    # A 100 m footway feeds ~3 dots (40 m spacing), not every vertex
    # and not one centroid: one dot per 40 m of mapped line.
    coords = [[24.74 + i * 0.0002, 59.44] for i in range(30)]
    p = write_geojson(str(tmp_path / "footway.geojson"), [
        line(coords, {"highway": "footway"}),
    ])
    pts, stats = G.read_evidence_points(p, "footway")
    assert stats["kept"] == 1
    # 332 m of line at 40 m spacing -> ~9 dots.
    assert 5 <= len(pts) <= 12


def test_read_evidence_points_closed_line_is_one_unit(tmp_path):
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    p = write_geojson(str(tmp_path / "closed.geojson"), [
        line(ring, {"surface": "asphalt"}),
    ])
    pts, stats = G.read_evidence_points(p, "asphalt")
    assert stats["kept"] == 1
    assert len(pts) == 1  # closed ring -> centroid, never densified


def test_bbox_center_handles_nesting():
    ring = [[24.75, 59.44], [24.752, 59.44], [24.752, 59.442],
            [24.75, 59.442], [24.75, 59.44]]
    assert G._bbox_center([ring]) == pytest.approx((24.751, 59.441))
    assert G._bbox_center([]) is None


def test_area_score_saturates_with_density_half():
    assert G.area_score(0, 1000) == 0
    assert G.area_score(1000, 1000) == 50
    assert G.area_score(3000, 1000) == 75


def test_stencil_shape_and_cutoff():
    st = G.stencil_weights(0.5, 75.0)
    by_off = {(dx, dy): w for dx, dy, w in st}
    assert by_off[(0, 0)] == pytest.approx(1.0)
    # Monotone decay along the axis, 4-sigma cutoff at 2 km.
    assert by_off[(1, 0)] > by_off[(10, 0)] > by_off[(20, 0)]
    assert (27, 0) not in by_off  # 27*75 m = 2.025 km > 2.0 km cutoff
    assert (26, 0) in by_off
    assert len(st) == pytest.approx(3.14159 * (2000 / 75) ** 2, rel=0.05)


def test_stencil_matches_pointwise():
    # The stencil sweep must equal the per-point sweep (sibling math)
    # for sources on cell centres: same kernel, same cutoff.
    g = tiny_grid(60)
    lon0, lat0 = g.center_of(g.cell_of(24.745, 59.442))
    acc_point = {}
    for lon, lat in [(lon0, lat0)] * 3:
        for k in range(g.cols * g.rows):
            clon, clat = g.center_of(k)
            d = G.hav_km(lon, lat, clon, clat)
            if d <= 2.0:
                acc_point[k] = acc_point.get(k, 0.0) + G.kernel(d, 0.5)
    snapped = G.snap_sources([(lon0, lat0)] * 3, cell_m=75.0)
    acc_stencil = G.count_kernel_field(g, snapped, 0.5, snap_m=75.0)
    assert set(acc_stencil) == set(acc_point)
    for k in acc_point:
        assert acc_stencil[k] == pytest.approx(acc_point[k], rel=1e-9)


def test_snap_sources_keeps_multiplicity():
    cells = G.snap_sources([(24.75, 59.44)] * 7 + [(24.76, 59.45)] * 3)
    assert sorted(cells.values()) == [3, 7]


def test_kernel_field_scores_near_high_far_unknown():
    # Density half (500): coincident dots sum to ~N (kernel <= 1),
    # so a pocket needs hundreds of dots to read green — by design.
    g = tiny_grid(60)
    lon0, lat0 = 24.74, 59.44
    snapped = G.snap_sources([(lon0, lat0)] * 1200)
    acc = G.count_kernel_field(g, snapped, G.P4OSM_CAL["darkness"]["sigma"])
    vals = G.score_area_cells(g, acc, G.P4OSM_CAL["darkness"]["half"])
    k = g.cell_of(lon0, lat0)
    assert vals[k] >= 50  # a lamp-lined pocket reads lit-mapped
    thin = G.count_kernel_field(g, G.snap_sources([(lon0, lat0)] * 20),
                                G.P4OSM_CAL["darkness"]["sigma"])
    thin_vals = G.score_area_cells(g, thin, G.P4OSM_CAL["darkness"]["half"])
    assert thin_vals[k] < 50  # twenty lamps do not paint green alone
    desert = g.cell_of(lon0 + 3500.0 / 1000 / G.LON_KM, lat0)
    assert vals[desert] == 255  # desert stays honestly unknown


def test_thin_overlay_dedupes_twins():
    pts = [(24.75, 59.44)] * 50 + [(24.76, 59.45)] * 50
    out = G.dedupe_cells(pts)
    assert len(out) == 2


def test_wire_contract_shape():
    g = tiny_grid()
    for layer, half in (("blockwalk", 1000.0), ("darkness", 500.0)):
        cal_half, sigma = G.contract_of(layer)
        assert cal_half == half and sigma == 0.5
        doc = G.encode_wire(g, bytearray([50]) * (g.cols * g.rows), layer)
        assert doc["half"] == half and doc["sigma"] == 0.5
        assert doc["per"] == 0 and doc["cap"] == 0
        assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
        raw = base64.b64decode(doc["data"])
        assert len(raw) == g.cols * g.rows
        assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse P4OSM_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_p4osm.ts"), encoding="utf-8").read()
    m = re.search(r"P4OSM_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "P4OSM_CAL block not found in layers_p4osm.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = G.P4OSM_CAL
    for layer in ("blockwalk", "darkness"):
        assert flat[layer]["half"] == py[layer]["half"]
        assert flat[layer]["sigma"] == py[layer]["sigma"]
