"""Probe guard for #699: verdict is dated and machine-checkable."""
from services.scoring.probe_viirs import VIIRS_VERDICT


def test_verdict_is_dated_and_explicit():
    assert VIIRS_VERDICT["checked"] >= "2026-09-19"
    assert VIIRS_VERDICT["kind"] in ("negative", "positive")
    if VIIRS_VERDICT["kind"] == "positive":
        assert VIIRS_VERDICT["follow_up"] is not None
