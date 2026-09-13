"""Group 3 cadastre waterfront dims, batch D (issue #154): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group03d as g03d
from dims_group03d import (
    GROUP03D_DIMS,
    GROUP03D_OVERPASS_FRAGMENT,
    GROUP03D_PARAM_IDS,
    GROUP03D_POI_KIND,
    SHOREDIST_HALF_M,
    dim_lake_level,
    dim_moorage,
    dim_recharge,
    dim_seawall,
    dim_shoredist,
    kinds_from_tags,
    score_group03d,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m moorage, ~450 m shore, ~80 m shore, ~1.2 km moorage.
POIS = [
    _poi("moorage", 0.001),
    _poi("shore", 0.004),
    _poi("shore", 0.0007),
    _poi("moorage", 0.011),
]


def test_moorage_near_marina_scores_high_with_honest_reason():
    v, reason = dim_moorage(TALLINN, POIS)
    assert v == 85
    assert "hinnang" in reason and "krundi-põhine" in reason


def test_moorage_far_is_low_with_permit_check():
    v, reason = dim_moorage(TALLINN, [_poi("moorage", 0.011)])
    assert v == 40
    assert "KOV" in reason
    assert dim_moorage(None, POIS)[0] is None
    assert dim_moorage(TALLINN, None)[0] is None


def test_moorage_absence_is_weak_low():
    v, reason = dim_moorage(TALLINN, [_poi("shore", 0.001)])
    assert v == 25
    assert "kaardistamata" in reason


def test_shoredist_matches_raster_formula():
    # round(100*d/(d+100)): nearest shore ~78 m -> 44.
    v, reason = dim_shoredist(TALLINN, POIS)
    assert v == 44
    assert "hinnang" in reason
    assert dim_shoredist(None, POIS)[0] is None
    assert dim_shoredist(TALLINN, None)[0] is None


def test_shoredist_close_flags_zone_check():
    v, reason = dim_shoredist(TALLINN, [_poi("shore", 0.0003)])
    assert v < 50
    assert "ehituskeeluvöönd" in reason
    assert "keelatud" not in reason  # never a legal ruling


def test_shoredist_absence_is_high():
    v, reason = dim_shoredist(TALLINN, [_poi("moorage", 0.001)])
    assert v == 90
    assert "kaardistamata" in reason


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_seawall, "inspektsioon"),
                       (dim_lake_level, "seire"),
                       (dim_recharge, "KOV")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"leisure": "marina"}) == "moorage"
    assert kinds_from_tags({"seamark:type": "mooring"}) == "moorage"
    assert kinds_from_tags({"seamark:type": "harbour"}) == "moorage"
    assert kinds_from_tags({"harbour": "yes"}) == "moorage"
    assert kinds_from_tags({"mooring": "yacht"}) == "moorage"
    assert kinds_from_tags({"mooring": "no"}) is None
    assert kinds_from_tags({"man_made": "pier"}) is None
    assert kinds_from_tags({"man_made": "breakwater"}) is None
    assert kinds_from_tags({"natural": "coastline"}) == "shore"
    assert kinds_from_tags({"natural": "water"}) == "shore"
    assert kinds_from_tags({"waterway": "river"}) is None
    assert kinds_from_tags({"natural": "wetland"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "marina" in GROUP03D_OVERPASS_FRAGMENT
    assert "coastline" in GROUP03D_OVERPASS_FRAGMENT
    assert "around:" in GROUP03D_OVERPASS_FRAGMENT
    assert len(GROUP03D_POI_KIND) == 5
    assert set(GROUP03D_DIMS) == {"seawall", "moorage", "lake_level",
                                  "recharge", "shoredist"}
    assert GROUP03D_PARAM_IDS == {"seawall": 331, "moorage": 332,
                                  "lake_level": 337, "recharge": 339,
                                  "shoredist": 340}
    assert SHOREDIST_HALF_M == 100.0


def test_score_group03d_rolls_up():
    dims, reasons = score_group03d(TALLINN, POIS)
    assert dims["moorage"] == 85
    assert dims["shoredist"] == 44
    assert dims["seawall"] is None
    assert dims["lake_level"] is None
    assert dims["recharge"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 2
    assert g03d.GROUP03D_DIMS is GROUP03D_DIMS
