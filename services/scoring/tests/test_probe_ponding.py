"""Probe guard for #706: verdict is dated and machine-checkable."""
from services.scoring.probe_ponding import PONDING_VERDICT


def test_verdict_is_dated_and_explicit():
    assert PONDING_VERDICT["checked"] >= "2026-09-19"
    assert PONDING_VERDICT["kind"] in ("negative", "positive")
    if PONDING_VERDICT["kind"] == "positive":
        assert PONDING_VERDICT["follow_up"] is not None
