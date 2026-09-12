"""Hermetic unit tests for the Group 15 raster builder (issue #116).

No network, no snapshot: the committed demo fixture + tiny grids only.
Run: python3 -m pytest scripts/build/test_batch_g15.py -q
"""

import base64
import json
import os
import re
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# dims_group15.py for the scorer<->builder drift check (same branch).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "services", "scoring"))

import batch_g15_edu as E  # noqa: E402
import dims_group15 as D15  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "batch_g15_demo.geojson")


def tiny_grid(n=9, step=75.0):
    # ~675 m square centred near Tallinn.
    return E.Grid([24.74, 59.43, 24.74 + n * step / 1000 / E.LON_KM,
                   59.43 + n * step / 1000 / E.LAT_KM], step)


def snap_dir(tmp_path):
    osm = tmp_path / "osm"
    osm.mkdir()
    shutil.copy(FIXTURE, osm / "harju-amenities.geojson")
    (osm / "derived-schools.json").write_text(json.dumps([
        {"lon": 24.75, "lat": 59.435, "tags": {"amenity": "school"}},
        {"lon": 24.75, "lat": 59.435, "tags": {"amenity": "school"}},
        {"lon": 24.751, "lat": 59.436, "tags": {"amenity": "school"}},
        {"lon": 24.9, "lat": 59.5, "tags": {"amenity": "kindergarten"}},
    ]), encoding="utf-8")
    return str(tmp_path)


def test_hav_km_lon_scale():
    # 1 degree of longitude at Harjumaa latitude ~57.29 km; latitude ~110.57.
    assert abs(E.hav_km(0.0, 0.0, 1.0, 0.0) - 57.29) < 1e-9
    assert abs(E.hav_km(0.0, 0.0, 0.0, 1.0) - 110.57) < 1e-9


def test_score_endpoints():
    assert E.saturate(0, 6.0) == 0.0
    assert E.saturate(6.0, 6.0) == 50.0
    assert E.quiet_from_half(0.0, 500.0) == 0.0
    assert E.quiet_from_half(500.0, 500.0) == 50.0
    assert E.quiet_from_half(float("inf"), 500.0) == 100.0
    assert E.shore_from_half(0.0, 600.0) == 100.0
    assert E.shore_from_half(600.0, 600.0) == 50.0
    assert E.shore_from_half(float("inf"), 600.0) == 0.0


def test_predicates_match_verified_snapshot_tags():
    assert E.is_school_tags({"amenity": "school"})
    assert not E.is_school_tags({"amenity": "kindergarten"})
    assert E.is_stadium_tags({"leisure": "stadium"})
    assert not E.is_stadium_tags({"leisure": "pitch"})  # no event traffic
    assert E.is_venue_tags({"amenity": "events_venue"})
    assert E.is_venue_tags({"amenity": "marketplace"})
    assert E.is_venue_tags({"tourism": "attraction"})
    # Sibling batch B1 tags stay unclaimed (disjoint layers, #98).
    assert not E.is_venue_tags({"amenity": "theatre"})
    assert not E.is_venue_tags({"tourism": "museum"})
    assert not E.is_venue_tags({"amenity": "community_centre"})
    assert E.is_water_tags({"natural": "water"})
    assert E.is_water_tags({"water": "pond"})
    assert not E.is_water_tags({"amenity": "fountain", "natural": "water"})
    assert not E.is_water_tags({"leisure": "swimming_pool"})
    assert not E.is_water_tags(None)


def test_dijkstra_exact_on_tiny_grid():
    g = tiny_grid()
    src = g.cell_of(*g.center_of(40))  # centre cell
    d = E.dijkstra_km(g, {src})
    assert d[src] == 0.0
    assert abs(d[src + 1] - g.step / 1000.0) < 1e-9
    row = [d[40 + i] for i in range(5)]
    assert row == sorted(row)


def test_count_within_exact():
    g = tiny_grid()
    lon, lat = g.center_of(40)
    acc = E.count_within(g, [(lon, lat)], 1500.0)
    assert acc[40] == 1  # own cell always counts
    assert acc[0] == 1  # whole 675 m grid inside 1.5 km
    acc_tight = E.count_within(g, [(lon, lat)], 10.0)
    assert acc_tight[40] == 1
    assert acc_tight[0] == 0  # far corner outside 10 m
    acc_far = E.count_within(g, [(lon + 1.0, lat)], 1500.0)
    assert all(v == 0 for v in acc_far)  # out-of-grid source ignored


def test_readers_on_fixture(tmp_path):
    snap = snap_dir(tmp_path)
    pts = E.read_school_points(snap)
    assert len(pts) == 2  # dupe collapsed, kindergarten excluded
    stats: dict = {}
    venues = E.read_polygon_points(snap, E.is_venue_tags, "venues", stats)
    assert stats["venues"] == 2  # events_venue point + attraction polygon
    assert len(venues) == 2
    g = E.Grid([24.74, 59.42, 24.77, 59.45], 75.0)
    feats = list(E._iter_geojson(os.path.join(
        snap, "osm", "harju-amenities.geojson")))
    cells = E.read_edge_cells(g, feats, E.is_water_tags, "water", stats)
    assert stats["water"] == 1  # fountain+natural=water excluded
    assert len(cells) > 0
    cells = E.read_edge_cells(g, feats, E.is_stadium_tags, "stadiums", stats)
    assert stats["stadiums"] == 1
    assert len(cells) > 0  # ring densified, not just the centroid


def test_build_layers_on_fixture(tmp_path):
    snap = snap_dir(tmp_path)
    water_path = os.path.join(snap, "osm", "harju-amenities.geojson")
    g = E.Grid([24.74, 59.42, 24.77, 59.45], 75.0)
    stats: dict = {}
    choice = E.build_layer(g, snap, "schoolchoice", stats)
    assert max(choice) > 0  # schools score where they stand
    fest = E.build_layer(g, snap, "festival", stats)
    assert min(fest) < 100  # red near the venue
    assert max(fest) == 100 or 255 in fest or max(fest) > min(fest)
    stad = E.build_layer(g, snap, "stadium", stats)
    assert min(stad) < 100
    water = E.build_layer(g, snap, "weedwater", stats,
                          water_path=water_path)
    assert max(water) > 0  # green at the shore
    red = E.build_layer(g, snap, "redistrict", stats)
    assert max(red) > 0
    with pytest.raises(FileNotFoundError):
        E.build_layer(g, snap, "weedwater", stats)  # no export in tmp snap
    for vals in (choice, fest, stad, water, red):
        assert len(vals) == g.cols * g.rows
        assert all(0 <= v <= 255 for v in vals)
        assert all(v == 255 or 0 <= v <= 100 for v in vals)


def test_wire_doc_shape():
    g = tiny_grid()
    vals = [50] * (g.cols * g.rows)
    doc = E.encode_wire(g, vals, "festival")
    assert doc["cols"] == g.cols and doc["rows"] == g.rows
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    assert doc["half"] == 500.0 and doc["sigma"] == 0.5
    assert doc["per"] == 0 and doc["cap"] == 0
    raw = base64.b64decode(doc["data"])
    assert len(raw) == g.cols * g.rows
    assert set(raw) == {50}


def test_spec_for_matches_ts_bonus():
    # Wire halves/sigmas must equal the TS bonus specs (contract check).
    assert E.spec_for("schoolchoice") == (6.0, 0.5)
    assert E.spec_for("redistrict") == (2.0, 0.8)
    assert E.spec_for("weedwater") == (600.0, 0.5)
    assert E.spec_for("festival") == (500.0, 0.5)
    assert E.spec_for("stadium") == (800.0, 0.8)


def test_py_cal_matches_scorer():
    # Builder and scorer share one calibration; fail on drift.
    assert E.G15_CAL["schoolchoice"]["half"] == D15.CHOICE_HALF
    assert E.G15_CAL["schoolchoice"]["radius_m"] == D15.CHOICE_RADIUS_M
    assert E.G15_CAL["redistrict"]["half"] == D15.DEPEND_HALF
    assert E.G15_CAL["redistrict"]["radius_m"] == D15.DEPEND_RADIUS_M
    assert E.G15_CAL["weedwater"]["half_m"] == D15.WATER_HALF_M
    assert E.G15_CAL["festival"]["half_m"] == D15.VENUE_HALF_M
    assert E.G15_CAL["stadium"]["half_m"] == D15.STADIUM_HALF_M


def test_ts_cal_matches_py_cal():
    # The web fallback must score with the same numbers as this builder;
    # parse GROUP15_CAL out of the TS source and fail on any drift.
    ts = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "apps", "web", "lib",
                           "layers_group15.ts"), encoding="utf-8").read()
    m = re.search(r"GROUP15_CAL = \{(.*?)\} as const", ts, re.S)
    assert m, "GROUP15_CAL block not found in layers_group15.ts"
    flat = {}
    for k, v in re.findall(r"(\w+): \{([^}]*)\}", m.group(1)):
        flat[k] = {kk: float(vv) for kk, vv in
                   re.findall(r"(\w+): ([\d.]+)", v)}
    py = E.G15_CAL
    assert flat["schoolchoice"]["sigma"] == py["schoolchoice"]["sigma"]
    assert flat["schoolchoice"]["radiusM"] == py["schoolchoice"]["radius_m"]
    assert flat["schoolchoice"]["half"] == py["schoolchoice"]["half"]
    assert flat["redistrict"]["sigma"] == py["redistrict"]["sigma"]
    assert flat["redistrict"]["radiusM"] == py["redistrict"]["radius_m"]
    assert flat["redistrict"]["half"] == py["redistrict"]["half"]
    assert flat["weedwater"]["halfM"] == py["weedwater"]["half_m"]
    assert flat["weedwater"]["sigma"] == py["weedwater"]["sigma"]
    assert flat["festival"]["halfM"] == py["festival"]["half_m"]
    assert flat["festival"]["sigma"] == py["festival"]["sigma"]
    assert flat["stadium"]["halfM"] == py["stadium"]["half_m"]
    assert flat["stadium"]["sigma"] == py["stadium"]["sigma"]
