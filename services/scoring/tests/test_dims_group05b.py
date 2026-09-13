"""Group 5 plans-B dims (issue #162): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group05b as g05b
from dims_group05b import (
    GROUP05B_DIMS,
    GROUP05B_OVERPASS_FRAGMENT,
    GROUP05B_PARAM_IDS,
    GROUP05B_POI_KIND,
    dim_buildout,
    dim_darksky,
    dim_gardens,
    dim_graywater,
    dim_livestock,
    kinds_from_tags,
    score_group05b,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m garden, ~450 m build site, ~80 m build site, ~1.2 km garden.
POIS = [
    _poi("garden", 0.001),
    _poi("buildsite", 0.004),
    _poi("buildsite", 0.0007),
    _poi("garden", 0.011),
]


def test_gardens_near_site_scores_high_with_honest_reason():
    v, reason = dim_gardens(TALLINN, POIS)
    assert v == 85
    assert "hinnang" in reason and "kogukonnaaed" in reason
    assert dim_gardens(None, POIS)[0] is None
    assert dim_gardens(TALLINN, None)[0] is None


def test_gardens_far_flags_distance():
    v, reason = dim_gardens(TALLINN, [_poi("garden", 0.011)])
    assert v == 40
    assert "kaugel" in reason


def test_gardens_absence_is_weak():
    v, reason = dim_gardens(TALLINN, [_poi("buildsite", 0.001)])
    assert v == 25
    assert "kaardistamata" in reason


def test_buildout_near_site_scores_high_with_honest_reason():
    v, reason = dim_buildout(TALLINN, POIS)
    assert v == 85
    assert "hinnang" in reason and "tiheneb" in reason
    assert dim_buildout(None, POIS)[0] is None
    assert dim_buildout(TALLINN, None)[0] is None


def test_buildout_far_flags_built_out():
    v, reason = dim_buildout(TALLINN, [_poi("buildsite", 0.011)])
    assert v == 40
    assert "valmis" in reason


def test_buildout_absence_is_weak():
    v, reason = dim_buildout(TALLINN, [_poi("garden", 0.001)])
    assert v == 25
    assert "kaardistamata" in reason


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_livestock, "loomapidamiseeskiri"),
                       (dim_graywater, "ehitusmäärus"),
                       (dim_darksky, "p63")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "allotments"}) == "garden"
    assert kinds_from_tags({"leisure": "garden", "garden:type": "community"}) == "garden"
    assert kinds_from_tags({"leisure": "garden", "garden:style": "kitchen"}) == "garden"
    assert kinds_from_tags({"landuse": "construction"}) == "buildsite"
    # Private backyards are OUT (not growing opportunity)...
    assert kinds_from_tags({"leisure": "garden"}) is None
    assert kinds_from_tags({"leisure": "garden", "garden:type": "residential"}) is None
    # ...orchards stay p409 agrifield's (no re-skin)...
    assert kinds_from_tags({"landuse": "orchard"}) is None
    assert kinds_from_tags({"landuse": "farmland"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "garden" in GROUP05B_OVERPASS_FRAGMENT
    assert "allotments" in GROUP05B_OVERPASS_FRAGMENT
    assert "construction" in GROUP05B_OVERPASS_FRAGMENT
    assert "around:" in GROUP05B_OVERPASS_FRAGMENT
    assert len(GROUP05B_POI_KIND) == 2
    assert set(GROUP05B_DIMS) == {"gardens", "livestock", "buildout",
                                  "graywater", "darksky"}
    assert GROUP05B_PARAM_IDS == {"gardens": 106, "livestock": 107,
                                  "buildout": 146, "graywater": 186,
                                  "darksky": 188}


def test_score_group05b_rolls_up():
    dims, reasons = score_group05b(TALLINN, POIS)
    assert dims["gardens"] == 85
    assert dims["buildout"] == 85
    assert dims["livestock"] is None
    assert dims["graywater"] is None
    assert dims["darksky"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 2
    assert g05b.GROUP05B_DIMS is GROUP05B_DIMS
