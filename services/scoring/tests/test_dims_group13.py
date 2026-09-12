"""Group 13 drone dims (issue #126): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture POIs, the query
fragment is asserted as text, and tag mapping runs on static tag dicts.
Run: python3 -m pytest services/scoring/tests/test_dims_group13.py -q
"""

import dims_group13 as g13
from dims_group13 import (
    GROUP13_DIMS,
    GROUP13_OVERPASS_FRAGMENT,
    GROUP13_POI_KIND,
    LAYER_META,
    dim_drone_clearance,
    dim_drone_viability,
    kinds_from_tags,
    score_group13,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~50 m aerodrome, ~800 m helipad, ~200 m park.
POIS = [
    _poi("aerodrome", 0.00045),
    _poi("helipad", 0.0072),
    _poi("park", 0.0018),
]


# --- tag mapping ----------------------------------------------------------


def test_kinds_airspace_sites():
    assert kinds_from_tags({"aeroway": "aerodrome"}) == "aerodrome"
    assert kinds_from_tags({"aeroway": "helipad"}) == "helipad"


def test_kinds_reject_garbage():
    assert kinds_from_tags({"aeroway": "runway"}) is None
    assert kinds_from_tags({"highway": "bus_stop"}) is None
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert kinds_from_tags("aeroway=aerodrome") is None


# --- p220 -----------------------------------------------------------------


def test_clearance_adjacent_airfield_scores_floor_with_honest_reason():
    v, reason = dim_drone_clearance(TALLINN, POIS)  # aerodrome ~50 m
    assert v == 20
    assert "hinnang" in reason and "mitte EANS DroneMap" in reason


def test_clearance_helipad_only_uses_same_bands():
    v, _ = dim_drone_clearance(TALLINN, [_poi("helipad", 0.0072)])  # ~800 m
    assert v == 40


def test_clearance_far_site_scores_high():
    v, _ = dim_drone_clearance(TALLINN, [_poi("aerodrome", 0.09)])  # ~10 km
    assert v == 90


def test_clearance_unmapped_is_weak_evidence_not_clear():
    v, reason = dim_drone_clearance(TALLINN, [_poi("park", 0.001)])
    assert v == 90
    assert "hinnang" in reason


def test_clearance_missing_inputs_stay_none():
    assert dim_drone_clearance(None, POIS)[0] is None
    assert dim_drone_clearance(TALLINN, None)[0] is None
    assert "puudub" in dim_drone_clearance(None, POIS)[1]


# --- p270 -----------------------------------------------------------------


def test_viability_blocked_by_airfield_despite_nearby_park():
    v, reason = dim_drone_viability(TALLINN, POIS)  # aero ~50 m + park ~200 m
    assert v == 30  # min(30, 80): the blocker binds, never averages away
    assert "hinnang" in reason and "mitte EANS DroneMap" in reason


def test_viability_clear_airspace_plus_open_yard_scores_top():
    pois = [_poi("aerodrome", 0.09), _poi("park", 0.0008)]  # 10 km + ~89 m
    v, _ = dim_drone_viability(TALLINN, pois)
    assert v == 95  # min(95, 100)


def test_viability_no_landing_space_caps_despite_clear_airspace():
    pois = [_poi("aerodrome", 0.09), _poi("school", 0.001)]
    v, reason = dim_drone_viability(TALLINN, pois)
    assert v == 25  # min(95, 25)
    assert "maandumisala" in reason


def test_viability_missing_inputs_stay_none():
    assert dim_drone_viability(None, POIS)[0] is None
    assert dim_drone_viability(TALLINN, None)[0] is None
    assert "puudub" in dim_drone_viability(None, POIS)[1]


# --- registry + wiring ----------------------------------------------------


def test_score_group13_keys_and_range():
    out = score_group13(TALLINN, POIS)
    assert sorted(out) == ["drone_clearance", "drone_viability"]
    assert all(v is None or 0 <= v <= 100 for v in out.values())
    assert {k for k, _, _ in GROUP13_DIMS} == set(out)
    assert score_group13(None, None) == {k: None for k in out}


def test_fragment_lists_aeroway_nwr_and_radius():
    assert '"aeroway"~"aerodrome|helipad"' in GROUP13_OVERPASS_FRAGMENT
    assert "node[" in GROUP13_OVERPASS_FRAGMENT
    assert "way[" in GROUP13_OVERPASS_FRAGMENT
    assert "{lat}" in GROUP13_OVERPASS_FRAGMENT and "{lon}" in GROUP13_OVERPASS_FRAGMENT


def test_poi_kind_table_covers_sites():
    aero = dict(GROUP13_POI_KIND)["aeroway"]
    assert aero["aerodrome"] == "aerodrome" and aero["helipad"] == "helipad"


def test_layer_meta_is_honest():
    for key in ("drone_clearance", "drone_viability"):
        assert "hinnang" in LAYER_META[key]["title"], key
        assert "mitte EANS DroneMap" in LAYER_META[key]["source"], key
    params = sorted(m["param"] for m in LAYER_META.values())
    assert params == [220, 270]


def test_module_exports_two_dims():
    assert len(GROUP13_DIMS) == 2
    assert [pid for _, pid, _ in GROUP13_DIMS] == ["p220", "p270"]
    assert g13 is not None
