"""Probe guard for #693: verdict is dated and machine-checkable."""
from services.scoring.probe_ookla import OOKLA_VERDICT


def test_verdict_is_dated_and_explicit():
    assert OOKLA_VERDICT["checked"] >= "2026-09-19"
    assert OOKLA_VERDICT["kind"] in ("negative", "positive")
    if OOKLA_VERDICT["kind"] == "positive":
        assert OOKLA_VERDICT["follow_up"] is not None
