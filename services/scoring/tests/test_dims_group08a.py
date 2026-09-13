"""Group 8 flood/climate dims, batch A (issue #167): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group08a as g08a
from dims_group08a import (
    GROUP08A_DIMS,
    GROUP08A_OVERPASS_FRAGMENT,
    GROUP08A_PARAM_IDS,
    GROUP08A_POI_KIND,
    WILDFIRE_HALF_M,
    dim_envrisk,
    dim_floodhist,
    dim_searise,
    dim_wildfire,
    kinds_from_tags,
    score_group08a,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m fuel, ~78 m fuel.
POIS = [
    _poi("fuel", 0.001),
    _poi("fuel", 0.0007),
]


def test_wildfire_matches_raster_formula():
    # round(100*d/(d+100)): nearest fuel ~78 m -> 44.
    v, reason = dim_wildfire(TALLINN, POIS)
    assert v == 44
    assert "hinnang" in reason
    assert dim_wildfire(None, POIS)[0] is None
    assert dim_wildfire(TALLINN, None)[0] is None


def test_wildfire_close_flags_clearance_check():
    v, reason = dim_wildfire(TALLINN, [_poi("fuel", 0.0002)])
    assert v < 50
    assert "kaitseruum" in reason
    assert "ohutu" not in reason  # never a fire-service verdict
    assert "ohtlik" not in reason


def test_wildfire_absence_is_high():
    v, reason = dim_wildfire(TALLINN, [_poi("moorage", 0.001)])
    assert v == 90
    assert "kaardistamata" in reason


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_envrisk, "KOV"),
                       (dim_floodhist, "DEM"),
                       (dim_searise, "projektsioon")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "forest"}) == "fuel"
    assert kinds_from_tags({"natural": "wood"}) == "fuel"
    assert kinds_from_tags({"natural": "scrub"}) == "fuel"
    assert kinds_from_tags({"natural": "heath"}) == "fuel"
    assert kinds_from_tags({"landuse": "meadow"}) is None
    assert kinds_from_tags({"natural": "grassland"}) is None
    assert kinds_from_tags({"natural": "wetland"}) is None
    assert kinds_from_tags({"building:material": "wood"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "forest" in GROUP08A_OVERPASS_FRAGMENT
    assert "wood|scrub|heath" in GROUP08A_OVERPASS_FRAGMENT
    assert "around:" in GROUP08A_OVERPASS_FRAGMENT
    assert len(GROUP08A_POI_KIND) == 2
    assert set(GROUP08A_DIMS) == {"envrisk", "wildfire",
                                  "floodhist", "searise"}
    assert GROUP08A_PARAM_IDS == {"envrisk": 46, "wildfire": 69,
                                  "floodhist": 112, "searise": 117}
    assert WILDFIRE_HALF_M == 100.0


def test_score_group08a_rolls_up():
    dims, reasons = score_group08a(TALLINN, POIS)
    assert dims["wildfire"] == 44
    assert dims["envrisk"] is None
    assert dims["floodhist"] is None
    assert dims["searise"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 1
    assert g08a.GROUP08A_DIMS is GROUP08A_DIMS
