"""Group 3 cadastre ground-truth dims, batch B (issue #152): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group03b as g03b
from dims_group03b import (
    GROUP03B_DIMS,
    GROUP03B_OVERPASS_FRAGMENT,
    GROUP03B_POI_KIND,
    SEPTIC_RADIUS_M,
    WATERRIGHTS_RADIUS_M,
    WATERTABLE_RADIUS_M,
    dim_geothermal,
    dim_septic,
    dim_soil_percolation,
    dim_water_rights,
    dim_water_table,
    kinds_from_tags,
    score_group03b,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m shallowsrc, ~450 m wetland, ~80 m flowwater, ~1.2 km flowwater.
POIS = [
    _poi("shallowsrc", 0.001),
    _poi("wetland", 0.004),
    _poi("flowwater", 0.0007),
    _poi("flowwater", 0.011),
]


def test_water_table_near_indicator_scores_low_with_honest_reason():
    v, reason = dim_water_table(TALLINN, POIS)
    assert v == 35
    assert "hinnang" in reason and "mitte" in reason


def test_water_table_absence_is_weak_good_sign_capped():
    v, reason = dim_water_table(TALLINN, [_poi("flowwater", 0.001)])
    assert v == 75
    assert "nõrk" in reason and "Maa-ameti" in reason
    assert dim_water_table(None, POIS)[0] is None
    assert dim_water_table(TALLINN, None)[0] is None


def test_water_table_mid_band():
    v, _ = dim_water_table(TALLINN, [_poi("wetland", 0.009)])  # ~1 km
    assert v == 70


def test_geothermal_is_always_none_with_registry_reason():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None)]:
        v, reason = dim_geothermal(origin, pois)
        assert v is None
        assert "EI OLE" in reason and "Maa-ameti" in reason


def test_septic_near_receptor_constrained_names_uvk_gap():
    v, reason = dim_septic(TALLINN, [_poi("shallowsrc", 0.0003)])  # ~33 m
    assert v == 40
    assert "hinnang" in reason and "mitte" in reason
    _, absent_reason = dim_septic(TALLINN, [])
    assert "ÜVK" in absent_reason
    v2, _ = dim_septic(TALLINN, [_poi("wetland", 0.002)])  # ~220 m
    assert v2 == 75
    assert dim_septic(TALLINN, [])[0] == 85
    assert dim_septic(None, POIS)[0] is None


def test_water_rights_near_flowwater_flags_title_check():
    v, reason = dim_water_rights(TALLINN, POIS)
    assert v == 55
    assert "hinnang" in reason and "kontroll" in reason
    _, absent_reason = dim_water_rights(TALLINN, [_poi("lake", 0.0005)])
    assert "kinnistusraamat" in absent_reason.lower()
    # Ponds/lakes are NOT flowwater: sibling p338 amenity kind stays out.
    assert dim_water_rights(TALLINN, [_poi("lake", 0.0005)])[0] == 85
    assert dim_water_rights(TALLINN, None)[0] is None


def test_soil_percolation_is_always_none_with_kov_reason():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None)]:
        v, reason = dim_soil_percolation(origin, pois)
        assert v is None
        assert "EI OLE" in reason and "KOV" in reason


def test_kinds_from_tags_splits_flowwater_wetland_shallowsrc():
    assert kinds_from_tags({"waterway": "stream"}) == "flowwater"
    assert kinds_from_tags({"waterway": "ditch"}) == "flowwater"
    assert kinds_from_tags({"man_made": "water_well"}) == "shallowsrc"
    assert kinds_from_tags({"natural": "spring"}) == "shallowsrc"
    assert kinds_from_tags({"natural": "wetland"}) == "wetland"
    assert kinds_from_tags({"natural": "water"}) is None  # p338 owns it
    assert kinds_from_tags({}) is None


def test_fragment_queries_nwr_parity_and_radii():
    for line in ("water_well", "natural", "wetland", "waterway"):
        assert line in GROUP03B_OVERPASS_FRAGMENT
    assert "way[" in GROUP03B_OVERPASS_FRAGMENT  # wetlands/waterways are ways
    assert "around:3000" in GROUP03B_OVERPASS_FRAGMENT
    assert "around:2000" in GROUP03B_OVERPASS_FRAGMENT
    assert WATERTABLE_RADIUS_M == 3000.0
    assert SEPTIC_RADIUS_M == 1000.0
    assert WATERRIGHTS_RADIUS_M == 2000.0
    kinds = {row[0]: row[1] for row in GROUP03B_POI_KIND}
    assert kinds["waterway"]["stream"] == "flowwater"
    assert kinds["natural"]["wetland"] == "wetland"


def test_registry_and_aggregator_cover_all_five():
    assert [k for k, _, _ in GROUP03B_DIMS] == [
        "water_table", "geothermal", "septic", "water_rights", "soil_percolation",
    ]
    out = score_group03b(TALLINN, POIS)
    assert out == {
        "water_table": 35,
        "geothermal": None,
        "septic": 60,
        "water_rights": 55,
        "soil_percolation": None,
    }
    assert g03b.GROUP03B_DIMS is GROUP03B_DIMS
