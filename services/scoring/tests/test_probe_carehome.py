"""Probe guard for #709: verdict is dated and machine-checkable."""
from services.scoring.probe_carehome import CAREHOME_VERDICT


def test_verdict_is_dated_and_explicit():
    assert CAREHOME_VERDICT["checked"] >= "2026-09-19"
    assert CAREHOME_VERDICT["kind"] in ("negative", "positive")
    if CAREHOME_VERDICT["kind"] == "positive":
        assert CAREHOME_VERDICT["follow_up"] is not None
