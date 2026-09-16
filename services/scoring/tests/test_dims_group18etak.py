"""Measured ETAK legs (issue #552): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture artefacts.
Run: python3 -m pytest services/scoring/tests/test_dims_group18etak.py -q
"""

import dims_group18etak as etak
from dims_group18etak import (
    DIMS,
    ETAK_CRS,
    ETAK_LICENCE,
    LAYER_META,
    check_vintage,
    dim_etal_relief,
    dim_etal_water,
    dim_etal_wetland,
    dim_etal_yard,
    histogram,
    score_etak,
)

TALLINN = (59.4372, 24.7536)


def _etak(vintage="2018-01-23T19:13:23Z", wetland=None, water=None,
          yard=None, relief=None):
    d = {"vintage": vintage}
    if wetland is not None:
        d["wetland"] = wetland
    if water is not None:
        d["water"] = water
    if yard is not None:
        d["yard"] = yard
    if relief is not None:
        d["relief"] = relief
    return d


# --- vintage discipline (DAILY feed vs survey vintages) --------------------

def test_vintage_gate():
    assert check_vintage("2018-01-23T19:13:23Z")
    assert check_vintage("2018")
    assert not check_vintage(None)
    assert not check_vintage("")
    assert not check_vintage(2018)


def test_unknown_vintage_flagged_not_silent():
    d = _etak(vintage="tundmatu",
              wetland={"inside": True, "near_m": 0, "tyyp": "Soovik"})
    s, reason = dim_etal_wetland(TALLINN, d)
    assert s is not None and "tundmatu vintage" in reason


# --- wetland → dampness ----------------------------------------------------

def test_wetland_inside_bands_follow_tyyp():
    assert dim_etal_wetland(
        TALLINN, _etak(wetland={"inside": True, "tyyp": "Madalsoo"}))[0] == 25
    assert dim_etal_wetland(
        TALLINN, _etak(wetland={"inside": True, "tyyp": "Raba"}))[0] == 25
    assert dim_etal_wetland(
        TALLINN, _etak(wetland={"inside": True, "tyyp": "Soovik"}))[0] == 35
    assert dim_etal_wetland(
        TALLINN, _etak(wetland={"inside": True, "tyyp": "Õõtsik"}))[0] == 35
    assert dim_etal_wetland(
        TALLINN, _etak(wetland={"inside": True, "tyyp": "Muu"}))[0] == 30
    s, reason = dim_etal_wetland(
        TALLINN, _etak(wetland={"inside": True, "tyyp": "Soovik"}))
    assert "mõõdetud" in reason and "OSM asemel ETAK" in reason


def test_wetland_near_bands():
    d = _etak(wetland={"inside": False, "near_m": 40, "tyyp": "Soovik"})
    assert dim_etal_wetland(TALLINN, d)[0] == 55
    d = _etak(wetland={"inside": False, "near_m": 120, "tyyp": "Soovik"})
    assert dim_etal_wetland(TALLINN, d)[0] == 70


def test_wetland_null_where_no_feature():
    assert dim_etal_wetland(TALLINN, None)[0] is None
    assert dim_etal_wetland(TALLINN, {})[0] is None
    assert dim_etal_wetland(None, _etak(
        wetland={"inside": True, "tyyp": "Raba"}))[0] is None
    s, reason = dim_etal_wetland(
        TALLINN, _etak(wetland={"inside": False, "near_m": 500}))
    assert s is None and "NULL" in reason


# --- water → drainage ------------------------------------------------------

def test_water_bands():
    d = _etak(water={"inside": True, "name": "Harku järv", "kind": "järv"})
    s, reason = dim_etal_water(TALLINN, d)
    assert s == 30 and "Harku" in reason and "mõõdetud" in reason
    d = _etak(water={"inside": False, "near_m": 20, "name": "Pirita jõgi"})
    assert dim_etal_water(TALLINN, d)[0] == 50
    d = _etak(water={"inside": False, "near_m": 80, "kind": "jõgi"})
    assert dim_etal_water(TALLINN, d)[0] == 65
    d = _etak(water={"inside": False, "near_m": 500})
    assert dim_etal_water(TALLINN, d)[0] is None


def test_water_null_where_no_feature():
    assert dim_etal_water(TALLINN, None)[0] is None
    assert dim_etal_water(TALLINN, {})[0] is None


# --- yard → impervious/green ------------------------------------------------

def test_yard_classes():
    d = _etak(yard={"inside": True, "klass": "Eraõued"})
    s, reason = dim_etal_yard(TALLINN, d)
    assert s == 45 and "kõvakate" in reason
    d = _etak(yard={"inside": True, "klass": "Tootmisõued"})
    assert dim_etal_yard(TALLINN, d)[0] == 45
    d = _etak(yard={"inside": True, "klass": "Haljasala"})
    assert dim_etal_yard(TALLINN, d)[0] == 70
    d = _etak(yard={"inside": True, "klass": "Muu kõlvik"})
    assert dim_etal_yard(TALLINN, d)[0] == 60
    d = _etak(yard={"inside": False, "klass": "Eraõued"})
    assert dim_etal_yard(TALLINN, d)[0] is None


# --- pinnamood licence gate -------------------------------------------------

def test_relief_always_null_gated():
    s, reason = dim_etal_relief(TALLINN, _etak(relief={"inside": True}))
    assert s is None and "litsents" in reason and "EI OLE" in reason
    s, _ = dim_etal_relief(TALLINN, None)
    assert s is None


# --- pre/post discrimination (fixture, clearly synthetic) -------------------

def test_upgrade_discriminates_on_fixture_windows():
    # Tallinn window: mixed distances; rural window: mostly far.
    tallinn = [10, 40, 120, 300, 25, 90, 200, 5, 60, 400, 30, 150]
    rural = [400, 600, 800, 500, 700, 450, 900, 550, 650, 750, 850, 1000]
    edges = [50, 150]
    assert histogram(tallinn, edges) == [5, 4, 3]
    assert histogram(rural, edges) == [0, 0, 12]


# --- wiring -----------------------------------------------------------------

def test_wiring():
    assert set(DIMS) == {"wetland", "water", "yard", "relief"}
    assert ETAK_CRS == "EPSG:3301"
    assert "CC BY 4.0" in ETAK_LICENCE
    out = score_etak(TALLINN, _etak(
        wetland={"inside": True, "tyyp": "Raba"},
        water={"inside": False, "near_m": 20},
        yard={"inside": True, "klass": "Haljasala"},
        relief={"inside": True}))
    assert out["wetland"][0] == 25
    assert out["water"][0] == 50
    assert out["yard"][0] == 70
    assert out["relief"][0] is None
    assert LAYER_META["crs"] == "EPSG:3301"
