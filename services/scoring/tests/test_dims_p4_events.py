"""P4 events demo + coverage dims (issues #310, #375): hermetic tests.

No network: both scorers are unpublished-feed NULLs (2026-09-13
dated-negative verdict, see dims_p4_events docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the per-param missing-input naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_events as events
from dims_p4_events import (
    P4_EVENTS_DIMS,
    dim_events_calendar,
    dim_fireworks_calendar,
    score_p4_events,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_events_calendar, dim_fireworks_calendar]

EXPECTED_KEYS = ["events_calendar", "fireworks_calendar"]

EXPECTED_PNUMS = ["P4-033", "P4-047"]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_all_reasons_carry_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "pole" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "kohapeal", "dims_p4_", "Lauluväljak", "kultuurikava",
            "Päästeamet", "tallinn.ee")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(events)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_demo_param_names_venue_shells_and_sadam_kesk_legs():
    _, reason = dim_events_calendar(TALLINN, POIS)
    assert "Lauluväljak" in reason
    assert "kultuurikava.ee" in reason
    assert "tallinn.ee/kultuur" in reason
    assert "dims_p4_sadam" in reason
    assert "dims_p4_kesk" in reason


def test_fireworks_slice_names_permit_gap_and_komun_ku_paaste_legs():
    _, reason = dim_fireworks_calendar(TALLINN, POIS)
    assert "ilutulestiku-lubade" in reason
    assert "jaanipäeva/uusaasta" in reason
    assert "dims_p4_komun" in reason
    assert "dims_p4_kudocs" in reason
    assert "dims_p4_paaste" in reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_EVENTS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_EVENTS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_EVENTS_DIMS}) == 2
    out = score_p4_events(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_events(None, None) == {k: None for k in EXPECTED_KEYS}
    assert events.P4_EVENTS_DIMS is P4_EVENTS_DIMS
