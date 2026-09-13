"""Group 18 rest-A dims (issue #172): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group18resta as g18a
from dims_group18resta import (
    DAYOPEN_HALF_M,
    GLASSGLARE_HALF_M,
    GROUP18A_DIMS,
    GROUP18A_OVERPASS_FRAGMENT,
    GROUP18A_PARAM_IDS,
    GROUP18A_POI_KIND,
    dim_crossvent,
    dim_dayopen,
    dim_driveway,
    dim_glassglare,
    dim_zoomlight,
    kinds_from_tags,
    score_group18resta,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~111 m tall mass, ~445 m glass facade, ~33 m glass facade.
POIS = [
    _poi("tallmass", 0.001),
    _poi("glassface", 0.004),
    _poi("glassface", 0.0003),
]


def test_dayopen_matches_raster_formula():
    # round(100*d/(d+150)): nearest tall mass ~111 m -> 43.
    v, reason = dim_dayopen(TALLINN, POIS)
    assert v == 43
    assert "hinnang" in reason
    assert "päikesetund" in reason  # never measured sun hours
    assert dim_dayopen(None, POIS)[0] is None
    assert dim_dayopen(TALLINN, None)[0] is None


def test_dayopen_close_flags_shading_check():
    v, reason = dim_dayopen(TALLINN, [_poi("tallmass", 0.0003)])
    assert v < 50
    assert "varjutust" in reason
    assert "päikesetunde mõõdetud pole" in reason


def test_dayopen_absence_is_open_sky():
    v, reason = dim_dayopen(TALLINN, [_poi("glassface", 0.001)])
    assert v == 90
    assert "kaardistamata" in reason


def test_glassglare_bands_are_calm_far():
    # Nearest facade ~33 m -> 35 with the low-sun glare check.
    v, reason = dim_glassglare(TALLINN, POIS)
    assert v == 35
    assert "hinnang" in reason
    assert "pimestust" in reason
    assert "luks" not in reason  # never a lux reading
    assert dim_glassglare(None, POIS)[0] is None
    assert dim_glassglare(TALLINN, None)[0] is None


def test_glassglare_mid_distance_is_half_calm():
    v, reason = dim_glassglare(TALLINN, [_poi("glassface", 0.001)])
    assert v == 50
    assert "pimestust" in reason


def test_glassglare_absence_is_glare_free():
    v, reason = dim_glassglare(TALLINN, [_poi("tallmass", 0.001)])
    assert v == 85
    assert "kaardistamata" in reason


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_crossvent, "korruseplaan"),
                       (dim_driveway, "kohapeal"),
                       (dim_zoomlight, "õhtusel")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"building:levels": "4"}) == "tallmass"
    assert kinds_from_tags({"building:levels": "9"}) == "tallmass"
    # Tall wins over glass: mass certainty beats orientation glare.
    assert kinds_from_tags({"building:levels": "5",
                            "building:material": "glass"}) == "tallmass"
    assert kinds_from_tags({"building:material": "glass"}) == "glassface"
    assert kinds_from_tags({"building:material": "mirror"}) == "glassface"
    # Low-rise glass still glares (mass and glare are separate facts).
    assert kinds_from_tags({"building:levels": "2",
                            "building:material": "glass"}) == "glassface"
    # Untagged reads low-rise, never tall; plaster never glares.
    assert kinds_from_tags({"building": "apartments"}) is None
    assert kinds_from_tags({"building:levels": "3"}) is None
    assert kinds_from_tags({"building:material": "plaster"}) is None
    assert kinds_from_tags({"building:material": "brick"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "building" in GROUP18A_OVERPASS_FRAGMENT
    assert "building:levels" in GROUP18A_OVERPASS_FRAGMENT
    assert "building:material" in GROUP18A_OVERPASS_FRAGMENT
    assert "glass" in GROUP18A_OVERPASS_FRAGMENT
    assert "around:" in GROUP18A_OVERPASS_FRAGMENT
    assert len(GROUP18A_POI_KIND) == 2
    assert set(GROUP18A_DIMS) == {"crossvent", "driveway", "zoomlight",
                                  "dayopen", "glassglare"}
    assert GROUP18A_PARAM_IDS == {"crossvent": 100, "driveway": 231,
                                  "zoomlight": 287, "dayopen": 34,
                                  "glassglare": 305}
    assert DAYOPEN_HALF_M == 150.0
    assert GLASSGLARE_HALF_M == 200.0


def test_score_group18resta_rolls_up():
    dims, reasons = score_group18resta(TALLINN, POIS)
    assert dims["dayopen"] == 43
    assert dims["glassglare"] == 35
    assert dims["crossvent"] is None
    assert dims["driveway"] is None
    assert dims["zoomlight"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 2
    assert g18a.GROUP18A_DIMS is GROUP18A_DIMS
