"""Probe guard for #694: verdict is dated and machine-checkable."""
from services.scoring.probe_water import WATER_VERDICT


def test_verdict_is_dated_and_explicit():
    assert WATER_VERDICT["checked"] >= "2026-09-19"
    assert WATER_VERDICT["kind"] in ("negative", "positive")
    if WATER_VERDICT["kind"] == "positive":
        assert WATER_VERDICT["follow_up"] is not None
