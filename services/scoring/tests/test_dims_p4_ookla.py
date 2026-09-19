"""P4 Ookla dims (issue #268): hermetic tests.

No network: fetch_ookla_parquet is never called here (its
contract — single polite GET per layer per quarter, file cache,
TTL, transport errors raise — is covered via the pure
cache_is_fresh helper plus a cache-hit fetch test that performs
no GET and a validation test that raises before any I/O).
Tile fixtures mix real observed Tallinn rows with synthetic
edge rows:

* REAL_* rows were read 2026-09-13 via bounded DuckDB
  range-reads over the Q1-2026 parquets (column chunks only,
  files never downloaded whole; full probe record in
  /tmp/hf-ookla/, never committed). Reused here as minimal
  shape fixtures under the dataset's CC BY-NC-SA 4.0 licence —
  full attribution in docs/p4_ookla.md; see the module
  docstring for the licence judgment call.
* Synthetic rows pin the edges no live row covers (weak band,
  medium band, thin tile, far origin).
"""

import json
import os
import time

import pytest

import dims_p4_ookla as ookla
from dims_p4_ookla import (
    OOKLA_LATEST_LABEL,
    OOKLA_LATEST_QUARTER,
    OOKLA_LATEST_YEAR,
    OOKLA_MIN_TESTS,
    OOKLA_RADIUS_M,
    OOKLA_TTL_DAYS,
    P4_OOKLA_DIMS,
    cache_is_fresh,
    coerce_tile,
    dim_ookla_fixed,
    dim_ookla_mobile,
    fetch_ookla_parquet,
    fetch_ookla_shapefile,
    load_ookla_snapshot,
    ookla_shapefile_url,
    ookla_url,
    quarter_label,
    score_p4_ookla,
    snapshot_cache_path,
    summarize_ookla_tallinn,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]
TARTU = (58.3780, 26.7280)  # far outside the Tallinn extract

#: Real observed fixed rows, Kesklinn 2026-09-13 (see docstring).
REAL_FIXED = [
    {"tile_x": 24.7604, "tile_y": 59.4325, "avg_d_kbps": 167207,
     "avg_u_kbps": 136686, "avg_lat_ms": 8, "tests": 76, "devices": 43,
     "quadkey": "1201202310211211"},
    {"tile_x": 24.7549, "tile_y": 59.4381, "avg_d_kbps": 121596,
     "avg_u_kbps": 111981, "avg_lat_ms": 5, "tests": 67, "devices": 33,
     "quadkey": "1201202310211030"},
    {"tile_x": 24.744, "tile_y": 59.4381, "avg_d_kbps": 130895,
     "avg_u_kbps": 94963, "avg_lat_ms": 5, "tests": 64, "devices": 40,
     "quadkey": "1201202310211020"},
    {"tile_x": 24.7659, "tile_y": 59.4353, "avg_d_kbps": 146065,
     "avg_u_kbps": 112833, "avg_lat_ms": 5, "tests": 64, "devices": 16,
     "quadkey": "1201202310211122"},
]

#: Real observed mobile rows, Kesklinn 2026-09-13 (see docstring).
REAL_MOBILE = [
    {"tile_x": 24.7659, "tile_y": 59.4381, "avg_d_kbps": 411901,
     "avg_u_kbps": 53896, "avg_lat_ms": 25, "tests": 49, "devices": 18,
     "quadkey": "1201202310211120"},
    {"tile_x": 24.7604, "tile_y": 59.4325, "avg_d_kbps": 271966,
     "avg_u_kbps": 39742, "avg_lat_ms": 22, "tests": 43, "devices": 26,
     "quadkey": "1201202310211211"},
    {"tile_x": 24.7604, "tile_y": 59.4381, "avg_d_kbps": 303814,
     "avg_u_kbps": 49228, "avg_lat_ms": 25, "tests": 41, "devices": 28,
     "quadkey": "1201202310211031"},
    {"tile_x": 24.7549, "tile_y": 59.4353, "avg_d_kbps": 307208,
     "avg_u_kbps": 37279, "avg_lat_ms": 19, "tests": 36, "devices": 21,
     "quadkey": "1201202310211032"},
]

#: Synthetic weak tile (Lasnamäe fringe, invented speeds).
WEAK_TILE = {"tile_x": 24.86, "tile_y": 59.44, "avg_d_kbps": 22000,
             "avg_u_kbps": 8000, "avg_lat_ms": 12, "tests": 12,
             "devices": 6, "quadkey": "1201202310303333"}
WEAK_ORIGIN = (59.4405, 24.86)

#: Synthetic medium tile (invented speeds, 30–100 Mbit/s band).
MED_TILE = {"tile_x": 24.70, "tile_y": 59.42, "avg_d_kbps": 45000,
            "avg_u_kbps": 20000, "avg_lat_ms": 9, "tests": 20,
            "devices": 9, "quadkey": "1201202310210000"}
MED_ORIGIN = (59.4203, 24.70)

#: Synthetic thin tile: hot speeds but only 2 tests — must be ignored.
THIN_TILE = {"tile_x": 24.753, "tile_y": 59.437, "avg_d_kbps": 250000,
             "avg_u_kbps": 100000, "avg_lat_ms": 4, "tests": 2,
             "devices": 1, "quadkey": "1201202310211222"}


def make_snapshot(fixed, mobile, year=2026, quarter=1):
    return summarize_ookla_tallinn(fixed, mobile, year, quarter)


SNAP = make_snapshot(REAL_FIXED, REAL_MOBILE)


# ---------------------------------------------------------------------------
# URL builder + cache helpers (no network).
# ---------------------------------------------------------------------------

def test_ookla_url_builds_documented_s3_layout():
    assert ookla_url("fixed", 2026, 1) == (
        "https://ookla-open-data.s3.amazonaws.com/parquet/performance/"
        "type=fixed/year=2026/quarter=1/"
        "2026-01-01_performance_fixed_tiles.parquet")
    assert ookla_url("mobile", 2024, 4) == (
        "https://ookla-open-data.s3.amazonaws.com/parquet/performance/"
        "type=mobile/year=2024/quarter=4/"
        "2024-10-01_performance_mobile_tiles.parquet")
    assert (OOKLA_LATEST_YEAR, OOKLA_LATEST_QUARTER) == (2026, 1)
    assert OOKLA_LATEST_LABEL == "2026-Q1"
    assert quarter_label(2026, 1) == "2026-Q1"
    assert OOKLA_TTL_DAYS == 90
    assert OOKLA_MIN_TESTS == 5
    assert OOKLA_RADIUS_M == 1000.0


def test_ookla_url_rejects_bad_layer_quarter_year():
    with pytest.raises(ValueError):
        ookla_url("wifi", 2026, 1)
    with pytest.raises(ValueError):
        ookla_url("fixed", 2026, 5)
    with pytest.raises(ValueError):
        ookla_url("fixed", 2018, 1)


def test_cache_is_fresh_pins_ttl_boundaries(tmp_path):
    missing = str(tmp_path / "nope.parquet")
    assert cache_is_fresh(missing) is False
    fresh = tmp_path / "fresh.parquet"
    fresh.write_bytes(b"x")
    now = time.time()
    os.utime(fresh, (now, now))
    assert cache_is_fresh(str(fresh), ttl_days=90, now=now + 10) is True
    assert cache_is_fresh(str(fresh), ttl_days=90,
                          now=now + 91 * 86400) is False


def test_fetch_returns_fresh_cache_without_network(tmp_path):
    cached = tmp_path / "ookla-fixed-2026Q1.parquet"
    cached.write_bytes(b"PAR1-fake")
    got = fetch_ookla_parquet("fixed", 2026, 1, cache_dir=str(tmp_path))
    assert got == str(cached)
    assert open(got, "rb").read() == b"PAR1-fake"


def test_fetch_validates_before_any_io(tmp_path):
    with pytest.raises(ValueError):
        fetch_ookla_parquet("wifi", 2026, 1, cache_dir=str(tmp_path))


# ---------------------------------------------------------------------------
# Shapefile-zip leg (#725): Q2 fixed-tile path, hermetic (no network —
# the zip body is operator/pull only; the live HEAD record lives in
# docs/p4_ookla_build_q2.md, never in a test).
# ---------------------------------------------------------------------------

def test_shapefile_url_builds_q2_fixed_path():
    # Byte-pins the probe-#693-verified 2026-Q2 fixed zip (HEAD 200,
    # 342651784 B, Last-Modified 2026-08-19 — see the build doc).
    assert ookla_shapefile_url("fixed", 2026, 2) == (
        "https://ookla-open-data.s3.amazonaws.com/shapefiles/performance/"
        "type=fixed/year=2026/quarter=2/"
        "2026-04-01_performance_fixed_tiles.zip")
    assert ookla_shapefile_url("mobile", 2024, 4) == (
        "https://ookla-open-data.s3.amazonaws.com/shapefiles/performance/"
        "type=mobile/year=2024/quarter=4/"
        "2024-10-01_performance_mobile_tiles.zip")


def test_shapefile_url_rejects_bad_layer_quarter_year():
    with pytest.raises(ValueError):
        ookla_shapefile_url("wifi", 2026, 2)
    with pytest.raises(ValueError):
        ookla_shapefile_url("fixed", 2026, 5)
    with pytest.raises(ValueError):
        ookla_shapefile_url("fixed", 2018, 2)


def test_shapefile_fetch_validates_before_any_io(tmp_path):
    with pytest.raises(ValueError):
        fetch_ookla_shapefile("wifi", 2026, 2, cache_dir=str(tmp_path))


def test_served_quarter_stays_q1_until_operator_pulls_q2():
    # The map + scorer serve the Q1 extract until the operator runs
    # the Q2 pull (docs/p4_ookla_build_q2.md): bumping LATEST without
    # the extract would degrade live layers to demo — pinned.
    assert (OOKLA_LATEST_YEAR, OOKLA_LATEST_QUARTER) == (2026, 1)
    assert OOKLA_LATEST_LABEL == "2026-Q1"


def test_snapshot_cache_path_and_load_roundtrip(tmp_path):
    assert snapshot_cache_path(str(tmp_path), 2026, 1).endswith(
        "ookla-tallinn-2026Q1.json")
    assert load_ookla_snapshot(str(tmp_path), 2026, 1) is None
    bad = tmp_path / "ookla-tallinn-2026Q1.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_ookla_snapshot(str(tmp_path), 2026, 1) is None
    bad.write_text("[1,2]", encoding="utf-8")
    assert load_ookla_snapshot(str(tmp_path), 2026, 1) is None
    bad.write_text(json.dumps(SNAP), encoding="utf-8")
    loaded = load_ookla_snapshot(str(tmp_path), 2026, 1)
    assert loaded["quarter"] == "2026-Q1"
    assert loaded["n_fixed"] == 4 and loaded["n_mobile"] == 4


# ---------------------------------------------------------------------------
# Coercion + snapshot.
# ---------------------------------------------------------------------------

def test_coerce_tile_skips_rows_without_join_key():
    assert coerce_tile({"tile_x": 24.75, "tile_y": 59.43,
                        "avg_d_kbps": 100})["avg_d_kbps"] == 100
    assert coerce_tile("nope") is None
    assert coerce_tile({"tile_y": 59.43, "avg_d_kbps": 100}) is None
    assert coerce_tile({"tile_x": 999.0, "tile_y": 59.43}) is None
    # Missing speeds parse (never guessed as 0) but never score.
    tile = coerce_tile({"tile_x": 24.75, "tile_y": 59.43,
                        "tests": 9, "quadkey": "q"})
    assert tile["avg_d_kbps"] is None
    assert tile["quadkey"] == "q"


def test_summarize_keeps_canonical_shape_and_counts():
    snap = make_snapshot(REAL_FIXED + [{"nope": 1}], REAL_MOBILE,
                         2026, 1)
    assert snap["quarter"] == "2026-Q1"
    assert snap["n_fixed"] == 4 and snap["n_mobile"] == 4
    assert set(snap["fixed"][0]) == {
        "tile_x", "tile_y", "avg_d_kbps", "avg_u_kbps",
        "avg_lat_ms", "tests", "devices", "quadkey"}


# ---------------------------------------------------------------------------
# Bands (single-tile snapshots pin each edge; nearest wins, no smoothing).
# ---------------------------------------------------------------------------

def _single(fixed=None, mobile=None):
    return make_snapshot([fixed] if fixed else [],
                         [mobile] if mobile else [])


def test_fixed_bands_from_weak_to_cap():
    origin = WEAK_ORIGIN
    v, _ = dim_ookla_fixed(origin, POIS, _single(fixed=WEAK_TILE))
    assert v == 35
    v, _ = dim_ookla_fixed(MED_ORIGIN, POIS, _single(fixed=MED_TILE))
    assert v == 55
    v, _ = dim_ookla_fixed(TALLINN, POIS, _single(fixed=REAL_FIXED[0]))
    assert v == 75
    hot = dict(REAL_FIXED[0], avg_d_kbps=350000)
    v, _ = dim_ookla_fixed(TALLINN, POIS, _single(fixed=hot))
    assert v == 85


def test_mobile_bands_share_edges_and_cap():
    v, _ = dim_ookla_mobile(TALLINN, POIS, _single(mobile=REAL_MOBILE[0]))
    assert v == 85  # 411 Mbit/s top tail, still capped
    v, _ = dim_ookla_mobile(TALLINN, POIS, _single(mobile=REAL_MOBILE[1]))
    assert v == 75  # 272 Mbit/s bulk
    v, _ = dim_ookla_mobile(WEAK_ORIGIN, POIS,
                            _single(mobile=dict(WEAK_TILE)))
    assert v == 35


def test_full_snapshot_scores_both_layers_at_center():
    out = score_p4_ookla(TALLINN, POIS, SNAP)
    assert out == {"ookla_fixed": 75, "ookla_mobile": 85}


def test_thin_tile_is_ignored_never_averaged():
    # Thin hot tile sits ~60 m from center; the qualifying 75-band
    # tile is farther — nearest-QUALIFYING must win, not nearest.
    snap = make_snapshot([THIN_TILE] + REAL_FIXED, REAL_MOBILE)
    v, reason = dim_ookla_fixed(TALLINN, POIS, snap)
    assert v == 75
    # A snapshot holding ONLY the thin tile covers nothing.
    v, reason = dim_ookla_fixed(TALLINN, POIS, _single(fixed=THIN_TILE))
    assert v is None
    assert "5 testi" in reason


def test_speedless_tile_parses_but_never_scores():
    nospeed = dict(REAL_FIXED[0])
    nospeed["avg_d_kbps"] = None
    v, _ = dim_ookla_fixed(TALLINN, POIS, _single(fixed=nospeed))
    assert v is None


# ---------------------------------------------------------------------------
# NULLs: every gap stays NULL with Estonian honesty markers.
# ---------------------------------------------------------------------------

def test_null_paths_stay_null():
    cases = [
        dim_ookla_fixed(None, POIS, SNAP),
        dim_ookla_mobile(None, POIS, SNAP),
        dim_ookla_fixed(TALLINN, POIS, None),
        dim_ookla_mobile(TALLINN, POIS, None),
        dim_ookla_fixed(TALLINN, POIS, {"quarter": "2026-Q1",
                                       "fixed": [], "mobile": []}),
        dim_ookla_fixed(TARTU, POIS, SNAP),
        dim_ookla_mobile(TARTU, POIS, SNAP),
        dim_ookla_fixed(TALLINN, None, None),
    ]
    for v, _ in cases:
        assert v is None


def test_all_null_reasons_carry_honesty_markers():
    nulls = [
        dim_ookla_fixed(None, POIS, SNAP)[1],
        dim_ookla_mobile(None, POIS, SNAP)[1],
        dim_ookla_fixed(TALLINN, POIS, None)[1],
        dim_ookla_mobile(TALLINN, POIS, {"quarter": "2026-Q1"})[1],
        dim_ookla_fixed(TALLINN, POIS, make_snapshot([], []))[1],
        dim_ookla_fixed(TARTU, POIS, SNAP)[1],
    ]
    for reason in nulls:
        assert "hinnang" in reason
        assert "EI OLE" in reason
        assert "ära feigi" in reason
        assert "netikaardilt" in reason and "rikkekaardilt" in reason
        assert "mõõdetud" not in reason
        assert "garanteeritud" not in reason


def test_no_snapshot_reason_names_quarterly_ingest():
    _, reason = dim_ookla_fixed(TALLINN, POIS, None)
    assert "2026-Q1" in reason
    assert "vahemällu" in reason


def test_empty_layer_names_region_cut_overturn_path():
    _, reason = dim_ookla_fixed(TALLINN, POIS, make_snapshot([], []))
    assert "tühi" in reason and "2026-04-16" in reason


# ---------------------------------------------------------------------------
# Scored reasons: proxy honesty, never fake precision.
# ---------------------------------------------------------------------------

def test_scored_reasons_name_tile_quarter_and_counts():
    v, reason = dim_ookla_fixed(TALLINN, POIS, SNAP)
    assert v == 75
    assert "hinnang" in reason
    assert "2026-Q1" in reason
    assert "122 Mbit/s" in reason
    assert "67 testi" in reason
    assert "~0,6 km ruudu" in reason
    assert "mitte aadressi mõõtmine" in reason
    assert "EI OLE" not in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    v, reason = dim_ookla_mobile(TALLINN, POIS, SNAP)
    assert v == 85
    assert "307 Mbit/s" in reason and "36 testi" in reason


def test_scores_capped_at_85_across_speed_sweep():
    for d_kbps in (1000, 29999, 30000, 99999, 100000, 299999,
                   300000, 900000):
        tile = dict(REAL_FIXED[0], avg_d_kbps=d_kbps)
        v, reason = dim_ookla_fixed(TALLINN, POIS, _single(fixed=tile))
        assert v is not None and v <= 85, d_kbps
        assert "EI OLE" not in reason


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_both_layers():
    assert [k for k, _, _ in P4_OOKLA_DIMS] == ["ookla_fixed", "ookla_mobile"]
    assert [p for _, p, _ in P4_OOKLA_DIMS] == ["P4-009", "P4-009"]
    assert len({fn for _, _, fn in P4_OOKLA_DIMS}) == 2
    assert ookla.P4_OOKLA_DIMS is P4_OOKLA_DIMS
    out = score_p4_ookla(TALLINN, POIS, SNAP)
    assert out == {"ookla_fixed": 75, "ookla_mobile": 85}
    assert score_p4_ookla(None, None, None) == {
        "ookla_fixed": None, "ookla_mobile": None}
    assert score_p4_ookla(TARTU, POIS, SNAP) == {
        "ookla_fixed": None, "ookla_mobile": None}
