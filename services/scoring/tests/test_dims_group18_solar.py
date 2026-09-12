"""Group 18 solar/shade/privacy dims (issue #123): hermetic scorer tests.

No network, no snapshot reads: scorers run on fixture POIs, the query
fragment is asserted as text, and tag mapping runs on static tag dicts.
Run: python3 -m pytest services/scoring/tests/test_dims_group18_solar.py -q
"""

import dims_group18_solar as gsol
from dims_group18_solar import (
    GROUP18_SOLAR_DIMS,
    GROUP18_SOLAR_OVERPASS_FRAGMENT,
    GROUP18_SOLAR_POI_KIND,
    LAYER_META,
    _bearing_deg,
    _levels,
    dim_privacy,
    dim_shade,
    dim_solar,
    dim_trespass,
    dim_winter_sun,
    kinds_from_tags,
    score_group18_solar,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


# ~50 m tall bldg, ~40 m tree south, ~150 m wood, ~30 m lamp, ~80 m lit way.
POIS = [
    _poi("sol_tall", 0.00045),
    _poi("sol_tree", -0.00036),
    _poi("sol_wood", 0.0012),
    _poi("sol_lamp", 0.00027),
    _poi("sol_lit", 0.00072),
    _poi("sol_bld", 0.002),
]


# --- tag mapping ----------------------------------------------------------


def test_kinds_building_levels_split():
    assert kinds_from_tags({"building": "yes", "building:levels": "5"}) == "sol_tall"
    assert kinds_from_tags({"building": "apartments", "building:levels": "4"}) == "sol_tall"
    assert kinds_from_tags({"building": "yes", "building:levels": "3;4"}) == "sol_bld"
    assert kinds_from_tags({"building": "house", "building:levels": "2"}) == "sol_bld"
    assert kinds_from_tags({"building": "yes"}) == "sol_bld"  # sparse levels: low
    assert kinds_from_tags({"building": "no"}) is None
    assert kinds_from_tags({"building": "no", "building:levels": "5"}) is None


def test_kinds_vegetation_lamps_lit():
    assert kinds_from_tags({"natural": "tree"}) == "sol_tree"
    assert kinds_from_tags({"natural": "wood"}) == "sol_wood"
    assert kinds_from_tags({"highway": "street_lamp"}) == "sol_lamp"
    assert kinds_from_tags({"highway": "residential", "lit": "yes"}) == "sol_lit"
    assert kinds_from_tags({"highway": "residential", "lit": "automatic"}) == "sol_lit"
    assert kinds_from_tags({"highway": "residential", "lit": "no"}) is None
    assert kinds_from_tags({"lit": "yes"}) is None  # no highway: not a corridor
    # One POI, one kind: masses read as mass, never as light.
    assert kinds_from_tags({"building": "yes", "building:levels": "6",
                            "lit": "yes"}) == "sol_tall"


def test_kinds_reject_garbage():
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert kinds_from_tags("building=yes") is None
    assert kinds_from_tags({"building": 42}) is None
    assert kinds_from_tags({"building:levels": "5"}) is None  # levels w/o building


def test_levels_parsing():
    assert _levels("5") == 5
    assert _levels("3;4") == 3
    assert _levels(" 6 ") == 6
    assert _levels("unknown") is None
    assert _levels("0") is None
    assert _levels("-2") is None
    assert _levels(5) is None
    assert _levels(None) is None


def test_bearing_south_is_180():
    south = _bearing_deg(TALLINN, TALLINN[0] - 0.001, TALLINN[1])
    north = _bearing_deg(TALLINN, TALLINN[0] + 0.001, TALLINN[1])
    assert abs(south - 180.0) < 0.5
    assert north < 0.5 or north > 359.5


# --- p253 -----------------------------------------------------------------


def test_shade_absent_is_low_with_honest_reason():
    v, reason = dim_shade(TALLINN, [_poi("sol_lamp", 0.001)])
    assert v == 25
    assert "hinnang" in reason and "mitte mõõdetud vari" in reason


def test_shade_density_bands_capped():
    assert dim_shade(TALLINN, [_poi("sol_tree", 0.001)])[0] == 55
    pois3 = [_poi("sol_tree", 0.0005 + i * 0.0002) for i in range(3)]
    assert dim_shade(TALLINN, pois3)[0] == 70
    pois8 = [_poi("sol_tall", 0.0002 + i * 0.0001) for i in range(8)]
    assert dim_shade(TALLINN, pois8)[0] == 80  # capped mild good
    v, reason = dim_shade(TALLINN, POIS)  # tall+tree+wood in 150 m
    assert v == 70
    assert "hinnang" in reason
    assert dim_shade(None, POIS)[0] is None
    assert dim_shade(TALLINN, None)[0] is None


# --- p443 -----------------------------------------------------------------


def test_winter_sun_open_south_scores_high():
    v, reason = dim_winter_sun(TALLINN, [_poi("sol_tall", 0.00045)])  # north only
    assert v == 85
    assert "hinnang" in reason and "mitte mõõdetud päikesetunnid" in reason


def test_winter_sun_north_obstruction_ignored_by_design():
    v, _ = dim_winter_sun(TALLINN, [_poi("sol_tall", 0.00018)])  # ~20 m north
    assert v == 85  # northern mass cannot block 7-deg noon sun


def test_winter_sun_south_bands():
    assert dim_winter_sun(TALLINN, [_poi("sol_tall", -0.00036)])[0] == 30  # ~40 m S
    assert dim_winter_sun(TALLINN, [_poi("sol_tree", -0.00135)])[0] == 60  # ~150 m S
    assert dim_winter_sun(TALLINN, [_poi("sol_tall", -0.0026)])[0] == 75  # ~290 m S
    v, reason = dim_winter_sun(TALLINN, POIS)  # tree ~40 m south wins
    assert v == 30
    assert "lõunakaare" in reason
    assert dim_winter_sun(TALLINN, None)[0] is None


# --- p64 ------------------------------------------------------------------


def test_solar_open_scores_high_with_honest_reason():
    v, reason = dim_solar(TALLINN, [_poi("sol_tree", 0.001)])
    assert v == 85
    assert "hinnang" in reason and "mitte mõõdetud kWh" in reason


def test_solar_tall_bands():
    assert dim_solar(TALLINN, [_poi("sol_tall", 0.00036)])[0] == 35  # ~40 m
    assert dim_solar(TALLINN, [_poi("sol_tall", 0.0008)])[0] == 50  # ~90 m
    assert dim_solar(TALLINN, [_poi("sol_tall", 0.0018)])[0] == 75  # ~200 m


def test_solar_dense_lowrise_caps_without_tall():
    pois = [_poi("sol_bld", 0.0001 + i * 0.00005) for i in range(4)]
    v, reason = dim_solar(TALLINN, pois)
    assert v == 70
    assert "kWh" in reason
    assert dim_solar(None, POIS)[0] is None


# --- p480 -----------------------------------------------------------------


def test_trespass_dark_scores_high():
    v, reason = dim_trespass(TALLINN, [_poi("sol_tree", 0.001)])
    assert v == 85
    assert "hinnang" in reason and "mitte mõõdetud luksid" in reason


def test_trespass_lamp_bands():
    assert dim_trespass(TALLINN, [_poi("sol_lamp", 0.0005)])[0] == 70
    pois3 = [_poi("sol_lamp", 0.0003 + i * 0.0002) for i in range(3)]
    assert dim_trespass(TALLINN, pois3)[0] == 55
    pois5 = [_poi("sol_lamp", 0.0002 + i * 0.0001) for i in range(5)]
    assert dim_trespass(TALLINN, pois5)[0] == 40


def test_trespass_lit_corridor_caps():
    v, reason = dim_trespass(TALLINN, POIS)  # 1 lamp + lit way ~80 m
    assert v == 60
    assert "valgustatud tee" in reason
    assert dim_trespass(TALLINN, None)[0] is None


# --- p40 ------------------------------------------------------------------


def test_privacy_rural_is_high():
    v, reason = dim_privacy(TALLINN, [_poi("sol_tree", 0.001)])
    assert v == 90
    assert "hinnang" in reason and "mitte mõõdetud vaateväljad" in reason


def test_privacy_bands():
    assert dim_privacy(TALLINN, [_poi("sol_bld", 0.00013)])[0] == 30  # ~15 m
    assert dim_privacy(TALLINN, [_poi("sol_bld", 0.0003)])[0] == 45  # ~33 m
    assert dim_privacy(TALLINN, [_poi("sol_bld", 0.0009)])[0] == 75  # ~100 m
    assert dim_privacy(TALLINN, [_poi("sol_bld", 0.0027)])[0] == 85  # ~300 m
    v, reason = dim_privacy(TALLINN, POIS)  # tall ~50 m
    assert v == 60
    assert "Lähim hoone" in reason
    assert dim_privacy(None, POIS)[0] is None


# --- registry + wiring ----------------------------------------------------


def test_score_group18_solar_keys_and_range():
    out = score_group18_solar(TALLINN, POIS)
    assert sorted(out) == ["privacy", "shade", "solar", "trespass", "winter_sun"]
    assert all(v is None or 0 <= v <= 100 for v in out.values())
    assert {k for k, _, _ in GROUP18_SOLAR_DIMS} == set(out)
    assert score_group18_solar(None, None) == {k: None for k in out}


def test_fragment_uses_node_and_way_per_pr118():
    for needle in ('node["building"]', 'way["building"]',
                   '"natural"="tree"', '"natural"="wood"',
                   '"highway"="street_lamp"', '"lit"'):
        assert needle in GROUP18_SOLAR_OVERPASS_FRAGMENT, needle
    # node-only would drop the 252k way buildings — both must be present.
    assert "node[" in GROUP18_SOLAR_OVERPASS_FRAGMENT
    assert "way[" in GROUP18_SOLAR_OVERPASS_FRAGMENT
    assert "{lat}" in GROUP18_SOLAR_OVERPASS_FRAGMENT
    assert "{lon}" in GROUP18_SOLAR_OVERPASS_FRAGMENT


def test_poi_kind_table_covers_points():
    table = dict(GROUP18_SOLAR_POI_KIND)
    assert table["natural"]["tree"] == "sol_tree"
    assert table["highway"]["street_lamp"] == "sol_lamp"


def test_layer_meta_is_honest():
    for key, meta in LAYER_META.items():
        assert "(hinnang)" in meta["title"], key
        assert "hinnang" in meta["source"], key
    params = sorted(m["param"] for m in LAYER_META.values())
    assert params == [40, 64, 253, 443, 480]
    assert "kWh" not in LAYER_META["solar"]["title"]
    assert "lux" not in LAYER_META["trespass"]["title"].lower()


def test_module_exports_five_dims():
    assert len(GROUP18_SOLAR_DIMS) == 5
    assert [pid for _, pid, _ in GROUP18_SOLAR_DIMS] == ["p253", "p443", "p64", "p480", "p40"]
    assert gsol is not None
