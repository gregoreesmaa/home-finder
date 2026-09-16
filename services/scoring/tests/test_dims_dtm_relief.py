"""DTM relief/flatness legs (issue #553): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture artefacts.
Run: python3 -m pytest services/scoring/tests/test_dims_dtm_relief.py -q
"""

import dims_dtm_relief as dtm
from dims_dtm_relief import (
    DIMS,
    DTM_COVERAGES,
    KLINT_NEAR_M,
    LAYER_META,
    character,
    check_vintage,
    dim_cycling,
    dim_klint_build,
    dim_lowland,
    dim_viewpoint,
    histogram,
    p336_crosscheck,
    score_dtm,
    slope_character,
)

TALLINN = (59.4372, 24.7536)


def _relief(vintage="2020", z=6.0, slope=3.0, relief=4.0, klint=500.0):
    return {"vintage": vintage, "z_m": z, "slope_pct": slope,
            "relief_m": relief, "klint_near_m": klint}


# --- vintage discipline ----------------------------------------------------

def test_coverages_observed_live():
    assert DTM_COVERAGES == frozenset({"dtm-25", "dtm-10", "dtm-1"})
    assert LAYER_META["crs"] == "EPSG:3301"


def test_vintage_gate():
    assert check_vintage("2020")
    assert check_vintage("2012")
    assert not check_vintage("2027")  # not observed / future
    assert not check_vintage(None)
    assert not check_vintage(2020)


def test_unknown_vintage_flagged_not_silent():
    s, reason = dim_lowland(TALLINN, _relief(vintage="2099"))
    assert s is not None and "tundmatu vintage" in reason


# --- character overlay first (no score field) ------------------------------

def test_character_has_no_score():
    assert slope_character(1.0) == "tasane"
    assert slope_character(3.0) == "lauge"
    assert slope_character(7.0) == "mõõdukas"
    assert slope_character(15.0) == "järske"
    assert slope_character(30.0) == "klint"
    txt = character(_relief(z=45.0, slope=25.0, relief=30.0))
    assert "klint" in txt and "45.0 m" in txt


def test_character_nodata_is_honest():
    assert "katet pole" in character(None)
    assert "katet pole" in character({"vintage": "2020"})


# --- lowland (flood-avoider, bad side) -------------------------------------

def test_lowland_bands():
    assert dim_lowland(TALLINN, _relief(z=2.0))[0] == 35
    assert dim_lowland(TALLINN, _relief(z=4.0))[0] == 55
    assert dim_lowland(TALLINN, _relief(z=7.0))[0] == 65
    assert dim_lowland(TALLINN, _relief(z=40.0))[0] == 75
    s, reason = dim_lowland(TALLINN, _relief(z=2.0))
    assert "niiske" in reason and "mõõdetud" in reason


def test_lowland_nodata_is_none():
    assert dim_lowland(TALLINN, None)[0] is None
    assert dim_lowland(None, _relief())[0] is None
    assert "puuduvad" in dim_lowland(TALLINN, None)[1]


# --- viewpoint (view-seeker, capped) ---------------------------------------

def test_viewpoint_capped():
    assert dim_viewpoint(TALLINN, _relief(relief=1.0))[0] == 55
    assert dim_viewpoint(TALLINN, _relief(relief=4.0))[0] == 65
    assert dim_viewpoint(TALLINN, _relief(relief=30.0))[0] <= 75
    s, reason = dim_viewpoint(TALLINN, _relief(relief=8.0))
    assert "vaatemaitse" in reason and "max 75" in reason


def test_viewpoint_unknown_relief_is_honest():
    d = {"vintage": "2020", "z_m": 10.0, "slope_pct": 3.0}
    s, reason = dim_viewpoint(TALLINN, d)
    assert s == 60 and "hinnang" in reason


# --- cycling (cyclist) -----------------------------------------------------

def test_cycling_bands():
    assert dim_cycling(TALLINN, _relief(slope=1.0))[0] == 80
    assert dim_cycling(TALLINN, _relief(slope=4.0))[0] == 65
    assert dim_cycling(TALLINN, _relief(slope=8.0))[0] == 50
    assert dim_cycling(TALLINN, _relief(slope=15.0))[0] == 35
    assert dim_cycling(TALLINN, _relief(slope=30.0))[0] == 25
    s, reason = dim_cycling(TALLINN, _relief(slope=8.0))
    assert "rattur" in reason


# --- klint build flag (buyer check, never a ban) ---------------------------

def test_klint_needs_both_nearness_and_steepness():
    s, reason = dim_klint_build(TALLINN, _relief(slope=25.0, klint=30.0))
    assert s == 40 and "lisakontroll" in reason and "mitte keeldu" in reason
    # near but flat -> ordinary
    assert dim_klint_build(TALLINN, _relief(slope=2.0, klint=30.0))[0] == 65
    # steep but far -> ordinary
    assert dim_klint_build(TALLINN, _relief(slope=25.0, klint=500.0))[0] == 65
    assert KLINT_NEAR_M == 50.0


def test_klint_unknown_distance_is_honest():
    d = {"vintage": "2020", "z_m": 40.0, "slope_pct": 25.0}
    s, reason = dim_klint_build(TALLINN, d)
    assert s == 65 and "hinnang" in reason


# --- p336 cross-check ------------------------------------------------------

def test_p336_crosscheck_table():
    assert p336_crosscheck(30.0, 25.0) == "mõlemad märgivad"
    assert p336_crosscheck(30.0, 2.0) == "ainult OSM"
    assert p336_crosscheck(500.0, 25.0) == "ainult mõõdetud"
    assert p336_crosscheck(500.0, 2.0) == "mõlemad vaikivad"
    assert p336_crosscheck(None, 2.0) == "andmed puuduvad"


# --- calibration windows discriminate (fixture, clearly synthetic) ---------

def test_calibration_windows_discriminate():
    klint = [18.0, 22.0, 25.0, 30.0, 15.0, 28.0]      # Lasnamäe edge
    nomme = [4.0, 6.0, 8.0, 5.0, 7.0, 9.0]              # Nõmme slope
    pirita = [0.5, 1.0, 1.5, 0.8, 1.2, 2.5]             # Pirita lowland
    edges = [2, 5, 10, 20]
    assert histogram(klint, edges) == [0, 0, 0, 2, 4]
    assert histogram(nomme, edges) == [0, 2, 4, 0, 0]
    assert histogram(pirita, edges) == [5, 1, 0, 0, 0]


# --- wiring ----------------------------------------------------------------

def test_wiring():
    assert set(DIMS) == {"lowland", "viewpoint", "cycling", "klint_build"}
    out = score_dtm(TALLINN, _relief())
    assert set(out) == set(DIMS)
    nulls = score_dtm(TALLINN, None)
    assert all(v[0] is None for v in nulls.values())
    assert "CC BY 4.0" in LAYER_META["licence"]
