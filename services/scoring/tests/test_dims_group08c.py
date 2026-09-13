"""Group 8 flood/climate dims, batch C (issue #169): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group08c as g08c
from dims_group08c import (
    GROUP08C_DIMS,
    GROUP08C_OVERPASS_FRAGMENT,
    GROUP08C_PARAM_IDS,
    GROUP08C_POI_KIND,
    SLIDEBUF_HALF_M,
    SURGEROAD_HALF_M,
    dim_burnscar,
    dim_buyout,
    dim_slidebuf,
    dim_surgeroad,
    kinds_from_tags,
    score_group08c,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m shore, ~450 m cliff, ~80 m cliff, ~1.2 km shore.
POIS = [
    _poi("shore", 0.001),
    _poi("cliff", 0.004),
    _poi("cliff", 0.0007),
    _poi("shore", 0.011),
]


def test_surgeroad_matches_raster_formula():
    # round(100*d/(d+150)): nearest shore ~111 m -> 43.
    v, reason = dim_surgeroad(TALLINN, POIS)
    assert v == 43
    assert "hinnang" in reason
    assert "üleujutuskaart" in reason  # never a flood map
    assert dim_surgeroad(None, POIS)[0] is None
    assert dim_surgeroad(TALLINN, None)[0] is None


def test_surgeroad_close_flags_street_check():
    v, reason = dim_surgeroad(TALLINN, [_poi("shore", 0.0003)])
    assert v < 50
    assert "läbitavust" in reason
    assert "üleujutatud" not in reason  # never a flood ruling


def test_surgeroad_absence_is_high():
    v, reason = dim_surgeroad(TALLINN, [_poi("cliff", 0.001)])
    assert v == 95
    assert "kaardistamata" in reason


def test_slidebuf_matches_raster_formula():
    # round(100*d/(d+100)): nearest cliff ~77 m -> 44.
    v, reason = dim_slidebuf(TALLINN, POIS)
    assert v == 44
    assert "hinnang" in reason
    assert dim_slidebuf(None, POIS)[0] is None
    assert dim_slidebuf(TALLINN, None)[0] is None


def test_slidebuf_close_flags_geology_check():
    v, reason = dim_slidebuf(TALLINN, [_poi("cliff", 0.0003)])
    assert v < 50
    assert "ehitusgeoloogiat" in reason
    assert "keelatud" not in reason  # never a ruling


def test_slidebuf_absence_is_high():
    v, reason = dim_slidebuf(TALLINN, [_poi("shore", 0.001)])
    assert v == 90
    assert "kaardistamata" in reason


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_burnscar, "päästeamet"),
                       (dim_buyout, "kindlustus")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"natural": "cliff"}) == "cliff"
    assert kinds_from_tags({"natural": "earth_bank"}) == "cliff"
    assert kinds_from_tags({"natural": "coastline"}) == "shore"
    assert kinds_from_tags({"natural": "water"}) == "shore"
    # Ungated roads would invert inland: highway maps to None.
    assert kinds_from_tags({"highway": "residential"}) is None
    assert kinds_from_tags({"highway": "secondary"}) is None
    # Forest tracks are not streets; sales points are not history.
    assert kinds_from_tags({"highway": "track", "flood_prone": "yes"}) is None
    assert kinds_from_tags({"office": "insurance"}) is None
    assert kinds_from_tags({"natural": "burnt"}) is None
    assert kinds_from_tags({"waterway": "river"}) is None
    assert kinds_from_tags({"natural": "wetland"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "cliff" in GROUP08C_OVERPASS_FRAGMENT
    assert "earth_bank" in GROUP08C_OVERPASS_FRAGMENT
    assert "coastline" in GROUP08C_OVERPASS_FRAGMENT
    assert "highway" not in GROUP08C_OVERPASS_FRAGMENT
    assert "around:" in GROUP08C_OVERPASS_FRAGMENT
    assert len(GROUP08C_POI_KIND) == 1
    assert set(GROUP08C_DIMS) == {"surgeroad", "slidebuf",
                                  "burnscar", "buyout"}
    assert GROUP08C_PARAM_IDS == {"surgeroad": 334, "slidebuf": 336,
                                  "burnscar": 371, "buyout": 372}
    assert SURGEROAD_HALF_M == 150.0
    assert SLIDEBUF_HALF_M == 100.0


def test_score_group08c_rolls_up():
    dims, reasons = score_group08c(TALLINN, POIS)
    assert dims["surgeroad"] == 43
    assert dims["slidebuf"] == 44
    assert dims["burnscar"] is None
    assert dims["buyout"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 2
    assert g08c.GROUP08C_DIMS is GROUP08C_DIMS
