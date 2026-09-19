"""Probe guard for #691: verdict is dated and machine-checkable."""
from services.scoring.probe_5g import COVERAGE5G_VERDICT


def test_verdict_is_dated_and_explicit():
    assert COVERAGE5G_VERDICT["checked"] >= "2026-09-19"
    assert COVERAGE5G_VERDICT["kind"] in ("negative", "positive")
    if COVERAGE5G_VERDICT["kind"] == "positive":
        assert COVERAGE5G_VERDICT["follow_up"] is not None
