"""P4 StaMT demo dim (issue #273): hermetic tests.

No network: the single scorer is a service-map NULL (2026-09-13
dated-negative verdict, see dims_p4_stamt docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the StaMT-leg naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_stamt as stamt
from dims_p4_stamt import (
    P4_STAMT_DIMS,
    dim_stamt_services,
    score_p4_stamt,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_stamt_services]

EXPECTED_KEYS = ["stamt_services"]

EXPECTED_PNUMS = ["P4-011"]


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
            "e-teenus", "nimistuotsing", "veebikaardilt",
            "kohapeal")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(stamt)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_stamt_slice_names_map_gap_and_cousin_legs():
    _, reason = dim_stamt_services(TALLINN, POIS)
    assert "Sotsiaal- ja Tervishoiuameti" in reason
    assert "veebikaardis" in reason
    assert "2026-09-13" in reason
    assert "Haridusameti" in reason
    assert "Tervisekassa" in reason
    assert "linnaosa tabeli" in reason


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_STAMT_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_STAMT_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_STAMT_DIMS}) == 1
    out = score_p4_stamt(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_stamt(None, None) == {k: None for k in EXPECTED_KEYS}
    assert stamt.P4_STAMT_DIMS is P4_STAMT_DIMS
