"""Hermetic tests for batch_maru_choropleth.py (issue #486).

Synthetic fixtures only: no PBF, no network, no snapshot, no MARU data.
The committed example fixture is structural-checked plus pinned SYNTHETIC
(never re-pulled here -- there is no bulk contract to pull from).
"""

import json
import os

import batch_maru_choropleth as b

HERE = os.path.dirname(os.path.abspath(__file__))
TS_PATH = os.path.join(HERE, "..", "..", "apps", "web", "lib",
                       "layers_maru.ts")
FIXTURE_PATH = os.path.join(HERE, "maru_kov_tables.example.json")

# Synthetic quarterly KOV rows (invented numbers -- the join SHAPE is
# what is pinned, never real MARU medians).
ROWS = [
    {"kov": "Näidisvald", "quarter": "2025-Q1",
     "median_eur_m2": 3000, "deals": 120},
    {"kov": "Näidisvald", "quarter": "2025-Q2",
     "median_eur_m2": 3100, "deals": 140},
    {"kov": "Näidisvald", "quarter": "2026-Q1",
     "median_eur_m2": 3200, "deals": 150},
    {"kov": "Näidisvald", "quarter": "2026-Q2",
     "median_eur_m2": 3300, "deals": 160},
    {"kov": "Testlinn", "quarter": "2026-Q1",
     "median_eur_m2": 1900, "deals": 7},
    {"kov": "Testlinn", "quarter": "2026-Q2",
     "median_eur_m2": 2000, "deals": 8},
    {"kov": "Langusvald", "quarter": "2025-Q2",
     "median_eur_m2": 1500, "deals": 14},
    {"kov": "Langusvald", "quarter": "2026-Q1",
     "median_eur_m2": 1450, "deals": 16},
    {"kov": "Langusvald", "quarter": "2026-Q2",
     "median_eur_m2": 1400, "deals": 12},
]


def test_normalise_kov_exact_only():
    assert b.normalise_kov("  NÄIDISVALD  ") == "näidisvald"
    assert b.normalise_kov("Testlinn") == "testlinn"
    assert b.normalise_kov("Testlinna") == "testlinna"  # near-miss kept apart
    assert b.normalise_kov(None) is None
    assert b.normalise_kov("   ") is None


def test_latest_rows_never_trended():
    assert b.latest_rows(ROWS, "Näidisvald")[0]["quarter"] == "2026-Q2"
    assert b.kov_value("Näidisvald", ROWS, "deals") == 160.0
    # Case/whitespace variants join; near-miss names stay empty.
    assert b.latest_rows(ROWS, "  NÄIDISVALD ") != []
    assert b.latest_rows(ROWS, "Näidisvalla") == []
    assert b.kov_quarters("Testlinn", ROWS) == ["2026-Q1", "2026-Q2"]
    assert b.kov_quarters("Olematu", ROWS) == []


def test_yoy_same_quarter_year_apart_only():
    assert abs(b.yoy_pct("Näidisvald", ROWS) - 200.0 / 3100 * 100) < 1e-9
    assert b.yoy_band(b.yoy_pct("Näidisvald", ROWS)) == 40  # +6.45% kiire
    assert b.yoy_pct("Testlinn", ROWS) is None  # no year-ago row: no guess
    assert b.yoy_band(None) is None


def test_yoy_band_boundaries():
    assert b.yoy_band(-5.0) == 75
    assert b.yoy_band(-4.99) == 65
    assert b.yoy_band(-0.01) == 65
    assert b.yoy_band(0.0) == 50
    assert b.yoy_band(5.0) == 50
    assert b.yoy_band(5.01) == 40
    assert b.yoy_band(10.0) == 40
    assert b.yoy_band(10.01) == 30
    assert b.yoy_band(float("nan")) is None


def test_deals_band_boundaries():
    assert b.deals_band(300) == 80
    assert b.deals_band(299) == 65
    assert b.deals_band(100) == 65
    assert b.deals_band(99) == 50
    assert b.deals_band(30) == 50
    assert b.deals_band(29) == 35
    assert b.deals_band(None) is None


def test_resale_composite_needs_both_legs():
    assert b.resale_band(160, 6.45) == 70  # deep + rising
    assert b.resale_band(160, -1.0) == 55  # deep, cooling
    assert b.resale_band(12, 1.0) == 50  # thin, stable
    assert b.resale_band(12, -6.67) == 35  # thin + falling
    assert b.resale_band(None, 6.45) is None  # no half-comps
    assert b.resale_band(160, None) is None


def test_qoq_consecutive_quarters_only_capped_at_70():
    assert abs(b.qoq_pct("Näidisvald", ROWS) - 10.0 / 150 * 100) < 1e-9
    assert b.qoq_band(b.qoq_pct("Näidisvald", ROWS)) == 55  # +6.7% stable
    assert b.qoq_band(14.3) == 70  # velocity cap is the top band
    assert b.qoq_band(10.0) == 70
    assert b.qoq_band(9.99) == 55
    assert b.qoq_band(-10.0) == 55
    assert b.qoq_band(-10.01) == 40
    # Langusvald latest pair (2026-Q1 -> 2026-Q2) is consecutive: -25%.
    assert b.qoq_pct("Langusvald", ROWS) == -25.0
    assert b.qoq_band(b.qoq_pct("Langusvald", ROWS)) == 40
    # Non-consecutive latest pair is NOT trended: drop 2026-Q1 and the
    # 2025-Q2/2026-Q2 year gap must NULL, never annualise.
    gap = [r for r in ROWS if not (
        r["kov"] == "Langusvald" and r["quarter"] == "2026-Q1")]
    assert b.qoq_pct("Langusvald", gap) is None


def test_kov_scores_demo_shapes():
    scores = b.kov_scores(ROWS)
    assert scores["näidisvald"] == {
        "kovkasv": 40, "kovkaive": 65, "kovedas": 70, "kovkiirus": 55}
    assert scores["testlinn"] == {
        "kovkasv": None, "kovkaive": 35, "kovedas": None, "kovkiirus": 70}
    assert scores["langusvald"] == {
        "kovkasv": 75, "kovkaive": 35, "kovedas": 35, "kovkiirus": 40}


def test_committed_fixture_is_synthetic_and_shaped():
    with open(FIXTURE_PATH, encoding="utf-8") as fh:
        fixture = json.load(fh)
    assert fixture.get("synthetic") is True  # never mistaken for MARU data
    names = {r["kov"] for r in fixture["rows"]}
    # Fake KOV names only: joinable to NO real polygon (fail-closed).
    assert names == {"Näidisvald", "Testlinn", "Langusvald"}
    for row in fixture["rows"]:
        assert set(row) == {"kov", "quarter", "median_eur_m2", "deals"}
        assert b._quarter_key(row["quarter"]) is not None
    assert b.kov_scores(fixture["rows"])["näidisvald"]["kovedas"] == 70


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
    # Same county grid as the sibling choropleth builder: fill and wire
    # share this Grid (self-consistency lock).
    assert (grid.cols, grid.rows) == (1681, 1843)


def test_encode_wire_shape():
    grid = _small_grid()
    doc = b.encode_wire(grid, {0: 60, 1: 300, 2: -5}, "kovkasv")
    assert doc["cols"] == grid.cols and doc["rows"] == grid.rows
    assert doc["half"] is None and doc["sigma"] == 0.5
    assert doc["unknown"] == 255 and doc["dtype"] == "uint8"
    assert doc["bbox"] == {"minlon": 24.0, "minlat": 59.0,
                           "maxlon": 24.01, "maxlat": 59.01}
    assert doc["step_m"] == 75.0
    import base64 as _b64
    raw = _b64.b64decode(doc["data"])
    assert len(raw) == grid.cols * grid.rows
    assert raw[0] == 60 and raw[1] == 100 and raw[2] == 0
    assert raw[3] == 255


def test_build_layer_null_skips_and_conflicts():
    grid = _small_grid()
    ring = [(24.0, 59.0), (24.01, 59.0), (24.01, 59.01),
            (24.0, 59.01), (24.0, 59.0)]
    rings = {"aaa": [ring], "zzz": [ring]}
    scores = {"aaa": {"kovkasv": 40}, "zzz": {"kovkasv": 75}}
    merged, conflicts = b.build_layer(grid, "kovkasv", rings, scores)
    assert conflicts > 0  # shared geometry double-claims, first wins
    assert set(merged.values()) == {40}
    scores_null = {"aaa": {"kovkasv": None}, "zzz": {"kovkasv": 75}}
    merged2, _ = b.build_layer(grid, "kovkasv", rings, scores_null)
    assert set(merged2.values()) == {75}  # NULL KOV contributes nothing


def test_read_kov_rings_fail_closed(tmp_path):
    extract = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "properties": {"name": "Näidisvald", "admin_level": "7"},
             "geometry": {"type": "Polygon", "coordinates": [[
                 [24.0, 59.0], [24.01, 59.0], [24.01, 59.01],
                 [24.0, 59.01], [24.0, 59.0]]]}},
            # Island side-product: no admin_level, must drop out.
            {"type": "Feature",
             "properties": {"name": "Skerri", "place": "islet"},
             "geometry": {"type": "Polygon", "coordinates": [[
                 [24.0, 59.0], [24.01, 59.0], [24.01, 59.01],
                 [24.0, 59.01], [24.0, 59.0]]]}},
        ],
    }
    path = os.path.join(str(tmp_path), "demo.geojson")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(extract, fh)
    rings = b.read_kov_rings(path)
    assert set(rings) == {"näidisvald"}


def test_main_probe_scores_without_polygons(capsys):
    b.main(["--tables", FIXTURE_PATH, "--probe"])
    out = capsys.readouterr().out
    assert "synthetic demo fixture" in out
    assert "näidisvald" in out and "langusvald" in out


def test_main_join_fails_closed_both_ways(tmp_path):
    import pytest as _pytest
    extract = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "properties": {"name": "Võõrvald", "admin_level": "7"},
             "geometry": {"type": "Polygon", "coordinates": [[
                 [24.0, 59.0], [24.01, 59.0], [24.01, 59.01],
                 [24.0, 59.01], [24.0, 59.0]]]}},
        ],
    }
    path = os.path.join(str(tmp_path), "foreign.geojson")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(extract, fh)
    # Synthetic fixture KOVs have no polygons here AND the polygon has
    # no fixture row: either direction aborts, never a silent fake map.
    with _pytest.raises(SystemExit):
        b.main(["--tables", FIXTURE_PATH, "--kov-extract", path,
                "--probe"])


def test_ts_calibration_drift():
    src = open(TS_PATH, encoding="utf-8").read()
    # Band rows mirrored exactly (verbatim rows, not loose numbers).
    assert "kovkasv: [[-5, 75], [0, 65], [5, 50], [10, 40]]" in src
    assert "kovkaive: [[300, 80], [100, 65], [30, 50]]" in src
    assert "kovkiirus: [[10, 70], [-10, 55]]" in src
    assert "kovkasv: 30" in src and "kovkaive: 35" in src
    assert "kovkiirus: 40" in src
    assert "TT->70" in src
    assert "sigma: 0.5" in src
    assert "MARUKOV_DECAY" in src
