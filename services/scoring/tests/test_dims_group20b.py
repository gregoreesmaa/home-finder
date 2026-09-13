"""Group 20 subjective per-listing dimensions, batch B (issue #213): hermetic tests.

No network: every scorer in this batch returns None by design (buyer-profile
sliders and block observations carry no area signal), so the tests assert
the NULL contract and the honesty wording of each Estonian reason.
"""

import dims_group20b as g20b
from dims_group20b import (
    GROUP20B_DIMS,
    dim_biophilic,
    dim_cohousing,
    dim_culture_enclave,
    dim_disaster_resilience,
    dim_flaw_permanence,
    dim_garden_sensory,
    dim_gated_security,
    dim_golf_ball_risk,
    dim_gut_veto,
    dim_hoarder_neighbor,
    dim_holiday_lights,
    dim_mutual_aid,
    dim_pet_density,
    dim_quarantine,
    dim_surveillance_culture,
    dim_timeline_desperation,
    dim_toxic_planting,
    dim_volunteerism,
    dim_work_zones,
    score_group20b,
)

TALLINN = (59.4372, 24.7536)

ALL_DIM_FNS = (
    dim_mutual_aid,
    dim_volunteerism,
    dim_garden_sensory,
    dim_work_zones,
    dim_quarantine,
    dim_pet_density,
    dim_disaster_resilience,
    dim_cohousing,
    dim_golf_ball_risk,
    dim_gated_security,
    dim_culture_enclave,
    dim_toxic_planting,
    dim_biophilic,
    dim_surveillance_culture,
    dim_holiday_lights,
    dim_hoarder_neighbor,
    dim_flaw_permanence,
    dim_timeline_desperation,
    dim_gut_veto,
)

EXPECTED_KEYS = (
    "mutual_aid",
    "volunteerism",
    "garden_sensory",
    "work_zones",
    "quarantine",
    "pet_density",
    "disaster_resilience",
    "cohousing",
    "golf_ball_risk",
    "gated_security",
    "culture_enclave",
    "toxic_planting",
    "biophilic",
    "surveillance_culture",
    "holiday_lights",
    "hoarder_neighbor",
    "flaw_permanence",
    "timeline_desperation",
    "gut_veto",
)

EXPECTED_PARAM_IDS = (
    "p168", "p170", "p239", "p281", "p283", "p349", "p380", "p383", "p385",
    "p388", "p390", "p398", "p410", "p413", "p449", "p461", "p488", "p490",
    "p500",
)


def _pois():
    return [{"kind": "whatever", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]


def test_all_nineteen_dims_are_always_none():
    for fn in ALL_DIM_FNS:
        for origin, pois in [(TALLINN, _pois()), (TALLINN, []), (None, None),
                             (None, _pois()), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_all_reasons_state_honesty_in_estonian():
    for fn in ALL_DIM_FNS:
        _, reason = fn(TALLINN, _pois())
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__


def test_reasons_point_at_the_buyer_side_input():
    for fn in ALL_DIM_FNS:
        _, reason = fn(TALLINN, _pois())
        assert ("küsimustik" in reason or "ostja" in reason
                or "vaatlus" in reason or "kohapeal" in reason), fn.__name__


def test_no_reason_fakes_an_area_score():
    joined = " ".join(fn(TALLINN, _pois())[1] for fn in ALL_DIM_FNS)
    assert "garanteeritud" not in joined.lower()
    assert "mõõdetud skoor" not in joined.lower()


def test_golf_ball_risk_names_the_radial_gradient_trap():
    _, reason = dim_golf_ball_risk(TALLINN, _pois())
    assert "gradient" in reason
    assert "kohapealset" in reason


def test_surveillance_culture_warns_camera_counts_measure_the_opposite():
    _, reason = dim_surveillance_culture(TALLINN, _pois())
    assert "vastupidist" in reason


def test_gut_veto_is_a_veto_not_a_score():
    _, reason = dim_gut_veto(TALLINN, _pois())
    assert "EI OLE skooritav" in reason


def test_registry_and_aggregator_cover_all_nineteen():
    assert [k for k, _, _ in GROUP20B_DIMS] == list(EXPECTED_KEYS)
    assert [p for _, p, _ in GROUP20B_DIMS] == list(EXPECTED_PARAM_IDS)
    out = score_group20b(TALLINN, _pois())
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_group20b(None, None) == {k: None for k in EXPECTED_KEYS}
    assert g20b.GROUP20B_DIMS is GROUP20B_DIMS
