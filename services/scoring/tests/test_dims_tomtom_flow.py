"""Tests for services/scoring/dims_tomtom_flow.py (issue #671).

Hermetic and pure: fixture speed samples, no network, no key. Pins
the no-key NULL path, banding, and the agree/disagree calibration.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from dims_tomtom_flow import (  # noqa: E402
    build_table,
    calibrate_vs_delay,
    dim_car_speed,
    score_tomtom_flow,
    speed_band,
)


def _table():
    return build_table([
        {"probe_id": "tartu-mnt", "band": "morning",
         "current": 28, "freeflow": 50},
        {"probe_id": "parnu-mnt", "band": "morning",
         "current": 48, "freeflow": 50},
    ])


def test_no_key_null_never_guesses():
    score, reason = dim_car_speed((59.437, 24.753), None)
    assert score is None
    assert "EI OLE" in reason


def test_speed_bands_pin_thresholds():
    assert speed_band(48, 50) == "free"
    assert speed_band(40, 50) == "steady"
    assert speed_band(28, 50) == "slow"
    assert speed_band(10, 50) == "jammed"
    assert speed_band(None, 50) is None
    assert speed_band(30, 0) is None
    assert speed_band(-5, 50) is None


def test_dim_reports_probe_context():
    score, reason = dim_car_speed((59.437, 24.753), _table(),
                                  "tartu-mnt")
    assert score == 45
    assert "tartu-mnt" in reason
    assert "mitte reaalajas" in reason


def test_calibration_agree_disagree():
    cal = calibrate_vs_delay(
        _table()["rows"],
        {"tartu-mnt": 1.2,  # delay steady vs flow slow -> disagree
         "parnu-mnt": 1.05})  # delay free vs flow free -> agree
    assert cal["agree"] == 1
    assert cal["disagree"] == 1
    kinds = {d["probe_id"]: d["verdict"] for d in cal["details"]}
    assert kinds == {"tartu-mnt": "disagree", "parnu-mnt": "agree"}


def test_calibration_skips_unknowns():
    cal = calibrate_vs_delay(
        [{"probe_id": "x", "band": "morning", "current": None,
          "freeflow": None, "speed_band": None}], {"x": 1.5})
    assert cal == {"agree": 0, "disagree": 0, "details": []}


def test_score_entry_point_and_quota_constants():
    out = score_tomtom_flow((59.437, 24.753), _table(), "parnu-mnt")
    assert out == {"car_speed": 75}
    assert score_tomtom_flow(None, None) == {"car_speed": None}
    import dims_tomtom_flow as d
    assert d.FLOW_MAX_CALLS == 80  # ~40 probes x 2 bands
    assert d.FLOW_BANDS == ("morning", "evening")
