"""Tests for batch_b5_safety.py (Group 14 public-safety raster builders).

Hermetic: hand-made fixture geojson + synthetic graphs only, never the
network and never the real snapshot PBF. Run:
python3 -m pytest scripts/build/test_batch_b5_safety.py -q
"""

import base64
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from batch_b5_safety import (  # noqa: E402
    LAYER_DEFAULTS,
    MAJOR_HIGHWAY,
    build_evac,
    build_points_layer,
    dedupe_points,
    is_dispatch,
    is_emergency,
    is_fire_station,
    is_hospital,
    is_hydrant,
    is_police,
)
from walk_graph import Graph, hav_km, key_of  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "batch_b5_demo.geojson")


def test_predicates_match_verified_snapshot_tags():
    assert is_police({"amenity": "police"})
    assert not is_police({"amenity": "hospital"})
    assert is_fire_station({"amenity": "fire_station"})
    assert not is_fire_station({"emergency": "fire_hydrant"})
    assert is_hospital({"amenity": "hospital"})
    assert not is_hospital({"amenity": "clinic"})  # p124, not p78
    assert is_hydrant({"emergency": "fire_hydrant"})
    assert not is_hydrant({"amenity": "fire_station"})
    assert not is_hydrant(None)
    # Combined layers.
    assert is_emergency({"amenity": "fire_station"})
    assert is_emergency({"amenity": "hospital"})
    assert not is_emergency({"amenity": "police"})
    assert is_dispatch({"amenity": "police"})
    assert is_dispatch({"amenity": "fire_station"})
    assert is_dispatch({"amenity": "hospital"})
    assert not is_dispatch({"amenity": "pharmacy"})
    assert not is_dispatch(None)


def test_major_highway_set_covers_verified_tags():
    assert MAJOR_HIGHWAY == {"motorway", "trunk", "primary"}


def test_resolve_fixture_counts_per_predicate():
    # Fixture: 1 police, 1 fire_station, 1 hospital, 1 hydrant, 1 pharmacy,
    # 1 trunk line, 1 residential line.
    assert wr.resolve_pois(FIXTURE, is_police)[0].__len__() == 1
    assert wr.resolve_pois(FIXTURE, is_fire_station)[0].__len__() == 1
    assert wr.resolve_pois(FIXTURE, is_hospital)[0].__len__() == 1
    assert wr.resolve_pois(FIXTURE, is_hydrant)[0].__len__() == 1
    assert wr.resolve_pois(FIXTURE, is_emergency)[0].__len__() == 2
    assert wr.resolve_pois(FIXTURE, is_dispatch)[0].__len__() == 3
    pts, stats = wr.resolve_length_km(FIXTURE, MAJOR_HIGHWAY)
    assert stats["kept"] == 1  # residential way is not egress
    assert len(pts) > 0


def test_dedupe_points_merges_colocated_only():
    # Same-station node+area pair (~5 m apart) merges; a hydrant 30 m
    # away stays separate (clusters read as more capacity).
    feats = [(24.75000, 59.44000, 1.0), (24.75005, 59.44003, 1.0), (24.75060, 59.44000, 1.0)]
    out = dedupe_points(feats)
    assert len(out) == 2
    assert out[0] == feats[0]  # first wins
    assert out[1] == feats[2]


def test_calibration_matches_ts_contract():
    # Locked with BATCH5_HALVES / BATCH5_DECAY in layers_batch5.ts.
    assert LAYER_DEFAULTS == {
        "safety": {"sigma": 0.8, "half": 1},
        "emergency": {"sigma": 0.8, "half": 2},
        "hydrants": {"sigma": 0.3, "half": 6},
        "evac": {"sigma": 0.5, "half": 2},
        "dispatch": {"sigma": 0.8, "half": 3},
    }


def _chain(x0, n, step=0.001):
    g = Graph()
    for i in range(n - 1):
        a, b = key_of(x0 + i * step, 59.44), key_of(x0 + (i + 1) * step, 59.44)
        g.add_edge(a, b, hav_km(x0 + i * step, 59.44, x0 + (i + 1) * step, 59.44))
    return g


def test_points_builder_end_to_end_on_synthetic_graph():
    # One hydrant, off the toy graph (exercises the Euclidean fallback
    # tier): the feature cell scores 100*1/(1+6) ~= 14, far cells stay
    # unknown (255), never zero.
    g = _chain(24.70, 2, step=0.0002)  # ~11 m apart: same 75 m cell
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    score_of, contract = build_points_layer(g, grid, 6, 0.3, FIXTURE, "hydrants")
    assert contract == {"half": 6, "sigma": 0.3}
    k = grid.cell_of(24.755, 59.438)
    assert k is not None
    assert score_of(k) == pytest.approx(100.0 / 7.0, abs=2.0)
    raw = wr.score_bytes(grid, score_of)
    assert raw[k] == round(100.0 / 7.0)
    # A cell ~3.7 km from the hydrant is unknown, never zero.
    far = grid.cell_of(24.691, 59.449)
    assert far is not None and raw[far] == 255


def test_evac_builder_uses_road_km_not_counts():
    g = _chain(24.70, 30, step=0.001)
    grid = wr.Grid((24.69, 59.42, 24.77, 59.44))
    score_of, contract = build_evac(g, grid, 12, 0.5, FIXTURE)
    assert contract == {"half": 12, "sigma": 0.5}
    # On the trunk line: known score in 0..100; far north corner unknown.
    on = grid.cell_of(24.75, 59.4305)
    assert on is not None
    assert score_of(on) is not None and 0 < score_of(on) <= 100
    raw = wr.score_bytes(grid, score_of)
    assert raw[grid.cell_of(24.769, 59.4395)] == 255


def test_wire_doc_carries_contract_and_unknown():
    g = _chain(24.70, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.43, 24.71, 59.45))
    score_of, _ = build_points_layer(g, grid, 1, 0.8, FIXTURE, "safety")
    doc = wr.encode_raster(grid, score_of, half=1, sigma=0.8)
    assert doc["half"] == 1 and doc["sigma"] == 0.8
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == grid.cols * grid.rows
    assert 255 in raw  # unknown cells survive encoding


def test_builder_is_hermetic_no_network_imports():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_b5_safety.py")).read()
    for mod in ("urllib", "requests", "socket", "http.client", "overpass"):
        assert mod not in src
