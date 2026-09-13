"""P4 Kohanimeregister guest-name dim (issue #313 demo, single-param): tests.

No network: the scorer is a register-only NULL (2026-09-13
dated-negative verdict, see dims_p4_kohanimi docstring), so the
tests pin the None contract, the Estonian honesty markers (hinnang
+ EI OLE + buyer-side check pointer), and the registry/aggregator
coverage. The module itself makes no network calls.
"""

import dims_p4_kohanimi as kohanimi
from dims_p4_kohanimi import (
    P4_KOHANIMI_DIMS,
    dim_guest_name_test,
    score_p4_kohanimi,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]


def test_guest_name_test_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_guest_name_test(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    _, reason = dim_guest_name_test(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # Concrete guest check, not a dead end.
    assert "taksojuhile" in reason
    assert "külalisparkimist" in reason
    assert "sissepääs" in reason
    assert "kohapeal" in reason


def test_reason_names_register_gap_not_a_feed():
    _, reason = dim_guest_name_test(TALLINN, POIS)
    assert "Kohanimeregister" in reason
    assert "interaktiivne" in reason
    assert "X-tee kaudu" in reason
    assert "hääldab" in reason


def test_reason_names_name_variants_not_a_verdict():
    # KNR returns name records (incl. unofficial/former variants),
    # never a pronounceability verdict — the reason must say so.
    _, reason = dim_guest_name_test(TALLINN, POIS)
    assert "mitteametlikud" in reason
    assert "endised" in reason
    assert "kirje" in reason


def test_reason_stays_param_scoped_to_kohanimi_slice():
    # The Kohanimeregister slice must not claim sibling P4-049 slices.
    _, reason = dim_guest_name_test(TALLINN, POIS)
    assert "Bolt" not in reason
    assert "TLT" not in reason
    assert "Peatus" not in reason
    assert "P4-022" not in reason
    assert "P4-029" not in reason
    assert "OSM" not in reason
    assert "wheelchair" not in reason


def test_registry_and_aggregator_cover_the_single_dim():
    assert [k for k, _, _ in P4_KOHANIMI_DIMS] == ["guest_name_test"]
    assert [p for _, p, _ in P4_KOHANIMI_DIMS] == ["P4-049"]
    assert len({fn for _, _, fn in P4_KOHANIMI_DIMS}) == 1
    assert score_p4_kohanimi(TALLINN, POIS) == {"guest_name_test": None}
    assert score_p4_kohanimi(None, None) == {"guest_name_test": None}
    assert kohanimi.P4_KOHANIMI_DIMS is P4_KOHANIMI_DIMS
