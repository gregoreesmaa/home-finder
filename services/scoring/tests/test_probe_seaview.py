"""Probe guard for #712: seaview verdict is dated and machine-checkable."""
from services.scoring.probe_seaview import SEAVIEW_VERDICT


def test_seaview_verdict_is_dated():
    assert SEAVIEW_VERDICT["checked"] >= "2026-09-19"
    assert SEAVIEW_VERDICT["density_pts_m2"] >= 0


def test_seaview_verdict_is_explicit_negative():
    assert SEAVIEW_VERDICT["kind"] == "negative"
    assert SEAVIEW_VERDICT["tile_points"] > 0
    assert SEAVIEW_VERDICT["follow_up"] is None
