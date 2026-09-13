"""P4 OSM demo + coverage dims (issues #280, #354): hermetic tests.

No network: scorers run on fixture POIs, the query fragment is asserted
as text, tag mapping runs on static tag dicts, and the module source is
asserted free of network imports (network lives in livability.fetch_pois).
"""

import inspect

import dims_p4_osm as p4o
from dims_p4_osm import (
    P4_OSM_DIMS,
    P4_OSM_OVERPASS_FRAGMENT,
    P4_OSM_POI_KIND,
    dim_activity,
    dim_arrival,
    dim_backyard_weather,
    dim_blackspots,
    dim_block_observer,
    dim_civic,
    dim_darkness,
    dim_delights,
    dim_fixit,
    dim_grocery,
    dim_herd,
    dim_horrors,
    dim_lastshop,
    dim_parking,
    dim_rats,
    dim_smell,
    dim_taxi,
    dim_thirdplace,
    dim_winter_maintenance,
    kinds_from_tags,
    score_p4_osm,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0, hours=None):
    poi = {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}
    if hours is not None:
        poi["hours"] = hours
    return poi


# ~55 m walkway, ~280 m sidewalk, ~560 m paved, ~1.1 km lit_area.
WALK_POIS = [
    _poi("walkway", 0.0005),
    _poi("sidewalk", 0.0025),
    _poi("paved", 0.005),
    _poi("lit_area", 0.010),
]

PROXY_FNS = [
    dim_block_observer, dim_blackspots, dim_parking, dim_grocery,
    dim_activity, dim_darkness, dim_arrival, dim_smell, dim_herd,
    dim_thirdplace, dim_taxi, dim_lastshop,
]

NULL_FNS = [
    dim_winter_maintenance, dim_fixit, dim_backyard_weather, dim_civic,
    dim_horrors, dim_delights, dim_rats,
]

EXPECTED_KEYS = [
    "block_observer", "blackspots", "parking", "winter", "fixit",
    "grocery", "backyard_weather", "activity", "darkness", "civic",
    "arrival", "smell", "herd", "thirdplace", "horrors", "delights",
    "taxi", "lastshop", "rats",
]

EXPECTED_PNUMS = [
    "P4-029", "P4-012", "P4-013", "P4-018", "P4-026", "P4-027", "P4-031",
    "P4-032", "P4-035", "P4-039", "P4-040", "P4-042", "P4-044", "P4-045",
    "P4-047", "P4-048", "P4-049", "P4-061", "P4-062",
]


def test_module_adds_no_network_calls():
    src = inspect.getsource(p4o)
    assert "httpx" not in src
    assert "urlopen" not in src
    assert "requests.get" not in src


def test_fragment_covers_demo_families_and_placeholders():
    for needle in (
            'node["highway"="crossing"]',
            'way["highway"~"footway|pedestrian"]',
            'way["sidewalk"',
            'way["surface"',
            '"traffic_calming"',
            '"amenity"="parking"',
            '"lit"~',
            '"cafe|bar|pub|restaurant|library"',
            '"atm|bank"',
            '"supermarket|convenience|greengrocer|general|bakery"',
            '"tourism"',
            '"craft"',
            '"leisure"="sauna"',
            'node["entrance"]',
            '"wheelchair"',
            'node["fixme"]',
    ):
        assert needle in P4_OSM_OVERPASS_FRAGMENT, needle
    assert "{lat}" in P4_OSM_OVERPASS_FRAGMENT
    assert "{lon}" in P4_OSM_OVERPASS_FRAGMENT


def test_poi_kind_rows_mint_only_new_kinds():
    table = dict(P4_OSM_POI_KIND)
    assert table["highway"] == {"footway": "walkway", "pedestrian": "walkway"}
    assert table["amenity"]["cafe"] == "thirdplace"
    assert table["amenity"]["atm"] == "money"
    assert table["shop"]["bakery"] == "bakery"
    assert table["shop"]["greengrocer"] == "grocery"
    assert table["tourism"]["museum"] == "culture"
    assert table["leisure"] == {"sauna": "thirdplace"}
    assert table["entrance"]["main"] == "entrance"
    assert table["wheelchair"]["yes"] == "stepfree"
    # Shared tags have NO row here (owned by sibling batches).
    assert "supermarket" not in table["shop"]
    assert "convenience" not in table["shop"]
    assert "parking" not in table["amenity"]
    assert "crossing" not in table["highway"]
    assert "yes" not in table.get("lit", {})


def test_kinds_from_tags_new_mappings():
    assert kinds_from_tags({"highway": "footway"}) == "walkway"
    assert kinds_from_tags({"highway": "pedestrian"}) == "walkway"
    assert kinds_from_tags({"footway": "sidewalk"}) == "walkway"
    assert kinds_from_tags({"sidewalk": "both"}) == "sidewalk"
    assert kinds_from_tags({"surface": "asphalt"}) == "paved"
    assert kinds_from_tags({"amenity": "cafe"}) == "thirdplace"
    assert kinds_from_tags({"amenity": "library"}) == "thirdplace"
    assert kinds_from_tags({"amenity": "bank"}) == "money"
    assert kinds_from_tags({"shop": "greengrocer"}) == "grocery"
    assert kinds_from_tags({"shop": "bakery"}) == "bakery"
    assert kinds_from_tags({"craft": "confectionery"}) == "bakery"
    assert kinds_from_tags({"tourism": "gallery"}) == "culture"
    assert kinds_from_tags({"leisure": "sauna"}) == "thirdplace"
    assert kinds_from_tags({"entrance": "main"}) == "entrance"
    assert kinds_from_tags({"wheelchair": "limited"}) == "stepfree"
    assert kinds_from_tags({"fixme": "check surface"}) == "fixme"
    assert kinds_from_tags({"amenity": "parking"}) == "lot_parking"
    assert kinds_from_tags({"amenity": "parking",
                            "parking": "surface"}) == "lot_parking"
    # Semicolon-split values read the first value.
    assert kinds_from_tags({"amenity": "cafe;bar"}) == "thirdplace"
    assert kinds_from_tags({"surface": "asphalt;concrete"}) == "paved"


def test_kinds_from_tags_shared_tags_stay_none():
    # Owned elsewhere: G18restb cornerfurn, G18 calming/street_parking/
    # lit_street, G18b lit_area, livability supermarket/convenience/pharmacy.
    assert kinds_from_tags({"highway": "crossing"}) is None
    assert kinds_from_tags({"traffic_calming": "bump"}) is None
    assert kinds_from_tags({"lit": "yes"}) is None
    assert kinds_from_tags({"shop": "supermarket"}) is None
    assert kinds_from_tags({"shop": "convenience"}) is None
    assert kinds_from_tags({"amenity": "pharmacy"}) is None
    assert kinds_from_tags({"amenity": "parking",
                            "parking": "street_side"}) is None
    assert kinds_from_tags({}) is None
    assert kinds_from_tags(None) is None
    assert kinds_from_tags({"building": "yes"}) is None


def test_open_late_heuristic():
    assert p4o._open_late("24/7") is True
    assert p4o._open_late("Mo-Su 08:00-23:00") is True
    assert p4o._open_late("Mo-Sa 09:00-21:00; Su 10:00-18:00") is True
    assert p4o._open_late("Mo-Sa 18:00-02:00") is True
    assert p4o._open_late("Mo-Fr 09:00-17:00") is False
    assert p4o._open_late(None) is None
    assert p4o._open_late("") is None
    assert p4o._open_late("unknown text") is None


def test_block_observer_bands_and_gap():
    v, reason = dim_block_observer(TALLINN, WALK_POIS)
    assert v == 85
    assert "hinnang" in reason and "Mapillary" in reason
    v, _ = dim_block_observer(TALLINN, [_poi("paved", 0.005)])  # ~560 m
    assert v == 50  # beyond 500 m radius -> coverage-gap fallback
    v, reason = dim_block_observer(TALLINN, [_poi("calming", 0.001)])
    assert v == 50
    assert "hinnangut ei ole" in reason
    assert dim_block_observer(None, WALK_POIS)[0] is None
    assert dim_block_observer(TALLINN, None)[0] is None


def test_blackspots_consumes_shared_kinds():
    v, reason = dim_blackspots(TALLINN, [_poi("cornerfurn", 0.001)])
    assert v == 80
    assert "hinnang" in reason and "mitte" in reason
    v, _ = dim_blackspots(TALLINN, [_poi("calming", 0.004)])  # ~450 m
    assert v == 62
    v, reason = dim_blackspots(TALLINN, [_poi("walkway", 0.001)])
    assert v == 50
    assert "Transpordiameti" in reason
    assert dim_blackspots(None, None)[0] is None


def test_parking_split_kinds():
    v, reason = dim_parking(TALLINN, [_poi("lot_parking", 0.001)])
    assert v == 80
    assert "hinnang" in reason and "garantii" in reason
    v, _ = dim_parking(TALLINN, [_poi("street_parking", 0.006)])  # ~670 m
    assert v == 62
    v, reason = dim_parking(TALLINN, [])
    assert v == 50
    assert "määrustikku" in reason
    assert dim_parking(TALLINN, None)[0] is None


def test_grocery_shared_kind_and_evening_variants():
    # Livability-canonical "supermarket" kind scores (hook-order proof).
    v, reason = dim_grocery(TALLINN, [_poi("supermarket", 0.002)])
    assert v == 85
    assert "lahtiolekuajad" in reason and "hinnang" in reason
    v, reason = dim_grocery(
        TALLINN, [_poi("grocery", 0.002, hours="Mo-Su 08:00-23:00")])
    assert v == 85
    assert "õhtune" in reason
    v, reason = dim_grocery(
        TALLINN, [_poi("grocery", 0.002, hours="Mo-Fr 09:00-17:00")])
    assert v == 85
    assert "enne 20" in reason
    v, reason = dim_grocery(TALLINN, [])
    assert v == 40
    assert "Barbora" in reason
    assert dim_grocery(None, [])[0] is None


def test_activity_labels_usage_not_safety():
    pois = [_poi("thirdplace", 0.001), _poi("bakery", 0.002),
            _poi("culture", 0.003)]
    v, reason = dim_activity(TALLINN, pois)
    assert v == 75
    assert "kasutus-hinnang" in reason
    assert "PPA" in reason
    v, reason = dim_activity(TALLINN, [])
    assert v == 40
    assert "mitte ohu-hinne" in reason
    v, reason = dim_activity(
        TALLINN, [_poi("thirdplace", 0.001, hours="Mo-Su 10:00-22:00")])
    assert "õhtune ankur" in reason
    assert dim_activity(TALLINN, None)[0] is None


def test_darkness_consumes_shared_lit_kinds():
    v, reason = dim_darkness(TALLINN, [_poi("lit_street", 0.001)])
    assert v == 72
    assert "hinnang" in reason and "mitte" in reason
    v, _ = dim_darkness(TALLINN, [_poi("lit_area", 0.004)])
    assert v == 62
    v, reason = dim_darkness(TALLINN, [])
    assert v == 45
    assert "VIIRS" in reason
    assert dim_darkness(None, [])[0] is None


def test_arrival_tight_radius_and_no_safety_claim():
    v, reason = dim_arrival(TALLINN, [_poi("walkway", 0.0005)])  # ~55 m
    assert v == 76
    assert "tipu-lõpu" in reason
    assert "ei ole turvaväide" in reason
    v, reason = dim_arrival(TALLINN, [_poi("walkway", 0.0025)])  # ~280 m
    assert v == 50  # beyond the param's own 200 m
    assert "hinnangut ei ole" in reason
    assert dim_arrival(TALLINN, None)[0] is None


def test_smell_coarse_bands():
    v, reason = dim_smell(TALLINN, [_poi("bakery", 0.002)])
    assert v == 72
    assert "jäme" in reason and "mitte ukse-täpsus" in reason
    v, reason = dim_smell(TALLINN, [])
    assert v == 55
    assert "kaebuste registrit" in reason
    assert dim_smell(None, None)[0] is None


def test_herd_taste_match_capped_never_worth():
    v, reason = dim_herd(TALLINN, [_poi("culture", 0.003)])
    assert v == 75
    assert "maitse-hinnang" in reason
    assert "mitte väärtushinnang" in reason
    assert "REL2021" in reason
    v, _ = dim_herd(TALLINN, [_poi("culture", 0.008)])
    assert v == 65
    v, _ = dim_herd(TALLINN, [])
    assert v == 55
    assert dim_herd(TALLINN, None)[0] is None


def test_thirdplace_evening_variants():
    v, reason = dim_thirdplace(
        TALLINN, [_poi("thirdplace", 0.002, hours="Mo-Su 10:00-22:00")])
    assert v == 85
    assert "õhtune" in reason and "kuuluvus-hinnang" in reason
    v, reason = dim_thirdplace(TALLINN, [_poi("thirdplace", 0.002)])
    assert v == 85
    assert "opening_hours" in reason
    v, reason = dim_thirdplace(TALLINN, [])
    assert v == 45
    assert dim_thirdplace(None, None)[0] is None


def test_taxi_weak_good_with_stepfree_extra():
    v, reason = dim_taxi(TALLINN, [_poi("entrance", 0.0005)])
    assert v == 80
    assert "nõrk hea-märk" in reason
    v, reason = dim_taxi(TALLINN, [_poi("entrance", 0.0005),
                                  _poi("stepfree", 0.001)])
    assert v == 80
    assert "ratastoolimärgistus" in reason
    v, reason = dim_taxi(TALLINN, [])
    assert v == 55
    assert "külalisparkimise" in reason
    assert dim_taxi(TALLINN, None)[0] is None


def test_lastshop_fringe_watch():
    # Livability-canonical "pharmacy" kind scores (hook-order proof).
    v, reason = dim_lastshop(TALLINN, [_poi("pharmacy", 0.004)])
    assert v == 85
    assert "elujõu-hinnang" in reason
    v, reason = dim_lastshop(TALLINN, [_poi("money", 0.012)])  # ~1.3 km
    assert v == 66
    v, reason = dim_lastshop(TALLINN, [])
    assert v == 35
    assert "Viimase-poe hoiatus" in reason
    assert "GTFS" in reason
    assert dim_lastshop(None, [])[0] is None


def test_proxy_reasons_carry_hinnang_never_ei_ole_or_measured():
    for fn in PROXY_FNS:
        for origin, pois in [(TALLINN, WALK_POIS), (TALLINN, []),
                             (TALLINN, [_poi("money", 0.001)])]:
            v, reason = fn(origin, pois)
            if v is None:
                continue  # missing-input path, tested separately
            assert "hinnang" in reason, fn.__name__
            assert "EI OLE" not in reason, fn.__name__
            assert "mõõdetud" not in reason, fn.__name__
            assert "garanteeritud" not in reason, fn.__name__


def test_missing_inputs_return_none_without_hinnang_claim():
    for fn in PROXY_FNS:
        v, _ = fn(None, WALK_POIS)
        assert v is None, fn.__name__
        v, _ = fn(TALLINN, None)
        assert v is None, fn.__name__


def test_all_seven_nulls_always_none_with_honesty_markers():
    for fn in NULL_FNS:
        for origin, pois in [(TALLINN, WALK_POIS), (TALLINN, []),
                             (None, None), (None, WALK_POIS),
                             (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__
        _, reason = fn(TALLINN, WALK_POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__


def test_null_reasons_name_the_missing_register():
    assert "winter_service" in dim_winter_maintenance(TALLINN, [])[1]
    assert "0 objekti" in dim_winter_maintenance(TALLINN, [])[1]
    assert "reageerimiskiirus" in dim_fixit(TALLINN, [])[1]
    assert "sensor.community" in dim_backyard_weather(TALLINN, [])[1]
    assert "pea peale" in dim_civic(TALLINN, [])[1]
    assert "taginfo 0" in dim_horrors(TALLINN, [])[1]
    assert "järjekordi" in dim_delights(TALLINN, [])[1]
    assert "heksitabelit" in dim_rats(TALLINN, [])[1]


def test_registry_and_aggregator_cover_all_nineteen():
    assert [k for k, _, _ in P4_OSM_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_OSM_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_OSM_DIMS}) == 19
    rich = WALK_POIS + [
        _poi("cornerfurn", 0.001), _poi("calming", 0.002),
        _poi("lot_parking", 0.003), _poi("supermarket", 0.004),
        _poi("bakery", 0.005), _poi("culture", 0.006),
        _poi("thirdplace", 0.002, hours="Mo-Su 08:00-23:00"),
        _poi("entrance", 0.001), _poi("money", 0.009),
    ]
    out = score_p4_osm(TALLINN, rich)
    assert set(out) == set(EXPECTED_KEYS)
    for key in ("block_observer", "blackspots", "parking", "grocery",
                "activity", "darkness", "arrival", "smell", "herd",
                "thirdplace", "taxi", "lastshop"):
        assert isinstance(out[key], int), key
    for key in ("winter", "fixit", "backyard_weather", "civic",
                "horrors", "delights", "rats"):
        assert out[key] is None, key
    assert score_p4_osm(None, None) == {k: None for k in EXPECTED_KEYS}
    assert p4o.P4_OSM_DIMS is P4_OSM_DIMS
