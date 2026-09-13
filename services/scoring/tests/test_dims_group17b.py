"""Group 17 municipal-services-B dims (issue #178): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group17b as g17b
from dims_group17b import (
    GROUP17B_DIMS,
    GROUP17B_OVERPASS_FRAGMENT,
    GROUP17B_PARAM_IDS,
    GROUP17B_POI_KIND,
    LAWN_RADIUS_M,
    dim_lawncare,
    dim_shoveling,
    dim_sidewalk,
    dim_sweeping,
    kinds_from_tags,
    score_group17b,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m lawn, ~220 m lawn, ~330 m lawn, ~1.2 km lawn.
POIS = [
    _poi("lawn", 0.001),
    _poi("lawn", 0.002),
    _poi("lawn", 0.003),
    _poi("lawn", 0.011),
]


def test_lawncare_counts_upkeep_visible_pocket():
    # Density bands (half=20 map would saturate on viewshed bands:
    # real Tallinn listings see hundreds of lawns within 800 m).
    dense = [_poi("lawn", 0.001 + i * 0.00001) for i in range(600)]
    v, reason = dim_lawncare(TALLINN, dense)
    assert v == 85
    assert "hinnang" in reason
    mid = [_poi("lawn", 0.001 + i * 0.00001) for i in range(300)]
    v, _ = dim_lawncare(TALLINN, mid)
    assert v == 70
    v, _ = dim_lawncare(TALLINN, [_poi("lawn", 0.001)])
    assert v == 55
    v, reason = dim_lawncare(TALLINN, [_poi("park", 0.001)])
    assert v == 45
    assert "teadmata" in reason
    assert dim_lawncare(None, POIS)[0] is None
    assert dim_lawncare(TALLINN, None)[0] is None


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_sidewalk, "heakorra"),
                       (dim_sweeping, "puhastuskalender"),
                       (dim_shoveling, "gritbin")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "grass"}) == "lawn"
    assert kinds_from_tags({"landuse": "grass;meadow"}) == "lawn"
    # A meadow is not a mowing-duty lawn (and stays livability's park).
    assert kinds_from_tags({"landuse": "meadow"}) is None
    # Footways stay pedinfra's, never re-scored here.
    assert kinds_from_tags({"highway": "footway"}) is None
    assert kinds_from_tags({"footway": "sidewalk"}) is None
    assert kinds_from_tags({"leisure": "garden"}) is None
    assert kinds_from_tags({"amenity": "grit_bin"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "grass" in GROUP17B_OVERPASS_FRAGMENT
    assert "landuse" in GROUP17B_OVERPASS_FRAGMENT
    assert "around:" in GROUP17B_OVERPASS_FRAGMENT
    # No meadow source (unmown by design) and no footway source
    # (footway density already scores as pedinfra).
    assert "meadow" not in GROUP17B_OVERPASS_FRAGMENT
    assert "highway" not in GROUP17B_OVERPASS_FRAGMENT
    assert "footway" not in GROUP17B_OVERPASS_FRAGMENT
    assert len(GROUP17B_POI_KIND) == 1
    assert set(GROUP17B_DIMS) == {"sidewalk", "sweeping", "shoveling",
                                  "lawncare"}
    assert GROUP17B_PARAM_IDS == {"sidewalk": 463, "sweeping": 464,
                                  "shoveling": 465, "lawncare": 469}
    assert LAWN_RADIUS_M == 800.0


def test_score_group17b_rolls_up():
    dims, reasons = score_group17b(TALLINN, POIS)
    assert dims["lawncare"] == 55
    assert dims["sidewalk"] is None
    assert dims["sweeping"] is None
    assert dims["shoveling"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 1
    assert g17b.GROUP17B_DIMS is GROUP17B_DIMS
