"""Hermetic tests for services/scoring/dims_group06b.py (issue #139).

Pure scorers only — synthetic origins/POIs, no network, no snapshot.
Run: python3 -m pytest services/scoring/tests/test_dims_group06b.py -q
"""

from dims_group06b import (
    ANTIQUES_RADIUS_M,
    GROUP06B_DIMS,
    GROUP06B_OVERPASS_FRAGMENT,
    GROUP06B_POI_KIND,
    PLASTER_RADIUS_M,
    SOCIETY_RADIUS_M,
    dim_antiques,
    dim_asbestos,
    dim_plaster_craft,
    dim_provenance,
    dim_settling,
    dim_society,
    dim_woodfire,
    kinds_from_tags,
    score_group06b,
)

TALLINN = (59.4374, 24.7454)  # Vanalinn


def _pois(kind, *coords):
    return [{"lat": la, "lon": lo, "kind": kind} for la, lo in coords]


def _near(n=1, dlat=0.001):
    return _pois("plasterbld", *[(TALLINN[0] + dlat * i, TALLINN[1]) for i in range(1, n + 1)])


def test_registry_covers_exactly_the_seven_assigned_params():
    assert [p for _, p, _ in GROUP06B_DIMS] == [
        "p352", "p353", "p354", "p355", "p356", "p359", "p360"]
    assert [k for k, _, _ in GROUP06B_DIMS] == [
        "plaster_craft", "antiques", "settling", "society",
        "woodfire", "asbestos", "provenance",
    ]


def test_missing_inputs_stay_none_never_zero():
    assert dim_plaster_craft(None, [])[0] is None
    assert dim_plaster_craft(TALLINN, None)[0] is None
    assert dim_antiques(None, [])[0] is None
    assert dim_antiques(TALLINN, None)[0] is None
    assert dim_society(None, [])[0] is None
    assert dim_society(TALLINN, None)[0] is None
    assert dim_woodfire(None, [])[0] is None
    assert dim_woodfire(TALLINN, None)[0] is None
    # Registry stubs stay None even with full inputs.
    assert dim_settling(TALLINN, _near(3))[0] is None
    assert dim_asbestos(TALLINN, _near(3))[0] is None
    assert dim_provenance(TALLINN, _near(3))[0] is None


def test_p352_counts_mapped_plaster_with_modest_bands():
    assert dim_plaster_craft(TALLINN, [])[0] == 30  # thin mapping, not 0
    assert dim_plaster_craft(TALLINN, _near(1))[0] == 50
    assert dim_plaster_craft(TALLINN, _near(3))[0] == 70
    dense = _pois("plasterbld", *[(TALLINN[0] + 0.0004 * i, TALLINN[1]) for i in range(1, 10)])
    assert dim_plaster_craft(TALLINN, dense)[0] == 100
    # Far houses (outside 500 m) do not count.
    assert dim_plaster_craft(TALLINN, _pois("plasterbld", (59.5, 24.9)))[0] == 30
    # Other kinds do not count.
    assert dim_plaster_craft(
        TALLINN, [{"lat": TALLINN[0], "lon": TALLINN[1], "kind": "woodbld"}])[0] == 30


def test_p352_reasons_are_honest_estonian():
    _, reason = dim_plaster_craft(TALLINN, _near(2))
    assert "hinnang" in reason
    assert "500 m" in reason
    _, empty_reason = dim_plaster_craft(TALLINN, [])
    assert "hõre" in empty_reason


def test_p353_is_boolean_with_unverified_marking():
    near = _pois("antiqueshop", (TALLINN[0] + 0.005, TALLINN[1]))
    assert dim_antiques(TALLINN, near)[0] == 1
    _, reason = dim_antiques(TALLINN, near)
    assert "täpsustamata" in reason
    assert "kauplus ≠ furnituuriladu" in reason
    assert dim_antiques(TALLINN, [])[0] == 0
    assert dim_antiques(TALLINN, _pois("antiqueshop", (59.5, 24.9)))[0] == 0
    assert ANTIQUES_RADIUS_M == 2000.0


def test_p355_parallels_p320_inverse_bands():
    assert dim_society(TALLINN, [])[0] == 90  # no heritage, no friction
    one = _pois("heritage", (TALLINN[0] + 0.001, TALLINN[1]))
    assert dim_society(TALLINN, one)[0] == 70
    dense = _pois("heritage", *[(TALLINN[0] + 0.001 * i, TALLINN[1]) for i in range(1, 10)])
    assert dim_society(TALLINN, dense)[0] == 25  # soft floor, never 0
    _, reason = dim_society(TALLINN, one)
    assert "hinnang" in reason
    assert "seltsiotsus" in reason
    assert SOCIETY_RADIUS_M == 800.0


def test_p356_is_inverse_never_zero_or_hundred():
    adjacent = _pois("woodbld", (TALLINN[0] + 0.0002, TALLINN[1]))
    assert dim_woodfire(TALLINN, adjacent)[0] == 20
    mid = _pois("woodbld", (TALLINN[0] + 0.002, TALLINN[1]))
    assert dim_woodfire(TALLINN, mid)[0] == 60
    assert dim_woodfire(TALLINN, [])[0] == 95  # thin mapping caveat, not clean bill
    _, reason = dim_woodfire(TALLINN, mid)
    assert "hinnang" in reason
    assert "konstruktsiooniuuring" in reason
    _, empty_reason = dim_woodfire(TALLINN, [])
    assert "hõre" in empty_reason


def test_no_map_stubs_name_the_missing_evidence():
    _, r354 = dim_settling(TALLINN, [])
    assert "geotehnilist ekspertiisi" in r354
    _, r359 = dim_asbestos(TALLINN, [])
    assert "laboriuuringut" in r359
    assert "kaardistamata ≠ puudub" in r359
    _, r360 = dim_provenance(TALLINN, [])
    assert "arhiivipäringut" in r360
    assert "start_date" in r360


def test_kinds_from_tags_routes_material_values():
    assert kinds_from_tags({"building:material": "plaster"}) == "plasterbld"
    assert kinds_from_tags({"building": "yes", "building:material": "wood"}) == "woodbld"
    assert kinds_from_tags({"shop": "antiques"}) == "antiqueshop"
    assert kinds_from_tags({"building:material": "plaster;brick"}) == "plasterbld"
    assert kinds_from_tags({"building:material": "brick"}) is None
    assert kinds_from_tags({"building:material": "concrete"}) is None
    assert kinds_from_tags({"shop": "supermarket"}) is None
    assert kinds_from_tags({"historic": "manor"}) is None  # G06 kind, not G06B
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None


def test_overpass_fragment_queries_nodes_and_ways():
    assert 'node["building:material"]' in GROUP06B_OVERPASS_FRAGMENT
    assert 'way["building:material"]' in GROUP06B_OVERPASS_FRAGMENT
    assert 'node["shop"="antiques"]' in GROUP06B_OVERPASS_FRAGMENT
    assert 'way["shop"="antiques"]' in GROUP06B_OVERPASS_FRAGMENT
    assert "around:2000" in GROUP06B_OVERPASS_FRAGMENT


def test_poi_kind_table_covers_material_and_antiques():
    assert dict(GROUP06B_POI_KIND)["building:material"] == {
        "plaster": "plasterbld", "wood": "woodbld"}
    assert dict(GROUP06B_POI_KIND)["shop"] == {"antiques": "antiqueshop"}


def test_score_group06b_entry_point_keys():
    out = score_group06b(TALLINN, _near(1))
    assert set(out) == {"plaster_craft", "antiques", "settling", "society",
                        "woodfire", "asbestos", "provenance"}
    assert out["plaster_craft"] == 50
    assert out["antiques"] == 0
    assert out["settling"] is None
    assert out["society"] == 90
    assert out["woodfire"] == 95
    assert out["asbestos"] is None
    assert out["provenance"] is None
    assert PLASTER_RADIUS_M == 500.0
