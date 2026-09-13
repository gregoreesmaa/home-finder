"""P4 opmaps demo dim (issue #267): hermetic tests.

No network: the single scorer is a marketing-map NULL (2026-09-13
dated-negative verdict, see dims_p4_opmaps docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the operator-leg naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_opmaps as opmaps
from dims_p4_opmaps import (
    P4_OPMAPS_DIMS,
    dim_operator_coverage,
    score_p4_opmaps,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_operator_coverage]

EXPECTED_KEYS = ["operator_coverage"]

EXPECTED_PNUMS = ["P4-009"]


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
            "netikaardilt", "Ookla", "OpenCellID", "rikkekaardilt")), \
            fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(opmaps)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_operator_slice_names_marketing_map_gap_and_cousin_legs():
    _, reason = dim_operator_coverage(TALLINN, POIS)
    assert "levikaart" in reason
    assert "Tele2" in reason
    assert "2026-09-13" in reason
    assert "netikaardilt" in reason
    assert "Ookla" in reason
    assert "OpenCellID" in reason
    assert "rikkekaardilt" in reason


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_OPMAPS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_OPMAPS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_OPMAPS_DIMS}) == 1
    out = score_p4_opmaps(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_opmaps(None, None) == {k: None for k in EXPECTED_KEYS}
    assert opmaps.P4_OPMAPS_DIMS is P4_OPMAPS_DIMS
