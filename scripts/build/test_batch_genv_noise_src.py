"""Hermetic unit tests for the GENV extra noise sources (issue #131).

No network, no snapshot: derived-*.geojson fixtures are inline/tmp. Run:
  python3 -m pytest scripts/build/test_batch_genv_noise_src.py -q
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import batch_genv_noise_src as N


def _write(snap_dir, name, features):
    osm = os.path.join(snap_dir, "osm")
    os.makedirs(osm, exist_ok=True)
    with open(os.path.join(osm, name), "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features},
                  f)


def _feat(props, gtype, coords):
    return {"type": "Feature", "properties": props,
            "geometry": {"type": gtype, "coordinates": coords}}


@pytest.fixture()
def snap(tmp_path):
    s = str(tmp_path)
    # Wind: two turbine nodes + one solar node (must be skipped) + one
    # heritage windmill node without generator tags (must be skipped).
    _write(s, "derived-wind.geojson", [
        _feat({"power": "generator", "generator:source": "wind"},
              "Point", [24.05, 59.38]),
        _feat({"power": "generator", "generator:source": "wind"},
              "Point", [24.06, 59.39]),
        _feat({"power": "generator", "generator:source": "solar"},
              "Point", [24.75, 59.44]),
        _feat({"man_made": "windmill", "name": "Kotlandi tuulik"},
              "Point", [23.50, 59.05]),
    ])
    # Quarry: one area + its closed twin + one member ring + one node.
    ring = [[24.40, 59.30], [24.41, 59.30], [24.41, 59.31],
            [24.40, 59.31], [24.40, 59.30]]
    _write(s, "derived-quarry.geojson", [
        _feat({"landuse": "quarry"}, "MultiPolygon", [[ring]]),
        _feat({"landuse": "quarry"}, "LineString", ring),
        _feat({"natural": "water"}, "LineString", ring),
        _feat({"landuse": "forest"}, "MultiPolygon", [[ring]]),
        _feat({"landuse": "quarry"}, "Point", [24.405, 59.305]),
    ])
    # Motorsport: one closed circuit (area + twin), one open centreline,
    # one tagged node, one untagged member dot.
    circ = [[24.20, 59.32], [24.21, 59.32], [24.21, 59.33],
            [24.20, 59.33], [24.20, 59.32]]
    _write(s, "derived-motorsport.geojson", [
        _feat({"leisure": "track", "sport": "motocross"},
              "MultiPolygon", [[circ]]),
        _feat({"leisure": "track", "sport": "motocross"},
              "LineString", circ),
        _feat({"leisure": "track", "sport": "karting"},
              "LineString", [[24.22, 59.32], [24.24, 59.32]]),
        _feat({"leisure": "track", "sport": "karting"},
              "Point", [24.23, 59.321]),
        _feat({"traffic_calming": "hump"}, "Point", [24.225, 59.3205]),
        _feat({"leisure": "track", "sport": "running"},
              "LineString", [[24.30, 59.32], [24.31, 59.32]]),
    ])
    # Range: one polygon + its closed twin.
    poly = [[24.65, 59.36], [24.66, 59.36], [24.66, 59.37],
            [24.65, 59.37], [24.65, 59.36]]
    _write(s, "derived-range.geojson", [
        _feat({"military": "range"}, "MultiPolygon", [[poly]]),
        _feat({"military": "range"}, "LineString", poly),
    ])
    return s


def test_wind_nodes_only_solar_and_heritage_out(snap):
    pts, stats = N.read_wind_points(snap)
    assert stats == {"features": 4, "kept": 2}
    assert (24.05, 59.38) in pts and (24.06, 59.39) in pts


def test_quarry_areas_twins_and_members_out(snap):
    pts, stats = N.read_quarry_points(snap)
    assert stats["features"] == 5
    assert stats["twins"] == 1
    assert stats["members"] == 2  # water ring + forest member polygon
    # Ring stride-samples (5-pt ring -> all 5 kept) + quarry node.
    assert len(pts) == 6
    assert (24.405, 59.305) in pts


def test_moto_areas_open_lines_nodes_only(snap):
    pts, stats = N.read_moto_points(snap)
    assert stats["features"] == 6
    assert stats["twins"] == 1  # closed motocross twin
    # Untagged hump dot + running track are members, not sources.
    assert stats["members"] == 2
    # Circuit ring (5) + tagged node (1) + densified open kart line.
    assert (24.23, 59.321) in pts
    line_n = len(N._densify_line([(24.22, 59.32), (24.24, 59.32)]))
    assert line_n > 2  # ~1.1 km open way densified to ~50 m steps
    assert len(pts) == 5 + 1 + line_n


def test_range_polygons_twins_out(snap):
    pts, stats = N.read_range_points(snap)
    assert stats == {"features": 2, "kept": 5, "twins": 1}


def test_union_registers_all_four_classes(snap):
    out, stats = N.lowspec_extra_points(snap)
    assert set(out) == {"wind", "quarry", "moto", "range"}
    assert set(stats) == {"wind", "quarry", "moto", "range"}
    assert all(len(v) > 0 for v in out.values())


def test_missing_export_fails_loudly(tmp_path):
    with pytest.raises(SystemExit):
        N.read_wind_points(str(tmp_path))


def test_first_value_semantics():
    assert N._first("wind;solar") == "wind"
    assert N._first(None) == ""
    assert N._first(42) == ""


def test_open_linestring_kept_closed_dropped():
    assert N._is_closed([[0.0, 0.0], [1.0, 1.0], [0.0, 0.0]])
    assert not N._is_closed([[0.0, 0.0], [1.0, 1.0]])
