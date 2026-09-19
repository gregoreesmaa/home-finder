"""Tests for services/scoring/dims_tomtom_parking.py (issue #674).

Hermetic and pure: fixture POIs, no network, no key. Pins the no-key
NULL path, the STATIC-ONLY label (never live free spaces), P&R
detection, and the amenity bands.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from dims_tomtom_parking import (  # noqa: E402
    STATIC_LABEL,
    build_table,
    dim_parking_amenity,
    is_park_and_ride,
    score_tomtom_parking,
)


def _table():
    return build_table([
        {"poi_id": "p1", "name": "Parkla A", "lat": 59.437,
         "lon": 24.753, "park_and_ride": False},
        {"poi_id": "p2", "name": "Ülemiste P&R ümberistumisparkla",
         "lat": 59.440, "lon": 24.760, "park_and_ride": True},
    ])


def test_no_key_null_never_guesses():
    score, reason = dim_parking_amenity((59.437, 24.753), None)
    assert score is None
    assert "EI OLE" in reason


def test_nearest_parking_scores_and_labels_static():
    score, reason = dim_parking_amenity((59.4371, 24.7531), _table())
    assert score == 75
    assert "staatiline" in reason  # never live free spaces
    assert "mitte reaalajas" in reason
    assert "Parkla A" in reason


def test_pr_bonus_note_without_scale_change():
    score, reason = dim_parking_amenity((59.4371, 24.7531), _table())
    assert score == 75  # nearest-parking scale unchanged ...
    assert "ümberistumisparkla" in reason  # ... but the P&R pair is named


def test_no_parking_nearby_is_context_not_bad():
    score, reason = dim_parking_amenity((59.30, 24.55), _table())
    assert score == 40
    assert "pole halb elamine" in reason


def test_pr_markers_and_static_label():
    assert is_park_and_ride("Ülemiste P&R") is True
    assert is_park_and_ride("Park and Ride Lot") is True
    assert is_park_and_ride("Tavaline parkla") is False
    assert is_park_and_ride(None) is False
    assert "staatiline" in STATIC_LABEL
    assert "mitte reaalajas" in STATIC_LABEL


def test_score_entry_point_and_quota_constants():
    out = score_tomtom_parking((59.4371, 24.7531), _table())
    assert out == {"parking_amenity": 75}
    assert score_tomtom_parking(None, None) == {"parking_amenity": None}
    import dims_tomtom_parking as d
    assert d.PARKING_MAX_CALLS == 10  # ~10 txn per monthly refresh
    assert d.PARKING_CATEGORY_VERIFIED is False  # spike-unverified
