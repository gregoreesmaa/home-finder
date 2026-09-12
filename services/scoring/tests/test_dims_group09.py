"""Hermetic unit tests for Group 9 noise-proxy dims (issue #104).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group09.py -q
"""

import math

import dims_group09 as G
from dims_group09 import (
    dim_braking,
    dim_lowfreq,
    dim_nuisance,
    dim_quiet_nature,
    dim_traffic,
    kinds_from_tags,
    score_group09,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_traffic, dim_quiet_nature, dim_nuisance, dim_lowfreq, dim_braking):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None


def test_traffic_bands():
    assert dim_traffic(TALLINN, [poi("major_road", 50)])[0] == 25
    assert dim_traffic(TALLINN, [poi("major_road", 150)])[0] == 45
    assert dim_traffic(TALLINN, [poi("major_road", 300)])[0] == 65
    assert dim_traffic(TALLINN, [poi("major_road", 900)])[0] == 80
    # Empty POI list: no mapped major within the fetch window -> quiet.
    assert dim_traffic(TALLINN, [])[0] == 85


def test_traffic_railway_counts():
    # Rail shares the traffic proxy (trains are traffic noise too).
    assert dim_traffic(TALLINN, [poi("railway", 50)])[0] == 25


def test_kinds_from_tags():
    assert kinds_from_tags({"highway": "motorway"}) == "major_road"
    assert kinds_from_tags({"highway": "tertiary"}) == "major_road"
    assert kinds_from_tags({"highway": "residential"}) is None
    assert kinds_from_tags({"railway": "rail"}) == "railway"
    assert kinds_from_tags({"railway": "level_crossing"}) == "brake_hotspot"
    assert kinds_from_tags({"highway": "traffic_signals"}) == "brake_hotspot"
    assert kinds_from_tags({"amenity": "bar"}) == "nightlife"
    assert kinds_from_tags({"amenity": "nightclub"}) == "nightlife"
    # Cinema is seated culture, not late-night nuisance.
    assert kinds_from_tags({"amenity": "cinema"}) is None
    assert kinds_from_tags({"landuse": "industrial"}) == "industrial"
    assert kinds_from_tags({"amenity": "school"}) is None


def test_quiet_nature_bonus():
    # Traffic at 500 m -> base 80; nature ramp +10*(1-d/600): 200 m -> +7.
    s, reason = dim_quiet_nature(
        TALLINN, [poi("major_road", 500), poi("forest", 200)])
    assert s == 87
    assert "200 m" in reason
    # Same traffic, nature far -> base only.
    s2, _ = dim_quiet_nature(TALLINN, [poi("major_road", 500)])
    assert s2 == 80
    # Adjacent nature rounds to the full +10: 85 + 10 = 95.
    s3, _ = dim_quiet_nature(TALLINN, [poi("forest", 10)])
    assert s3 == 95
    # Unmapped nature never punishes: traffic quietness stands alone.
    s4, _ = dim_quiet_nature(TALLINN, [poi("major_road", 900)])
    assert s4 == 80


def test_nuisance_bands():
    assert dim_nuisance(TALLINN, [poi("nightlife", 100)])[0] == 30
    assert dim_nuisance(TALLINN, [poi("industrial", 250)])[0] == 55
    assert dim_nuisance(TALLINN, [poi("nightlife", 500)])[0] == 75
    assert dim_nuisance(TALLINN, [])[0] == 85


def test_lowfreq_bands():
    assert dim_lowfreq(TALLINN, [poi("railway", 100)])[0] == 30
    assert dim_lowfreq(TALLINN, [poi("railway", 400)])[0] == 55
    assert dim_lowfreq(TALLINN, [poi("industrial", 900)])[0] == 75
    assert dim_lowfreq(TALLINN, [])[0] == 90


def test_braking_bands_and_base_kinds():
    # brake_hotspot (signals/crossings) + base-query kinds both count.
    assert dim_braking(TALLINN, [poi("brake_hotspot", 30)])[0] == 30
    assert dim_braking(TALLINN, [poi("bus_stop", 100)])[0] == 55
    assert dim_braking(TALLINN, [poi("rail_station", 250)])[0] == 75
    assert dim_braking(TALLINN, [])[0] == 90


def test_honesty_labels():
    # Load-bearing: proxies, never decibels. Every reason — including the
    # None paths — says proksi; none mentions dB/dBA.
    fns = (dim_traffic, dim_quiet_nature, dim_nuisance, dim_lowfreq, dim_braking)
    for fn in fns:
        for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                             (TALLINN, [poi("major_road", 120),
                                        poi("railway", 400),
                                        poi("nightlife", 200),
                                        poi("industrial", 700),
                                        poi("forest", 150),
                                        poi("bus_stop", 80)])):
            _, reason = fn(origin, pois)
            assert "proksi" in reason.lower(), (fn.__name__, reason)
            assert "dB" not in reason, (fn.__name__, reason)


def test_score_group09_registry():
    dims, reasons = score_group09(
        TALLINN, [poi("major_road", 500), poi("forest", 200)])
    assert set(dims) == {"traffic", "quiet_nature", "nuisance", "lowfreq", "braking"}
    assert set(G.GROUP09_PARAM_IDS.values()) == {16, 138, 162, 301, 493}
    assert len(reasons) == 5
    dims_none, reasons_none = score_group09(None, None)
    assert all(v is None for v in dims_none.values())
    assert reasons_none == []


def test_scores_within_bounds():
    # Sweep distances: every non-None score stays absolute 0..100.
    for d in (0, 10, 49, 50, 51, 300, 1000, 5000):
        pois = [poi("major_road", d), poi("railway", d), poi("nightlife", d),
                poi("industrial", d), poi("brake_hotspot", d),
                poi("forest", d), poi("bus_stop", d)]
        dims, _ = score_group09(TALLINN, pois)
        for v in dims.values():
            assert v is not None and 0 <= v <= 100
