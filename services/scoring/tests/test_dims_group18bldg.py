"""3D building-height dims (issue #547): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture artefacts.
Run: python3 -m pytest services/scoring/tests/test_dims_group18bldg.py -q
"""

import math

import dims_group18bldg as bldg
from dims_group18bldg import (
    BLDG_DIMS,
    LAYER_META,
    SHADOW_FACTOR,
    WINTER_SUN_ALT_DEG,
    dim_bldg_overlook,
    dim_bldg_shade,
    ehr_link_rate,
    score_bldg,
    shade_polygon,
    shadow_length_m,
)

TALLINN = (59.4372, 24.7536)


def _bldg(z_max=27.5, dist=18.0, als_year=2024, lod="LoD1",
          etak="12345", ehr="999"):
    return {"als_year": als_year,
            "nearest": {"z_max": z_max, "dist_m": dist, "etak_id": etak,
                        "ehr_gid": ehr, "lod": lod}}


# --- shadow physics ----------------------------------------------------------

def test_shadow_factor_matches_stated_angle():
    assert WINTER_SUN_ALT_DEG == 12.0
    assert abs(SHADOW_FACTOR - 1.0 / math.tan(math.radians(12.0))) < 1e-9
    assert abs(shadow_length_m(27.5) - 27.5 * SHADOW_FACTOR) < 1e-9


def test_shade_polygon_worked_example():
    # One-building worked example (docs carry the sketch): 27.5 m slab,
    # winter sun azimuth 180 deg (south) -> shadow points north (~129 m).
    poly = shade_polygon(27.5, 180.0)
    assert poly["length_m"] == round(27.5 * SHADOW_FACTOR, 1)
    assert poly["dy_m"] > 100  # deep winter shadow, stated sketch
    assert abs(poly["dx_m"]) < 1.0  # due-south sun: no east-west throw


# --- shade bands: old geometry caps -> measured -------------------------------

def test_shade_measured_bands():
    # 27.5 m at 18 m: deep inside the ~129 m shadow -> worst half.
    s, reason = dim_bldg_shade(TALLINN, _bldg())
    assert s == 25 and "27.5 m" in reason and "ALS 2024" in reason
    assert "hinnang" in reason
    assert dim_bldg_shade(TALLINN, _bldg(z_max=12.0, dist=10.0))[0] == 45
    assert dim_bldg_shade(TALLINN, _bldg(z_max=8.0, dist=5.0))[0] == 55
    # Just outside one shadow length but inside two -> possible.
    assert dim_bldg_shade(TALLINN, _bldg(z_max=10.0, dist=60.0))[0] == 70
    # Far clear -> high.
    assert dim_bldg_shade(TALLINN, _bldg(z_max=10.0, dist=200.0))[0] == 85


def test_shade_unknown_als_flagged():
    s, reason = dim_bldg_shade(TALLINN, _bldg(als_year=None))
    assert s is not None and "tundmatu ALS-aasta" in reason


def test_shade_nodata_is_none():
    assert dim_bldg_shade(TALLINN, None)[0] is None
    assert dim_bldg_shade(None, _bldg())[0] is None
    assert dim_bldg_shade(TALLINN, {})[0] is None
    assert dim_bldg_shade(TALLINN, {"als_year": 2024})[0] is None
    s, reason = dim_bldg_shade(TALLINN, None)
    assert "EHR/ALS" in reason


# --- overlooking ---------------------------------------------------------------

def test_overlook_bands():
    assert dim_bldg_overlook(TALLINN, _bldg())[0] == 35
    assert dim_bldg_overlook(TALLINN, _bldg(z_max=12.0, dist=40.0))[0] == 55
    assert dim_bldg_overlook(TALLINN, _bldg(z_max=8.0, dist=40.0))[0] == 75
    assert dim_bldg_overlook(TALLINN, _bldg(z_max=30.0, dist=150.0))[0] == 90
    assert dim_bldg_overlook(TALLINN, None)[0] is None


# --- EHR join path (recorded, not rebuilt) --------------------------------------

def test_ehr_link_rate():
    rows = [{"ehr_gid": "a"}, {"ehr_gid": None}, {"ehr_gid": "c"},
            {"etak_id": "x"}]
    assert ehr_link_rate(rows) == 0.5
    assert ehr_link_rate([]) is None


# --- pre/post histogram shape ----------------------------------------------------

def test_upgrade_discriminates_tallinn_window_shape():
    # Fixture window (synthetic, labelled): footprint-only guesses give
    # two heights one band; measured z_max spreads three bands.
    heights = [8.5, 9.0, 12.0, 27.5, 30.0, 6.5]
    scores = [dim_bldg_shade(TALLINN, _bldg(z_max=h, dist=10.0))[0]
              for h in heights]
    assert len(set(scores)) >= 3


# --- registry wiring ---------------------------------------------------------------

def test_dims_registry_and_entry_point():
    assert [k for k, _, _ in BLDG_DIMS] == ["bldg_shade", "bldg_overlook"]
    assert [p for _, p, _ in BLDG_DIMS] == ["p405", "p468"]
    assert score_bldg(TALLINN, _bldg()) == {
        "bldg_shade": 25, "bldg_overlook": 35}
    assert score_bldg(TALLINN, None) == {
        "bldg_shade": None, "bldg_overlook": None}
    assert set(LAYER_META) == {"bldg_shade", "bldg_overlook"}
    assert all("hinnang" in m["title"] for m in LAYER_META.values())
    assert bldg.LOD_LICENCE.startswith("CC BY 4.0")
