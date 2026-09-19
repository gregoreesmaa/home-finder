"""Probe guard for #707: verdict is dated and machine-checkable."""
from services.scoring.probe_lamps import LAMPS_VERDICT


def test_verdict_is_dated_and_explicit():
    assert LAMPS_VERDICT["checked"] >= "2026-09-19"
    assert LAMPS_VERDICT["kind"] in ("negative", "positive")
    if LAMPS_VERDICT["kind"] == "positive":
        assert LAMPS_VERDICT["follow_up"] is not None
