"""Tests for services/scoring/dims_tomtom_evpois.py (issue #673).

Hermetic and pure: fixture POIs, no network, no key. Pins the
no-key NULL path, the STATIC-ONLY label (never live availability),
and the amenity bands.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from dims_tomtom_evpois import (  # noqa: E402
    STATIC_LABEL,
    build_table,
    dim_ev_amenity,
    score_tomtom_ev,
)


def _table():
    return build_table([
        {"poi_id": "ev1", "name": "Laadija A", "lat": 59.437,
         "lon": 24.753, "connectors": ["CCS"]},
        {"poi_id": "ev2", "name": "Laadija B", "lat": 59.450,
         "lon": 24.800, "connectors": None},
    ])


def test_no_key_null_never_guesses():
    score, reason = dim_ev_amenity((59.437, 24.753), None)
    assert score is None
    assert "EI OLE" in reason


def test_nearest_charger_scores_and_labels_static():
    score, reason = dim_ev_amenity((59.4371, 24.7531), _table())
    assert score == 75
    assert "staatiline" in reason  # never live availability
    assert "mitte reaalajas" in reason
    assert "Laadija A" in reason


def test_no_charger_nearby_is_context_not_bad():
    score, reason = dim_ev_amenity((59.30, 24.55), _table())
    assert score == 35
    assert "pole halb elamine" in reason


def test_static_label_constant_pins_wording():
    assert "staatiline" in STATIC_LABEL
    assert "mitte reaalajas" in STATIC_LABEL


def test_score_entry_point_and_quota_constants():
    out = score_tomtom_ev((59.4371, 24.7531), _table())
    assert out == {"ev_amenity": 75}
    assert score_tomtom_ev(None, None) == {"ev_amenity": None}
    import dims_tomtom_evpois as d
    assert d.EV_MAX_CALLS == 20  # ~20 txn per monthly refresh
    assert d.EV_CATEGORY_VERIFIED is False  # spike-unverified, must re-check
