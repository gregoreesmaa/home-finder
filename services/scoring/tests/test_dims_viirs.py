"""Tests for services/scoring/dims_viirs.py (issue #719).

Hermetic: grids are hand-written fixtures (anchored on the live
2026-09-19 spot-check: saturated centre 255 -> 10, dark bog 11.6 ->
90). No network anywhere.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dims_viirs import (  # noqa: E402
    VIIRS_DIMS,
    brightness_band,
    dim_viirs_brightness,
    score_viirs,
)

# Fixture grid (synthetic positions, REAL ladder anchors).
FIXTURE_CELLS = [
    {"lat": 59.437, "lon": 24.745, "mean": 255.0},  # saturated centre
    {"lat": 59.507, "lon": 24.475, "mean": 9.4},    # dark outskirts
    {"lat": 58.439, "lon": 25.109, "mean": 11.6},   # dark bog
]


def test_band_ladder_matches_builder():
    assert brightness_band(255.0) == 10
    assert brightness_band(9.4) == 90
    assert brightness_band(11.6) == 90
    assert brightness_band(91.6) == 50
    assert brightness_band(None) is None
    assert brightness_band(-1.0) is None


def test_bright_centre_scores_low_dark_bog_high():
    score, reason = dim_viirs_brightness((59.437, 24.745), FIXTURE_CELLS)
    assert score == 10
    assert "heledusproksi" in reason
    assert "2016" in reason
    score2, _ = dim_viirs_brightness((58.439, 25.109), FIXTURE_CELLS)
    assert score2 == 90
    assert score2 > score  # contrast direction pinned


def test_missing_grid_is_honest_null():
    score, reason = dim_viirs_brightness((59.437, 24.745), None)
    assert score is None
    assert "teadmata" in reason
    score2, _ = dim_viirs_brightness(None, FIXTURE_CELLS)
    assert score2 is None


def test_registry_shape():
    assert VIIRS_DIMS == (("viirs_brightness", "P4-035",
                           dim_viirs_brightness),)


def test_score_entry_point():
    assert score_viirs((59.437, 24.745),
                       FIXTURE_CELLS) == {"viirs_brightness": 10}
