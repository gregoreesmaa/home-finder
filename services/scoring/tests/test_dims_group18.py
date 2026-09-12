"""Group 18 street-traffic dims (issue #113): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture POIs, the query
fragment is asserted as text, and tag mapping runs on static tag dicts.
Run: python3 -m pytest services/scoring/tests/test_dims_group18.py -q
"""

import dims_group18 as g18
from dims_group18 import (
    GROUP18_DIMS,
    GROUP18_OVERPASS_FRAGMENT,
    GROUP18_POI_KIND,
    LAYER_META,
    _max_speed,
    dim_calming,
    dim_lighting,
    dim_parking,
    dim_school_gridlock,
    dim_traffic,
    kinds_from_tags,
    score_group18,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~50 m fast road, ~150 m busy road, ~200 m school, ~100 m lit street.
POIS = [
    _poi("fast_road", 0.00045),
    _poi("busy_road", 0.00135),
    _poi("school", 0.0018),
    _poi("lit_street", 0.0009),
    _poi("calming", 0.002),
    _poi("street_parking", 0.001),
]


# --- tag mapping ----------------------------------------------------------


def test_kinds_highway_classes():
    assert kinds_from_tags({"highway": "motorway"}) == "fast_road"
    assert kinds_from_tags({"highway": "trunk"}) == "fast_road"
    assert kinds_from_tags({"highway": "primary"}) == "fast_road"
    assert kinds_from_tags({"highway": "secondary"}) == "busy_road"
    assert kinds_from_tags({"highway": "residential"}) is None
    assert kinds_from_tags({"highway": "living_street"}) is None


def test_kinds_maxspeed_tiers():
    assert kinds_from_tags({"maxspeed": "90"}) == "fast_road"
    assert kinds_from_tags({"maxspeed": "70"}) == "fast_road"
    assert kinds_from_tags({"maxspeed": "50"}) == "busy_road"
    assert kinds_from_tags({"maxspeed": "30"}) is None
    assert kinds_from_tags({"maxspeed": "EE:urban"}) is None
    # Class wins ties: a slowed primary still carries volume.
    assert kinds_from_tags({"highway": "primary", "maxspeed": "30"}) == "fast_road"
    # Speed upgrades: an unclassified 90-road reads fast.
    assert kinds_from_tags({"highway": "unclassified", "maxspeed": "90"}) == "fast_road"


def test_kinds_calming_parking_lit():
    assert kinds_from_tags({"traffic_calming": "table"}) == "calming"
    assert kinds_from_tags({"traffic_calming": "bump"}) == "calming"
    assert kinds_from_tags({"traffic_calming": "no"}) is None
    assert kinds_from_tags({"amenity": "parking", "parking": "street_side"}) == "street_parking"
    assert kinds_from_tags({"amenity": "parking", "parking": "lane"}) == "street_parking"
    assert kinds_from_tags({"amenity": "parking", "parking": "surface"}) is None
    assert kinds_from_tags({"amenity": "parking"}) is None
    assert kinds_from_tags({"highway": "residential", "lit": "yes"}) == "lit_street"
    assert kinds_from_tags({"highway": "residential", "lit": "no"}) is None
    assert kinds_from_tags({"lit": "yes"}) is None  # no highway: not a street
    # One POI, one kind: arterials read as roads, never as lighting.
    assert kinds_from_tags({"highway": "primary", "lit": "yes"}) == "fast_road"


def test_kinds_reject_garbage():
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert kinds_from_tags("highway=primary") is None
    assert kinds_from_tags({"highway": 42}) is None


def test_max_speed_parsing():
    assert _max_speed("50") == 50
    assert _max_speed("30;50") == 30
    assert _max_speed("EE:urban") is None
    assert _max_speed(50) is None
    assert _max_speed("-5") is None
    assert _max_speed(None) is None


# --- p82 ------------------------------------------------------------------


def test_traffic_adjacent_fast_scores_floor_with_honest_reason():
    v, reason = dim_traffic(TALLINN, POIS)  # fast ~50 m wins over busy ~150 m
    assert v == 25
    assert "hinnang" in reason and "mitte mõõdetud liiklus" in reason


def test_traffic_busy_only_uses_gentler_bands():
    v, _ = dim_traffic(TALLINN, [_poi("busy_road", 0.00135)])  # ~150 m
    assert v == 60
    v2, _ = dim_traffic(TALLINN, [_poi("fast_road", 0.0045)])  # ~500 m
    assert v2 == 70


def test_traffic_calm_fallback_is_90_not_100():
    v, reason = dim_traffic(TALLINN, [_poi("school", 0.001)])
    assert v == 90
    assert "1,5 km" in reason


def test_traffic_missing_inputs_stay_none():
    assert dim_traffic(None, POIS)[0] is None
    assert dim_traffic(TALLINN, None)[0] is None
    assert "puudub" in dim_traffic(None, POIS)[1]


# --- p83 ------------------------------------------------------------------


def test_parking_absent_is_mild_floor():
    v, reason = dim_parking(TALLINN, [_poi("school", 0.001)])
    assert v == 40
    assert "300 m" in reason


def test_parking_density_bands():
    assert dim_parking(TALLINN, [_poi("street_parking", 0.001)])[0] == 65
    pois3 = [_poi("street_parking", 0.001 + i * 0.0002) for i in range(3)]
    assert dim_parking(TALLINN, pois3)[0] == 80
    pois6 = [_poi("street_parking", 0.001 + i * 0.0002) for i in range(6)]
    assert dim_parking(TALLINN, pois6)[0] == 80
    assert dim_parking(None, POIS)[0] is None


# --- p166 -----------------------------------------------------------------


def test_calming_absent_is_neutral():
    v, reason = dim_calming(TALLINN, [_poi("school", 0.001)])
    assert v == 45
    assert "500 m" in reason


def test_calming_presence_scores_up_capped():
    assert dim_calming(TALLINN, [_poi("calming", 0.002)])[0] == 65
    pois3 = [_poi("calming", 0.002 + i * 0.0003) for i in range(3)]
    assert dim_calming(TALLINN, pois3)[0] == 80
    assert dim_calming(TALLINN, None)[0] is None


# --- p350 -----------------------------------------------------------------


def test_lighting_near_lit_street_scores_top():
    v, reason = dim_lighting(TALLINN, POIS)  # lit ~100 m
    assert v == 100
    assert "hinnang" in reason


def test_lighting_bands_and_absent():
    assert dim_lighting(TALLINN, [_poi("lit_street", 0.0054)])[0] == 55  # ~600 m
    v, reason = dim_lighting(TALLINN, [_poi("school", 0.001)])
    assert v == 40
    assert "1 km" in reason
    assert dim_lighting(None, POIS)[0] is None


# --- p441 -----------------------------------------------------------------


def test_gridlock_no_school_is_high():
    v, reason = dim_school_gridlock(TALLINN, [_poi("fast_road", 0.00045)])
    assert v == 85
    assert "500 m" in reason


def test_gridlock_school_without_arterial_is_moderate():
    v, reason = dim_school_gridlock(TALLINN, [_poi("school", 0.0018)])  # ~200 m
    assert v == 70
    assert "hinnang" in reason


def test_gridlock_school_plus_arterial_scores_low():
    v, reason = dim_school_gridlock(TALLINN, POIS)  # school ~200 m + fast ~50 m
    assert v == 40
    assert "mitte mõõdetud liiklus" in reason
    assert dim_school_gridlock(TALLINN, None)[0] is None


# --- registry + wiring ----------------------------------------------------


def test_score_group18_keys_and_range():
    out = score_group18(TALLINN, POIS)
    assert sorted(out) == ["calming", "lighting", "parking", "school_gridlock", "traffic"]
    assert all(v is None or 0 <= v <= 100 for v in out.values())
    assert {k for k, _, _ in GROUP18_DIMS} == set(out)
    assert score_group18(None, None) == {k: None for k in out}


def test_fragment_lists_every_tag():
    for needle in ("traffic_calming", '"amenity"="parking"', "motorway|trunk|primary|secondary",
                   '"maxspeed"', '"lit"'):
        assert needle in GROUP18_OVERPASS_FRAGMENT, needle
    assert "{lat}" in GROUP18_OVERPASS_FRAGMENT and "{lon}" in GROUP18_OVERPASS_FRAGMENT


def test_poi_kind_table_covers_classes():
    highway = dict(GROUP18_POI_KIND)["highway"]
    assert highway["primary"] == "fast_road" and highway["secondary"] == "busy_road"
    lit = dict(GROUP18_POI_KIND)["lit"]
    assert lit["yes"] == "lit_street" and "no" not in lit


def test_layer_meta_is_honest():
    assert "hinnang" in LAYER_META["traffic"]["title"]
    assert "mitte mõõdetud liiklus" in LAYER_META["traffic"]["source"]
    assert "hinnang" in LAYER_META["school_gridlock"]["title"]
    assert "mitte mõõdetud liiklus" in LAYER_META["school_gridlock"]["source"]
    params = sorted(m["param"] for m in LAYER_META.values())
    assert params == [82, 83, 166, 350, 441]


def test_module_exports_five_dims():
    assert len(GROUP18_DIMS) == 5
    assert [pid for _, pid, _ in GROUP18_DIMS] == ["p82", "p83", "p166", "p350", "p441"]
    assert g18 is not None
