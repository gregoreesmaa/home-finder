"""Tests for batch_g02b_lift.py (Group 2 batch-B lift-proxy raster builder).

Hermetic: hand-made fixture geojson + synthetic graphs only, never the
network and never the real snapshot PBF. Run:
python3 -m pytest scripts/build/test_batch_g02b.py -q
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from batch_g02b_lift import (  # noqa: E402
    LAYER_DEFAULTS,
    LIFT_MIN_LEVELS,
    build_points_layer,
    dedupe_points,
    is_liftproxy,
    levels_of,
)
from walk_graph import Graph, hav_km, key_of  # noqa: E402


def test_lift_cutoff_is_five_storeys():
    assert LIFT_MIN_LEVELS == 5


def test_levels_parses_first_value_only():
    assert levels_of({"building:levels": "5"}) == 5.0
    assert levels_of({"building:levels": "9"}) == 9.0
    assert levels_of({"building:levels": "5;6"}) == 5.0  # multi-value edge: first wins
    assert levels_of({"building:levels": "4"}) == 4.0
    assert levels_of({}) is None
    assert levels_of(None) is None
    assert levels_of({"building:levels": ""}) is None
    assert levels_of({"building:levels": "abc"}) is None
    assert levels_of({"building:levels": 5}) is None  # tags are strings, never faked


def test_predicate_matches_verified_snapshot_tags():
    assert is_liftproxy({"building:levels": "5"})
    assert is_liftproxy({"building:levels": "9"})
    assert is_liftproxy({"building:levels": "16"})
    assert not is_liftproxy({"building:levels": "4"})
    assert not is_liftproxy({"building:levels": "1"})
    assert not is_liftproxy({"building": "yes"})  # untagged levels: unknown, never lift
    assert not is_liftproxy({})
    assert not is_liftproxy(None)


def _poi_geojson(path):
    feats = [
        {"type": "Feature", "id": "w1", "properties": {"building:levels": "9"},
         "geometry": {"type": "Point", "coordinates": [24.755, 59.438]}},
        {"type": "Feature", "id": "w2", "properties": {"building:levels": "5"},
         "geometry": {"type": "Point", "coordinates": [24.760, 59.440]}},
        {"type": "Feature", "id": "w3", "properties": {"building:levels": "2"},
         "geometry": {"type": "Point", "coordinates": [24.770, 59.445]}},
        {"type": "Feature", "id": "w4", "properties": {"building": "yes"},
         "geometry": {"type": "Point", "coordinates": [24.780, 59.450]}},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for feat in feats:
            f.write(json.dumps(feat) + "\n")
    return path


def test_resolve_poi_counts_per_predicate(tmp_path):
    poi = _poi_geojson(str(tmp_path / "lift.geojson"))
    pts, stats = wr.resolve_pois(poi, is_liftproxy)
    assert len(pts) == 2  # 9- and 5-storey only; 2-storey + untagged excluded
    assert stats["kept"] == 2


def test_dedupe_points_merges_colocated_only():
    # Same-tower node+area pair (~5 m apart) merges; a tower 30 m
    # away stays separate (clusters read as more lift-dense).
    feats = [(24.75000, 59.44000, 1.0), (24.75005, 59.44003, 1.0), (24.75060, 59.44000, 1.0)]
    out = dedupe_points(feats)
    assert len(out) == 2
    assert out[0] == feats[0]  # first wins
    assert out[1] == feats[2]


def test_calibration_matches_ts_contract():
    # Locked with G02B_HALVES / G02B_DECAY in layers_group02b.ts.
    assert LAYER_DEFAULTS == {
        "liftproxy": {"sigma": 0.3, "half": 2},
    }


def _chain(x0, n, step=0.001):
    g = Graph()
    for i in range(n - 1):
        a, b = key_of(x0 + i * step, 59.44), key_of(x0 + (i + 1) * step, 59.44)
        g.add_edge(a, b, hav_km(x0 + i * step, 59.44, x0 + (i + 1) * step, 59.44))
    return g


def test_points_builder_end_to_end_on_synthetic_graph(tmp_path):
    # Two towers, off the toy graph (exercises the Euclidean fallback
    # tier): the feature cell stacks the on-cell tower (weight 1) plus
    # ~0.5 kernel weight from the second tower ~360 m out, scoring
    # 100*1.48/3.48 ~= 42. Far cells stay unknown (255), never zero.
    poi = _poi_geojson(str(tmp_path / "lift.geojson"))
    g = _chain(24.70, 2, step=0.0002)  # ~11 m apart: same 75 m cell
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    score_of, contract = build_points_layer(g, grid, 2, 0.3, poi, "liftproxy")
    assert contract == {"half": 2, "sigma": 0.3}
    k = grid.cell_of(24.755, 59.438)
    assert k is not None
    assert score_of(k) == pytest.approx(42.5, abs=3.0)
    raw = wr.score_bytes(grid, score_of)
    assert raw[k] == round(score_of(k))
    # A cell ~3.7 km from the tower is unknown, never zero.
    far = grid.cell_of(24.691, 59.449)
    assert far is not None and raw[far] == 255


def test_builder_writes_derived_points(tmp_path):
    poi = _poi_geojson(str(tmp_path / "lift.geojson"))
    derived = str(tmp_path / "derived-liftproxy.json")
    g = _chain(24.70, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    build_points_layer(g, grid, 2, 0.3, poi, "liftproxy", derived=derived)
    pts = json.load(open(derived, encoding="utf-8"))
    assert len(pts) == 2
    for p in pts:
        assert set(p) == {"lon", "lat", "a"}  # unit weights, splat with layer half
        assert p["a"] == 1
