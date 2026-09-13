"""Group 5 plans-F dims (issue #166): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, and tag mapping runs on static tag dicts.
"""

import dims_group05f as g05f
from dims_group05f import (
    GROUP05F_DIMS,
    GROUP05F_OVERPASS_FRAGMENT,
    GROUP05F_PARAM_IDS,
    GROUP05F_POI_KIND,
    KEEP_AB_BUILDING,
    UPCYCLE_RADIUS_M,
    dim_darksky_community,
    dim_upcycle,
    kinds_from_tags,
    score_group05f,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~110 m, ~220 m, ~330 m derelict stock; ~1.2 km unrelated.
POIS = [
    _poi("derelict", 0.001),
    _poi("derelict", 0.002),
    _poi("derelict", 0.003),
    _poi("commzone", 0.011),
]


def test_upcycle_counts_reuse_pocket():
    v, reason = dim_upcycle(TALLINN, POIS)
    assert v == 80
    assert "hinnang" in reason
    assert "mahajäetud" in reason
    assert "KOV otsus" not in reason  # never a rezoning ruling
    v, _ = dim_upcycle(TALLINN, [_poi("derelict", 0.001)])
    assert v == 65
    v, reason = dim_upcycle(TALLINN, [_poi("commzone", 0.001)])
    assert v == 45
    assert "Stabiilne" in reason or "stabiilne" in reason
    assert dim_upcycle(None, POIS)[0] is None
    assert dim_upcycle(TALLINN, None)[0] is None


def test_registry_null_stays_null_with_check():
    v, reason = dim_darksky_community(TALLINN, POIS)
    assert v is None
    assert "IDA" in reason
    assert "p63" in reason
    # NULL for EVERY input, including missing origin (never faked).
    assert dim_darksky_community(None, None)[0] is None


def test_kinds_from_tags():
    assert kinds_from_tags({"abandoned": "yes", "building": "yes"}) == "derelict"
    assert kinds_from_tags({"abandoned": "yes", "building": "industrial"}) == "derelict"
    assert kinds_from_tags({"disused": "yes", "building": "yes"}) == "derelict"
    assert kinds_from_tags({"abandoned:building": "yes"}) == "derelict"
    assert kinds_from_tags({"abandoned:building": "garage"}) == "derelict"
    assert kinds_from_tags({"abandoned:building": "school"}) == "derelict"
    # A forest bunker is not rezoning stock — out even with lifecycle flags.
    assert kinds_from_tags({"building": "bunker", "abandoned": "yes"}) is None
    assert kinds_from_tags({"abandoned:building": "bunker"}) is None
    assert kinds_from_tags({"abandoned:building": "roof"}) is None
    assert kinds_from_tags({"abandoned:building": "level_crossing"}) is None
    # Stale flags: bare lifecycle keys without a building key stay out
    # (the ACTIVE ferry terminal carries disused=yes).
    assert kinds_from_tags({"disused": "yes"}) is None
    assert kinds_from_tags({"abandoned": "yes"}) is None
    # Infrastructure, not buildings; quarries/landfills score elsewhere.
    assert kinds_from_tags({"abandoned": "tunnel"}) is None
    assert kinds_from_tags({"abandoned:landuse": "quarry"}) is None
    assert kinds_from_tags({"landuse": "industrial"}) is None  # industprox's own
    assert kinds_from_tags({"landuse": "brownfield"}) is None  # brownsoil's own
    assert kinds_from_tags({}) is None


def test_fragment_and_registry_shape():
    assert "abandoned" in GROUP05F_OVERPASS_FRAGMENT
    assert "disused" in GROUP05F_OVERPASS_FRAGMENT
    assert "abandoned:building" in GROUP05F_OVERPASS_FRAGMENT
    assert "around:" in GROUP05F_OVERPASS_FRAGMENT
    assert "industrial" not in GROUP05F_OVERPASS_FRAGMENT
    assert "brownfield" not in GROUP05F_OVERPASS_FRAGMENT
    assert len(GROUP05F_POI_KIND) == 3
    assert set(GROUP05F_DIMS) == {"darksky_community", "upcycle"}
    assert GROUP05F_PARAM_IDS == {"darksky_community": 389, "upcycle": 485}
    assert UPCYCLE_RADIUS_M == 800.0
    assert "bunker" not in KEEP_AB_BUILDING


def test_score_group05f_rolls_up():
    dims, reasons = score_group05f(TALLINN, POIS)
    assert dims["upcycle"] == 80
    assert dims["darksky_community"] is None
    # NULL dims contribute no reasons (no fake evidence).
    assert len(reasons) == 1
    assert g05f.GROUP05F_DIMS is GROUP05F_DIMS
