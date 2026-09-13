"""Hermetic tests for batch_statkov_choropleth.py (issue #485).

Synthetic fixtures only: no PBF, no network, no snapshot. The committed
aggregate fixture is structural-checked (never re-pulled here).
"""

import json
import os

import batch_statkov_choropleth as b

HERE = os.path.dirname(os.path.abspath(__file__))
TS_PATH = os.path.join(HERE, "..", "..", "apps", "web", "lib",
                       "layers_statkov.ts")
FIXTURE_PATH = os.path.join(HERE, "statkov_px_tables.json")


def test_normalise_kov():
    assert b.normalise_kov("..Anija vald") == "anija"
    assert b.normalise_kov("Anija vald") == "anija"
    assert b.normalise_kov("..Tallinn") == "tallinn"
    assert b.normalise_kov("Tallinn") == "tallinn"
    assert b.normalise_kov("Keila linn") == "keila"
    assert b.normalise_kov("  ..Lääne-Harju   vald ") == "lääne-harju"
    assert b.normalise_kov(None) is None
    assert b.normalise_kov("   ") is None
    assert b.normalise_kov("...") is None


def test_fixture_rates_and_nulls():
    kovs = {
        "Demo": {"rvr_saldo_2025": 100.0, "eh_completions_2025": 50.0,
                 "rr_tulud_2025": 10000.0, "rr_tulem_2025": 800.0,
                 "pop_2025_01_01": 10000.0, "pop_2026_01_01": 10200.0},
        "NoPop": {"rvr_saldo_2025": 100.0, "eh_completions_2025": 50.0,
                  "rr_tulud_2025": 10000.0, "rr_tulem_2025": 800.0,
                  "pop_2025_01_01": None, "pop_2026_01_01": 10200.0},
        "NoTulud": {"rvr_saldo_2025": 5.0, "eh_completions_2025": 1.0,
                    "rr_tulud_2025": 0.0, "rr_tulem_2025": 10.0,
                    "pop_2025_01_01": 5000.0, "pop_2026_01_01": 5000.0},
    }
    rates = b.fixture_rates(kovs)
    assert rates["Demo"]["net_k"] == 100.0 / 10100.0 * 1000.0
    assert rates["Demo"]["comp_k"] == 50.0 / 10100.0 * 1000.0
    assert rates["Demo"]["margin"] == 8.0
    assert rates["NoPop"]["net_k"] is None
    assert rates["NoPop"]["comp_k"] is None
    assert rates["NoPop"]["margin"] == 8.0
    assert rates["NoTulud"]["margin"] is None  # zero tulud never divides


def test_band_boundaries():
    assert b.band_score("kovmigr", 10.0) == 75
    assert b.band_score("kovmigr", 9.99) == 60
    assert b.band_score("kovmigr", -5.0) == 60
    assert b.band_score("kovmigr", -5.01) == 45
    assert b.band_score("kovmigr", -20.0) == 45
    assert b.band_score("kovmigr", -20.01) == 30
    assert b.band_score("kovehit", 20.0) == 30
    assert b.band_score("kovehit", 10.0) == 45
    assert b.band_score("kovehit", 4.0) == 60
    assert b.band_score("kovehit", 3.99) == 70
    assert b.band_score("kovfisc", 10.0) == 70
    assert b.band_score("kovfisc", 5.0) == 60
    assert b.band_score("kovfisc", 0.0) == 45
    assert b.band_score("kovfisc", -0.01) == 30
    assert b.band_score("kovmigr", None) is None
    assert b.band_score("kovehit", float("nan")) is None


def test_kov_scores_real_fixture_shape():
    # Synthetic mini-fixture: score shape per layer, NULL where absent.
    fixture = {"kovs": {
        "Boom": {"rvr_saldo_2025": 500.0, "eh_completions_2025": 5.0,
                 "rr_tulud_2025": 20000.0, "rr_tulem_2025": 2500.0,
                 "pop_2025_01_01": 10000.0, "pop_2026_01_01": 10000.0},
        "Gap": {"rvr_saldo_2025": None, "eh_completions_2025": None,
                "rr_tulud_2025": None, "rr_tulem_2025": None,
                "pop_2025_01_01": None, "pop_2026_01_01": None},
    }}
    scores = b.kov_scores(fixture)
    assert scores["Boom"] == {"kovmigr": 75, "kovehit": 70, "kovfisc": 70}
    assert scores["Gap"] == {"kovmigr": None, "kovehit": None,
                             "kovfisc": None}


def test_committed_fixture_structure():
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        fixture = json.load(fh)
    assert len(fixture["kovs"]) == 16
    for name, row in fixture["kovs"].items():
        for key in ("rvr_saldo_2025", "eh_completions_2025", "rr_tulud_2025",
                    "rr_tulem_2025", "pop_2025_01_01", "pop_2026_01_01"):
            assert key in row, (name, key)
            assert row[key] is None or isinstance(row[key], (int, float))
    # Stable truths (not exact values -- the fixture re-harvests quarterly).
    assert fixture["kovs"]["Tallinn"]["pop_2026_01_01"] > 400000
    assert fixture["period"].startswith("2025")


def test_douglas_peucker():
    straight = [(0.0, 0.0), (0.25, 0.0), (0.5, 0.0), (0.75, 0.0), (1.0, 0.0)]
    assert b.douglas_peucker(straight, 0.01) == [(0.0, 0.0), (1.0, 0.0)]
    spike = [(0.0, 0.0), (0.5, 0.5), (1.0, 0.0)]
    assert b.douglas_peucker(spike, 0.01) == spike  # endpoints + spike kept
    assert b.douglas_peucker([(0.0, 0.0), (1.0, 1.0)], 0.5) == [
        (0.0, 0.0), (1.0, 1.0)]


def _small_grid():
    return b.Grid(bbox=[24.0, 59.0, 24.01, 59.01], step_m=75.0)


def test_fill_cells_exact_square():
    grid = _small_grid()
    ring = [(24.0, 59.0), (24.01, 59.0), (24.01, 59.01),
            (24.0, 59.01), (24.0, 59.0)]
    cells = b.fill_cells(grid, [ring])
    # Full small box fills every cell: cols x rows, no more, no less.
    assert len(cells) == grid.cols * grid.rows
    assert min(cells) == 0
    assert max(cells) == grid.cols * grid.rows - 1


def test_fill_cells_hole_stays_empty():
    grid = _small_grid()
    outer = [(24.0, 59.0), (24.01, 59.0), (24.01, 59.01),
             (24.0, 59.01), (24.0, 59.0)]
    side = (24.01 - 24.0) / 3.0
    hole = [(24.0 + side, 59.0 + 0.002), (24.0 + 2 * side, 59.0 + 0.002),
            (24.0 + 2 * side, 59.01 - 0.002),
            (24.0 + side, 59.01 - 0.002),
            (24.0 + side, 59.0 + 0.002)]
    cells = b.fill_cells(grid, [outer, hole])
    assert 0 < len(cells) < grid.cols * grid.rows  # hole cut out
    mid = grid.cell_of(24.0 + 1.5 * side, 59.005)
    assert mid not in cells
    corner = grid.cell_of(24.0 + 0.5 * side, 59.005)
    assert corner in cells


def test_fill_cells_degenerate():
    grid = _small_grid()
    assert b.fill_cells(grid, []) == set()
    assert b.fill_cells(grid, [[(24.0, 59.0)]]) == set()


def test_county_grid_dims_locked():
    grid = b.Grid()
    # Current builder generation (1681 x 1843, ~4.13 MB single-JSON
    # files); older masters use 1682 -- grids are per-layer, so the
    # lock is self-consistency (fill and wire share this Grid).
    assert (grid.cols, grid.rows) == (1681, 1843)


def test_encode_wire_bbox_object():
    # cleanRaster (apps/web/lib/layers.ts) requires bbox {minlon,...}.
    grid = _small_grid()
    doc = b.encode_wire(grid, {}, "kovmigr")
    assert doc["bbox"] == {"minlon": 24.0, "minlat": 59.0,
                           "maxlon": 24.01, "maxlat": 59.01}


def test_build_layer_null_skips_and_conflicts():
    grid = _small_grid()
    ring = [(24.0, 59.0), (24.01, 59.0), (24.01, 59.01),
            (24.0, 59.01), (24.0, 59.0)]
    rings = {"aaa": [ring], "zzz": [ring]}
    scores = {"aaa": {"kovmigr": 60}, "zzz": {"kovmigr": 75}}
    merged, conflicts = b.build_layer(grid, "kovmigr", rings, scores)
    assert conflicts > 0  # shared geometry double-claims, first wins
    assert set(merged.values()) == {60}
    scores_null = {"aaa": {"kovmigr": None}, "zzz": {"kovmigr": 75}}
    merged2, _ = b.build_layer(grid, "kovmigr", rings, scores_null)
    assert set(merged2.values()) == {75}  # NULL KOV contributes nothing


def test_encode_wire_shape():
    grid = _small_grid()
    doc = b.encode_wire(grid, {0: 60, 1: 300, 2: -5}, "kovmigr")
    assert doc["cols"] == grid.cols and doc["rows"] == grid.rows
    assert doc["half"] is None and doc["sigma"] == 0.5
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    import base64 as _b64
    raw = _b64.b64decode(doc["data"])
    assert len(raw) == grid.cols * grid.rows
    assert raw[0] == 60 and raw[1] == 100 and raw[2] == 0
    assert raw[3] == 255


def test_ts_calibration_drift():
    src = open(TS_PATH, encoding="utf-8").read()
    # Band rows mirrored exactly (verbatim rows, not loose numbers).
    assert "kovmigr: [[10, 75], [-5, 60], [-20, 45]]" in src
    assert "kovehit: [[20, 30], [10, 45], [4, 60]]" in src
    assert "kovfisc: [[10, 70], [5, 60], [0, 45]]" in src
    assert "kovmigr: 30" in src and "kovehit: 70" in src
    assert "kovfisc: 30" in src
    assert "sigma: 0.5" in src
    assert "STATKOV_DECAY" in src
