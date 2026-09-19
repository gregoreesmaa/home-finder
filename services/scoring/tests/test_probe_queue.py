"""Probe guard for #690: verdict is dated and machine-checkable."""
from services.scoring.probe_queue import QUEUE_VERDICT


def test_verdict_is_dated_and_explicit():
    assert QUEUE_VERDICT["checked"] >= "2026-09-19"
    assert QUEUE_VERDICT["kind"] in ("negative", "positive")
    if QUEUE_VERDICT["kind"] == "positive":
        assert QUEUE_VERDICT["follow_up"] is not None
