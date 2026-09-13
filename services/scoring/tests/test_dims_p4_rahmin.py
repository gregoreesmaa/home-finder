"""P4 Rahandusministeerium dims (issues #315 demo + #377 coverage): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_rahmin.md) means both scorers are documented NULLs, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side check), the split-slice cousin pointers,
and the registry/aggregator coverage.
"""

import dims_p4_rahmin as rahmin
from dims_p4_rahmin import (
    P4_RAHMIN_DIMS,
    dim_automaks_revenue,
    dim_fiscal_rahmin,
    score_p4_rahmin,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_fiscal_rahmin,
    dim_automaks_revenue,
]

EXPECTED_KEYS = [
    "fiscal_rahmin",
    "automaks_revenue",
]

EXPECTED_PNUMS = [
    "P4-019", "P4-037",
]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_both_reasons_carry_honesty_markers_and_concrete_check():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_p4_019_reason_names_ministry_gap_and_scored_cousins():
    _, reason = dim_fiscal_rahmin(TALLINN, POIS)
    # The demo leg: ministry KOV finance table (debt, investments,
    # land-tax trend), per-KOV annual shape.
    assert "võlakoormus" in reason
    assert "per-KOV tabel" in reason
    assert "tallinn.ee" in reason
    # Split-slice contract: the stat / EMTA / cityplans / G16 legs
    # stay scored where they live — this NULL must name them.
    assert "dims_p4_stat" in reason
    assert "dim_kov_fiscal_stat" in reason
    assert "dims_p4_emta" in reason
    assert "dim_fiscal_health" in reason
    assert "dims_p4_cityplans" in reason
    assert "dim_investeering_cityplans" in reason
    assert "dims_group16" in reason


def test_p4_037_reason_names_calibration_and_exposure_cousins():
    _, reason = dim_automaks_revenue(TALLINN, POIS)
    # The coverage leg: revenue calibration feeding the exposure
    # band — buyer computes their own car figure meanwhile.
    assert "kalibr" in reason
    assert "avalik.emta.ee" in reason
    assert "TLT/Peatus.ee" in reason
    # Split-slice contract: the EMTA / park / trans / cityplans /
    # peatus / tlt legs stay scored where they live — named here.
    assert "dims_p4_emta" in reason
    assert "dim_policy_exposure" in reason
    assert "dims_p4_park" in reason
    assert "dim_zone_cost" in reason
    assert "dims_p4_trans" in reason
    assert "dim_policy_restrictions" in reason
    assert "dims_p4_cityplans" in reason
    assert "dim_poliitika_kava_cityplans" in reason
    assert "dims_p4_peatus" in reason
    assert "dims_p4_tlt" in reason
    assert "dim_tlt_commute_offset" in reason


def test_table_vs_calibration_shapes_do_not_double_score():
    _, table_reason = dim_fiscal_rahmin(TALLINN, POIS)
    _, calib_reason = dim_automaks_revenue(TALLINN, POIS)
    # Per-KOV fiscal table (P4-019) vs revenue calibration feeding
    # the exposure band (P4-037): different honest shapes, so the
    # reasons must read differently.
    assert "finantstervis" in table_reason
    assert "laekumise kalibreering" in calib_reason
    assert table_reason != calib_reason


def test_module_adds_no_network_calls():
    import pathlib
    import re
    src = pathlib.Path(rahmin.__file__).read_text(encoding="utf-8")
    assert re.search(r"^\s*(import|from)\s+\S*(urllib|socket|requests|httplib|http\.client)",
                     src, flags=re.M) is None
    assert "urlopen" not in src
    assert re.search(r"^[A-Z_]*OVERPASS[A-Z_]*\s*=", src, flags=re.M) is None
    assert re.search(r"^def fetch_\w+", src, flags=re.M) is None


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_RAHMIN_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_RAHMIN_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_RAHMIN_DIMS}) == 2
    out = score_p4_rahmin(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_rahmin(None, None) == {k: None for k in EXPECTED_KEYS}
    assert rahmin.P4_RAHMIN_DIMS is P4_RAHMIN_DIMS
