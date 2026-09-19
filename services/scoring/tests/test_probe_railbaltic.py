"""Probe guard for #704: Rail Baltica verdict is dated and machine-checkable."""
from services.scoring.probe_railbaltic import RAILBALTIC_VERDICT


def test_railbaltic_verdict_is_dated():
    assert RAILBALTIC_VERDICT["checked"] >= "2026-09-19"
    assert RAILBALTIC_VERDICT["notices_window"] > 0


def test_railbaltic_verdict_is_explicit_negative():
    assert RAILBALTIC_VERDICT["kind"] == "negative"
    assert RAILBALTIC_VERDICT["tallinn_rb_notices"] == 0
    assert RAILBALTIC_VERDICT["follow_up"] is None
