"""P4 kohtud demo dim (issue #317): hermetic tests.

No network: the single scorer is a closed-decisions-feed NULL
(2026-09-13 dated-negative verdict, see dims_p4_kohtud docstring), so
the tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + buyer-side check pointer), the kohtud-leg
naming, and the registry/aggregator coverage. The module itself
makes no network calls (pinned by source inspection). No personal
data anywhere: fixtures carry only coordinates/POIs, never case or
party records.
"""

import inspect

import dims_p4_kohtud as kohtud
from dims_p4_kohtud import (
    P4_KOHTUD_DIMS,
    dim_enforcement_kohtud,
    score_p4_kohtud,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_enforcement_kohtud]

EXPECTED_KEYS = ["enforcement_kohtud"]

EXPECTED_PNUMS = ["P4-020"]


def test_single_dim_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "Ametlike", "notarikontrollist", "KÜ")), \
            fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(kohtud)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_kohtud_slice_names_closed_feed_and_open_checks():
    _, reason = dim_enforcement_kohtud(TALLINN, POIS)
    assert "Kohtute infosüsteemi" in reason
    assert "kohus.ee" in reason
    assert "Riigi Teataja" in reason and "e-toimik" in reason
    assert "2026-09-13" in reason
    assert "isikuandmetega" in reason
    assert "Ametlike" in reason and "Teadaannete" in reason
    assert "notar.ee" in reason
    assert "kaardikiht puudub" in reason


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_KOHTUD_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_KOHTUD_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_KOHTUD_DIMS}) == 1
    out = score_p4_kohtud(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_kohtud(None, None) == {k: None for k in EXPECTED_KEYS}
    assert kohtud.P4_KOHTUD_DIMS is P4_KOHTUD_DIMS
