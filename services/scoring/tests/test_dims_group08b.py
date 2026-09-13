"""Group 8 flood/climate-B dims (issue #168): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group08b as g08b
from dims_group08b import (
    GROUP08B_DIMS,
    GROUP08B_OVERPASS_FRAGMENT,
    GROUP08B_PARAM_IDS,
    GROUP08B_POI_KIND,
    SALTSPRAY_HALF_M,
    dim_drought,
    dim_saltspray,
    dim_winddir,
    dim_windtunnel,
    kinds_from_tags,
    score_group08b,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m tower, ~450 m sea, ~80 m sea, ~1.2 km tower.
POIS = [
    _poi("tallbuild", 0.001),
    _poi("seashore", 0.004),
    _poi("seashore", 0.0007),
    _poi("tallbuild", 0.011),
]


def test_windtunnel_near_tower_scores_low_with_honest_reason():
    v, reason = dim_windtunnel(TALLINN, POIS)
    assert v == 50
    assert "hinnang" in reason and "kanjoniefekt" in reason
    assert dim_windtunnel(None, POIS)[0] is None
    assert dim_windtunnel(TALLINN, None)[0] is None


def test_windtunnel_close_flags_canyon_check():
    v, reason = dim_windtunnel(TALLINN, [_poi("tallbuild", 0.0003)])
    assert v == 35
    assert "kanjoniefekt" in reason


def test_windtunnel_absence_is_calm():
    v, reason = dim_windtunnel(TALLINN, [_poi("seashore", 0.001)])
    assert v == 85
    assert "kaardistamata" in reason


def test_saltspray_matches_raster_formula():
    # round(100*d/(d+500)): nearest sea ~78 m -> 13.
    v, reason = dim_saltspray(TALLINN, POIS)
    assert v == 13
    assert "hinnang" in reason
    assert dim_saltspray(None, POIS)[0] is None
    assert dim_saltspray(TALLINN, None)[0] is None


def test_saltspray_close_flags_facade_check():
    v, reason = dim_saltspray(TALLINN, [_poi("seashore", 0.0003)])
    assert v < 50
    assert "soolakorrosioon" in reason
    assert "määr" not in reason  # never a corrosion-rate ruling


def test_saltspray_absence_is_high():
    v, reason = dim_saltspray(TALLINN, [_poi("tallbuild", 0.001)])
    assert v == 90
    assert "kaardistamata" in reason


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_drought, "mullakaart"),
                       (dim_winddir, "edelavool")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"building:levels": "5"}) == "tallbuild"
    assert kinds_from_tags({"building:levels": "9"}) == "tallbuild"
    assert kinds_from_tags({"building:levels": "5;4"}) == "tallbuild"
    assert kinds_from_tags({"building:levels": "4"}) is None
    assert kinds_from_tags({"building:levels": "2"}) is None
    assert kinds_from_tags({"building": "yes", "height": "30"}) is None
    assert kinds_from_tags({"natural": "coastline"}) == "seashore"
    assert kinds_from_tags({"natural": "water"}) is None
    assert kinds_from_tags({"waterway": "river"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "building:levels" in GROUP08B_OVERPASS_FRAGMENT
    assert "coastline" in GROUP08B_OVERPASS_FRAGMENT
    assert "around:" in GROUP08B_OVERPASS_FRAGMENT
    assert len(GROUP08B_POI_KIND) == 2
    assert set(GROUP08B_DIMS) == {"drought", "winddir",
                                  "windtunnel", "saltspray"}
    assert GROUP08B_PARAM_IDS == {"drought": 118, "winddir": 182,
                                  "windtunnel": 255, "saltspray": 333}
    assert SALTSPRAY_HALF_M == 500.0


def test_score_group08b_rolls_up():
    dims, reasons = score_group08b(TALLINN, POIS)
    assert dims["windtunnel"] == 50
    assert dims["saltspray"] == 13
    assert dims["drought"] is None
    assert dims["winddir"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 2
    assert g08b.GROUP08B_DIMS is GROUP08B_DIMS
