"""Group 8 flood/climate dims, batch D (issue #170): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group08d as g08d
from dims_group08d import (
    GROUP08D_DIMS,
    GROUP08D_OVERPASS_FRAGMENT,
    GROUP08D_PARAM_IDS,
    GROUP08D_POI_KIND,
    VERNALPOOL_HALF_M,
    dim_floodcreep,
    dim_frost_heave,
    dim_saltwater,
    dim_vernalpool,
    kinds_from_tags,
    score_group08d,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m pond, ~450 m pond, ~2 km pond.
POIS = [
    _poi("vernalpool", 0.001),
    _poi("vernalpool", 0.004),
    _poi("vernalpool", 0.018),
]


def test_vernalpool_near_pond_scores_low_with_honest_reason():
    v, reason = dim_vernalpool(TALLINN, POIS)
    # round(100*111/(111+300)) = 27.
    assert v == 27
    assert "hinnang" in reason
    # Under 100 m the reason flags spring dampness/mosquitoes.
    v2, reason2 = dim_vernalpool(TALLINN, [_poi("vernalpool", 0.0005)])
    assert v2 < 27
    assert "liigniiskus" in reason2


def test_vernalpool_far_is_high():
    v, reason = dim_vernalpool(TALLINN, [_poi("vernalpool", 0.018)])
    assert v > 80
    assert "hinnang" in reason
    assert dim_vernalpool(None, POIS)[0] is None
    assert dim_vernalpool(TALLINN, None)[0] is None


def test_vernalpool_matches_raster_formula():
    # round(100*d/(d+300)): nearest pond ~445 m -> 60.
    v, _ = dim_vernalpool(TALLINN, [_poi("vernalpool", 0.004)])
    assert v == 60


def test_vernalpool_absence_is_near_clean():
    v, reason = dim_vernalpool(TALLINN, [_poi("shore", 0.001)])
    assert v == 95
    assert "kaardistamata" in reason
    assert "kaardistamata lompe" in reason  # unmapped pools may exist


def test_registry_nulls_stay_null_with_checks():
    for fn, needle in ((dim_frost_heave, "geotehniline"),
                       (dim_saltwater, "kaevuvee"),
                       (dim_floodcreep, "üleujutuskaart")):
        v, reason = fn(TALLINN, POIS)
        assert v is None
        assert needle in reason
        # NULL for EVERY input, including missing origin (never faked).
        assert fn(None, None)[0] is None


def test_kinds_from_tags_strict_ephemeral_only():
    assert kinds_from_tags({"natural": "water", "water": "pond",
                            "intermittent": "yes"}) == "vernalpool"
    assert kinds_from_tags({"natural": "water", "water": "basin",
                            "intermittent": "yes"}) == "vernalpool"
    # Permanent pond (no intermittent): not ephemeral.
    assert kinds_from_tags({"natural": "water", "water": "pond"}) is None
    assert kinds_from_tags({"natural": "water", "water": "lake",
                            "intermittent": "yes"}) is None
    # Intermittent flow features belong to p50 drainage, not p447.
    assert kinds_from_tags({"waterway": "ditch",
                            "intermittent": "yes"}) is None
    assert kinds_from_tags({"natural": "water", "water": "river",
                            "intermittent": "yes"}) is None
    # Wetlands stay p50/p257's, seasonal=* alone is tourism tagging.
    assert kinds_from_tags({"natural": "wetland",
                            "intermittent": "yes"}) is None
    assert kinds_from_tags({"natural": "water", "water": "pond",
                            "seasonal": "yes"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "intermittent" in GROUP08D_OVERPASS_FRAGMENT
    assert "pond|basin" in GROUP08D_OVERPASS_FRAGMENT
    assert "around:" in GROUP08D_OVERPASS_FRAGMENT
    assert len(GROUP08D_POI_KIND) == 1
    assert set(GROUP08D_DIMS) == {"frost_heave", "saltwater",
                                  "floodcreep", "vernalpool"}
    assert GROUP08D_PARAM_IDS == {"frost_heave": 377, "saltwater": 378,
                                  "floodcreep": 429, "vernalpool": 447}
    assert VERNALPOOL_HALF_M == 300.0


def test_score_group08d_rolls_up():
    dims, reasons = score_group08d(TALLINN, POIS)
    assert dims["vernalpool"] == 27
    assert dims["frost_heave"] is None
    assert dims["saltwater"] is None
    assert dims["floodcreep"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 1
    assert g08d.GROUP08D_DIMS is GROUP08D_DIMS
