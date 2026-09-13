"""P4 creditinfo dims (issues #259 demo + #340 coverage): hermetic tests.

No network: both scorers are closed-feed NULLs, so the tests pin the
None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), and the registry/aggregator coverage.
"""

import dims_p4_creditinfo as creditinfo
from dims_p4_creditinfo import (
    P4_CREDITINFO_DIMS,
    dim_enforcement_ci,
    dim_ku_loan_fund,
    score_p4_creditinfo,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_ku_loan_fund, dim_enforcement_ci]

EXPECTED_KEYS = ["ku_loan_fund", "enforcement_ci"]
EXPECTED_PNUMS = ["P4-007", "P4-020"]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_both_reasons_carry_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "KÜ", "e-Äriregistrist", "Ametlike",
            "notarikontrollist", "kohapeal")), fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_ku_loan_fund_names_closed_feed_and_ku_report():
    _, reason = dim_ku_loan_fund(TALLINN, POIS)
    assert "Creditinfo" in reason and "Krediidiinfo" in reason
    assert "maksehäired" in reason
    assert "majandusaasta aruanne" in reason
    assert "ära feigi" in reason


def test_enforcement_ci_names_gated_scores_and_open_checks():
    _, reason = dim_enforcement_ci(TALLINN, POIS)
    assert "krediidiskoor" in reason
    assert "Ametlike" in reason and "Teadaannete" in reason
    assert "notar.ee" in reason
    assert "kaardikiht puudub" in reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_CREDITINFO_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_CREDITINFO_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_CREDITINFO_DIMS}) == 2
    out = score_p4_creditinfo(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_creditinfo(None, None) == {k: None for k in EXPECTED_KEYS}
    assert creditinfo.P4_CREDITINFO_DIMS is P4_CREDITINFO_DIMS
