"""Overturn re-check for p317 park upkeep quality (issue #240): tests.

No network: the scorer is a contract-only NULL (2026-09-13
dated-negative verdict, see dims_overturn_p317 docstring), so the
tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + buyer-side check pointer), the dated
verdict / re-check note, and the registry/aggregator coverage.
The module itself makes no network calls.
"""

import dims_overturn_p317 as overturn
from dims_overturn_p317 import (
    OVERTURN_P317_DIMS,
    RECHECK_AFTER,
    VERDICT_DATE,
    dim_park_upkeep_overturn,
    score_overturn_p317,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "park", "lat": 59.4382, "lon": 24.7536}]


def test_park_upkeep_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_park_upkeep_overturn(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    _, reason = dim_park_upkeep_overturn(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # Concrete manual check, not a dead end.
    assert "KOV-ist" in reason
    assert "hoolduslepingut" in reason
    assert "niidukordade" in reason
    assert "kohapeal" in reason


def test_reason_names_evidence_gap_not_a_feed():
    _, reason = dim_park_upkeep_overturn(TALLINN, POIS)
    assert "matkarada" in reason
    assert "E11" in reason
    assert "JS-vaadet" in reason
    assert "hanketeated" in reason
    assert "pargipõhise" in reason
    assert "liiteta" in reason


def test_reason_stays_param_scoped_to_p317():
    # The overturn note must not claim sibling Group 11 slices or
    # invent a proxy the hunt refused (density, operator, vendor).
    _, reason = dim_park_upkeep_overturn(TALLINN, POIS)
    assert "postkast" not in reason.lower()
    assert "taga-tänav" not in reason.lower()
    assert "tihedus" not in reason.lower()
    assert "operaator" not in reason.lower()
    assert "töövõtja" not in reason.lower()


def test_verdict_is_dated_with_recheck_note():
    # The KEEP verdict expires: re-check surfaces by RECHECK_AFTER.
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2027-03-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_registry_and_aggregator_cover_the_single_dim():
    assert [k for k, _, _ in OVERTURN_P317_DIMS] == ["park_upkeep_overturn"]
    assert [p for _, p, _ in OVERTURN_P317_DIMS] == ["p317"]
    assert len({fn for _, _, fn in OVERTURN_P317_DIMS}) == 1
    assert score_overturn_p317(TALLINN, POIS) == {"park_upkeep_overturn": None}
    assert score_overturn_p317(None, None) == {"park_upkeep_overturn": None}
    assert overturn.OVERTURN_P317_DIMS is OVERTURN_P317_DIMS
