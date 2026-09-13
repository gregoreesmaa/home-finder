"""P4 TTJA netikaart dim (issue #266 demo, single-param): hermetic tests.

No network: the scorer is an interactive-map-only NULL (2026-09-13
dated-negative verdict, see dims_p4_ttja_net docstring), so the
tests pin the None contract, the Estonian honesty markers (hinnang
+ EI OLE + buyer-side check pointer), and the registry/aggregator
coverage. The module itself makes no network calls.
"""

import dims_p4_ttja_net as ttja
from dims_p4_ttja_net import (
    P4_TTJA_NET_DIMS,
    dim_broadband_address,
    score_p4_ttja_net,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]


def test_broadband_address_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_broadband_address(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    _, reason = dim_broadband_address(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # Concrete manual check, not a dead end.
    assert "käsitsi" in reason
    assert "sideteenuste kaardilt" in reason
    assert "levikaardilt" in reason


def test_reason_names_interactive_app_gap_not_a_feed():
    _, reason = dim_broadband_address(TALLINN, POIS)
    assert "X-GIS" in reason
    assert "kaardirakenduses" in reason
    assert "päringuliides puudub" in reason


def test_reason_stays_param_scoped_to_ttja_slice():
    # The TTJA slice must not claim sibling P4-009 slices.
    _, reason = dim_broadband_address(TALLINN, POIS)
    assert "SAIDI" not in reason
    assert "Elering" not in reason
    assert "Ookla" not in reason


def test_registry_and_aggregator_cover_the_single_dim():
    assert [k for k, _, _ in P4_TTJA_NET_DIMS] == ["broadband_address"]
    assert [p for _, p, _ in P4_TTJA_NET_DIMS] == ["P4-009"]
    assert len({fn for _, _, fn in P4_TTJA_NET_DIMS}) == 1
    assert score_p4_ttja_net(TALLINN, POIS) == {"broadband_address": None}
    assert score_p4_ttja_net(None, None) == {"broadband_address": None}
    assert ttja.P4_TTJA_NET_DIMS is P4_TTJA_NET_DIMS
