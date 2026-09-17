"""Forest-change dims (issue #548): hermetic gate + band tests.

No network, no snapshot reads: the gate and the pure banding run on
fixture changes. Run:
python3 -m pytest services/scoring/tests/test_dims_p4_forestchange.py -q
"""

from datetime import date

from dims_p4_forestchange import (
    CAVEAT,
    FORESTCHANGE_DIMS,
    LAYER_META,
    LICENCE_OK,
    LICENCE_NOTE,
    _age_years,
    _score_change,
    dim_forest_recent,
    score_forestchange,
)

TALLINN = (59.4372, 24.7536)
TODAY = date(2026, 9, 16)


def _chg(dist, first="2023-05-01", second="2024-05-01", area=1.2):
    return {"dist_m": dist, "first_date": first,
            "second_date": second, "area_ha": area}


# --- licence gate: OPEN since the #624 verdict ----------------------------------

def test_licence_gate_open_with_note():
    # Bundled ETAK-open-data-licence.pdf + PUBLIC catalogue access
    # (verdict in the module docstring): the pinned bands go live.
    assert LICENCE_OK is True
    assert "litsents" in LICENCE_NOTE
    s, reason = dim_forest_recent(TALLINN, [_chg(100)], TODAY)
    assert s == 30
    assert "ametlik raiestatistika" in reason  # publisher caveat present
    assert score_forestchange(TALLINN, [_chg(100)], TODAY) == {
        "forest_recent": 30}


def test_empty_window_is_null_never_safe():
    s, reason = dim_forest_recent(TALLINN, [], TODAY)
    assert s is None  # gated today; NULL rule also pinned below


def test_nodata_reasons():
    assert dim_forest_recent(None, [_chg(100)], TODAY)[0] is None
    assert dim_forest_recent(TALLINN, None, TODAY)[0] is None


# --- pure bands (pinned now, live on licence-day) ---------------------------------

def test_age_parser():
    assert _age_years("2023-05-01", "2024-05-01", TODAY) is not None
    age = _age_years("2023-05-01", "2024-05-01", TODAY)
    assert age is not None and 2.0 < age < 3.0
    assert _age_years(None, None, TODAY) is None
    assert _age_years("vigane", "ka-vigane", TODAY) is None
    assert _age_years(date(2020, 1, 1), None, TODAY) is not None


def test_score_bands():
    assert _score_change(1.0, 200) == 30    # fresh + near
    assert _score_change(3.0, 500) == 30    # edge inclusive
    assert _score_change(2.0, 1000) == 55   # fresh + mid
    assert _score_change(7.0, 300) == 60    # older + near (regrowth)
    assert _score_change(15.0, 300) == 70   # old + near
    assert _score_change(1.0, 5000) == 70   # fresh + far
    assert _score_change(None, 100) is None
    assert _score_change(1.0, None) is None


def test_live_shape_gate_open():
    # The worst change wins and the empty window stays NULL (never
    # "safe forest").
    s, reason = dim_forest_recent(
        TALLINN, [_chg(1200, "2023-05-01", "2024-05-01"), _chg(200)],
        TODAY)
    assert s == 30 and "200 m" in reason and CAVEAT in reason
    s2, reason2 = dim_forest_recent(TALLINN, [], TODAY)
    assert s2 is None and "turvalist metsa see ei tõenda" in reason2
    assert "turvaline mets" not in reason2  # never the positive claim


# --- registry wiring ---------------------------------------------------------------

def test_dims_registry_and_entry_point():
    assert [k for k, _, _ in FORESTCHANGE_DIMS] == ["forest_recent"]
    assert set(LAYER_META) == {"forest_recent"}
    assert "litsents" in LAYER_META["forest_recent"]["source"]
