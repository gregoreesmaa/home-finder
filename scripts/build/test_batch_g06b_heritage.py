"""Tests for batch_g06b_heritage.py (Group 6 leftover raster builders).

Hermetic: hand-made fixture geojson + synthetic graphs only, never the
network and never the real snapshot PBF. Run:
python3 -m pytest scripts/build/test_batch_g06b_heritage.py -q
"""

import base64
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import walk_raster as wr  # noqa: E402
from batch_g06b_heritage import (  # noqa: E402
    BUILDERS,
    LAYER_DEFAULTS,
    build_avoid_layer,
    build_points_layer,
    dedupe_points,
    is_antiques,
    is_plaster,
    is_wood,
)
from walk_graph import Graph, hav_km, key_of  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "batch_g06b_demo.geojson")


def test_predicates_match_verified_snapshot_tags():
    assert is_plaster({"building": "yes", "building:material": "plaster"})
    assert not is_plaster({"building": "yes", "building:material": "brick"})
    assert not is_plaster({"building:material": "wood"})
    assert is_antiques({"shop": "antiques", "name": "x"})
    assert not is_antiques({"shop": "supermarket"})
    assert is_wood({"building": "house", "building:material": "wood"})
    assert not is_wood({"building:material": "plaster"})
    for pred in (is_plaster, is_antiques, is_wood):
        assert not pred({"shop": "supermarket"})
        assert not pred({})
        assert not pred(None)


def test_resolve_fixture_counts_per_predicate():
    # Fixture: 1 plaster node + 1 plaster polygon, 1 antiques node,
    # 1 wood node + 1 wood polygon, 1 supermarket, 1 brick house.
    pts, stats = wr.resolve_pois(FIXTURE, is_plaster)
    assert len(pts) == 2 and stats["kept"] == 2
    pts, stats = wr.resolve_pois(FIXTURE, is_antiques)
    assert len(pts) == 1 and stats["kept"] == 1
    pts, stats = wr.resolve_pois(FIXTURE, is_wood)
    assert len(pts) == 2 and stats["kept"] == 2


def test_dedupe_points_merges_colocated_only():
    # Same-house node+area pair (~5 m apart) merges; a house 30 m away
    # stays separate (rows read as denser craft/fire areas).
    feats = [(24.75000, 59.44000, 1.0), (24.75005, 59.44003, 1.0), (24.75060, 59.44000, 1.0)]
    out = dedupe_points(feats)
    assert len(out) == 2
    assert out[0] == feats[0]  # first wins
    assert out[1] == feats[2]


def test_calibration_matches_ts_contract():
    # Locked with GROUP06B_HALVES / GROUP06B_DECAY in layers_group06b.ts
    # (woodfire half 0.21 == sigma*ln2, the 50-score walk-km).
    assert LAYER_DEFAULTS == {
        "plaster": {"kind": "area", "sigma": 0.5, "half": 6},
        "antiques": {"kind": "area", "sigma": 0.5, "half": 1},
        "woodfire": {"kind": "avoid", "sigma": 0.3, "half": 0.21},
    }
    assert BUILDERS["area"] is build_points_layer
    assert BUILDERS["avoid"] is build_avoid_layer
    # Kinds route each layer to its scorer.
    assert BUILDERS[LAYER_DEFAULTS["plaster"]["kind"]] is build_points_layer
    assert BUILDERS[LAYER_DEFAULTS["woodfire"]["kind"]] is build_avoid_layer


def _chain(x0, lat, n, step=0.001):
    g = Graph()
    for i in range(n - 1):
        a, b = key_of(x0 + i * step, lat), key_of(x0 + (i + 1) * step, lat)
        g.add_edge(a, b, hav_km(x0 + i * step, lat, x0 + (i + 1) * step, lat))
    return g


def test_points_builder_end_to_end_on_synthetic_graph():
    # Fixture plaster features, off the toy graph (exercises the Euclidean
    # fallback tier): the house cell accumulates 1.0 + polygon K(~0.45 km,
    # sigma 0.5) ~= 0.67 -> S ~= 1.67 -> 100*1.67/7.67 ~= 22. Far cells
    # stay unknown (255), never zero.
    g = _chain(24.70, 59.44, 2, step=0.0002)  # ~11 m apart: same 75 m cell
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    score_of, contract = build_points_layer("plaster", g, grid, 6, 0.5, FIXTURE)
    assert contract == {"half": 6, "sigma": 0.5}
    k = grid.cell_of(24.7454, 59.4374)
    assert k is not None
    s = score_of(k)
    assert s is not None and 15 < s < 30
    raw = wr.score_bytes(grid, score_of)
    assert raw[k] == round(s)  # encoding round-trips the baked score
    # A cell ~3.7 km from the plaster houses is unknown, never zero.
    far = grid.cell_of(24.691, 59.449)
    assert far is not None and raw[far] == 255


def test_antiques_lone_dealer_caps_mid_ramp():
    # One dealer, half 1: on top S=1 -> 50 (amber "maybe"); the BOOLEAN
    # verdict lives in the scorer dim, the map shows proximity only.
    g = _chain(24.70, 59.44, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    score_of, contract = build_points_layer("antiques", g, grid, 1, 0.5, FIXTURE)
    assert contract == {"half": 1, "sigma": 0.5}
    k = grid.cell_of(24.7464, 59.439)
    assert k is not None
    s = score_of(k)
    assert s is not None and 40 < s < 60


def test_avoid_builder_is_inverse_on_synthetic_graph():
    # Toy chain THROUGH the fixture wooden house (24.7138, 59.4295):
    # the house cell reads ~0 (max attention), a cell 1.3 km down the
    # chain (past the 1.2 km cutoff) stays unknown (255), never faked
    # safe-green.
    g = _chain(24.69, 59.4295, 51)  # 51 verts x ~55 m ~= 2.8 km
    grid = wr.Grid((24.685, 59.425, 24.745, 59.435))
    score_of, contract = build_avoid_layer("woodfire", g, grid, 0.21, 0.3, FIXTURE)
    assert contract == {"half": 0.21, "sigma": 0.3}
    home = grid.cell_of(24.7138, 59.4295)
    assert home is not None
    s = score_of(home)
    assert s is not None and s < 10  # snap gap only (~11 m)
    raw = wr.score_bytes(grid, score_of)
    assert raw[home] == round(s)
    # Mid-chain cell ~0.21 km east of the house reads ~50 (the half).
    mid = grid.cell_of(24.7138 + 0.21 / 55.9, 59.4295)
    assert mid is not None
    m = score_of(mid)
    assert m is not None and 35 < m < 65
    # Past-cutoff cell is unknown, never zero/green.
    far = grid.cell_of(24.69, 59.4295)
    assert far is not None and raw[far] == 255


def test_wire_doc_carries_contract_and_unknown():
    g = _chain(24.70, 59.44, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.43, 24.71, 59.45))
    score_of, _ = build_points_layer("plaster", g, grid, 6, 0.5, FIXTURE)
    doc = wr.encode_raster(grid, score_of, half=6, sigma=0.5)
    assert doc["half"] == 6 and doc["sigma"] == 0.5
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    raw = base64.b64decode(doc["data"])
    assert len(raw) == grid.cols * grid.rows
    assert 255 in raw  # unknown cells survive encoding


def test_derived_points_are_unit_weighted():
    import tempfile

    g = _chain(24.70, 59.44, 2, step=0.0002)
    grid = wr.Grid((24.69, 59.42, 24.79, 59.45))
    with tempfile.TemporaryDirectory() as d:
        derived = os.path.join(d, "derived-plaster.json")
        build_points_layer("plaster", g, grid, 6, 0.5, FIXTURE, derived)
        pts = json.load(open(derived, encoding="utf-8"))
    assert len(pts) == 2
    for p in pts:
        assert p["a"] == 1
        assert 24.0 < p["lon"] < 25.0 and 59.0 < p["lat"] < 60.0


def test_builder_is_hermetic_no_network_imports():
    src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "batch_g06b_heritage.py")).read()
    for mod in ("urllib", "requests", "socket", "http.client", "overpass"):
        assert mod not in src
