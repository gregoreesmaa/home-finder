"""Group 3 cadastre per-listing dims, batch C (issue #153): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group03c as g03c
from dims_group03c import (
    GROUP03C_DIMS,
    GROUP03C_OVERPASS_FRAGMENT,
    GROUP03C_POI_KIND,
    RIPARIAN_RADIUS_M,
    SPRINGS_RADIUS_M,
    WETLAND_RADIUS_M,
    dim_riparian_constraints,
    dim_soil_ph,
    dim_springs,
    dim_unregistered_easements,
    dim_wetland_proximity,
    kinds_from_tags,
    score_group03c,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~111 m wetland, ~445 m reserve, ~222 m shallowsrc, ~78 m flowwater,
# ~1.2 km shore.
POIS = [
    _poi("wetland", 0.001),
    _poi("reserve", 0.004),
    _poi("shallowsrc", 0.002),
    _poi("flowwater", 0.0007),
    _poi("shore", 0.011),
]


def test_wetland_proximity_near_scores_low_mid_with_metres_reason():
    v, reason = dim_wetland_proximity(TALLINN, POIS)
    assert v == 45
    assert "111 m" in reason and "hinnang" in reason
    assert "meetrites" in reason  # the param's own REAL unit, honestly


def test_wetland_proximity_absence_is_weak_good_sign_capped():
    v, reason = dim_wetland_proximity(TALLINN, [_poi("shallowsrc", 0.001)])
    assert v == 75
    assert "nõrk" in reason and "EELIS" in reason
    assert dim_wetland_proximity(None, POIS)[0] is None
    assert dim_wetland_proximity(TALLINN, None)[0] is None


def test_wetland_proximity_mid_band_and_reserve_only():
    v, _ = dim_wetland_proximity(TALLINN, [_poi("reserve", 0.009)])  # ~1 km
    assert v == 72
    v2, r2 = dim_wetland_proximity(TALLINN, [_poi("reserve", 0.001)])
    assert v2 == 45 and "kaitsepiirangu" in r2


def test_springs_near_scores_low_ignoring_wetlands():
    # Wetlands must NOT move p256 (p183 owns that framing, #152).
    v, reason = dim_springs(TALLINN, POIS)
    assert v == 55
    assert "hinnang" in reason and "mitte" in reason
    v2, _ = dim_springs(TALLINN, [_poi("wetland", 0.001)])
    assert v2 == 70  # wetland-only reads as absence here


def test_springs_absence_cap_is_weaker_than_p183():
    # p183 absence caps at 75 WITH wetlands counted; p256 excludes them,
    # so its absence evidence is strictly weaker (cap 70, reason says so).
    v, reason = dim_springs(TALLINN, [])
    assert v == 70
    assert "märgalad arvestamata" in reason and "p183" in reason
    assert dim_springs(None, POIS)[0] is None
    assert dim_springs(TALLINN, None)[0] is None


def test_soil_ph_is_always_none_with_registry_reason():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None)]:
        v, reason = dim_soil_ph(origin, pois)
        assert v is None
        assert "EI OLE" in reason and "ESDAC" in reason


def test_unregistered_easements_is_always_none_with_audit_reason():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None)]:
        v, reason = dim_unregistered_easements(origin, pois)
        assert v is None
        assert "EI OLE" in reason and "õigusaudit" in reason


def test_riparian_near_flowwater_flags_constraint_check():
    v, reason = dim_riparian_constraints(TALLINN, POIS)
    assert v == 55
    assert "hinnang" in reason and "kontroll" in reason
    _, absent_reason = dim_riparian_constraints(TALLINN, [_poi("lake", 0.0005)])
    assert "kinnistusraamat" in absent_reason.lower()
    # Ponds/lakes are NOT flowwater/shore: p338 amenity kind stays out.
    assert dim_riparian_constraints(TALLINN, [_poi("lake", 0.0005)])[0] == 85
    assert dim_riparian_constraints(TALLINN, None)[0] is None


def test_riparian_counts_shore_unlike_p228():
    # Disjoint from p228 (#152, flowing water only): the sea shore binds
    # the Water Act zones too, so shore-only scores here, not absence.
    v, reason = dim_riparian_constraints(TALLINN, [_poi("shore", 0.002)])
    assert v == 70
    assert "mererand" in reason


def test_kinds_from_tags_maps_new_kinds_and_yields_water_to_none():
    assert kinds_from_tags({"waterway": "river"}) == "flowwater"
    assert kinds_from_tags({"waterway": "drain"}) == "flowwater"
    assert kinds_from_tags({"man_made": "water_well"}) == "shallowsrc"
    assert kinds_from_tags({"natural": "spring"}) == "shallowsrc"
    assert kinds_from_tags({"natural": "wetland"}) == "wetland"
    assert kinds_from_tags({"natural": "coastline"}) == "shore"
    assert kinds_from_tags({"leisure": "nature_reserve"}) == "reserve"
    assert kinds_from_tags({"boundary": "protected_area"}) == "reserve"
    assert kinds_from_tags({"boundary": "nature_reserve"}) == "reserve"
    assert kinds_from_tags({"natural": "water"}) is None  # p338 owns it
    assert kinds_from_tags({"natural": "wood"}) is None  # wildcorr owns it
    assert kinds_from_tags({}) is None


def test_fragment_queries_nwr_parity_and_radii():
    for line in ("wetland", "spring", "water_well", "nature_reserve",
                 "protected_area", "coastline", "waterway"):
        assert line in GROUP03C_OVERPASS_FRAGMENT
    assert "way[" in GROUP03C_OVERPASS_FRAGMENT  # areas are ways/relations
    assert "around:3000" in GROUP03C_OVERPASS_FRAGMENT
    assert "around:2000" in GROUP03C_OVERPASS_FRAGMENT
    assert WETLAND_RADIUS_M == 3000.0
    assert SPRINGS_RADIUS_M == 3000.0
    assert RIPARIAN_RADIUS_M == 2000.0
    kinds = {row[0]: row[1] for row in GROUP03C_POI_KIND}
    assert kinds["boundary"]["protected_area"] == "reserve"
    assert kinds["natural"]["coastline"] == "shore"
    # Shared #152 spellings (dedup, do not double-count on integration).
    assert kinds["natural"]["wetland"] == "wetland"
    assert kinds["natural"]["spring"] == "shallowsrc"
    assert kinds["waterway"]["stream"] == "flowwater"


def test_registry_and_aggregator_cover_all_five():
    assert [k for k, _, _ in GROUP03C_DIMS] == [
        "wetland_proximity", "springs", "soil_ph", "unregistered_easements",
        "riparian_constraints",
    ]
    out = score_group03c(TALLINN, POIS)
    assert out == {
        "wetland_proximity": 45,
        "springs": 55,
        "soil_ph": None,
        "unregistered_easements": None,
        "riparian_constraints": 55,
    }
    assert g03c.GROUP03C_DIMS[0][1] == "p254"
    assert score_group03c(None, None) == {
        "wetland_proximity": None,
        "springs": None,
        "soil_ph": None,
        "unregistered_easements": None,
        "riparian_constraints": None,
    }
