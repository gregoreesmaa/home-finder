"""Hermetic tests for services/scoring/dims_group06.py (issue #138).

Pure scorers only — synthetic origins/POIs, no network, no snapshot.
Run: python3 -m pytest services/scoring/tests/test_dims_group06.py -q
"""

from dims_group06 import (
    GROUP06_DIMS,
    GROUP06_OVERPASS_FRAGMENT,
    GROUP06_POI_KIND,
    HERITAGE_RADIUS_M,
    dim_commission,
    dim_facade_easements,
    dim_heritage_district,
    dim_leadglass,
    dim_tax_credits,
    kinds_from_tags,
    score_group06,
)

TALLINN = (59.4374, 24.7454)  # Vanalinn


def _pois(*coords):
    return [{"lat": la, "lon": lo, "kind": "heritage"} for la, lo in coords]


def test_registry_covers_exactly_the_five_assigned_params():
    assert [p for _, p, _ in GROUP06_DIMS] == ["p72", "p158", "p272", "p320", "p351"]
    assert [k for k, _, _ in GROUP06_DIMS] == [
        "heritage_district", "tax_credits", "facade_easements",
        "commission", "leadglass",
    ]


def test_missing_inputs_stay_none_never_zero():
    assert dim_heritage_district(None, [])[0] is None
    assert dim_heritage_district(TALLINN, None)[0] is None
    assert dim_commission(None, [])[0] is None
    assert dim_commission(TALLINN, None)[0] is None
    # Registry stubs stay None even with full inputs (abort-deal path).
    assert dim_tax_credits(TALLINN, _pois(TALLINN))[0] is None
    assert dim_facade_easements(TALLINN, _pois(TALLINN))[0] is None
    assert dim_leadglass(TALLINN, _pois(TALLINN))[0] is None


def test_p72_counts_mapped_heritage_with_modest_bands():
    assert dim_heritage_district(TALLINN, [])[0] == 20
    one = _pois((TALLINN[0] + 0.001, TALLINN[1]))
    assert dim_heritage_district(TALLINN, one)[0] == 45  # one manor is not a district
    three = _pois(*[(TALLINN[0] + 0.001 * i, TALLINN[1]) for i in range(1, 4)])
    assert dim_heritage_district(TALLINN, three)[0] == 65
    dense = _pois(*[(TALLINN[0] + 0.001 * i, TALLINN[1]) for i in range(1, 10)])
    assert dim_heritage_district(TALLINN, dense)[0] == 100
    # Far objects (outside 800 m) do not count.
    assert dim_heritage_district(TALLINN, _pois((59.5, 24.9)))[0] == 20
    # Non-heritage kinds do not count.
    assert dim_heritage_district(TALLINN, [{"lat": TALLINN[0], "lon": TALLINN[1], "kind": "shop"}])[0] == 20


def test_p72_reasons_are_honest_estonian():
    _, reason = dim_heritage_district(TALLINN, _pois(TALLINN))
    assert "hinnang" in reason
    assert "800 m" in reason
    _, empty_reason = dim_heritage_district(TALLINN, [])
    assert "Muinsuskaitseameti registrit snapshots pole" in empty_reason


def test_p320_is_the_soft_inverse_of_p72():
    assert dim_commission(TALLINN, [])[0] == 90  # no heritage, no friction
    one = _pois((TALLINN[0] + 0.001, TALLINN[1]))
    assert dim_commission(TALLINN, one)[0] == 70
    dense = _pois(*[(TALLINN[0] + 0.001 * i, TALLINN[1]) for i in range(1, 10)])
    assert dim_commission(TALLINN, dense)[0] == 25  # soft floor, never 0
    _, reason = dim_commission(TALLINN, one)
    assert "hinnang" in reason
    assert "menetlusotsus" in reason


def test_no_map_stubs_name_the_missing_register():
    _, r158 = dim_tax_credits(TALLINN, [])
    assert "EUR" in r158 and "Muinsuskaitseameti registri" in r158
    assert "katkestatakse" in r158  # abort-deal semantics
    _, r272 = dim_facade_easements(TALLINN, [])
    assert "katastriseaduslikku" in r272
    _, r351 = dim_leadglass(TALLINN, [])
    assert "aknaregister puudub" in r351


def test_kinds_from_tags_maps_any_heritage_key():
    assert kinds_from_tags({"historic": "manor"}) == "heritage"
    assert kinds_from_tags({"historic": "memorial"}) == "heritage"
    assert kinds_from_tags({"heritage": "1"}) == "heritage"
    assert kinds_from_tags({"heritage": "yes"}) == "heritage"
    assert kinds_from_tags({"unesco": "yes"}) == "heritage"
    assert kinds_from_tags({"historic": "manor;yes"}) == "heritage"
    assert kinds_from_tags({"shop": "supermarket"}) is None
    assert kinds_from_tags({"historic": ""}) is None
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None


def test_overpass_fragment_queries_nodes_and_ways():
    for key in ("historic", "heritage", "unesco"):
        assert 'node["%s"]' % key in GROUP06_OVERPASS_FRAGMENT
        assert 'way["%s"]' % key in GROUP06_OVERPASS_FRAGMENT
    assert "around:2000" in GROUP06_OVERPASS_FRAGMENT


def test_poi_kind_table_covers_the_three_keys():
    assert {k for k, _ in GROUP06_POI_KIND} == {"historic", "heritage", "unesco"}


def test_score_group06_entry_point_keys():
    out = score_group06(TALLINN, _pois(TALLINN))
    assert set(out) == {"heritage_district", "tax_credits", "facade_easements",
                        "commission", "leadglass"}
    assert out["heritage_district"] == 45
    assert out["commission"] == 70
    assert out["tax_credits"] is None
    assert out["facade_easements"] is None
    assert out["leadglass"] is None
    assert HERITAGE_RADIUS_M == 800.0
