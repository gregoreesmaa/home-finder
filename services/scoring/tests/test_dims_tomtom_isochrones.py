"""Tests for services/scoring/dims_tomtom_isochrones.py (issue #670).

Hermetic and pure: fixture shed rings, no network, no key. Pins the
no-key NULL path, hub counting, and the Estonian buyer reason.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from dims_tomtom_isochrones import (  # noqa: E402
    build_table,
    dim_jobs_within_30min,
    point_in_ring,
    score_tomtom_sheds,
)

RING = [(59.40, 24.70), (59.40, 24.80), (59.47, 24.80), (59.47, 24.70)]


def _table():
    return build_table([
        {"hub": "city-center", "budget_s": 1800, "band": "rush",
         "ring": RING},
        {"hub": "ulemiste", "budget_s": 1800, "band": "rush",
         "ring": RING},
        {"hub": "port", "budget_s": 1800, "band": "offpeak",
         "ring": RING},
        {"hub": "mustamae", "budget_s": 900, "band": "rush",
         "ring": RING},
    ])


def test_no_key_null_never_guesses():
    score, reason = dim_jobs_within_30min((59.437, 24.753), None)
    assert score is None
    assert "EI OLE" in reason


def test_rush_30min_hubs_count_offpeak_ignored():
    score, reason = dim_jobs_within_30min((59.44, 24.75), _table())
    assert score == 50  # 2 rush hubs cover; off-peak + 15-min ignored
    assert "2/5" in reason


def test_outside_all_sheds_is_far_not_bad():
    score, _ = dim_jobs_within_30min((59.50, 24.90), _table())
    assert score == 35


def test_point_in_ring_parity():
    assert point_in_ring(59.44, 24.75, RING) is True
    assert point_in_ring(59.50, 24.90, RING) is False
    assert point_in_ring(59.44, 24.75, []) is False


def test_score_entry_point_and_quota_constants():
    out = score_tomtom_sheds((59.44, 24.75), _table())
    assert out == {"jobs_within_30min": 50}
    assert score_tomtom_sheds(None, None) == {"jobs_within_30min": None}
    import dims_tomtom_isochrones as d
    assert d.SHED_MAX_CALLS == 20  # 5 hubs x 2 budgets x 2 bands
    assert d.SHED_BUDGETS_S == (900, 1800)
