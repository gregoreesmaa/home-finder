"""Tests for services/scoring/dims_tomtom_incidents.py (issue #672).

Hermetic and pure: fixture incidents, no network, no key. Pins the
no-key NULL path, the STALE-is-NULL expiry rule, and nearby scoring.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from dims_tomtom_incidents import (  # noqa: E402
    INCIDENTS_TTL_S,
    build_table,
    dim_teeolud,
    is_fresh,
    score_tomtom_incidents,
)


def _table(ts=None):
    return build_table([
        {"incident_id": "i1", "category": 8, "magnitude": 3,
         "description": "Ummik Tartu mnt", "points": [(59.428, 24.78)]},
        {"incident_id": "i2", "category": 10, "magnitude": 1,
         "description": None, "points": [(59.41, 24.70)]},
    ], fetched_at=time.time() if ts is None else ts)


def test_no_key_null_never_guesses():
    score, reason = dim_teeolud((59.437, 24.753), None)
    assert score is None
    assert "EI OLE" in reason


def test_stale_snapshot_is_null_never_live():
    old = _table(time.time() - INCIDENTS_TTL_S - 60)
    assert is_fresh(old) is False
    score, reason = dim_teeolud((59.437, 24.753), old)
    assert score is None
    assert "aegunud" in reason


def test_nearby_jam_scores_down_with_magnitude():
    score, reason = dim_teeolud((59.428, 24.781), _table())
    assert score == 60  # 1 nearby incident
    assert "suur" in reason  # magnitude 3
    assert "mitte reaalajas" in reason


def test_no_nearby_is_free():
    score, _ = dim_teeolud((59.49, 24.60), _table())
    assert score == 75


def test_score_entry_point_and_quota_constants():
    out = score_tomtom_incidents((59.428, 24.781), _table())
    assert out == {"teeolud": 60}
    assert score_tomtom_incidents(None, None) == {"teeolud": None}
    import dims_tomtom_incidents as d
    assert d.INCIDENTS_MAX_CALLS == 2  # 1-2 txn/day
    assert d.INCIDENTS_TTL_S == 6 * 3600
