"""Group 10 utility-registry dims, batch C (issue #121): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group10c as g10c
from dims_group10c import (
    GROUP10C_DIMS,
    GROUP10C_OVERPASS_FRAGMENT,
    GROUP10C_POI_KIND,
    dim_internet,
    dim_ota,
    dim_redundancy,
    dim_waste,
    dim_water,
    kinds_from_tags,
    score_group10c,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~245 m telecom, ~600 m waterpoint, ~145 m wastepoint, ~1 km broadcast,
# second telecom ~2 km (redundancy depth = 2).
POIS = [
    _poi("telecom", 0.0022),
    _poi("waterpoint", 0.0054),
    _poi("wastepoint", 0.0013),
    _poi("broadcast", 0.008),
    _poi("telecom", 0.018),
]


def test_internet_near_confirmed_mast_with_honest_reason():
    v, reason = dim_internet(TALLINN, POIS)
    assert v == 100
    assert "sidekasutusega mast" in reason and "mitte mõõdetud" in reason


def test_internet_ignores_generic_masts_and_absent_is_soft_floor():
    assert dim_internet(TALLINN, [_poi("mast", 0.001)])[0] == 35  # sibling kind
    v, reason = dim_internet(TALLINN, [p for p in POIS if p["kind"] != "telecom"])
    assert v == 35
    assert "TTJA" in reason or "KKIS" in reason


def test_internet_missing_inputs_stay_none():
    assert dim_internet(None, POIS)[0] is None
    assert dim_internet(TALLINN, None)[0] is None
    assert "puudub" in dim_internet(None, POIS)[1]


def test_water_near_point_scores_high_with_registry_gap_named():
    v, reason = dim_water(TALLINN, POIS)  # ~600 m
    assert v == 85
    assert "veepunkt" in reason and "veeallika" in reason


def test_water_absent_is_neutral_not_fail():
    v, reason = dim_water(TALLINN, [p for p in POIS if p["kind"] != "waterpoint"])
    assert v == 45
    assert "kraanivee" in reason
    assert dim_water(TALLINN, None)[0] is None
    assert dim_water(None, POIS)[0] is None


def test_waste_near_collection_point_scores_top():
    v, reason = dim_waste(TALLINN, POIS)  # ~145 m
    assert v == 100
    assert "jäätmekogumispunkt" in reason


def test_waste_ignores_litter_bins_and_absent_is_neutral():
    assert dim_waste(TALLINN, [_poi("wastepoint", 0.001)] + [_poi("waste_basket", 0.0005)])[0] == 100
    v, reason = dim_waste(TALLINN, [_poi("waste_basket", 0.0005)])
    assert v == 50  # baskets alone do not count as collection service
    assert "2 km" in reason
    assert dim_waste(None, POIS)[0] is None


def test_redundancy_counts_confirmed_telecom_only():
    v, reason = dim_redundancy(TALLINN, POIS)  # 2 telecom within 3 km
    assert v == 80
    assert "2" in reason and "mitte mõõdetud" in reason


def test_redundancy_absent_is_soft_floor():
    v, reason = dim_redundancy(TALLINN, [p for p in POIS if p["kind"] != "telecom"])
    assert v == 30
    assert "dubleerimise" in reason
    assert dim_redundancy(TALLINN, None)[0] is None
    assert dim_redundancy(None, POIS)[0] is None


def test_ota_near_broadcast_scores_top_with_honest_reason():
    v, reason = dim_ota(TALLINN, POIS)  # ~890 m
    assert v == 100
    assert "ringhäälingumast" in reason and "mitte mõõdetud" in reason


def test_ota_ignores_cellular_and_absent_is_soft_floor():
    assert dim_ota(TALLINN, [_poi("telecom", 0.001)])[0] == 60  # cellular excluded
    v, reason = dim_ota(TALLINN, [p for p in POIS if p["kind"] != "broadcast"])
    assert v == 60
    assert "30 km" in reason
    assert dim_ota(TALLINN, None)[0] is None


def test_ota_wide_bands_radio_horizon_order():
    # 1° latitude ≈ 111.2 km: 5/15/25/35 km north of the origin.
    assert dim_ota(TALLINN, [_poi("broadcast", 0.045)])[0] == 100
    assert dim_ota(TALLINN, [_poi("broadcast", 0.135)])[0] == 85
    assert dim_ota(TALLINN, [_poi("broadcast", 0.225)])[0] == 70
    v, reason = dim_ota(TALLINN, [_poi("broadcast", 0.315)])
    assert v == 60  # beyond radio-horizon-order radius: soft floor, not fail
    assert "mitte mõõdetud" in reason


def test_kinds_from_tags_telecom_broadcast_aware():
    assert kinds_from_tags({"man_made": "communications_tower"}) == "telecom"
    assert kinds_from_tags({"man_made": "mast", "tower:type": "communication"}) == "telecom"
    assert kinds_from_tags({"man_made": "tower", "tower:type": "communication"}) == "telecom"
    assert kinds_from_tags({"man_made": "mast"}) is None  # generic: sibling p52
    assert kinds_from_tags({"man_made": "tower"}) is None  # church/clock towers
    assert kinds_from_tags({"man_made": "antenna"}) == "broadcast"
    assert kinds_from_tags({"man_made": "mast", "communication:television": "yes"}) == "broadcast"
    assert kinds_from_tags({"man_made": "mast", "communication:radio": "yes"}) == "broadcast"
    # Aviation nav aids are not home broadcast, even as antennas.
    assert kinds_from_tags({"man_made": "antenna", "airmark": "beacon",
                            "beacon:type": "ILS"}) is None
    assert kinds_from_tags({"airmark": "beacon"}) is None
    assert kinds_from_tags({"man_made": "water_well"}) == "waterpoint"
    assert kinds_from_tags({"natural": "spring"}) == "waterpoint"
    assert kinds_from_tags({"amenity": "drinking_water"}) == "waterpoint"
    assert kinds_from_tags({"amenity": "waste_disposal"}) == "wastepoint"
    assert kinds_from_tags({"amenity": "recycling"}) == "wastepoint"
    assert kinds_from_tags({"amenity": "waste_basket"}) is None  # furniture, excluded
    assert kinds_from_tags({"man_made": "wastewater_plant"}) is None  # disamenity, excluded
    assert kinds_from_tags({"amenity": "school"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_covers_verified_tags_both_geometries():
    for needle in ("man_made", "mast", "tower", "communications_tower", "antenna",
                   "tower:type", "water_well", "spring", "drinking_water",
                   "waste_disposal", "recycling", "communication:radio",
                   "communication:television", "around:5000", "{lat}", "{lon}",
                   "node[", "way["):
        assert needle in GROUP10C_OVERPASS_FRAGMENT
    flat = {v for _, m in GROUP10C_POI_KIND for v in m.values()}
    assert {"telecom", "broadcast", "waterpoint", "wastepoint"} <= flat


def test_score_group10c_registry_and_aggregate():
    assert [pid for _, pid, _ in GROUP10C_DIMS] == ["p51", "p53", "p54", "p262", "p265"]
    dims = score_group10c(TALLINN, POIS)
    assert dims == {"internet": 100, "water": 85, "waste": 100,
                    "redundancy": 80, "ota": 100}
    assert all(v is None for v in score_group10c(None, None).values())
    assert set(dims) == {k for k, _, _ in GROUP10C_DIMS}
    assert g10c.INTERNET_RADIUS_M == 5000.0
    assert g10c.OTA_RADIUS_M == 30000.0
