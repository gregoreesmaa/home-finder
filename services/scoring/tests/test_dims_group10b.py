"""Group 10 utility dims batch B (issue #107): hermetic scorer + wiring tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group10b as g10b
from dims_group10b import (
    EMERGENCY_RADIUS_M,
    GROUP10B_DIMS,
    GROUP10B_OVERPASS_FRAGMENT,
    GROUP10B_POI_KIND,
    dim_emergency,
    dim_grid_reliability,
    dim_shadow,
    dim_solar,
    dim_underground,
    kinds_from_tags,
    score_group10b,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~600 m substation x2, ~500 m rooftop PV x3, ~2.7 km mast x2,
# ~700 m fire station, ~300 m buried cable.
POIS = [
    _poi("substation", 0.0054),
    _poi("substation", -0.0054),
    _poi("solargen", 0.0045),
    _poi("solargen", -0.0045),
    _poi("solargen", 0.0046, 0.001),
    _poi("mast", 0.024),
    _poi("mast", -0.024),
    _poi("emergency", 0.0063),
    _poi("ugutil", 0.0027),
]


def test_grid_reliability_counts_feeds_not_distance():
    v, reason = dim_grid_reliability(TALLINN, POIS)  # 2 substations
    assert v == 80
    assert "alajaamu" in reason and "mitte mõõdetud" in reason


def test_grid_reliability_absent_is_soft_floor():
    v, reason = dim_grid_reliability(TALLINN, [p for p in POIS if p["kind"] != "substation"])
    assert v == 35
    assert "3 km" in reason
    assert dim_grid_reliability(None, POIS)[0] is None
    assert dim_grid_reliability(TALLINN, None)[0] is None
    assert "puudub" in dim_grid_reliability(None, POIS)[1]


def test_solar_uptake_bands():
    v, reason = dim_solar(TALLINN, POIS)  # 3 solargen -> 80
    assert v == 80
    assert "päikesegeneraatoreid" in reason and "mitte mõõdetud" in reason
    v0, r0 = dim_solar(TALLINN, [p for p in POIS if p["kind"] != "solargen"])
    assert v0 == 45  # unmapped PV is normal, not a failure
    assert "pole" in r0
    assert dim_solar(TALLINN, None)[0] is None


def test_shadow_gap_bands_distinct_from_nearest():
    v, reason = dim_shadow(TALLINN, POIS)  # 2 masts in 5 km -> 80
    assert v == 80
    assert "mobiilimaste" in reason and "mitte mõõdetud" in reason
    v0, r0 = dim_shadow(TALLINN, [p for p in POIS if p["kind"] != "mast"])
    assert v0 == 25  # shadow zone floor
    assert "leviauk" in r0
    assert dim_shadow(None, POIS)[0] is None


def test_emergency_nearest_response_site():
    v, reason = dim_emergency(TALLINN, POIS)  # ~700 m -> 100
    assert v == 100
    assert "päästeteenistus" in reason and "mitte mõõdetud" in reason
    v2, _ = dim_emergency(TALLINN, [_poi("emergency", 0.02)])  # ~2.2 km -> 65
    assert v2 == 65
    v3, r3 = dim_emergency(TALLINN, [_poi("mast", 0.001)])
    assert v3 == 30  # masts are not response sites
    assert "5 km" in r3
    assert dim_emergency(TALLINN, None)[0] is None


def test_emergency_radius_constant_matches_reason():
    assert EMERGENCY_RADIUS_M == 5000.0


def test_underground_sparse_tier_neutral_absence():
    v, reason = dim_underground(TALLINN, POIS)  # 1 cable -> 75
    assert v == 75
    assert "maa-aluseid kaableid" in reason
    v0, r0 = dim_underground(TALLINN, [p for p in POIS if p["kind"] != "ugutil"])
    assert v0 == 55  # burial is rarely mapped; absence is neutral
    assert "kaardistamata" in r0
    v2, _ = dim_underground(TALLINN, [_poi("ugutil", 0.001), _poi("ugutil", -0.001)])
    assert v2 == 90
    assert dim_underground(None, POIS)[0] is None


def test_kinds_from_tags_solar_and_burial_aware():
    assert kinds_from_tags({"power": "substation"}) == "substation"
    assert kinds_from_tags({"man_made": "mast"}) == "mast"
    assert kinds_from_tags(
        {"power": "generator", "generator:source": "solar"}) == "solargen"
    assert kinds_from_tags(
        {"power": "generator", "generator:source": "diesel"}) == "generator"
    assert kinds_from_tags({"power": "generator"}) == "generator"
    assert kinds_from_tags({"power": "cable"}) == "ugutil"
    assert kinds_from_tags({"power": "line", "location": "underground"}) == "ugutil"
    # Buried substations stay substations (p56 feeds, not p476 cables).
    assert kinds_from_tags(
        {"power": "substation", "location": "underground"}) == "substation"
    assert kinds_from_tags({"amenity": "fire_station"}) == "emergency"
    assert kinds_from_tags({"amenity": "police"}) == "emergency"
    assert kinds_from_tags({"amenity": "hospital"}) == "emergency"
    assert kinds_from_tags({"emergency": "ambulance_station"}) == "emergency"
    # Equipment / non-response tags map to nothing.
    assert kinds_from_tags({"emergency": "fire_hydrant"}) is None
    assert kinds_from_tags({"emergency": "defibrillator"}) is None
    assert kinds_from_tags({"amenity": "clinic"}) is None
    assert kinds_from_tags({"amenity": "school"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_kind_table_cover_verified_tags():
    for needle in ("man_made", "mast", "power", "substation", "generator",
                   "cable", "fire_station", "police", "hospital",
                   "ambulance_station", "around:5000", "{lat}", "{lon}"):
        assert needle in GROUP10B_OVERPASS_FRAGMENT
    flat = {v for _, m in GROUP10B_POI_KIND for v in m.values()}
    assert {"mast", "substation", "generator", "ugutil", "emergency"} <= flat


def test_score_group10b_registry_and_aggregate():
    assert [pid for _, pid, _ in GROUP10B_DIMS] == ["p56", "p213", "p216", "p420", "p476"]
    dims = score_group10b(TALLINN, POIS)
    assert dims == {"gridrel": 80, "solar": 80, "shadow": 80,
                    "emergency": 100, "underground": 75}
    assert all(v is None for v in score_group10b(None, None).values())
    assert set(dims) == {k for k, _, _ in GROUP10B_DIMS}
    assert g10b.GRID_RADIUS_M == 3000.0
    assert g10b.SOLAR_RADIUS_M == 2000.0
    assert g10b.SHADOW_RADIUS_M == 5000.0
    assert g10b.UG_RADIUS_M == 1000.0
