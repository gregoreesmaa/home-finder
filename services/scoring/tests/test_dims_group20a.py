"""Group 20 subjective-A dims (issue #212): hermetic tests.

No network: every scorer is a buyer-side NULL, so the tests pin the
None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side input pointer), and the registry/aggregator coverage.
"""

import dims_group20a as g20a
from dims_group20a import (
    GROUP20A_DIMS,
    dim_architectural_style,
    dim_child_safety,
    dim_civic_alignment,
    dim_civic_engagement,
    dim_cobuying,
    dim_demographic_balance,
    dim_design_philosophy,
    dim_downsizing,
    dim_emotional_resonance,
    dim_entertaining_capacity,
    dim_holiday_decor,
    dim_neighborhood_vibe,
    dim_pet_architecture,
    dim_pride_of_ownership,
    dim_studio_potential,
    dim_tech_privacy,
    dim_transient_neighbors,
    dim_trick_or_treat,
    dim_universal_design,
    score_group20a,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_neighborhood_vibe,
    dim_pride_of_ownership,
    dim_demographic_balance,
    dim_civic_engagement,
    dim_universal_design,
    dim_entertaining_capacity,
    dim_studio_potential,
    dim_child_safety,
    dim_pet_architecture,
    dim_downsizing,
    dim_cobuying,
    dim_architectural_style,
    dim_design_philosophy,
    dim_emotional_resonance,
    dim_tech_privacy,
    dim_civic_alignment,
    dim_holiday_decor,
    dim_trick_or_treat,
    dim_transient_neighbors,
]

EXPECTED_KEYS = [
    "vibe",
    "pride_ownership",
    "demographic_balance",
    "civic_engagement",
    "universal_design",
    "entertaining",
    "studio_potential",
    "child_safety",
    "pet_arch",
    "downsizing",
    "cobuying",
    "arch_style",
    "design_philosophy",
    "emotional_resonance",
    "tech_privacy",
    "civic_alignment",
    "holiday_decor",
    "trick_or_treat",
    "transient_neighbors",
]

EXPECTED_PNUMS = [
    "p18", "p81", "p85", "p90", "p98", "p104", "p105", "p122", "p126",
    "p127", "p128", "p131", "p133", "p134", "p136", "p161", "p163",
    "p164", "p165",
]


def test_all_nineteen_dims_always_none_for_every_input():
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
            "ostjaprofiili", "küsimustik", "kuulutus",
            "vaatlus", "kohapeal", "KÜ")), fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_taste_sliders_point_at_profile_not_area():
    for fn in (dim_neighborhood_vibe, dim_architectural_style,
               dim_design_philosophy, dim_downsizing, dim_tech_privacy):
        _, reason = fn(TALLINN, POIS)
        assert "ostjaprofiili" in reason or "profiili" in reason


def test_census_cousin_params_name_the_missing_grid():
    for fn in (dim_demographic_balance, dim_civic_alignment):
        _, reason = fn(TALLINN, POIS)
        assert "REL2021" in reason
        assert "ära feigi" in reason


def test_transient_density_names_missing_scrape_and_ku_check():
    _, reason = dim_transient_neighbors(TALLINN, POIS)
    assert "kraapimist" in reason and "KÜ" in reason


def test_block_observations_point_at_on_site_visit():
    for fn in (dim_pride_of_ownership, dim_holiday_decor, dim_trick_or_treat):
        _, reason = fn(TALLINN, POIS)
        assert "kvartali vaatluse" in reason or "kohapeal" in reason


def test_gut_feeling_stays_with_buyer():
    _, reason = dim_emotional_resonance(TALLINN, POIS)
    assert "kõhutunde veto" in reason and "ostjale" in reason


def test_registry_and_aggregator_cover_all_nineteen():
    assert [k for k, _, _ in GROUP20A_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in GROUP20A_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in GROUP20A_DIMS}) == 19
    out = score_group20a(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_group20a(None, None) == {k: None for k in EXPECTED_KEYS}
    assert g20a.GROUP20A_DIMS is GROUP20A_DIMS
