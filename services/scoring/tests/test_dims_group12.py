"""Group 12 commute dim (issue #126): hermetic scorer + wiring tests.

No network, no snapshot reads: the scorer runs on fixture POIs, the GTFS
sidecar join runs on static dicts, the query fragment is asserted as text,
and tag mapping runs on static tag dicts.
Run: python3 -m pytest services/scoring/tests/test_dims_group12.py -q
"""

import dims_group12 as g12
from dims_group12 import (
    DFLT_DEPS,
    GROUP12_DIMS,
    GROUP12_OVERPASS_FRAGMENT,
    GROUP12_POI_KIND,
    LAYER_META,
    MINUTES_BANDS,
    dim_commute,
    estimate_minutes,
    kinds_from_tags,
    score_group12,
    stop_pois_from_counts,
)

TALLINN = (59.4372, 24.7536)


def _stop(dlat, deps, dlon=0.0):
    poi = {"kind": "stop_wday", "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}
    if deps != "omit":
        poi["deps"] = deps
    return poi


# --- tag mapping ----------------------------------------------------------


def test_kinds_stop_positions():
    assert kinds_from_tags({"highway": "bus_stop"}) == "stop_wday"
    assert kinds_from_tags({"public_transport": "platform"}) == "stop_wday"
    assert kinds_from_tags({"public_transport": "stop_position"}) == "stop_wday"


def test_kinds_reject_garbage():
    assert kinds_from_tags({"highway": "residential"}) is None
    assert kinds_from_tags({"aeroway": "helipad"}) is None
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert kinds_from_tags("highway=bus_stop") is None


# --- GTFS sidecar join ------------------------------------------------------


def test_sidecar_join_attaches_deps():
    coords = {"s1": (24.75, 59.44), "s2": (24.76, 59.45)}
    pois = stop_pois_from_counts(coords, {"s1": 530})
    by_lon = {p["lon"]: p for p in pois}
    assert by_lon[24.75]["deps"] == 530
    assert by_lon[24.75]["kind"] == "stop_wday"
    assert by_lon[24.76]["deps"] is None  # OSM-only position


# --- minutes model ----------------------------------------------------------


def test_estimate_minutes_walk_wait_ride():
    walk, wait, total = estimate_minutes(118, 530)
    assert abs(walk - 118 / 75.0) < 1e-9
    assert abs(wait - 540.0 / 530) < 1e-9
    assert abs(total - (walk + wait + 20.0)) < 1e-9


def test_estimate_minutes_wait_capped_and_defaulted():
    _, wait_tiny, _ = estimate_minutes(100, 8)  # 540/8 = 67.5 -> cap
    assert wait_tiny == 40.0
    _, wait_none, _ = estimate_minutes(100, None)
    assert abs(wait_none - 540.0 / DFLT_DEPS) < 1e-9
    _, wait_zero, _ = estimate_minutes(100, 0)
    assert abs(wait_zero - 540.0 / DFLT_DEPS) < 1e-9


def test_minutes_bands_cover_reachable_range():
    limits = [lim for lim, _ in MINUTES_BANDS]
    assert limits[-1] == float("inf")  # worst scored case ~80 min is banded
    assert MINUTES_BANDS[0] == (25, 100)


# --- p11 --------------------------------------------------------------------


def test_commute_balti_like_scores_top_with_honest_reason():
    v, reason = dim_commute(TALLINN, [_stop(0.00106, 530)])  # ~118 m, D=530
    assert v == 100
    assert "hinnang" in reason and "530" in reason


def test_commute_lasnamae_like_scores_mid():
    v, reason = dim_commute(TALLINN, [_stop(0.002, 40)])  # ~222 m, D=40
    assert v == 70  # walk 3.0 + wait 13.5 + ride 20 = ~36.5 min
    assert "hinnang" in reason


def test_commute_viimsi_like_scores_high():
    v, _ = dim_commute(TALLINN, [_stop(0.00098, 71)])  # ~109 m, D=71
    assert v == 85  # ~29 min


def test_commute_osm_only_stop_uses_flagged_default():
    v, reason = dim_commute(TALLINN, [_stop(0.0018, "omit")])  # ~200 m, no deps
    assert v == 70  # walk 2.7 + default wait 18 + ride 20 = ~41 min
    assert "sõiduplaanita" in reason


def test_commute_worst_window_scores_floor_not_zero():
    v, reason = dim_commute(TALLINN, [_stop(0.0134, 8)])  # ~1490 m, D=8
    assert v == 25  # walk 19.9 + capped wait 40 + 20 = ~80 min
    assert "hinnang" in reason


def test_commute_beyond_window_is_unknown_not_bad():
    v, reason = dim_commute(TALLINN, [_stop(0.02, 500)])  # ~2.2 km
    assert v is None
    assert "1,5 km" in reason


def test_commute_missing_inputs_stay_none():
    assert dim_commute(None, [_stop(0.001, 100)])[0] is None
    assert dim_commute(TALLINN, None)[0] is None
    assert "puudub" in dim_commute(None, [_stop(0.001, 100)])[1]


def test_commute_nearest_stop_wins():
    pois = [_stop(0.009, 974), _stop(0.00106, 530)]  # far frequent + near frequent
    v, _ = dim_commute(TALLINN, pois)
    assert v == 100


# --- registry + wiring ----------------------------------------------------


def test_score_group12_keys_and_range():
    out = score_group12(TALLINN, [_stop(0.00106, 530)])
    assert sorted(out) == ["commute"]
    assert all(v is None or 0 <= v <= 100 for v in out.values())
    assert {k for k, _, _ in GROUP12_DIMS} == set(out)
    assert score_group12(None, None) == {k: None for k in out}


def test_fragment_lists_stop_tags():
    assert '"highway"="bus_stop"' in GROUP12_OVERPASS_FRAGMENT
    assert '"public_transport"="platform"' in GROUP12_OVERPASS_FRAGMENT
    assert "{lat}" in GROUP12_OVERPASS_FRAGMENT and "{lon}" in GROUP12_OVERPASS_FRAGMENT


def test_poi_kind_table_covers_stops():
    highway = dict(GROUP12_POI_KIND)["highway"]
    assert highway["bus_stop"] == "stop_wday"
    pt = dict(GROUP12_POI_KIND)["public_transport"]
    assert pt["platform"] == "stop_wday" and pt["stop_position"] == "stop_wday"


def test_layer_meta_is_honest():
    assert "hinnang" in LAYER_META["commute"]["title"]
    assert "marsruutimata" in LAYER_META["commute"]["source"]
    assert LAYER_META["commute"]["param"] == 11


def test_module_exports_one_dim():
    assert len(GROUP12_DIMS) == 1
    assert [pid for _, pid, _ in GROUP12_DIMS] == ["p11"]
    assert g12 is not None
