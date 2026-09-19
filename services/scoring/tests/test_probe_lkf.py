"""Probe guard for #708: verdict is dated and machine-checkable."""
from services.scoring.probe_lkf import LKF_VERDICT


def test_verdict_is_dated_and_explicit():
    assert LKF_VERDICT["checked"] >= "2026-09-19"
    assert LKF_VERDICT["kind"] in ("negative", "positive")
    if LKF_VERDICT["kind"] == "positive":
        assert LKF_VERDICT["follow_up"] is not None
