"""Probe guard for #705: verdict is dated and machine-checkable."""
from services.scoring.probe_catchment import CATCHMENT_VERDICT


def test_verdict_is_dated_and_explicit():
    assert CATCHMENT_VERDICT["checked"] >= "2026-09-19"
    assert CATCHMENT_VERDICT["kind"] in ("negative", "positive")
    if CATCHMENT_VERDICT["kind"] == "positive":
        assert CATCHMENT_VERDICT["follow_up"] is not None
