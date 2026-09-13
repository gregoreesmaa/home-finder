"""Group 5 plans-C dims (issue #163): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group05c as g05c
from dims_group05c import (
    GROUP05C_DIMS,
    GROUP05C_OVERPASS_FRAGMENT,
    GROUP05C_PARAM_IDS,
    GROUP05C_POI_KIND,
    VIEWSHED_RADIUS_M,
    WINDSOLAR_HALF_M,
    dim_commbleed,
    dim_eminent,
    dim_flightreroute,
    dim_viewshed,
    dim_windsolar,
    kinds_from_tags,
    score_group05c,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m commercial, ~450 m farm, ~80 m farm, ~1.2 km commercial.
POIS = [
    _poi("commzone", 0.001),
    _poi("windfarm", 0.004),
    _poi("solarfarm", 0.0007),
    _poi("commzone", 0.011),
]


def test_commbleed_near_mall_scores_low_with_honest_reason():
    v, reason = dim_commbleed(TALLINN, POIS)
    assert v == 35
    assert "hinnang" in reason and "planeeringut" in reason
    assert dim_commbleed(None, POIS)[0] is None
    assert dim_commbleed(TALLINN, None)[0] is None


def test_commbleed_absence_is_calm():
    v, reason = dim_commbleed(TALLINN, [_poi("windfarm", 0.001)])
    assert v == 85
    assert "kaardistamata" in reason


def test_windsolar_matches_raster_formula():
    # round(100*d/(d+800)): nearest farm ~78 m -> 9.
    v, reason = dim_windsolar(TALLINN, POIS)
    assert v == 9
    assert "hinnang" in reason
    assert dim_windsolar(None, POIS)[0] is None
    assert dim_windsolar(TALLINN, None)[0] is None


def test_windsolar_close_flags_noise_check():
    v, reason = dim_windsolar(TALLINN, [_poi("windfarm", 0.0003)])
    assert v < 50
    assert "müra" in reason
    assert "register" not in reason  # never a production ruling


def test_windsolar_absence_is_high():
    v, reason = dim_windsolar(TALLINN, [_poi("commzone", 0.001)])
    assert v == 90
    assert "kaardistamata" in reason


def test_viewshed_counts_protection_pocket():
    pois = [_poi("viewpoint", 0.001), _poi("viewpoint", 0.002),
            _poi("viewpoint", 0.003)]
    v, reason = dim_viewshed(TALLINN, pois)
    assert v == 80
    assert "hinnang" in reason
    v, _ = dim_viewshed(TALLINN, [_poi("viewpoint", 0.001)])
    assert v == 65
    v, reason = dim_viewshed(TALLINN, [_poi("commzone", 0.001)])
    assert v == 45
    assert "teadmata" in reason
    assert dim_viewshed(None, POIS)[0] is None
    assert dim_viewshed(TALLINN, None)[0] is None


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_eminent, "sundvõõrandamis"),
                       (dim_flightreroute, "EANS")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "commercial"}) == "commzone"
    assert kinds_from_tags({"landuse": "retail"}) == "commzone"
    assert kinds_from_tags({"shop": "mall"}) == "commzone"
    assert kinds_from_tags({"shop": "supermarket"}) is None  # grocery's own
    assert kinds_from_tags({"power": "generator",
                            "generator:source": "wind"}) == "windfarm"
    assert kinds_from_tags({"power": "generator", "generator:source": "wind",
                            "location": "roof"}) == "windfarm"
    assert kinds_from_tags({"power": "generator", "generator:source": "solar",
                            "location": "ground"}) == "solarfarm"
    assert kinds_from_tags({"power": "generator", "generator:source": "solar",
                            "location": "surface"}) == "solarfarm"
    # A rooftop panel is not a farm; unknown location stays out too.
    assert kinds_from_tags({"power": "generator", "generator:source": "solar",
                            "location": "roof"}) is None
    assert kinds_from_tags({"power": "generator",
                            "generator:source": "solar"}) is None
    assert kinds_from_tags({"power": "generator",
                            "generator:source": "diesel"}) is None
    assert kinds_from_tags({"tourism": "viewpoint"}) == "viewpoint"
    assert kinds_from_tags({"tourism": "museum"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "commercial" in GROUP05C_OVERPASS_FRAGMENT
    assert "mall" in GROUP05C_OVERPASS_FRAGMENT
    assert "generator" in GROUP05C_OVERPASS_FRAGMENT
    assert "viewpoint" in GROUP05C_OVERPASS_FRAGMENT
    assert "around:" in GROUP05C_OVERPASS_FRAGMENT
    assert len(GROUP05C_POI_KIND) == 4
    assert set(GROUP05C_DIMS) == {"eminent", "flightreroute",
                                  "commbleed", "windsolar", "viewshed"}
    assert GROUP05C_PARAM_IDS == {"eminent": 221, "flightreroute": 222,
                                  "commbleed": 223, "windsolar": 224,
                                  "viewshed": 225}
    assert WINDSOLAR_HALF_M == 800.0
    assert VIEWSHED_RADIUS_M == 800.0


def test_score_group05c_rolls_up():
    dims, reasons = score_group05c(TALLINN, POIS)
    assert dims["commbleed"] == 35
    assert dims["windsolar"] == 9
    assert dims["viewshed"] == 45
    assert dims["eminent"] is None
    assert dims["flightreroute"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 3
    assert g05c.GROUP05C_DIMS is GROUP05C_DIMS
