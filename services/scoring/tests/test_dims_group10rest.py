"""Group 10 utilities-rest dims (issue #171): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group10rest as g10r
from dims_group10rest import (
    GROUP10REST_DIMS,
    GROUP10REST_OVERPASS_FRAGMENT,
    GROUP10REST_PARAM_IDS,
    GROUP10REST_POI_KIND,
    SKYVIEW_HALF_M,
    dim_deadzone,
    dim_skyview,
    kinds_from_tags,
    score_group10rest,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m obstruction (~100*d/(d+150) = 42 on the raster; the dim
# band reads 50), ~450 m obstruction.
POIS = [
    _poi("skyobst", 0.001),
    _poi("skyobst", 0.004),
]


def test_skyview_near_obstruction_scores_low_with_honest_reason():
    v, reason = dim_skyview(TALLINN, POIS)
    assert v == 50
    assert "hinnang" in reason and "Starlink" in reason
    assert dim_skyview(None, POIS)[0] is None
    assert dim_skyview(TALLINN, None)[0] is None


def test_skyview_bands_track_raster_loosely():
    # <=75 m -> 35, <=150 m -> 50, <=300 m -> 70, beyond -> 85.
    v, _ = dim_skyview(TALLINN, [_poi("skyobst", 0.0005)])
    assert v == 35
    v, _ = dim_skyview(TALLINN, [_poi("skyobst", 0.0012)])
    assert v == 50
    v, _ = dim_skyview(TALLINN, [_poi("skyobst", 0.002)])
    assert v == 70
    v, reason = dim_skyview(TALLINN, [_poi("skyobst", 0.005)])
    assert v == 85
    assert "lage" in reason


def test_skyview_absence_is_calm():
    v, reason = dim_skyview(TALLINN, [_poi("commzone", 0.001)])
    assert v == 90
    assert "kaardistamata" in reason


def test_deadzone_stays_null_with_check():
    v, reason = dim_deadzone(TALLINN, POIS)
    assert v is None
    assert "kohapeal" in reason
    # NULL for EVERY input, including missing origin (never faked).
    assert dim_deadzone(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"building:levels": "5"}) == "skyobst"
    assert kinds_from_tags({"building": "apartments",
                            "building:levels": "9"}) == "skyobst"
    # A family house does not block the dish cone.
    assert kinds_from_tags({"building:levels": "4"}) is None
    # Guessing height would fake precision: level-less stays out.
    assert kinds_from_tags({"building": "apartments"}) is None
    assert kinds_from_tags({"building:levels": "tower"}) is None
    assert kinds_from_tags({"natural": "wood"}) == "skyobst"
    assert kinds_from_tags({"landuse": "forest"}) == "skyobst"
    # A tree row is not a canopy.
    assert kinds_from_tags({"natural": "tree_row"}) is None
    assert kinds_from_tags({"natural": "tree"}) is None
    assert kinds_from_tags({"shop": "mall"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "building" in GROUP10REST_OVERPASS_FRAGMENT
    assert "building:levels" in GROUP10REST_OVERPASS_FRAGMENT
    assert "wood" in GROUP10REST_OVERPASS_FRAGMENT
    assert "forest" in GROUP10REST_OVERPASS_FRAGMENT
    assert "around:" in GROUP10REST_OVERPASS_FRAGMENT
    assert len(GROUP10REST_POI_KIND) == 2
    assert set(GROUP10REST_DIMS) == {"skyview", "deadzone"}
    assert GROUP10REST_PARAM_IDS == {"skyview": 215, "deadzone": 491}
    assert SKYVIEW_HALF_M == 150.0


def test_score_group10rest_rolls_up():
    dims, reasons = score_group10rest(TALLINN, POIS)
    assert dims["skyview"] == 50
    assert dims["deadzone"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 1
    assert g10r.GROUP10REST_DIMS is GROUP10REST_DIMS
