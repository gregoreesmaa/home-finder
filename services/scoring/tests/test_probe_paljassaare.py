"""Probe guard for #710: verdict is dated and machine-checkable."""
from services.scoring.probe_paljassaare import PALJASSAARE_VERDICT


def test_verdict_is_dated_and_explicit():
    assert PALJASSAARE_VERDICT["checked"] >= "2026-09-19"
    assert PALJASSAARE_VERDICT["kind"] in ("negative", "positive")
    if PALJASSAARE_VERDICT["kind"] == "negative":
        assert "No keyless" in PALJASSAARE_VERDICT["note"]
    else:
        assert PALJASSAARE_VERDICT["follow_up"] is not None
