"""P4 Terviseamet dims (issues #289 demo + #362 coverage): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_tervise.md) means both scorers are documented NULLs, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side check), the split-slice cousin pointers,
and the registry/aggregator coverage.
"""

import dims_p4_tervise as tervise
from dims_p4_tervise import (
    P4_TERVISE_DIMS,
    dim_country_health_nuisances,
    dim_water_quality_monitoring,
    score_p4_tervise,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_water_quality_monitoring,
    dim_country_health_nuisances,
]

EXPECTED_KEYS = [
    "water_quality_monitoring",
    "country_health_nuisances",
]

EXPECTED_PNUMS = [
    "P4-017", "P4-024",
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


def test_p4_017_reason_points_at_vtiav_lookup_and_scored_cousins():
    _, reason = dim_water_quality_monitoring(TALLINN, POIS)
    assert "vtiav.sm.ee" in reason
    assert "iseteeninduse" in reason
    # Split-slice contract: the Tallinna Vesi + geology-side legs stay
    # scored where they live — this NULL must name them, not rescore.
    assert "dims_p4_tvesi" in reason
    assert "dim_water_sewer_zone" in reason
    assert "dims_p4_maa_subsurface" in reason
    assert "dim_water_sewer" in reason


def test_p4_024_reason_names_county_grain_and_future_source_slices():
    _, reason = dim_country_health_nuisances(TALLINN, POIS)
    assert "maakondade-kaupa" in reason
    assert "Harju" in reason
    assert "supluskohtade nimekirjast" in reason
    assert "vtiav.sm.ee" in reason
    assert "puugihaiguste lehelt" in reason
    assert "kohapealsel vaatlusel" in reason
    # Terviseamet legs only: õietolm / PRIA / EELIS / farmikaebused
    # belong to future source issues, named — never scored here.
    for marker in ("PRIA", "EELIS", "farmikaebuste", "ietolmu"):
        assert marker in reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_TERVISE_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_TERVISE_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_TERVISE_DIMS}) == 2
    out = score_p4_tervise(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_tervise(None, None) == {k: None for k in EXPECTED_KEYS}
    assert tervise.P4_TERVISE_DIMS is P4_TERVISE_DIMS
