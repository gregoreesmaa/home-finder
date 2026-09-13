"""Group 1 listing-portal dims, batch A (issue #202): hermetic tests.

No network: all twenty dims are NULL by contract (per-listing facts with
no honest snapshot area signal), so tests assert None + Estonian
buyer-check reasons on fixture inputs, plus registry/aggregator shape.
"""

import dims_group01a as g01a
from dims_group01a import (
    GROUP01A_DIMS,
    dim_backup_heating,
    dim_bathrooms,
    dim_bedrooms,
    dim_finishes,
    dim_flex_space,
    dim_floor_plan_flow,
    dim_gear_storage,
    dim_kitchen,
    dim_laundry,
    dim_move_in_readiness,
    dim_mudroom,
    dim_outdoor_kitchen,
    dim_outdoor_living,
    dim_parking,
    dim_primary_suite,
    dim_purchase_price,
    dim_smart_home,
    dim_storage,
    dim_utility_costs,
    dim_workspace,
    score_group01a,
)

TALLINN = (59.4372, 24.7536)

ALL_DIMS = [
    dim_purchase_price,
    dim_utility_costs,
    dim_bedrooms,
    dim_bathrooms,
    dim_floor_plan_flow,
    dim_kitchen,
    dim_workspace,
    dim_storage,
    dim_parking,
    dim_move_in_readiness,
    dim_finishes,
    dim_outdoor_living,
    dim_smart_home,
    dim_primary_suite,
    dim_laundry,
    dim_mudroom,
    dim_flex_space,
    dim_gear_storage,
    dim_outdoor_kitchen,
    dim_backup_heating,
]

POIS = [{"kind": "parking", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]


def test_all_twenty_dims_are_always_none_with_honest_reason():
    for fn in ALL_DIMS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, reason = fn(origin, pois)
            assert v is None, fn.__name__
            assert "EI OLE" in reason, fn.__name__
            assert "hinnang" in reason, fn.__name__
            assert "ära feigi" in reason, fn.__name__


def test_reasons_name_the_listing_artefact_not_the_map():
    artefacts = {
        "dim_purchase_price": "Maa-ameti",
        "dim_utility_costs": "arveid",
        "dim_bedrooms": "korruseplaani",
        "dim_bathrooms": "korruseplaani",
        "dim_floor_plan_flow": "kohapeal",
        "dim_kitchen": "kohapeal",
        "dim_workspace": "plaanilt",
        "dim_storage": "panipaiga",
        "dim_parking": "kuulutuse-fakt",
        "dim_move_in_readiness": "kohapealse",
        "dim_finishes": "kohapeal",
        "dim_outdoor_living": "kuulutusest",
        "dim_smart_home": "maaklerilt",
        "dim_primary_suite": "plaanilt",
        "dim_laundry": "plaanilt",
        "dim_mudroom": "plaanilt",
        "dim_flex_space": "registriandmeid",
        "dim_gear_storage": "garaaži",
        "dim_outdoor_kitchen": "kommunikatsioonide",
        "dim_backup_heating": "küttesüsteemide",
    }
    by_name = {fn.__name__: fn for fn in ALL_DIMS}
    assert set(by_name) == set(artefacts)
    for name, needle in artefacts.items():
        _, reason = by_name[name](TALLINN, POIS)
        assert needle in reason, name


def test_parking_stays_null_next_to_mapped_parking():
    # Closest call in the batch (see module docstring): area parking
    # density must not score THIS listing's garage.
    v, reason = dim_parking(TALLINN, POIS)
    assert v is None
    assert "garaaž" in reason.lower()


def test_no_overpass_fragment_or_poi_kinds():
    # NULL dims need no live-path wiring: the module must not grow a
    # query fragment or tag mapping by accident.
    assert not hasattr(g01a, "GROUP01A_OVERPASS_FRAGMENT")
    assert not hasattr(g01a, "GROUP01A_POI_KIND")
    assert not hasattr(g01a, "kinds_from_tags")


def test_registry_and_aggregator_cover_all_twenty():
    assert [k for k, _, _ in GROUP01A_DIMS] == [
        "purchase_price", "utility_costs", "bedrooms", "bathrooms",
        "floor_plan_flow", "kitchen", "workspace", "storage", "parking",
        "move_in_readiness", "finishes", "outdoor_living", "smart_home",
        "primary_suite", "laundry", "mudroom", "flex_space",
        "gear_storage", "outdoor_kitchen", "backup_heating",
    ]
    assert [p for _, p, _ in GROUP01A_DIMS] == [
        "p1", "p5", "p22", "p23", "p24", "p25", "p26", "p27", "p28",
        "p32", "p36", "p37", "p39", "p92", "p93", "p94", "p99",
        "p109", "p110", "p119",
    ]
    out = score_group01a(TALLINN, POIS)
    assert out == {key: None for key, _, _ in GROUP01A_DIMS}
    assert len(out) == 20
    assert g01a.GROUP01A_DIMS is GROUP01A_DIMS
