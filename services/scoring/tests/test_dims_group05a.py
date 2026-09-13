"""Group 5 plans-A dims (issue #161): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group05a as g05a
from dims_group05a import (
    GROUP05A_DIMS,
    GROUP05A_OVERPASS_FRAGMENT,
    GROUP05A_PARAM_IDS,
    GROUP05A_POI_KIND,
    dim_adapt,
    dim_ehitus,
    dim_korterstock,
    dim_rentrestr,
    dim_zoning,
    kinds_from_tags,
    score_group05a,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m site, ~220 m stock, ~1 km site.
POIS = [
    _poi("devsite", 0.001),
    _poi("apartstock", 0.002),
    _poi("devsite", 0.009),
]


def test_ehitus_near_site_scores_high_with_honest_reason():
    v, reason = dim_ehitus(TALLINN, POIS)
    assert v == 80
    assert "hinnang" in reason and "areneb" in reason
    assert dim_ehitus(None, POIS)[0] is None
    assert dim_ehitus(TALLINN, None)[0] is None


def test_ehitus_far_flags_register_check():
    v, reason = dim_ehitus(TALLINN, [_poi("devsite", 0.009)])
    assert v == 35  # ~1 km: inside the 2 km band, distant reason
    assert "kaugel" in reason
    assert "kehtestatud" not in reason  # never a plan ruling


def test_ehitus_absence_is_weak():
    v, reason = dim_ehitus(TALLINN, [_poi("apartstock", 0.001)])
    assert v == 30
    assert "kaardistamata" in reason


def test_korterstock_near_stock_scores_high_with_honest_reason():
    v, reason = dim_korterstock(TALLINN, POIS)
    assert v == 75
    assert "hinnang" in reason
    assert dim_korterstock(None, POIS)[0] is None
    assert dim_korterstock(TALLINN, None)[0] is None


def test_korterstock_close_scores_top():
    v, reason = dim_korterstock(TALLINN, [_poi("apartstock", 0.0003)])
    assert v == 85
    assert "likviidne" in reason


def test_korterstock_far_flags_no_euros():
    v, reason = dim_korterstock(TALLINN, [_poi("apartstock", 0.009)])
    assert v == 45
    assert "kaugel" in reason
    assert "euro" in reason  # euros never measured


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_adapt, "EHR"),
                       (dim_zoning, "PLANK"),
                       (dim_rentrestr, "KOV")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "construction"}) == "devsite"
    assert kinds_from_tags({"building": "construction"}) == "devsite"
    assert kinds_from_tags({"building": "apartments"}) == "apartstock"
    # Entrances / addresses never map (no multi-count on integration).
    assert kinds_from_tags({"entrance": "staircase"}) is None
    assert kinds_from_tags({"addr:housenumber": "1"}) is None
    # Student-pressure tags stay p386 rentbleed's (zero overlap).
    assert kinds_from_tags({"building": "dormitory"}) is None
    assert kinds_from_tags({"amenity": "university"}) is None
    assert kinds_from_tags({"landuse": "residential"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "construction" in GROUP05A_OVERPASS_FRAGMENT
    assert "apartments" in GROUP05A_OVERPASS_FRAGMENT
    assert "around:" in GROUP05A_OVERPASS_FRAGMENT
    assert len(GROUP05A_POI_KIND) == 2
    assert set(GROUP05A_DIMS) == {"adapt", "zoning", "rentrestr",
                                  "ehitus", "korterstock"}
    assert GROUP05A_PARAM_IDS == {"adapt": 45, "zoning": 47,
                                  "rentrestr": 74, "ehitus": 42,
                                  "korterstock": 44}


def test_score_group05a_rolls_up():
    dims, reasons = score_group05a(TALLINN, POIS)
    assert dims["ehitus"] == 80
    assert dims["korterstock"] == 75
    assert dims["adapt"] is None
    assert dims["zoning"] is None
    assert dims["rentrestr"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 2
    assert g05a.GROUP05A_DIMS is GROUP05A_DIMS
