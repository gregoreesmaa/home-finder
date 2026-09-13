"""P4 Tallinna välireklaam / reklaamimaks dim (issue #318 demo): tests.

No network: the scorer is a procedure-only NULL (2026-09-13
dated-negative verdict, see dims_p4_reklaam docstring), so the
tests pin the None contract, the Estonian honesty markers (hinnang
+ EI OLE + buyer-side check pointer), and the registry/aggregator
coverage. The module itself makes no network calls.
"""

import dims_p4_reklaam as reklaam
from dims_p4_reklaam import (
    P4_REKLAAM_DIMS,
    dim_ad_wall_yield,
    score_p4_reklaam,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]


def test_ad_wall_yield_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_ad_wall_yield(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    _, reason = dim_ad_wall_yield(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # Concrete manual check, not a dead end.
    assert "haldurilt" in reason
    assert "KÜ-lt" in reason
    assert "viiluseina" in reason
    assert "loavõimalust" in reason


def test_reason_names_procedure_gap_not_a_feed():
    _, reason = dim_ad_wall_yield(TALLINN, POIS)
    assert "Riigi Teataja" in reason
    assert "määruses" in reason
    assert "taotluse" in reason
    assert "menetluse" in reason
    assert "tootlustabel puudub" in reason


def test_reason_keeps_tax_as_cost_not_yield():
    # Reklaamimaks is a per-m² cost schedule; scoring it as yield
    # would invert the param's question (yield kicker).
    _, reason = dim_ad_wall_yield(TALLINN, POIS)
    assert "reklaamimaksu määrad" in reason
    assert "tulu-hinnang" in reason
    assert "tootlusnumbrit" in reason


def test_reason_stays_param_scoped_to_reklaam_slice():
    # The reklaam slice must not claim sibling P4-036 slices.
    _, reason = dim_ad_wall_yield(TALLINN, POIS)
    assert "Elering" not in reason
    assert "Elektrilevi" not in reason
    assert "EHR" not in reason
    assert "LiDAR" not in reason
    assert "LoD2" not in reason
    assert "Utilitas" not in reason
    assert "kaugküte" not in reason
    assert "feed-in" not in reason
    assert "mikrotootja" not in reason
    assert "katuse" not in reason


def test_registry_and_aggregator_cover_the_single_dim():
    assert [k for k, _, _ in P4_REKLAAM_DIMS] == ["ad_wall_yield"]
    assert [p for _, p, _ in P4_REKLAAM_DIMS] == ["P4-036"]
    assert len({fn for _, _, fn in P4_REKLAAM_DIMS}) == 1
    assert score_p4_reklaam(TALLINN, POIS) == {"ad_wall_yield": None}
    assert score_p4_reklaam(None, None) == {"ad_wall_yield": None}
    assert reklaam.P4_REKLAAM_DIMS is P4_REKLAAM_DIMS
