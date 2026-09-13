"""P4 TTJA consumer-complaints dim (issue #295 demo, single-param): tests.

No network: the scorer is a register-only NULL (2026-09-13
dated-negative verdict, see dims_p4_ttjacons docstring), so the
tests pin the None contract, the Estonian honesty markers (hinnang
+ EI OLE + buyer-side check pointer), and the registry/aggregator
coverage. The module itself makes no network calls.
"""

import dims_p4_ttjacons as ttjacons
from dims_p4_ttjacons import (
    P4_TTJACONS_DIMS,
    dim_seller_complaint_record,
    score_p4_ttjacons,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]


def test_seller_complaint_record_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_seller_complaint_record(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    _, reason = dim_seller_complaint_record(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # Concrete manual check, not a dead end.
    assert "käsitsi" in reason
    assert "JVIS" in reason
    assert "mustast nimekirjast" in reason
    assert "otsusteregistrist" in reason


def test_reason_names_register_gap_not_a_feed():
    _, reason = dim_seller_complaint_record(TALLINN, POIS)
    assert "otsusteregistris" in reason
    assert "HTML-tabelina" in reason
    assert "registrikoodita" in reason
    assert "päringuliides puudub" in reason


def test_reason_stays_param_scoped_to_ttja_slice():
    # The TTJA slice must not claim sibling P4-021 slices.
    _, reason = dim_seller_complaint_record(TALLINN, POIS)
    assert "EHR" not in reason
    assert "ehitaja" not in reason
    assert "Äriregister" not in reason
    assert "Ametlikud Teadaanded" not in reason
    assert "tehingud" not in reason
    assert "relist" not in reason


def test_registry_and_aggregator_cover_the_single_dim():
    assert [k for k, _, _ in P4_TTJACONS_DIMS] == ["seller_complaint_record"]
    assert [p for _, p, _ in P4_TTJACONS_DIMS] == ["P4-021"]
    assert len({fn for _, _, fn in P4_TTJACONS_DIMS}) == 1
    assert score_p4_ttjacons(TALLINN, POIS) == {"seller_complaint_record": None}
    assert score_p4_ttjacons(None, None) == {"seller_complaint_record": None}
    assert ttjacons.P4_TTJACONS_DIMS is P4_TTJACONS_DIMS
