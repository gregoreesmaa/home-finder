"""Probe guard for #689: verdict is dated and machine-checkable."""
from services.scoring.probe_outage import OUTAGE_VERDICT


def test_verdict_is_dated_and_explicit():
    assert OUTAGE_VERDICT["checked"] >= "2026-09-19"
    assert OUTAGE_VERDICT["kind"] in ("negative", "positive")
    if OUTAGE_VERDICT["kind"] == "positive":
        assert OUTAGE_VERDICT["follow_up"] is not None
