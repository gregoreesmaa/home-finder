"""Probe guard for #696: verdict is dated and machine-checkable."""
from services.scoring.probe_str import STR_VERDICT


def test_verdict_is_dated_and_explicit():
    assert STR_VERDICT["checked"] >= "2026-09-19"
    assert STR_VERDICT["kind"] in ("negative", "positive")
    if STR_VERDICT["kind"] == "positive":
        assert STR_VERDICT["follow_up"] is not None
