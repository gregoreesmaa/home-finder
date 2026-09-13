"""P4 Haridusamet dims (issues #270 demo + #346 coverage): hermetic tests.

No network: all three scorers are unpublished-feed NULLs (2026-09-13
dated-negative verdict, see dims_p4_haridus docstring), so the
tests pin the None contract, the Estonian honesty markers (hinnang
+ EI OLE + buyer-side check pointer), and the registry/aggregator
coverage. The module itself makes no network calls.
"""

import dims_p4_haridus as haridus
from dims_p4_haridus import (
    P4_HARIDUS_DIMS,
    dim_catchment_turnover,
    dim_kindergarten_queue_gp,
    dim_school_plan_liquidity,
    score_p4_haridus,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_kindergarten_queue_gp, dim_school_plan_liquidity,
           dim_catchment_turnover]

EXPECTED_KEYS = ["kindergarten_queue_gp", "school_plan_liquidity",
                 "catchment_turnover"]
EXPECTED_PNUMS = ["P4-011", "P4-025", "P4-052"]


def test_all_three_dims_always_none_for_every_input():
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
        assert any(marker in reason for marker in (
            "e-teenus", "nimistuotsing", "arengukava", "REL2021",
            "tehingu", "KÜ", "kohapeal")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_queue_dim_names_queue_table_gap_and_both_live_checks():
    _, reason = dim_kindergarten_queue_gp(TALLINN, POIS)
    assert "järjekorra statistikat" in reason
    assert "masinvoogus pole" in reason
    assert "lasteaiakoha taotlemise e-teenusest" in reason
    assert "nimistuotsingust" in reason


def test_liquidity_dim_names_arengukava_doc_and_cousin_checks():
    _, reason = dim_school_plan_liquidity(TALLINN, POIS)
    assert "arengukava dokumendi" in reason
    assert "masinloetavat voogu" in reason
    assert "REL2021" in reason and "DOM-mediaane" in reason


def test_turnover_dim_names_catchment_gap_without_churn_calm():
    _, reason = dim_catchment_turnover(TALLINN, POIS)
    assert "teeninduspiirkondade muutusi" in reason
    assert "tehingute käivet" in reason and "remondifondi" in reason


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_HARIDUS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_HARIDUS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_HARIDUS_DIMS}) == 3
    out = score_p4_haridus(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_haridus(None, None) == {k: None for k in EXPECTED_KEYS}
    assert haridus.P4_HARIDUS_DIMS is P4_HARIDUS_DIMS
