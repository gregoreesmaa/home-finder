"""Group 17 HOA-rest dims (issue #196): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group17rest as g17r
from dims_group17rest import (
    GROUP17REST_DIMS,
    GROUP17REST_OVERPASS_FRAGMENT,
    GROUP17REST_PARAM_IDS,
    GROUP17REST_POI_KIND,
    PRIVROAD_HALF_M,
    dim_assessment,
    dim_hoarestrict,
    dim_initfee,
    dim_maintcost,
    dim_occupancy,
    dim_privroad,
    dim_rentalcap,
    dim_reserves,
    dim_sharedphrase,
    dim_submeter,
    dim_trashetiquette,
    dim_vehiclerestrict,
    kinds_from_tags,
    score_group17rest,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~78 m private road, ~450 m private road.
POIS = [
    _poi("privroad", 0.0007),
    _poi("privroad", 0.004),
]


def test_privroad_near_road_scores_low_with_honest_reason():
    v, reason = dim_privroad(TALLINN, POIS)
    assert v == 35
    assert "hinnang" in reason and "teehoolduslepingut" in reason
    assert dim_privroad(None, POIS)[0] is None
    assert dim_privroad(TALLINN, None)[0] is None


def test_privroad_absence_is_calm():
    v, reason = dim_privroad(TALLINN, [_poi("commzone", 0.001)])
    assert v == 85
    assert "kaardistamata" in reason


def test_privroad_far_road_is_calm_public_street():
    v, reason = dim_privroad(TALLINN, [_poi("privroad", 0.011)])
    assert v == 70
    assert "hinnang" in reason


def test_document_nulls_stay_null_with_checks():
    cases = (
        (dim_maintcost, "riregistrist"),
        (dim_hoarestrict, "hikiri"),
        (dim_reserves, "riregistrist"),
        (dim_vehiclerestrict, "KOV"),
        (dim_occupancy, "osakaal"),
        (dim_trashetiquette, "compost"),
        (dim_assessment, "riregistrist"),
        (dim_submeter, "süsteem"),
        (dim_sharedphrase, "kuulutus"),
        (dim_rentalcap, "hikiri"),
        (dim_initfee, "maks"),
    )
    assert len(cases) == 11
    for fn, needle in cases:
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"highway": "service",
                            "access": "private"}) == "privroad"
    assert kinds_from_tags({"highway": "track",
                            "access": "private"}) == "privroad"
    assert kinds_from_tags({"highway": "residential",
                            "access": "private"}) == "privroad"
    assert kinds_from_tags({"highway": "living_street",
                            "access": "private"}) == "privroad"
    assert kinds_from_tags({"highway": "unclassified",
                            "access": "private"}) == "privroad"
    # A private driveway is not an agreement road; a parking aisle
    # is not a road at all.
    assert kinds_from_tags({"highway": "service", "service": "driveway",
                            "access": "private"}) is None
    assert kinds_from_tags({"highway": "service", "service": "parking_aisle",
                            "access": "private"}) is None
    # Public streets carry no burden.
    assert kinds_from_tags({"highway": "service"}) is None
    assert kinds_from_tags({"highway": "residential"}) is None
    # A car park is not a road; a footway is not a maintained road.
    assert kinds_from_tags({"amenity": "parking",
                            "access": "private"}) is None
    assert kinds_from_tags({"highway": "footway",
                            "access": "private"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "private" in GROUP17REST_OVERPASS_FRAGMENT
    assert "service" in GROUP17REST_OVERPASS_FRAGMENT
    assert "residential" in GROUP17REST_OVERPASS_FRAGMENT
    assert "around:" in GROUP17REST_OVERPASS_FRAGMENT
    assert len(GROUP17REST_POI_KIND) == 1
    assert set(GROUP17REST_DIMS) == {"maintcost", "hoarestrict", "reserves",
                                     "vehiclerestrict", "occupancy",
                                     "trashetiquette", "privroad",
                                     "assessment", "submeter",
                                     "sharedphrase", "rentalcap", "initfee"}
    assert GROUP17REST_PARAM_IDS == {"maintcost": 4, "hoarestrict": 49,
                                     "reserves": 142, "vehiclerestrict": 145,
                                     "occupancy": 152, "trashetiquette": 167,
                                     "privroad": 245, "assessment": 246,
                                     "submeter": 247, "sharedphrase": 278,
                                     "rentalcap": 368, "initfee": 427}
    assert PRIVROAD_HALF_M == 200.0


def test_score_group17rest_rolls_up():
    dims, reasons = score_group17rest(TALLINN, POIS)
    assert dims["privroad"] == 35
    for key in ("maintcost", "hoarestrict", "reserves", "vehiclerestrict",
                "occupancy", "trashetiquette", "assessment", "submeter",
                "sharedphrase", "rentalcap", "initfee"):
        assert dims[key] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 1
    assert g17r.GROUP17REST_DIMS is GROUP17REST_DIMS
