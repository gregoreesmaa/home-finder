"""Group 5 plans-E dims (issue #165): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group05e as g05e
from dims_group05e import (
    GROUP05E_DIMS,
    GROUP05E_OVERPASS_FRAGMENT,
    GROUP05E_PARAM_IDS,
    GROUP05E_POI_KIND,
    EQUESTRIAN_RADIUS_M,
    dim_age55,
    dim_agrihood,
    dim_equestrian,
    dim_flyin,
    dim_multifam,
    kinds_from_tags,
    score_group05e,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# One riding campus ~110 m out, a second ~330 m out.
POIS = [
    _poi("riding", 0.001),
    _poi("riding", 0.003),
    _poi("commzone", 0.001),
]


def test_equestrian_counts_campuses_with_honest_reason():
    v, reason = dim_equestrian(TALLINN, POIS)
    assert v == 65
    assert "hinnang" in reason and "planeeringuotsust" in reason
    assert dim_equestrian(None, POIS)[0] is None
    assert dim_equestrian(TALLINN, None)[0] is None


def test_equestrian_pocket_and_desert():
    v, reason = dim_equestrian(TALLINN, POIS + [_poi("riding", 0.002)])
    assert v == 80
    assert "hea" in reason
    v, reason = dim_equestrian(TALLINN, [_poi("commzone", 0.001)])
    assert v == 45
    assert "teadmata" in reason


def test_no_map_dims_stay_null_with_buyer_check():
    for fn in (dim_multifam, dim_flyin, dim_age55, dim_agrihood):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        # NULL for every input, including missing origin (never fake).
        assert fn(None, POIS)[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None
    assert "planeeringute registrist" in dim_multifam(TALLINN, POIS)[1]
    assert "flightcorr" in dim_flyin(TALLINN, POIS)[1]
    assert "arendajalt" in dim_age55(TALLINN, POIS)[1]
    assert "gardens" in dim_agrihood(TALLINN, POIS)[1]


def test_kinds_from_tags_needs_the_sport_tag_for_pitches():
    assert kinds_from_tags({"leisure": "horse_riding"}) == "riding"
    assert kinds_from_tags({"sport": "equestrian"}) == "riding"
    assert kinds_from_tags({"leisure": "pitch", "sport": "equestrian"}) == "riding"
    assert kinds_from_tags({"highway": "bridleway"}) == "riding"
    assert kinds_from_tags({"building": "stable"}) == "riding"
    # A plain football pitch is not an arena.
    assert kinds_from_tags({"leisure": "pitch"}) is None
    assert kinds_from_tags({"leisure": "pitch", "sport": "soccer"}) is None
    assert kinds_from_tags({"building": "yes"}) is None
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None


def test_overpass_fragment_queries_centres_arenas_stables_trails():
    for line in (
        'node["leisure"="horse_riding"]',
        'node["sport"="equestrian"]',
        'node["highway"="bridleway"]',
        'node["building"="stable"]',
        'way["leisure"="horse_riding"]',
        'way["sport"="equestrian"]',
        'way["highway"="bridleway"]',
        'way["building"="stable"]',
    ):
        assert line in GROUP05E_OVERPASS_FRAGMENT
    # nwr/ parity: node-only would drop way-mapped arenas (PR #118).
    assert "way[" in GROUP05E_OVERPASS_FRAGMENT
    pairs = set()
    for key, mapping in GROUP05E_POI_KIND:
        pairs.update({(key, dst) for dst in mapping.values()})
    assert ("leisure", "riding") in pairs
    assert ("sport", "riding") in pairs


def test_registry_wiring():
    assert GROUP05E_PARAM_IDS == {
        "multifam": 365,
        "equestrian": 381,
        "flyin": 382,
        "age55": 384,
        "agrihood": 387,
    }
    assert set(GROUP05E_DIMS) == {
        "multifam", "equestrian", "flyin", "age55", "agrihood",
    }
    assert EQUESTRIAN_RADIUS_M == 800.0
    dims, reasons = score_group05e(TALLINN, POIS)
    assert dims["equestrian"] == 65
    assert dims["multifam"] is None
    assert dims["flyin"] is None
    assert dims["age55"] is None
    assert dims["agrihood"] is None
    # NULL dims contribute no reason; the proxy reason is honest.
    assert len(reasons) == 1 and "hinnang" in reasons[0]
    assert g05e.EQUESTRIAN_RADIUS_M == 800.0
