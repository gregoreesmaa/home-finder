"""Group 10 utility-grid dims (issue #105): hermetic scorer + wiring tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group10 as g10
from dims_group10 import (
    GROUP10_DIMS,
    GROUP10_OVERPASS_FRAGMENT,
    GROUP10_POI_KIND,
    _max_volts,
    dim_emf,
    dim_hvline,
    dim_overhead,
    dim_signal,
    dim_substation,
    kinds_from_tags,
    score_group10,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~250 m mast, ~600 m substation, ~150 m pole, ~300 m HV line way-center.
POIS = [
    _poi("mast", 0.0022),
    _poi("substation", 0.0054),
    _poi("powerline", 0.0013),
    _poi("hvline", 0.0027),
]


def test_signal_near_mast_scores_top_with_honest_reason():
    v, reason = dim_signal(TALLINN, POIS)
    assert v == 100
    assert "mobiilimast" in reason and "mitte mõõdetud" in reason


def test_signal_absent_is_soft_floor_not_fail():
    v, reason = dim_signal(TALLINN, [p for p in POIS if p["kind"] != "mast"])
    assert v == 30
    assert "5 km" in reason


def test_signal_missing_inputs_stay_none():
    assert dim_signal(None, POIS)[0] is None
    assert dim_signal(TALLINN, None)[0] is None
    assert "puudub" in dim_signal(None, POIS)[1]


def test_emf_close_infra_scores_low_inverted():
    v, reason = dim_emf(TALLINN, POIS)  # pole ~150 m
    assert v == 45
    assert "mitte mõõdetud" in reason


def test_emf_boundary_and_absent():
    assert dim_emf(TALLINN, [_poi("substation", 0.0008)])[0] == 25  # ~89 m
    v, reason = dim_emf(TALLINN, [_poi("mast", 0.001)])  # masts excluded
    assert v == 100
    assert "pole" in reason or "liini" in reason
    assert dim_emf(None, POIS)[0] is None


def test_substation_proximity_is_good():
    v, reason = dim_substation(TALLINN, POIS)  # ~600 m
    assert v == 85
    assert "alajaam" in reason
    v2, _ = dim_substation(TALLINN, [_poi("powerline", 0.001)])
    assert v2 == 30  # lines alone do not count as substations
    assert dim_substation(TALLINN, None)[0] is None


def test_overhead_inverted_with_high_floor():
    v, reason = dim_overhead(TALLINN, POIS)  # pole ~150 m
    assert v == 45
    assert "tormihaavatavuse" in reason
    v2, r2 = dim_overhead(TALLINN, [_poi("mast", 0.001)])
    assert v2 == 90
    assert "pole" in r2 or "liini" in r2
    assert dim_overhead(None, POIS)[0] is None


def test_hvline_ignores_distribution():
    v, reason = dim_hvline(TALLINN, POIS)  # hv ~300 m
    assert v == 65
    assert "kõrgepingeliin" in reason
    v2, _ = dim_hvline(TALLINN, [p for p in POIS if p["kind"] != "hvline"])
    assert v2 == 100  # distribution line nearby is not transmission
    assert dim_hvline(TALLINN, None)[0] is None


def test_max_volts_parsing():
    assert _max_volts("110000") == 110000
    assert _max_volts("330000;110000") == 330000
    assert _max_volts("10000") == 10000
    assert _max_volts("110") == 110000  # bare kV style
    assert _max_volts("foo") is None
    assert _max_volts(None) is None


def test_kinds_from_tags_voltage_aware():
    assert kinds_from_tags({"man_made": "mast"}) == "mast"
    assert kinds_from_tags({"man_made": "tower"}) == "mast"
    assert kinds_from_tags({"man_made": "communications_tower"}) == "mast"
    assert kinds_from_tags({"power": "substation"}) == "substation"
    assert kinds_from_tags({"power": "tower"}) == "powerline"
    assert kinds_from_tags({"power": "pole"}) == "powerline"
    assert kinds_from_tags({"power": "minor_line"}) == "powerline"
    assert kinds_from_tags({"power": "line"}) == "powerline"  # untagged: generic
    assert kinds_from_tags({"power": "line", "voltage": "10000"}) == "powerline"
    assert kinds_from_tags({"power": "line", "voltage": "110000"}) == "hvline"
    assert kinds_from_tags({"power": "line", "voltage": "330000;110000"}) == "hvline"
    assert kinds_from_tags({"amenity": "school"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_kind_table_cover_verified_tags():
    for needle in ("man_made", "mast", "tower", "power", "substation",
                   "line", "minor_line", "around:5000", "{lat}", "{lon}"):
        assert needle in GROUP10_OVERPASS_FRAGMENT
    flat = {v for _, m in GROUP10_POI_KIND for v in m.values()}
    assert {"mast", "substation", "powerline"} <= flat


def test_score_group10_registry_and_aggregate():
    assert [pid for _, pid, _ in GROUP10_DIMS] == ["p52", "p135", "p211", "p214", "p404"]
    dims = score_group10(TALLINN, POIS)
    assert dims == {"signal": 100, "emf": 45, "substation": 85,
                    "overhead": 45, "hvline": 65}
    assert all(v is None for v in score_group10(None, None).values())
    assert set(dims) == {k for k, _, _ in GROUP10_DIMS}
    assert g10.HV_VOLTS == 110000
