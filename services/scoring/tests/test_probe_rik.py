"""Probe guard for #697: verdict is dated and machine-checkable."""
from services.scoring.probe_rik import RIK_VERDICT


def test_verdict_is_dated_and_explicit():
    assert RIK_VERDICT["checked"] >= "2026-09-19"
    assert RIK_VERDICT["kind"] in ("negative", "positive")
    if RIK_VERDICT["kind"] == "positive":
        assert RIK_VERDICT["follow_up"] is not None
