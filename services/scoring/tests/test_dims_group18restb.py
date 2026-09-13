"""Group 18 rest-B dims (issue #173): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group18restb as g18b
from dims_group18restb import (
    DAYLIGHT_RADIUS_M,
    FISHBOWL_RADIUS_M,
    GROUP18B_DIMS,
    GROUP18B_OVERPASS_FRAGMENT,
    GROUP18B_PARAM_IDS,
    GROUP18B_POI_KIND,
    MOSSRISK_HALF_M,
    MOSSRISK_RADIUS_M,
    dim_daylight,
    dim_emshield,
    dim_fishbowl,
    dim_mossrisk,
    dim_patiosun,
    kinds_from_tags,
    score_group18restb,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~55 m corner furniture, ~78 m forest, ~111 m building, ~445 m forest.
POIS = [
    _poi("cornerfurn", 0.0005),
    _poi("forest", 0.0007),
    _poi("building", 0.001),
    _poi("forest", 0.004),
]


def test_daylight_open_counts_high_with_honest_reason():
    v, reason = dim_daylight(TALLINN, POIS)
    assert v == 90
    assert "hinnang" in reason and "avar" in reason
    assert dim_daylight(None, POIS)[0] is None
    assert dim_daylight(TALLINN, None)[0] is None


def test_daylight_dense_flags_shading_check():
    v, reason = dim_daylight(TALLINN, [_poi("building", 0.0002)] * 45)
    assert v == 60
    v, reason = dim_daylight(TALLINN, [_poi("building", 0.0002)] * 120)
    assert v == 30
    assert "varjutust" in reason
    assert "luks" in reason  # never a lux measurement


def test_fishbowl_near_furniture_scores_low_with_honest_reason():
    v, reason = dim_fishbowl(TALLINN, POIS)
    assert v == 30
    assert "hinnang" in reason and "privaatsust" in reason
    assert dim_fishbowl(None, POIS)[0] is None
    assert dim_fishbowl(TALLINN, None)[0] is None


def test_fishbowl_absence_is_calm_but_honest():
    v, reason = dim_fishbowl(TALLINN, [_poi("building", 0.001)])
    assert v == 80
    assert "kaardistamata" in reason
    # Mid-range furniture reads mid-scale (track the raster loosely).
    v, _ = dim_fishbowl(TALLINN, [_poi("cornerfurn", 0.003)])
    assert v == 70


def test_mossrisk_matches_raster_formula():
    # round(100*d/(d+250)): nearest stand ~78 m -> 24.
    v, reason = dim_mossrisk(TALLINN, POIS)
    assert v == 24
    assert "hinnang" in reason
    assert dim_mossrisk(None, POIS)[0] is None
    assert dim_mossrisk(TALLINN, None)[0] is None


def test_mossrisk_close_flags_roof_check():
    v, reason = dim_mossrisk(TALLINN, [_poi("forest", 0.0003)])
    assert v < 50
    assert "katuse" in reason
    assert "mõõtmine" in reason  # never a moisture reading


def test_mossrisk_absence_and_out_of_range_are_high():
    v, reason = dim_mossrisk(TALLINN, [_poi("building", 0.001)])
    assert v == 88
    assert "kaardistamata" in reason
    # A stand 1.1 km out sits past the 1 km search net: same high calm.
    v, _ = dim_mossrisk(TALLINN, [_poi("forest", 0.01)])
    assert v == 88


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_patiosun, "LoD2"),
                       (dim_emshield, "DEM")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"building": "yes"}) == "building"
    assert kinds_from_tags({"building": "apartments"}) == "building"
    assert kinds_from_tags({"building": "house"}) == "building"
    assert kinds_from_tags({"building": "no"}) is None  # not shade
    assert kinds_from_tags({"highway": "crossing"}) == "cornerfurn"
    assert kinds_from_tags({"highway": "traffic_signals"}) == "cornerfurn"
    assert kinds_from_tags({"junction": "yes"}) == "cornerfurn"
    assert kinds_from_tags({"highway": "residential"}) is None
    assert kinds_from_tags({"natural": "wood"}) == "forest"
    assert kinds_from_tags({"landuse": "forest"}) == "forest"
    # A street tree is not a moss stand (map excludes trees too).
    assert kinds_from_tags({"natural": "tree"}) is None
    assert kinds_from_tags({"natural": "scrub"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "building" in GROUP18B_OVERPASS_FRAGMENT
    assert "crossing" in GROUP18B_OVERPASS_FRAGMENT
    assert "wood" in GROUP18B_OVERPASS_FRAGMENT
    assert "forest" in GROUP18B_OVERPASS_FRAGMENT
    assert "around:" in GROUP18B_OVERPASS_FRAGMENT
    assert len(GROUP18B_POI_KIND) == 5
    assert set(GROUP18B_DIMS) == {"patiosun", "emshield",
                                  "daylight", "fishbowl", "mossrisk"}
    assert GROUP18B_PARAM_IDS == {"patiosun": 394, "emshield": 403,
                                  "daylight": 405, "fishbowl": 468,
                                  "mossrisk": 479}
    assert MOSSRISK_HALF_M == 250.0
    assert MOSSRISK_RADIUS_M == 1000.0
    assert DAYLIGHT_RADIUS_M == 300.0
    assert FISHBOWL_RADIUS_M == 400.0


def test_score_group18restb_rolls_up():
    dims, reasons = score_group18restb(TALLINN, POIS)
    assert dims["daylight"] == 90
    assert dims["fishbowl"] == 30
    assert dims["mossrisk"] == 24
    assert dims["patiosun"] is None
    assert dims["emshield"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 3
    assert g18b.GROUP18B_DIMS is GROUP18B_DIMS
