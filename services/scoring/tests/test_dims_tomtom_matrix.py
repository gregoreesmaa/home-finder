"""Tests for services/scoring/dims_tomtom_matrix.py (issue #669).

Hermetic and pure: fixture matrix bodies, no network, no key.
Pins the no-key NULL path, banding, and the Estonian buyer reason.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from dims_tomtom_matrix import (  # noqa: E402
    build_table,
    dim_car_commute,
    score_tomtom_matrix,
)


def _table():
    return build_table([
        {"area_id": "a1", "hub": "city-center",
         "rush_s": 1500, "offpeak_s": 1200},
        {"area_id": "a1", "hub": "ulemiste",
         "rush_s": 900, "offpeak_s": 840},
        {"area_id": "a2", "hub": "city-center",
         "rush_s": None, "offpeak_s": None},
    ])


def test_no_key_null_never_guesses():
    score, reason = dim_car_commute((59.437, 24.753), None, "a1")
    assert score is None
    assert "EI OLE" in reason


def test_best_hub_wins_and_reason_carries_surcharge():
    score, reason = dim_car_commute((59.437, 24.753), _table(), "a1")
    assert score == 75  # best hub: 900 s = 15 min -> kiire
    assert "15 min" in reason
    assert "ulemiste" in reason
    assert "+1 ummikulisand" in reason or "ummikulisand" in reason


def test_unmeasured_area_is_null_not_bad():
    score, reason = dim_car_commute((59.437, 24.753), _table(), "a2")
    assert score is None
    assert "mõõtmata pole halb" in reason


def test_score_entry_point():
    out = score_tomtom_matrix((59.437, 24.753), _table(), "a1")
    assert out == {"car_commute": 75}
    assert score_tomtom_matrix(None, None, None) == {"car_commute": None}


def test_quota_constants_pin_issue_math():
    import dims_tomtom_matrix as d
    assert d.MATRIX_ORIGINS == 196
    assert len(d.HUBS) == 5
    assert d.MATRIX_MAX_CALLS == 10  # 5 hubs x rush + off-peak
    assert d.MATRIX_TXN_PER_BAND == 980  # issue-body number
    assert d.MATRIX_TXN_PER_REFRESH <= d.MATRIX_DAILY_BUDGET
