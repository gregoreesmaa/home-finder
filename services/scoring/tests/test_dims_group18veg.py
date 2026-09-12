"""Vegetation + street-ops dims (issue #122): hermetic scorer + wiring tests.

No network, no snapshot reads: scorers run on fixture POIs, the query
fragment is asserted as text, and tag mapping runs on static tag dicts.
Run: python3 -m pytest services/scoring/tests/test_dims_group18veg.py -q
"""

import dims_group18veg as veg
from dims_group18veg import (
    LAYER_META,
    VEG_DIMS,
    VEG_OVERPASS_FRAGMENT,
    VEG_POI_KIND,
    _parse_height,
    dim_leaf_burden,
    dim_mature_tree,
    dim_snowplow,
    dim_tree_roots,
    dim_trimming,
    kinds_from_tags,
    score_veg,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~50 m mature, ~120 m deciduous, ~100 m generic tree, ~200 m power line,
# ~70 m arterial, ~400 m local street.
POIS = [
    _poi("mature_tree", 0.00045),
    _poi("decid_tree", 0.0011),
    _poi("tree", 0.0009),
    _poi("power_line", 0.0018),
    _poi("plow_arterial", 0.00045, 0.0009),
    _poi("plow_local", 0.0036),
]


# --- tag mapping ----------------------------------------------------------


def test_kinds_maturity_signals():
    assert kinds_from_tags({"natural": "tree", "height": "12"}) == "mature_tree"
    assert kinds_from_tags({"natural": "tree", "height": "13 m"}) == "mature_tree"
    assert kinds_from_tags(
        {"natural": "tree", "height": "7"}) == "tree"  # below 8 m
    assert kinds_from_tags(
        {"natural": "tree", "circumference": "2.1"}) == "mature_tree"
    assert kinds_from_tags(
        {"natural": "tree", "diameter_crown": "9"}) == "mature_tree"
    assert kinds_from_tags(
        {"natural": "tree", "denotation": "avenue"}) == "mature_tree"
    assert kinds_from_tags(
        {"natural": "tree", "denotation": "urban"}) == "tree"
    assert kinds_from_tags({"natural": "tree"}) == "tree"


def test_kinds_deciduous_split():
    assert kinds_from_tags(
        {"natural": "tree", "leaf_type": "broadleaved"}) == "decid_tree"
    assert kinds_from_tags(
        {"natural": "tree", "leaf_type": "mixed"}) == "decid_tree"
    assert kinds_from_tags(
        {"natural": "tree", "leaf_cycle": "deciduous"}) == "decid_tree"
    assert kinds_from_tags(
        {"natural": "tree", "leaf_type": "needleleaved"}) == "tree"
    assert kinds_from_tags(
        {"natural": "tree", "leaf_cycle": "evergreen"}) == "tree"
    # Mature + shedding reads as its own kind (both scorers need it).
    assert kinds_from_tags(
        {"natural": "tree", "height": "14",
         "leaf_type": "broadleaved"}) == "mature_decid"
    assert kinds_from_tags(
        {"natural": "tree_row", "leaf_type": "broadleaved"}) == "decid_tree"
    assert kinds_from_tags({"natural": "tree_row"}) == "tree"
    assert kinds_from_tags({"natural": "wood"}) == "wood"


def test_kinds_power_and_plow_roads():
    assert kinds_from_tags({"power": "line"}) == "power_line"
    assert kinds_from_tags({"power": "minor_line"}) == "power_line"
    assert kinds_from_tags({"highway": "motorway"}) == "plow_arterial"
    assert kinds_from_tags({"highway": "trunk"}) == "plow_arterial"
    assert kinds_from_tags({"highway": "primary"}) == "plow_arterial"
    assert kinds_from_tags({"highway": "secondary"}) == "plow_arterial"
    assert kinds_from_tags({"highway": "tertiary"}) == "plow_local"
    assert kinds_from_tags({"highway": "residential"}) == "plow_local"
    assert kinds_from_tags({"highway": "unclassified"}) == "plow_local"
    assert kinds_from_tags({"highway": "living_street"}) == "plow_local"
    assert kinds_from_tags({"highway": "service"}) is None  # private plowing
    assert kinds_from_tags({"highway": "footway"}) is None


def test_kinds_priority_power_over_road():
    # One POI, one kind: a corridor way reads as power, never as road.
    assert kinds_from_tags({"power": "line", "highway": "service"}) == "power_line"


def test_kinds_reject_garbage():
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert kinds_from_tags("natural=tree") is None
    assert kinds_from_tags({"natural": 42}) is None
    assert kinds_from_tags({"natural": "tree", "height": 42}) == "tree"


def test_parse_height():
    assert _parse_height("12") == 12.0
    assert _parse_height("13 m") == 13.0
    assert _parse_height("10;12") == 10.0
    assert _parse_height("tundmatu") is None
    assert _parse_height(12) is None
    assert _parse_height("0") is None
    assert _parse_height(None) is None


# --- p65 ------------------------------------------------------------------


def test_mature_adjacent_caps_at_fall_zone():
    v, reason = dim_mature_tree(TALLINN, [_poi("mature_tree", 0.00018)])  # ~20 m
    assert v == 20
    assert "tormikahju" in reason


def test_mature_density_bands():
    assert dim_mature_tree(TALLINN, [_poi("mature_tree", 0.00135)])[0] == 60
    pois3 = [_poi("mature_tree", 0.001 + i * 0.0002) for i in range(3)]
    assert dim_mature_tree(TALLINN, pois3)[0] == 45
    pois6 = [_poi("mature_tree", 0.0005 + i * 0.0002) for i in range(6)]
    v, reason = dim_mature_tree(TALLINN, pois6)
    assert v == 30
    assert "hinnang" in reason


def test_mature_fallback_reads_generic_canopy():
    v, _ = dim_mature_tree(TALLINN, [_poi("tree", 0.0018)])  # ~200 m generic
    assert v == 70
    v, reason = dim_mature_tree(TALLINN, [_poi("plow_local", 0.001)])
    assert v == 85
    assert "kaardistus" in reason


def test_mature_missing_inputs_stay_none():
    assert dim_mature_tree(None, POIS)[0] is None
    assert dim_mature_tree(TALLINN, None)[0] is None
    assert "puudub" in dim_mature_tree(None, POIS)[1]


# --- p259 -----------------------------------------------------------------


def test_roots_bands_by_nearest_distance():
    assert dim_tree_roots(TALLINN, [_poi("tree", 0.00008)])[0] == 25  # ~9 m
    assert dim_tree_roots(TALLINN, [_poi("tree", 0.00017)])[0] == 45  # ~19 m
    assert dim_tree_roots(TALLINN, [_poi("tree", 0.0003)])[0] == 65  # ~33 m
    assert dim_tree_roots(TALLINN, [_poi("tree", 0.00045)])[0] == 80  # ~50 m
    assert dim_tree_roots(TALLINN, [_poi("tree", 0.0008)])[0] == 80  # ~89 m


def test_roots_far_or_absent_is_high():
    v, _ = dim_tree_roots(TALLINN, [_poi("tree", 0.00135)])  # ~150 m
    assert v == 90
    v, reason = dim_tree_roots(TALLINN, [_poi("plow_local", 0.001)])
    assert v == 90
    assert dim_tree_roots(TALLINN, None)[0] is None
    assert dim_tree_roots(None, POIS)[0] is None


def test_p65_vs_p259_are_distinct_halves():
    # Same single generic tree at ~150 m: p259 (100 m nearest half) clears
    # it, p65 (200 m density half with generic fallback) still notices it.
    pois = [_poi("tree", 0.00135)]
    assert dim_tree_roots(TALLINN, pois)[0] == 90
    assert dim_mature_tree(TALLINN, pois)[0] == 70
    # Same single mature at ~50 m: density half reads one crown (60),
    # root half reads beyond the root zone (80) — different reducers, both
    # tested, never aliased.
    pois_m = [_poi("mature_tree", 0.00045)]
    assert dim_mature_tree(TALLINN, pois_m)[0] == 60
    assert dim_tree_roots(TALLINN, pois_m)[0] == 80


# --- p395 -----------------------------------------------------------------


def test_leaf_deciduous_count_bands():
    assert dim_leaf_burden(TALLINN, [_poi("decid_tree", 0.0009)])[0] == 65
    pois3 = [_poi("decid_tree", 0.0005 + i * 0.0002) for i in range(3)]
    assert dim_leaf_burden(TALLINN, pois3)[0] == 50
    pois7 = [_poi("decid_tree", 0.0003 + i * 0.00015) for i in range(7)]
    v, reason = dim_leaf_burden(TALLINN, pois7)
    assert v == 30
    assert "hinnang" in reason


def test_leaf_unknown_leaf_type_is_moderate_not_worst():
    v, reason = dim_leaf_burden(TALLINN, [_poi("tree", 0.0009)])
    assert v == 65
    assert "lehetüüp" in reason


def test_leaf_absent_is_high():
    v, _ = dim_leaf_burden(TALLINN, [_poi("plow_local", 0.001)])
    assert v == 90
    assert dim_leaf_burden(TALLINN, None)[0] is None
    assert dim_leaf_burden(None, POIS)[0] is None


# --- p319 -----------------------------------------------------------------


def test_trimming_corridor_plus_trees_scores_exposure():
    v, reason = dim_trimming(TALLINN, POIS)  # line ~200 m + tree ~100 m
    assert v == 45
    assert "hinnang" in reason and "register puudub" in reason


def test_trimming_corridor_without_trees_is_moderate():
    v, reason = dim_trimming(TALLINN, [_poi("power_line", 0.0018)])
    assert v == 70
    assert "hinnang" in reason


def test_trimming_far_from_corridors_is_high():
    v, reason = dim_trimming(TALLINN, [_poi("tree", 0.0009)])
    assert v == 80
    assert "500 m" in reason
    assert dim_trimming(TALLINN, None)[0] is None
    assert dim_trimming(None, POIS)[0] is None


# --- p446 -----------------------------------------------------------------


def test_snowplow_arterial_berm_bands():
    v, reason = dim_snowplow(
        TALLINN, [_poi("plow_arterial", 0.00045)])  # ~50 m
    assert v == 40
    assert "hinnang" in reason
    v2, _ = dim_snowplow(TALLINN, [_poi("plow_arterial", 0.0018)])  # ~200 m
    assert v2 == 60


def test_snowplow_local_street_bands():
    v, reason = dim_snowplow(TALLINN, [_poi("plow_local", 0.0009)])  # ~100 m
    assert v == 75
    assert "hinnang" in reason
    v2, _ = dim_snowplow(TALLINN, [_poi("plow_local", 0.0036)])  # ~400 m
    assert v2 == 85


def test_snowplow_no_mapped_road_is_uncertain_mid():
    v, reason = dim_snowplow(TALLINN, [_poi("tree", 0.001)])
    assert v == 55
    assert "eratee" in reason
    assert dim_snowplow(TALLINN, None)[0] is None
    assert dim_snowplow(None, POIS)[0] is None


# --- registry + wiring ----------------------------------------------------


def test_registry_covers_all_five_params():
    assert [pid for _, pid, _ in VEG_DIMS] == ["p65", "p259", "p395", "p319", "p446"]
    out = score_veg(TALLINN, POIS)
    assert sorted(out) == ["leaf_burden", "mature_tree", "snowplow",
                           "tree_roots", "trimming"]
    assert all(v is None or 0 <= v <= 100 for v in out.values())
    assert out == {"mature_tree": 60, "tree_roots": 80, "leaf_burden": 65,
                   "trimming": 45, "snowplow": 40}


def test_scores_absolute_zero_to_100_unknown_stays_none():
    assert score_veg(None, None) == {k: None for k in
                                     ("mature_tree", "tree_roots",
                                      "leaf_burden", "trimming", "snowplow")}


def test_fragment_and_kind_table_cover_snapshot_tags():
    assert 'node["natural"="tree"]' in VEG_OVERPASS_FRAGMENT
    assert 'way["natural"~"tree|tree_row|wood"]' in VEG_OVERPASS_FRAGMENT
    assert 'way["power"~"line|minor_line"]' in VEG_OVERPASS_FRAGMENT
    assert "motorway|trunk|primary|secondary" in VEG_OVERPASS_FRAGMENT
    assert "tertiary|residential|unclassified" in VEG_OVERPASS_FRAGMENT
    keys = [k for k, _ in VEG_POI_KIND]
    assert keys == ["natural", "power", "highway"]
    # Extraction convention locked: nwr/ (PR #118), ways need centroids.
    assert "nwr/natural=tree" in veg.__doc__
    assert "nwr/power=line" in veg.__doc__
    assert "out center" in veg.__doc__


def test_layer_meta_marks_proxies_honestly():
    assert LAYER_META["trimming"]["param"] == 319
    assert LAYER_META["snowplow"]["param"] == 446
    for key in ("trimming", "snowplow"):
        meta = LAYER_META[key]
        assert "(hinnang)" in meta["title"]
        assert "hinnang" in meta["good"] and "hinnang" in meta["bad"]
        assert "hinnang" in meta["source"]
