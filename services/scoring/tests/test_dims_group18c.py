"""Group 18B green-blue/street dims (issue #126): hermetic scorer tests.

No network, no snapshot reads: scorers run on fixture POIs, the query
fragment is asserted as text, and tag mapping runs on static tag dicts.
Run: python3 -m pytest services/scoring/tests/test_dims_group18c.py -q
"""

import dims_group18c as g18c
from dims_group18c import (
    GROUP18B_DIMS,
    GROUP18B_OVERPASS_FRAGMENT,
    LAYER_META,
    dim_heat,
    dim_visibility,
    kinds_from_tags,
    score_group18b,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~100 m park, ~200 m forest, ~450 m street, ~2.2 km water.
POIS = [
    _poi("park", 0.0009),
    _poi("forest", 0.0018),
    _poi("street", 0.004),
    _poi("water", 0.02),
]


# --- tag mapping ----------------------------------------------------------


def test_kinds_highway_corridors():
    assert kinds_from_tags({"highway": "residential"}) == "street"
    assert kinds_from_tags({"highway": "primary"}) == "street"
    assert kinds_from_tags({"highway": "footway"}) == "street"
    assert kinds_from_tags({"highway": "service"}) == "street"
    assert kinds_from_tags({"highway": "tertiary_link"}) == "street"
    assert kinds_from_tags({"highway": "busway"}) == "street"


def test_kinds_exclude_stops_and_unbuilt():
    assert kinds_from_tags({"highway": "bus_stop"}) is None
    assert kinds_from_tags({"highway": "proposed"}) is None
    assert kinds_from_tags({"highway": "construction"}) is None


def test_kinds_exclude_node_furniture():
    # A stray node POI must never pose as a corridor.
    assert kinds_from_tags({"highway": "crossing"}) is None
    assert kinds_from_tags({"highway": "traffic_signals"}) is None
    assert kinds_from_tags({"highway": "elevator"}) is None
    assert kinds_from_tags({"highway": "street_lamp"}) is None


def test_kinds_reject_garbage():
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert kinds_from_tags("highway=residential") is None
    assert kinds_from_tags({"highway": 42}) is None
    assert kinds_from_tags({"natural": "wood"}) is None  # forest leg is livability's


# --- p113 -----------------------------------------------------------------


def test_heat_near_green_scores_top_with_honest_reason():
    v, reason = dim_heat(TALLINN, POIS)  # park ~100 m wins over forest ~200 m
    assert v == 95
    assert "hinnang" in reason and "mitte mõõdetud temperatuur" in reason


def test_heat_bands_and_far_fallback():
    assert dim_heat(TALLINN, [_poi("forest", 0.0036)])[0] == 65  # ~400 m
    assert dim_heat(TALLINN, [_poi("water", 0.008)])[0] == 50  # ~890 m
    v, reason = dim_heat(TALLINN, [_poi("school", 0.001)])
    assert v == 30
    assert "1,5 km" in reason


def test_heat_missing_inputs_stay_none():
    assert dim_heat(None, POIS)[0] is None
    assert dim_heat(TALLINN, None)[0] is None
    assert "puudub" in dim_heat(None, POIS)[1]


# --- p411 -----------------------------------------------------------------


def test_visibility_open_frontage_scores_high():
    v, reason = dim_visibility(TALLINN, [_poi("street", 0.0012)])  # ~133 m
    assert v == 75
    assert "hinnang" in reason


def test_visibility_distant_forest_does_not_penalise():
    v, reason = dim_visibility(TALLINN, POIS)  # street ~450 m + forest ~200 m
    assert v == 45  # base 45, forest at 200 m is outside the 150 m penalty
    assert "hinnang" in reason


def test_visibility_enclosed_penalty_applies():
    pois = [_poi("street", 0.0012), _poi("forest", 0.0008)]  # ~133 m + ~89 m
    v, reason = dim_visibility(TALLINN, pois)
    assert v == 65  # base 75 - 10
    assert "puude varjus" in reason


def test_visibility_remote_or_unmapped_is_low():
    v, reason = dim_visibility(TALLINN, [_poi("street", 0.0054)])  # ~600 m
    assert v == 25
    assert "hinnang" in reason
    v2, _ = dim_visibility(TALLINN, [_poi("school", 0.001)])
    assert v2 == 25


def test_visibility_missing_inputs_stay_none():
    assert dim_visibility(None, POIS)[0] is None
    assert dim_visibility(TALLINN, None)[0] is None
    assert "puudub" in dim_visibility(None, POIS)[1]


# --- registry + wiring ----------------------------------------------------


def test_score_group18b_keys_and_range():
    out = score_group18b(TALLINN, POIS)
    assert sorted(out) == ["heat", "visibility"]
    assert all(v is None or 0 <= v <= 100 for v in out.values())
    assert {k for k, _, _ in GROUP18B_DIMS} == set(out)
    assert score_group18b(None, None) == {k: None for k in out}


def test_fragment_lists_highway_ways():
    assert 'way["highway"]' in GROUP18B_OVERPASS_FRAGMENT
    assert "{lat}" in GROUP18B_OVERPASS_FRAGMENT and "{lon}" in GROUP18B_OVERPASS_FRAGMENT


def test_layer_meta_is_honest():
    assert "hinnang" in LAYER_META["heat"]["title"]
    assert "mitte mõõdetud temperatuur" in LAYER_META["heat"]["source"]
    assert "hinnang" in LAYER_META["visibility"]["title"]
    params = sorted(m["param"] for m in LAYER_META.values())
    assert params == [113, 411]


def test_module_exports_two_dims():
    assert len(GROUP18B_DIMS) == 2
    assert [pid for _, pid, _ in GROUP18B_DIMS] == ["p113", "p411"]
    assert g18c is not None
