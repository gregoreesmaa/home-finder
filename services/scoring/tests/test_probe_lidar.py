"""Probe guard for #703: lidar verdict is dated and machine-checkable."""
from services.scoring.probe_lidar import LIDAR_VERDICT


def test_lidar_verdict_is_dated():
    assert LIDAR_VERDICT["checked"] >= "2026-09-19"
    assert LIDAR_VERDICT["density_pts_m2"] >= 0


def test_lidar_verdict_is_explicit_negative():
    assert LIDAR_VERDICT["kind"] == "negative"
    assert LIDAR_VERDICT["tile_points"] > 0
    assert LIDAR_VERDICT["follow_up"] is None
