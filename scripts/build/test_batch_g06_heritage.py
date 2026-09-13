"""Tests for batch_g06_heritage.py (Group 6 heritage raster builder).

Hermetic: hand-made fixture geojson + synthetic graphs only, never the
network and never the real snapshot PBF. Run:
python3 -m pytest scripts/build/test_batch_g06_heritage.py -q
"""

import base64
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from batch_g06_heritage import (  # noqa: E402
    LAYER_DEFAULTS,
    build_points_layer,
    dedupe_points,
    is_heritage,
)
from walk_graph import Graph, hav_km, key_of  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "batch_g06_demo.geojson")


def test_predicate_matches_verified_snapshot_tags():
    assert is_heritage({"historic": "manor"})
    assert is_heritage({"historic": "memorial"})
    assert is_heritage({"historic": "castle", "heritage": "2"})
    assert is_heritage({"heritage": "1"})
    assert is_heritage({"unesco": "yes"})
    assert not is_heritage({"shop": "supermarket"})
    assert not is_heritage({"amenity": "police"})
    assert not is_heritage({})
    assert not is_heritage(None)


def test_resolve_fixture_counts_per_predicate():
    # Fixture: 1 manor node, 1 memorial node, 1 castle polygon, 1 shop.
    pts, stats = wr.resolve_pois(FIXTURE, is_heritage)
    assert len(pts) == 3
    assert stats["kept"] == 3


def test_dedupe_points_merges_colocated_only():
    # Same-object node+area pair (~5 m apart) merges; a memorial 30 m
    # away stays separate (clusters read as a denser heritage area).
    feats = [(24.75000, 59.44000, 1.0), (24.75005, 59.44003, 1.0), (24.75060, 59.44000, 1.0)]
    out = dedupe_points(feats)
    assert len(out) == 2
    assert out[0] == feats[0]  # first wins
    assert out[1] == feats[2]


def test_calibration_matches_ts_contract():
    # Locked with GROUP06_HALVES / GROUP06_DECAY in layers_group06.ts.
    assert LAYER_DEFAULTS == {
        "heritage": {"sigma": 0.8, "half": 2},
    }


def _chain(x0, n, step=0.001):
    g = Graph()
    for i in range(n - 1):
        a, b = key_of(x0 + i * step, 59.44), key_of(x0 + (i + 1) * step, 59.44)
        g.add_edge(a, b, hav_km(x0 + i * step, 59.44, x0 + (i + 1) * step, 59.44))
    return g


def test_points_builder_end_to_end_on_synthetic_graph():
    # All three fixture features, off the toy graph (exercises the
    # Euclidean fallback tier): the manor cell accumulates manor 1.0 +
    # memorial K(~0.55 km, sigma 0.8) ~= 0.79 + castle K(~1.2 km) ~= 0.32,
    # S ~= 2.1 -> 100*2.1/4.1 ~= 51. Far cells stay unknown (255),
    # never zero.
    g = _chain(24.70, 2, step=0.0002)  # ~11 m apart: same 75 m cell
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    score_of, contract = build_points_layer(g, grid, 2, 0.8, FIXTURE)
    assert contract == {"half": 2, "sigma": 0.8}
    k = grid.cell_of(24.7454, 59.4374)
    assert k is not None
    s = score_of(k)
    assert s is not None and 45 < s < 65
    raw = wr.score_bytes(grid, score_of)
    assert raw[k] == round(s)  # encoding round-trips the baked score
    # A cell ~3.7 km from the manor is unknown, never zero.
    far = grid.cell_of(24.691, 59.449)
    assert far is not None and raw[far] == 255


def test_wire_doc_carries_contract_and_unknown():
    g = _chain(24.70, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.43, 24.71, 59.45))
    score_of, _ = build_points_layer(g, grid, 2, 0.8, FIXTURE)
    doc = wr.encode_raster(grid, score_of, half=2, sigma=0.8)
    assert doc["half"] == 2 and doc["sigma"] == 0.8
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == grid.cols * grid.rows
    assert 255 in raw  # unknown cells survive encoding


def test_derived_points_are_unit_weighted():
    import tempfile

    g = _chain(24.70, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    with tempfile.TemporaryDirectory() as d:
        derived = os.path.join(d, "derived-heritage.json")
        build_points_layer(g, grid, 2, 0.8, FIXTURE, derived)
        pts = json.load(open(derived, encoding="utf-8"))
    assert len(pts) == 3
    for p in pts:
        assert p["a"] == 1
        assert 24.0 < p["lon"] < 25.0 and 59.0 < p["lat"] < 60.0


def test_builder_is_hermetic_no_network_imports():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_g06_heritage.py")).read()
    for mod in ("urllib", "requests", "socket", "http.client", "overpass"):
        assert mod not in src
