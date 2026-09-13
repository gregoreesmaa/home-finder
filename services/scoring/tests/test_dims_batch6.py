"""Batch 6 leftover dims (issue #133): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture POIs, the query
fragment is asserted as text, and tag mapping runs on static tag dicts.
Run: python3 -m pytest services/scoring/tests/test_dims_batch6.py -q
"""

import dims_batch6 as b6
from dims_batch6 import (
    CAMPUS_KINDS,
    FAMILY_BANDS,
    GROUPB6_DIMS,
    GROUPB6_OVERPASS_FRAGMENT,
    GROUPB6_POI_KIND,
    RENT_HALF_M,
    dim_family_proximity,
    dim_rental_pressure,
    kinds_from_tags,
    score_batch6,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


def test_family_bands():
    # ~400 m -> 100; ~900 m -> 90; ~3 km -> 60; ~20 km -> 25.
    assert dim_family_proximity(TALLINN, [_poi("family", 0.0036)])[0] == 100
    assert dim_family_proximity(TALLINN, [_poi("family", 0.008)])[0] == 90
    assert dim_family_proximity(TALLINN, [_poi("family", 0.027)])[0] == 60
    assert dim_family_proximity(TALLINN, [_poi("family", 0.18)])[0] == 25


def test_family_nearest_wins_and_other_kinds_ignored():
    pois = [_poi("family", 0.05), _poi("family", 0.004),
            _poi("university", 0.0001)]
    s, reason = dim_family_proximity(TALLINN, pois)
    assert s == 100  # nearest family binds, campus kind ignored
    assert "hinnang" in reason


def test_family_missing_is_none_never_faked():
    s, _ = dim_family_proximity(TALLINN, [_poi("university", 0.001)])
    assert s is None  # no family POI -> unknown, not zero
    s, _ = dim_family_proximity(TALLINN, None)
    assert s is None
    s, _ = dim_family_proximity(None, [_poi("family", 0.001)])
    assert s is None


def test_rental_pressure_inverted_and_mirrors_map_half():
    assert RENT_HALF_M == 800.0  # == rentbleed map master half
    # On campus -> ~0; ~800 m -> 50; far -> high.
    assert dim_rental_pressure(TALLINN, [_poi("university", 0.0001)])[0] < 10
    assert dim_rental_pressure(TALLINN, [_poi("college", 0.0072)])[0] == 50
    s, reason = dim_rental_pressure(TALLINN, [_poi("dormitory", 0.09)])
    assert s > 85
    assert "hinnang" in reason and "EUR" not in reason
    assert "€" not in reason


def test_rental_pressure_dedupes_twins():
    p = _poi("university", 0.0072)
    twin = dict(p)
    s1, _ = dim_rental_pressure(TALLINN, [p])
    s2, _ = dim_rental_pressure(TALLINN, [p, twin])
    assert s1 == s2 == 50


def test_rental_pressure_no_campus_is_calm():
    s, _ = dim_rental_pressure(TALLINN, [_poi("school", 0.001)])
    assert s == 100
    s, _ = dim_rental_pressure(TALLINN, None)
    assert s is None


def test_kinds_from_tags_campus_only():
    assert kinds_from_tags({"amenity": "university"}) == "university"
    assert kinds_from_tags({"amenity": "college"}) == "college"
    assert kinds_from_tags({"building": "dormitory"}) == "dormitory"
    assert kinds_from_tags({"amenity": "dormitory"}) == "dormitory"
    assert kinds_from_tags({"amenity": "school"}) is None
    assert kinds_from_tags({"aeroway": "helipad"}) is None
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert CAMPUS_KINDS == {"university", "college", "dormitory"}


def test_overpass_fragment_uses_nwr():
    for line in GROUPB6_OVERPASS_FRAGMENT.strip().splitlines():
        assert line.strip().startswith(("node[", "way["))
    assert "university|college|dormitory" in GROUPB6_OVERPASS_FRAGMENT
    assert 'building"="dormitory' in GROUPB6_OVERPASS_FRAGMENT
    assert "family" not in GROUPB6_OVERPASS_FRAGMENT  # buyer input, never fetched
    assert GROUPB6_POI_KIND[0][0] == "amenity"


def test_registry_and_entry_point():
    assert [k for k, _, _ in GROUPB6_DIMS] == ["family_proximity", "rental_pressure"]
    assert [p for _, p, _ in GROUPB6_DIMS] == ["p17", "p386"]
    out = score_batch6(TALLINN, [_poi("family", 0.0036),
                                 _poi("university", 0.0072)])
    assert out == {"family_proximity": 100, "rental_pressure": 50}
    assert FAMILY_BANDS[-1] == (float("inf"), 25)


def test_module_imports_cleanly():
    assert callable(b6.score_batch6)
