"""CHM measured-canopy dims (issue #546): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture artefacts.
Run: python3 -m pytest services/scoring/tests/test_dims_group18chm.py -q
"""

import dims_group18chm as chm
from dims_group18chm import (
    CHM_DIMS,
    CHM_VINTAGES,
    FALL_CAP_M,
    LAYER_META,
    check_vintage,
    dim_chm_fall,
    dim_chm_leaf,
    dim_chm_shade,
    histogram,
    score_chm,
)

TALLINN = (59.4372, 24.7536)


def _canopy(vintage="2024_suvi", h25=18.5, h100=22.0, decid=True):
    return {"vintage": vintage, "max_h_25m": h25,
            "max_h_100m": h100, "decid_near": decid}


# --- vintage discipline ----------------------------------------------------

def test_vintage_gate():
    assert check_vintage("2024_suvi")
    assert check_vintage("2008-11")
    assert len(CHM_VINTAGES) == 24
    assert not check_vintage("2025_suvi")  # not observed live
    assert not check_vintage(None)
    assert not check_vintage(2024)


def test_unknown_vintage_flagged_not_silent():
    s, reason = dim_chm_fall(TALLINN, _canopy(vintage="2025_suvi"))
    assert s is not None and "tundmatu vintage" in reason


# --- fall zone: measured metres, bands on class breaks ---------------------

def test_fall_bands_follow_class_breaks():
    assert dim_chm_fall(TALLINN, _canopy(h25=0.5))[0] == 85
    assert dim_chm_fall(TALLINN, _canopy(h25=3.0))[0] == 70
    assert dim_chm_fall(TALLINN, _canopy(h25=8.0))[0] == 55
    assert dim_chm_fall(TALLINN, _canopy(h25=15.0))[0] == 40
    assert dim_chm_fall(TALLINN, _canopy(h25=25.0))[0] == 25
    assert dim_chm_fall(TALLINN, _canopy(h25=45.0))[0] == 15  # over cap
    s, reason = dim_chm_fall(TALLINN, _canopy(h25=18.5))
    assert s == 40 and "18.5 m" in reason and "2024_suvi" in reason


def test_fall_nodata_is_none():
    assert dim_chm_fall(TALLINN, None)[0] is None
    assert dim_chm_fall(None, _canopy())[0] is None
    assert dim_chm_fall(TALLINN, {"vintage": "2024_suvi"})[0] is None
    s, reason = dim_chm_fall(TALLINN, None)
    assert "CHM andmed puuduvad" in reason


def test_fall_no_cover_window_is_honest_fallback():
    s, reason = dim_chm_fall(TALLINN, _canopy(h25=None, h100=12.0))
    assert s == 80 and "katet pole" in reason


# --- leaf: height + proxy, unknown leaf never worst ------------------------

def test_leaf_deciduous_bands():
    assert dim_chm_leaf(TALLINN, _canopy(h100=0.5))[0] == 90
    assert dim_chm_leaf(TALLINN, _canopy(h100=3.0))[0] == 65
    assert dim_chm_leaf(TALLINN, _canopy(h100=15.0))[0] == 35
    assert dim_chm_leaf(TALLINN, _canopy(h100=28.0))[0] == 20


def test_leaf_unknown_leaf_moderate_never_worst():
    s, reason = dim_chm_leaf(
        TALLINN, _canopy(h100=28.0, decid=None))
    assert s == 55 and "kaardistamata" in reason


def test_leaf_nodata_is_none():
    assert dim_chm_leaf(TALLINN, None)[0] is None


# --- shade cross-check ------------------------------------------------------

def test_shade_bands():
    assert dim_chm_shade(TALLINN, _canopy(h25=2.0))[0] == 85
    assert dim_chm_shade(TALLINN, _canopy(h25=8.0))[0] == 65
    assert dim_chm_shade(TALLINN, _canopy(h25=15.0))[0] == 45
    assert dim_chm_shade(TALLINN, _canopy(h25=25.0))[0] == 30
    assert dim_chm_shade(TALLINN, _canopy(h25=35.0))[0] == 20
    assert dim_chm_shade(TALLINN, None)[0] is None


# --- histogram helper (pre/post upgrade check) -------------------------------

def test_histogram_bins():
    assert histogram([1, 2, 3, 9], [2, 5]) == [2, 1, 1]
    assert histogram([], [2, 5]) == [0, 0, 0]


def test_upgrade_discriminates_on_fixture_window():
    # Synthetic fixture window (clearly labelled — real Tallinn-window run
    # belongs to the bulk job): proxy guesses cluster, measured spreads.
    proxy = [25] * 12  # old flat 25 m cap: no discrimination
    measured = [2.0, 3.5, 8.0, 12.0, 15.0, 18.5, 22.0, 26.0,
                5.0, 9.5, 14.0, 31.0]
    edges = [4, 10, 20, 30]
    assert histogram(proxy, edges) == [0, 0, 0, 12, 0]
    assert histogram(measured, edges) == [2, 3, 4, 2, 1]
    scores = [dim_chm_fall(TALLINN, _canopy(h25=h))[0] for h in measured]
    assert len(set(scores)) >= 4  # measured metres spread across bands


# --- registry wiring ----------------------------------------------------------

def test_dims_registry_and_entry_point():
    assert [k for k, _, _ in CHM_DIMS] == ["chm_fall", "chm_leaf", "chm_shade"]
    assert [p for _, p, _ in CHM_DIMS] == ["p65", "p395", "p479"]
    out = score_chm(TALLINN, _canopy())
    assert out == {"chm_fall": 40, "chm_leaf": 20, "chm_shade": 45}
    assert score_chm(TALLINN, None) == {
        "chm_fall": None, "chm_leaf": None, "chm_shade": None}
    assert FALL_CAP_M == 40.0
    assert set(LAYER_META) == {"chm_fall", "chm_leaf", "chm_shade"}
    assert all("CHM" in m["source"] for m in LAYER_META.values())
    assert chm.CHM_LICENCE.startswith("CC BY 4.0")
