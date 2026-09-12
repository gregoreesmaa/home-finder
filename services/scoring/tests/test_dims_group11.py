"""Group 11 dims (batch B2, issue #97): pure scorers offline, no network.

Covers p88 (school-bus proxy), p101 (specialised recreation), p124
(specialised medical), p190 (foraging) and the p317 upkeep stub, plus the
query-fragment / tag-mapping wiring the live path needs on integration.
"""

import livability
from dims_group11 import (
    GROUP11_DIMS,
    GROUP11_OVERPASS_FRAGMENT,
    GROUP11_POI_KIND,
    dim_forage,
    dim_medical_special,
    dim_park_upkeep,
    dim_rec_special,
    dim_school_bus,
    kinds_from_tags,
    score_group11,
)

TALLINN = (59.4372, 24.7536)
POIS = [
    {"kind": "school", "lat": 59.4380, "lon": 24.7550},       # ~120 m
    {"kind": "bus_stop", "lat": 59.4375, "lon": 24.7540},     # ~50 m
    {"kind": "hospital", "lat": 59.4450, "lon": 24.7600},     # ~900 m
    {"kind": "dentist", "lat": 59.4500, "lon": 24.7700},      # ~1.7 km
    {"kind": "rec_special", "lat": 59.4420, "lon": 24.7620},  # ~750 m
    {"kind": "scrub", "lat": 59.4350, "lon": 24.7500},        # ~300 m
    {"kind": "forest", "lat": 59.4600, "lon": 24.7800},       # ~3 km
]


def test_school_bus_proxy_scores_school_plus_stop():
    v, reason = dim_school_bus(TALLINN, POIS)
    assert v == 100  # school ~120 m, stop within 500 m
    assert "hinnang" in reason and "kool" in reason and "peatus" in reason
    # no stop nearby: same school, capped with the nearest-stop reason
    far = [p for p in POIS if p["kind"] != "bus_stop"]
    v2, r2 = dim_school_bus(TALLINN, far)
    assert v2 == 45
    assert "hinnang" in r2 and "peatus" in r2
    # no school at all: low floor, never a pass
    v3, r3 = dim_school_bus(TALLINN, [p for p in POIS if p["kind"] == "bus_stop"])
    assert v3 == 15
    assert "hinnang" in r3


def test_school_bus_ignores_kindergarten_and_missing_data():
    kinder = [{"kind": "kindergarten", "lat": 59.4380, "lon": 24.7550},
              {"kind": "bus_stop", "lat": 59.4375, "lon": 24.7540}]
    v, _ = dim_school_bus(TALLINN, kinder)
    assert v == 15, "kindergarten has no school bus; must not score as school"
    v2, r2 = dim_school_bus(None, POIS)
    assert v2 is None and "puudub" in r2
    v3, r3 = dim_school_bus(TALLINN, None)
    assert v3 is None and "puudub" in r3


def test_rec_special_bands_and_reasons():
    v, reason = dim_rec_special(TALLINN, POIS)
    assert v == 100
    assert "erisport" in reason and "m" in reason
    v2, r2 = dim_rec_special(TALLINN, [])
    assert v2 == 25 and "2 km" in r2
    v3, r3 = dim_rec_special(None, POIS)
    assert v3 is None and "puudub" in r3
    v4, r4 = dim_rec_special(TALLINN, None)
    assert v4 is None and "puudub" in r4
    # generic park must NOT feed the specialised tier
    v5, _ = dim_rec_special(TALLINN, [{"kind": "park", "lat": 59.4373, "lon": 24.7537}])
    assert v5 == 25


def test_medical_special_prefers_nearest_tier():
    v, reason = dim_medical_special(TALLINN, POIS)
    assert v == 100  # hospital ~900 m
    assert "haigla" in reason
    only_dentist = [p for p in POIS if p["kind"] == "dentist"]
    v2, _ = dim_medical_special(TALLINN, only_dentist)
    assert v2 == 100, "dentist ~1.7 km still inside the 2 km top band"
    v3, r3 = dim_medical_special(TALLINN, [])
    assert v3 == 25 and "5 km" in r3
    v4, r4 = dim_medical_special(TALLINN, None)
    assert v4 is None and "puudub" in r4
    # GP-level clinic stays in the generic services dim, not here
    v5, _ = dim_medical_special(TALLINN, [{"kind": "clinic", "lat": 59.4373, "lon": 24.7537}])
    assert v5 == 25


def test_forage_uses_forest_and_scrub():
    v, reason = dim_forage(TALLINN, POIS)
    assert v == 100  # scrub ~300 m beats forest ~3 km
    assert "korjeala" in reason
    only_forest = [p for p in POIS if p["kind"] == "forest"]
    v2, _ = dim_forage(TALLINN, only_forest)
    assert v2 == 60, "forest ~3 km falls through to the last band (live: outside fetch)"
    v2b, r2 = dim_forage(TALLINN, [])
    assert v2b == 20
    assert "1,5 km" in r2
    v3, r3 = dim_forage(TALLINN, None)
    assert v3 is None and "puudub" in r3
    # meadow/park greenery is not foraging land
    v4, _ = dim_forage(TALLINN, [{"kind": "park", "lat": 59.4373, "lon": 24.7537}])
    assert v4 == 20


def test_park_upkeep_stub_returns_null_with_reason():
    v, reason = dim_park_upkeep()
    assert v is None
    assert "puuduvad" in reason
    assert "park_upkeep" in GROUP11_DIMS


def test_registry_and_batch_scoring():
    assert set(GROUP11_DIMS) == {
        "school_bus", "rec_special", "medical_special", "forage", "park_upkeep",
    }
    for _, (title, _) in GROUP11_DIMS.items():
        assert title and isinstance(title, str)
    dims, reasons = score_group11(TALLINN, POIS)
    assert set(dims) == set(GROUP11_DIMS)
    assert dims["park_upkeep"] is None
    assert dims["school_bus"] == 100 and dims["forage"] == 100
    assert all(isinstance(r, str) and r for r in reasons)
    dims_none, _ = score_group11(None, None)
    assert all(v is None for v in dims_none.values())


def test_tag_mapping_covers_new_kinds_without_collisions():
    assert kinds_from_tags({"amenity": "hospital"}) == "hospital"
    assert kinds_from_tags({"amenity": "dentist"}) == "dentist"
    for leisure in ("sports_centre", "sports_hall", "stadium", "swimming_pool",
                    "water_park", "ice_rink", "golf_course", "fitness_centre"):
        assert kinds_from_tags({"leisure": leisure}) == "rec_special", leisure
    assert kinds_from_tags({"natural": "scrub"}) == "scrub"
    assert kinds_from_tags({"natural": "heath"}) == "scrub"
    assert kinds_from_tags({"leisure": "park"}) is None
    assert kinds_from_tags({"amenity": "clinic"}) is None
    assert kinds_from_tags({}) is None
    # no new tag value may already mean something else in the live pipeline
    live_values = {val for _, mapping in livability._POI_KIND for val in mapping}
    for _, mapping in GROUP11_POI_KIND:
        assert not (set(mapping) & live_values), "tag collision with live pipeline"


def test_overpass_fragment_lists_every_new_tag():
    for token in ("hospital", "dentist", "sports_centre", "sports_hall",
                  "stadium", "swimming_pool", "water_park", "ice_rink",
                  "golf_course", "fitness_centre", "scrub", "heath"):
        assert token in GROUP11_OVERPASS_FRAGMENT, token
    assert "around:5000" in GROUP11_OVERPASS_FRAGMENT  # sparse medical tier
    assert "around:2000" in GROUP11_OVERPASS_FRAGMENT  # suburban sports tier
    assert "around:1500" in GROUP11_OVERPASS_FRAGMENT  # scrub/heath
    assert GROUP11_OVERPASS_FRAGMENT.count("node[") == 3
    assert GROUP11_OVERPASS_FRAGMENT.count("way[") == 3
