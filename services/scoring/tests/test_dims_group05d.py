"""Group 5 plans-D dims (issue #164): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group05d as g05d
from dims_group05d import (
    GROUP05D_DIMS,
    GROUP05D_OVERPASS_FRAGMENT,
    GROUP05D_PARAM_IDS,
    GROUP05D_POI_KIND,
    STRSAT_HALF_M,
    dim_eminent_history,
    dim_heritage_trees,
    dim_nonconforming_cert,
    dim_preexisting_nonconforming,
    dim_strsat,
    kinds_from_tags,
    score_group05d,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m hotel bed, ~450 m apartment, ~80 m hostel.
POIS = [
    _poi("strstay", 0.001),
    _poi("strstay", 0.004),
    _poi("strstay", 0.0007),
]


def test_kinds_from_tags_routes_five_stay_values():
    for v in ("apartment", "guest_house", "hostel", "hotel", "motel"):
        assert kinds_from_tags({"tourism": v}) == "strstay"
    assert kinds_from_tags({"tourism": "hotel;apartments"}) == "strstay"
    # Foot traffic without beds carries no G05D signal.
    assert kinds_from_tags({"tourism": "restaurant"}) is None
    assert kinds_from_tags({"tourism": "museum"}) is None
    assert kinds_from_tags({"amenity": "bar"}) is None
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None


def test_overpass_fragment_queries_beds_node_and_way():
    assert "tourism" in GROUP05D_OVERPASS_FRAGMENT
    assert "apartment" in GROUP05D_OVERPASS_FRAGMENT
    assert "guest_house" in GROUP05D_OVERPASS_FRAGMENT
    assert "hostel" in GROUP05D_OVERPASS_FRAGMENT
    assert "hotel" in GROUP05D_OVERPASS_FRAGMENT
    assert "node[" in GROUP05D_OVERPASS_FRAGMENT
    assert "way[" in GROUP05D_OVERPASS_FRAGMENT
    assert "restaurant" not in GROUP05D_OVERPASS_FRAGMENT


def test_poi_kind_rows_cover_five_values():
    keys = dict(GROUP05D_POI_KIND)
    assert set(keys["tourism"]) == {"apartment", "guest_house",
                                    "hostel", "hotel", "motel"}
    assert set(keys["tourism"].values()) == {"strstay"}


def test_strsat_near_bed_scores_low_with_honest_reason():
    v, reason = dim_strsat(TALLINN, POIS)
    assert v == 25
    assert "hinnang" in reason and "Airbnb" in reason
    assert dim_strsat(None, POIS)[0] is None
    assert dim_strsat(TALLINN, None)[0] is None


def test_strsat_mid_distance_bands():
    # ~450 m apartment -> 55.
    v, _ = dim_strsat(TALLINN, [_poi("strstay", 0.004)])
    assert v == 55
    # ~1.2 km bed -> 85 with the thin-mapping caveat, never an all-clear.
    v, reason = dim_strsat(TALLINN, [_poi("strstay", 0.011)])
    assert v == 85


def test_strsat_absence_is_calm_with_caveat():
    v, reason = dim_strsat(TALLINN, [_poi("tallbuild", 0.001)])
    assert v == 85
    assert "kaardistamata" in reason


def test_no_map_stubs_always_none_with_buyer_check():
    for fn in (dim_heritage_trees, dim_nonconforming_cert,
               dim_preexisting_nonconforming, dim_eminent_history):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert len(reason) > 20
    assert "Keskkonnaamet" in dim_heritage_trees(TALLINN, POIS)[1]
    assert "sertifikaadi" in dim_nonconforming_cert(TALLINN, POIS)[1].lower()
    assert "Riigi Teataja" in dim_eminent_history(TALLINN, POIS)[1]


def test_registry_wiring():
    assert set(GROUP05D_DIMS) == {"heritage_trees", "strsat",
                                  "nonconforming_cert",
                                  "preexisting_nonconforming",
                                  "eminent_history"}
    assert GROUP05D_PARAM_IDS == {"heritage_trees": 226, "strsat": 230,
                                  "nonconforming_cert": 244,
                                  "preexisting_nonconforming": 275,
                                  "eminent_history": 280}
    assert STRSAT_HALF_M == 350.0
    dims, reasons = score_group05d(TALLINN, POIS)
    assert dims["strsat"] == 25
    assert dims["heritage_trees"] is None
    assert dims["nonconforming_cert"] is None
    assert dims["preexisting_nonconforming"] is None
    assert dims["eminent_history"] is None
    # None stubs contribute no reasons; the proxy reason survives.
    assert len(reasons) == 1 and "Airbnb" in reasons[0]
