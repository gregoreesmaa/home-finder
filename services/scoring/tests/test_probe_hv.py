"""Probe guard for #698: verdict is dated and machine-checkable."""
from services.scoring.probe_hv import HV_VERDICT


def test_verdict_is_dated_and_explicit():
    assert HV_VERDICT["checked"] >= "2026-09-19"
    assert HV_VERDICT["kind"] in ("negative", "positive")
    if HV_VERDICT["kind"] == "positive":
        assert HV_VERDICT["follow_up"] is not None
