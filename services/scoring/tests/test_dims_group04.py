"""Group 4 title/legal dims (issue #204): hermetic tests.

No network: every scorer is a registry NULL by construction
(e-Kinnistusraamat is a paid registry, not in the snapshot), so the
tests pin the None + Estonian buyer-check reason contract for all
seventeen params, the dim registry, and the all-None aggregator.
"""

import dims_group04 as g04
from dims_group04 import (
    GROUP04_DIMS,
    dim_adverse_possession,
    dim_air_rights,
    dim_coop_approval,
    dim_deed_covenants,
    dim_ground_lease,
    dim_lease_encumbrance,
    dim_mineral_severance,
    dim_mineral_timber_rights,
    dim_morals_clause,
    dim_probate_delay,
    dim_property_stigma,
    dim_squatter_holdover,
    dim_stigma_laws,
    dim_title_cleanliness,
    dim_title_cloud,
    dim_trust_llc_transfer,
    dim_view_covenant,
    score_group04,
)

TALLINN = (59.4372, 24.7536)

POIS = [{"kind": "operator", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]

ALL_FNS = [
    dim_mineral_timber_rights,
    dim_deed_covenants,
    dim_property_stigma,
    dim_title_cleanliness,
    dim_mineral_severance,
    dim_stigma_laws,
    dim_lease_encumbrance,
    dim_view_covenant,
    dim_air_rights,
    dim_adverse_possession,
    dim_morals_clause,
    dim_trust_llc_transfer,
    dim_probate_delay,
    dim_ground_lease,
    dim_squatter_holdover,
    dim_coop_approval,
    dim_title_cloud,
]


def test_all_seventeen_dims_are_none_with_honest_estonian_reason():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, reason = fn(origin, pois)
            assert v is None, fn.__name__
            assert "EI OLE" in reason, fn.__name__
            assert "hinnang" in reason, fn.__name__
            assert "kontrolli" in reason or "küsi" in reason or "telli" in reason, \
                fn.__name__


def test_reasons_name_the_registry_check_not_a_map():
    joined = " ".join(fn(TALLINN, POIS)[1] for fn in ALL_FNS)
    assert "kinnistusraamat" in joined
    assert "notari" in joined
    assert "EI OLE" in joined
    assert "garanteeritud" not in joined
    assert "mõõdetud omand" not in joined


def test_specialist_checks_point_at_their_registries():
    assert "KKIS" in dim_deed_covenants(TALLINN, POIS)[1]
    assert "Ametlikud Teadaanded" in dim_probate_delay(TALLINN, POIS)[1] or \
        "Ametlike Teadaannete" in dim_probate_delay(TALLINN, POIS)[1]
    assert "e-Äriregistri" in dim_trust_llc_transfer(TALLINN, POIS)[1]
    assert "planeeringut" in dim_air_rights(TALLINN, POIS)[1]
    assert "ühistult" in dim_coop_approval(TALLINN, POIS)[1]


def test_view_covenant_names_the_viewshed_gap():
    _, reason = dim_view_covenant(TALLINN, POIS)
    assert "kõrgusmudel" in reason


def test_stigma_dims_flag_no_area_gradient():
    _, r139 = dim_property_stigma(TALLINN, POIS)
    assert "tänava" in r139  # brands the whole street — unfair
    _, r242 = dim_stigma_laws(TALLINN, POIS)
    assert "gradient" in r242


def test_registry_and_aggregator_cover_all_seventeen():
    assert [p for _, p, _ in GROUP04_DIMS] == [
        "p76", "p80", "p139", "p144", "p229", "p242", "p248", "p271",
        "p274", "p276", "p279", "p361", "p362", "p364", "p367", "p369",
        "p428",
    ]
    assert [k for k, _, _ in GROUP04_DIMS] == [
        "mineral_timber_rights", "deed_covenants", "property_stigma",
        "title_cleanliness", "mineral_severance", "stigma_laws",
        "lease_encumbrance", "view_covenant", "air_rights",
        "adverse_possession", "morals_clause", "trust_llc_transfer",
        "probate_delay", "ground_lease", "squatter_holdover",
        "coop_approval", "title_cloud",
    ]
    out = score_group04(TALLINN, POIS)
    assert set(out) == {k for k, _, _ in GROUP04_DIMS}
    assert all(v is None for v in out.values())
    assert len(out) == 17
    assert g04.GROUP04_DIMS is GROUP04_DIMS
