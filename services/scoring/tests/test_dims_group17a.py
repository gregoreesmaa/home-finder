"""Group 17 municipal-services-A dims (issue #177): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group17a as g17a
from dims_group17a import (
    GROUP17A_DIMS,
    GROUP17A_OVERPASS_FRAGMENT,
    GROUP17A_PARAM_IDS,
    GROUP17A_POI_KIND,
    SERVICE_RADIUS_M,
    dim_binconceal,
    dim_compost,
    dim_gritbin,
    dim_leafdrop,
    dim_sched,
    kinds_from_tags,
    score_group17a,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m compost, ~220 m gritbin, ~330 m leafdrop, ~1.2 km compost.
POIS = [
    _poi("compostsite", 0.001),
    _poi("gritbin", 0.002),
    _poi("leafdrop", 0.003),
    _poi("compostsite", 0.011),
]


def test_compost_counts_serviced_pocket():
    pois = [_poi("compostsite", 0.001), _poi("compostsite", 0.002),
            _poi("compostsite", 0.003)]
    v, reason = dim_compost(TALLINN, pois)
    assert v == 80
    assert "hinnang" in reason
    v, _ = dim_compost(TALLINN, [_poi("compostsite", 0.001)])
    assert v == 65
    v, reason = dim_compost(TALLINN, [_poi("gritbin", 0.001)])
    assert v == 45
    assert "teadmata" in reason
    assert dim_compost(None, POIS)[0] is None
    assert dim_compost(TALLINN, None)[0] is None


def test_gritbin_counts_winter_service():
    pois = [_poi("gritbin", 0.001), _poi("gritbin", 0.002),
            _poi("gritbin", 0.003)]
    v, reason = dim_gritbin(TALLINN, pois)
    assert v == 80
    assert "hinnang" in reason
    v, _ = dim_gritbin(TALLINN, [_poi("gritbin", 0.001)])
    assert v == 65
    v, reason = dim_gritbin(TALLINN, [_poi("compostsite", 0.001)])
    assert v == 45
    assert "teadmata" in reason
    assert dim_gritbin(None, POIS)[0] is None
    assert dim_gritbin(TALLINN, None)[0] is None


def test_leafdrop_counts_collection():
    pois = [_poi("leafdrop", 0.001), _poi("leafdrop", 0.002),
            _poi("leafdrop", 0.003)]
    v, reason = dim_leafdrop(TALLINN, pois)
    assert v == 80
    assert "hinnang" in reason
    v, _ = dim_leafdrop(TALLINN, [_poi("leafdrop", 0.001)])
    assert v == 65
    v, reason = dim_leafdrop(TALLINN, [_poi("gritbin", 0.001)])
    assert v == 45
    assert "teadmata" in reason
    assert dim_leafdrop(None, POIS)[0] is None
    assert dim_leafdrop(TALLINN, None)[0] is None


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_sched, "kogumiskalender"),
                       (dim_binconceal, "varjesein")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"amenity": "grit_bin"}) == "gritbin"
    assert kinds_from_tags({"amenity": "recycling", "recycling_type": "centre",
                            "recycling:green_waste": "yes"}) == "compostsite"
    assert kinds_from_tags({"amenity": "recycling", "recycling_type": "centre",
                            "recycling:garden_waste": "yes"}) == "compostsite"
    assert kinds_from_tags({"amenity": "recycling",
                            "recycling:food_waste": "yes"}) == "compostsite"
    assert kinds_from_tags({"amenity": "recycling",
                            "recycling:organic": "yes"}) == "compostsite"
    assert kinds_from_tags({"amenity": "recycling",
                            "recycling:green_waste": "yes"}) == "leafdrop"
    assert kinds_from_tags({"amenity": "waste_disposal",
                            "recycling:green_waste": "yes"}) == "leafdrop"
    # Plain containers stay p54's; untagged litter bins stay out.
    assert kinds_from_tags({"amenity": "recycling"}) is None
    assert kinds_from_tags({"amenity": "recycling",
                            "recycling:paper": "yes"}) is None
    assert kinds_from_tags({"amenity": "waste_disposal"}) is None
    assert kinds_from_tags({"amenity": "recycling",
                            "recycling_type": "centre"}) is None
    assert kinds_from_tags({"shop": "supermarket"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "recycling" in GROUP17A_OVERPASS_FRAGMENT
    assert "waste_disposal" in GROUP17A_OVERPASS_FRAGMENT
    assert "grit_bin" in GROUP17A_OVERPASS_FRAGMENT
    assert "around:" in GROUP17A_OVERPASS_FRAGMENT
    # No road-class source: road class already scores inverted as p446.
    assert "highway" not in GROUP17A_OVERPASS_FRAGMENT
    assert len(GROUP17A_POI_KIND) == 1
    assert set(GROUP17A_DIMS) == {"sched", "compost", "gritbin",
                                  "leafdrop", "binconceal"}
    assert GROUP17A_PARAM_IDS == {"sched": 60, "compost": 187,
                                  "gritbin": 311, "leafdrop": 312,
                                  "binconceal": 347}
    assert SERVICE_RADIUS_M == 800.0


def test_score_group17a_rolls_up():
    dims, reasons = score_group17a(TALLINN, POIS)
    assert dims["compost"] == 65
    assert dims["gritbin"] == 65
    assert dims["leafdrop"] == 65
    assert dims["sched"] is None
    assert dims["binconceal"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 3
    assert g17a.GROUP17A_DIMS is GROUP17A_DIMS
