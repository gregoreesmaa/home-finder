"""P4 citybudget dim (issue #326 demo only): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_citybudget.md) means the scorer is a documented NULL, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side check), the split-slice cousin pointers,
and the registry/aggregator coverage.
"""

import dims_p4_citybudget as citybudget
from dims_p4_citybudget import (
    P4_CITYBUDGET_DIMS,
    dim_eelarve_citybudget,
    score_p4_citybudget,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

EXPECTED_KEYS = [
    "eelarve_citybudget",
]

EXPECTED_PNUMS = [
    "P4-019",
]


def test_dim_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_eelarve_citybudget(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_concrete_check():
    _, reason = dim_eelarve_citybudget(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_reason_names_budget_gap_and_buyer_side_checks():
    _, reason = dim_eelarve_citybudget(TALLINN, POIS)
    # The demo leg: Tallinna linna eelarve (debt, investments,
    # land-tax trend), per-KOV annual shape, human budget pages plus
    # year-stamped file attachments.
    assert "võlakoormus" in reason
    assert "per-KOV tabel" in reason
    assert "tallinna-linna-eelarve" in reason
    assert "tallinn.ee" in reason


def test_reason_names_scored_cousins_never_rescored():
    _, reason = dim_eelarve_citybudget(TALLINN, POIS)
    # Split-slice contract: the stat / EMTA / rahmin / riigik /
    # cityplans / G16 legs stay scored where they live — this NULL
    # must name them.
    assert "dims_p4_stat" in reason
    assert "dim_kov_fiscal_stat" in reason
    assert "dims_p4_emta" in reason
    assert "dim_fiscal_health" in reason
    assert "dims_p4_rahmin" in reason
    assert "dim_fiscal_rahmin" in reason
    assert "dims_p4_riigik" in reason
    assert "dim_audit_riigik" in reason
    assert "dims_p4_cityplans" in reason
    assert "dim_investeering_cityplans" in reason
    assert "dims_group16" in reason


def test_module_adds_no_network_calls():
    import pathlib
    import re
    src = pathlib.Path(citybudget.__file__).read_text(encoding="utf-8")
    assert re.search(r"^\s*(import|from)\s+\S*(urllib|socket|requests|httplib|http\.client)",
                     src, flags=re.M) is None
    assert "urlopen" not in src
    assert re.search(r"^[A-Z_]*OVERPASS[A-Z_]*\s*=", src, flags=re.M) is None
    assert re.search(r"^def fetch_\w+", src, flags=re.M) is None


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_CITYBUDGET_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_CITYBUDGET_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_CITYBUDGET_DIMS}) == 1
    out = score_p4_citybudget(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_citybudget(None, None) == {k: None for k in EXPECTED_KEYS}
    assert citybudget.P4_CITYBUDGET_DIMS is P4_CITYBUDGET_DIMS
