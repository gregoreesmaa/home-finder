"""Hermetic unit tests for the Group 5 plans-B builder (issue #162).

No network, no snapshot: grids are tiny, fixtures inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_g05b.py -q
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

import batch_g05b_plans as B


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return B.Grid([24.74, 59.43, 24.74 + n * step / 1000 / B.LON_KM,
                   59.43 + n * step / 1000 / B.LAT_KM], step)


def _poi_geojson(path, coords_props):
    with open(path, "w", encoding="utf-8") as f:
        for i, (lon, lat, props) in enumerate(coords_props):
            f.write(json.dumps(
                {"type": "Feature", "id": "n%d" % i, "properties": props,
                 "geometry": {"type": "Point",
                              "coordinates": [lon, lat]}}) + "\n")
    return path


# ---------------------------------------------------------------------------
# Garden predicate.
# ---------------------------------------------------------------------------

def test_keep_garden_predicate():
    # Allotments + community/kitchen gardens are sources.
    assert B.keep_garden({"landuse": "allotments"})
    assert B.keep_garden({"leisure": "garden", "garden:type": "community"})
    assert B.keep_garden({"leisure": "garden", "garden:style": "kitchen"})
    # Bare residential gardens are OUT: a backyard is not opportunity...
    assert not B.keep_garden({"leisure": "garden"})
    assert not B.keep_garden({"leisure": "garden", "garden:type": "residential"})
    # ...orchards/farmland stay p409 agrifield's (no re-skin)...
    assert not B.keep_garden({"landuse": "orchard"})
    assert not B.keep_garden({"landuse": "farmland"})
    assert not B.keep_garden({"landuse": "meadow"})
    # ...and member junk never matches.
    assert not B.keep_garden({"barrier": "gate"})
    assert not B.keep_garden({"addr:street": "Niidi"})
    assert not B.keep_garden({})
    assert not B.keep_garden(None)


def test_keep_buildout_predicate():
    assert B.keep_buildout({"landuse": "construction"})
    assert B.keep_buildout({"landuse": "construction", "construction": "commercial"})
    assert not B.keep_buildout({"landuse": "residential"})
    assert not B.keep_buildout({"landuse": "brownfield"})
    assert not B.keep_buildout({"barrier": "gate", "access": "no"})
    assert not B.keep_buildout({})
    assert not B.keep_buildout(None)


def test_garden_poi_resolution(tmp_path):
    p = str(tmp_path / "gard.geojson")
    feats = [
        {"type": "Feature", "id": "n1",
         "properties": {"leisure": "garden", "garden:type": "community"},
         "geometry": {"type": "Point", "coordinates": [24.755, 59.438]}},
        {"type": "Feature", "id": "n2",
         "properties": {"landuse": "allotments"},
         "geometry": {"type": "Point", "coordinates": [24.760, 59.440]}},
        {"type": "Feature", "id": "n3",
         "properties": {"leisure": "garden"},
         "geometry": {"type": "Point", "coordinates": [24.770, 59.445]}},
        {"type": "Feature", "id": "n4",
         "properties": {"landuse": "orchard"},
         "geometry": {"type": "Point", "coordinates": [24.780, 59.450]}},
    ]
    with open(p, "w", encoding="utf-8") as f:
        for feat in feats:
            f.write(json.dumps(feat) + "\n")
    pts, stats = wr.resolve_pois(p, B.keep_garden)
    assert len(pts) == 2  # community + allotments; backyard + orchard out
    assert stats["kept"] == 2


def test_count_field_end_to_end_on_tiny_grid(tmp_path):
    # One garden at the grid centre: the facility cell stacks kernel ~1
    # (centroid offset only), scoring 100*1/2 = 50 at half 1.
    # Neighbours decay, far cells stay unknown (255), never zero.
    g = tiny_grid(25)
    clon, clat = g.center_of(12 * g.cols + 12)
    p = _poi_geojson(str(tmp_path / "gard.geojson"),
                     [(clon, clat, {"landuse": "allotments"})])
    acc, feats = B.build_count_field(g, 1, 0.3, p, B.keep_garden, "gardens")
    assert len(feats) == 1
    score_of = B._area_score(acc, 1)
    k = g.cell_of(clon, clat)
    assert k is not None
    assert score_of(k) == pytest.approx(50.0, abs=3.0)
    vals = B.score_bytes(g, score_of)
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


def test_buildout_half_two_needs_two_sites(tmp_path):
    # One pit at half 2 reads 100*1/3 = 33; two co-located sites
    # (>20 m apart) stack S ~2, scoring 100*2/4 = 50.
    g = tiny_grid(25)
    clon, clat = g.center_of(12 * g.cols + 12)
    p = _poi_geojson(str(tmp_path / "con.geojson"),
                     [(clon, clat, {"landuse": "construction"})])
    acc, feats = B.build_count_field(g, 2, 0.3, p, B.keep_buildout, "buildout")
    assert len(feats) == 1
    assert B._area_score(acc, 2)(g.cell_of(clon, clat)) == pytest.approx(33.0, abs=3.0)
    p2 = _poi_geojson(str(tmp_path / "con2.geojson"),
                      [(clon, clat, {"landuse": "construction"}),
                       (clon + 0.0006, clat, {"landuse": "construction"})])
    acc2, feats2 = B.build_count_field(g, 2, 0.3, p2, B.keep_buildout, "buildout")
    assert len(feats2) == 2
    assert B._area_score(acc2, 2)(g.cell_of(clon, clat)) == pytest.approx(50.0, abs=5.0)


def test_dedupe_merges_ring_twins():
    # Same garden exported as LineString + MultiPolygon ring pair
    # collapses to one dot; distinct beds stay separate.
    pts = [(24.75, 59.43, 1.0), (24.75001, 59.43001, 1.0), (24.76, 59.44, 1.0)]
    out = B.dedupe_points(pts)
    assert len(out) == 2
    assert out[0][:2] == (24.75, 59.43)


def test_wire_contract_shape():
    g = tiny_grid()
    half, sigma = B.contract_of("gardens")
    assert half == 1 and sigma == 0.3
    half_b, sigma_b = B.contract_of("buildout")
    assert half_b == 2 and sigma_b == 0.3
    doc = B.encode_wire(g, bytearray([50]) * (g.cols * g.rows), "gardens")
    assert doc["half"] == 1 and doc["sigma"] == 0.3
    bdoc = B.encode_wire(g, bytearray([33]) * (g.cols * g.rows), "buildout")
    assert bdoc["half"] == 2 and bdoc["sigma"] == 0.3
    assert doc["per"] == 0 and doc["cap"] == 0
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse G05B_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group05b.ts"), encoding="utf-8").read()
    m = re.search(r"G05B_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "G05B_CAL block not found in layers_group05b.ts"
    body = m.group(1)
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", body):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = B.G05B_CAL
    assert flat["gardens"]["half"] == py["gardens"]["half"]
    assert flat["gardens"]["sigma"] == py["gardens"]["sigma"]
    assert flat["buildout"]["half"] == py["buildout"]["half"]
    assert flat["buildout"]["sigma"] == py["buildout"]["sigma"]
