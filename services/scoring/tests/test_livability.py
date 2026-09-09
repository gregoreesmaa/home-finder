"""Livability dimensions: pure scorers offline, network behind injectables."""

import livability
from livability import (
    combine,
    commute_target,
    dim_connect,
    dim_green,
    dim_rail,
    dim_schools,
    dim_services,
    dim_transit,
    dim_urban,
    dim_water,
    enrich_row,
    haversine_km,
    parse_overpass,
)

TALLINN = (59.4372, 24.7536)
POIS = [
    {"kind": "school", "lat": 59.4380, "lon": 24.7550},       # ~120 m
    {"kind": "bus_stop", "lat": 59.4375, "lon": 24.7540},     # ~50 m
    {"kind": "bus_stop", "lat": 59.4385, "lon": 24.7560},     # ~200 m
    {"kind": "park", "lat": 59.4400, "lon": 24.7600},         # ~500 m
    {"kind": "supermarket", "lat": 59.4360, "lon": 24.7520},  # ~200 m
    {"kind": "rail_station", "lat": 59.4390, "lon": 24.7580},  # ~350 m
    {"kind": "water", "lat": 59.4430, "lon": 24.7650},        # ~900 m
]


def test_haversine_tallinn_tartu():
    assert 160 < haversine_km(TALLINN, (58.3780, 26.7290)) < 170


def test_dim_schools_bands_and_reasons():
    v, reason = dim_schools(TALLINN, POIS)
    assert v == 100
    assert "kool" in reason and "m" in reason
    v2, _ = dim_schools(TALLINN, [])
    assert v2 == 15
    v3, r3 = dim_schools(None, POIS)
    assert v3 is None and "puudub" in r3
    v4, _ = dim_schools(TALLINN, None)
    assert v4 is None


def test_dim_transit_counts_stops():
    v, reason = dim_transit(TALLINN, POIS)
    assert v == 60  # 2 stops within 500 m
    assert "peatus" in reason
    v2, _ = dim_transit(TALLINN, [])
    assert v2 == 15


def test_dim_green_and_services():
    v, r = dim_green(TALLINN, POIS)
    assert v == 80 and "Park" in r or "park" in r
    v2, r2 = dim_services(TALLINN, POIS)
    assert v2 == 100 and "pood" in r2


def test_commute_target_and_bands():
    assert commute_target("Kotzebue 12, Tallinn")[0] == "Tallinn"
    assert commute_target("Sireli tee 4, Haiba, Saue vald")[0] == "Tallinn keskus"
    assert commute_target("Tähe 45, Tartu")[0] == "Tartu"
    assert commute_target("Metsa 1, Raplamaa küla") is None


def test_connect_reports_travel_times_not_bird_flight():
    """#75: centre/station/shop options as estimated minutes."""
    v, reason = dim_connect(TALLINN, POIS, "Kotzebue 12, Tallinn")
    assert v == 100  # at the centre: car ~0 min
    assert "hinnang" in reason and "min" in reason
    assert "linnulennult" not in reason
    # unknown city: shop-on-foot option still scores
    v2, r2 = dim_connect(TALLINN, POIS, "Metsa 1, Raplamaa küla")
    assert v2 is not None and "pood jalgsi" in r2
    # no origin, no data
    v3, r3 = dim_connect(None, POIS, "Kotzebue 12, Tallinn")
    assert v3 is None and "puudub" in r3
    # origin but nothing reachable: honest low score
    v4, r4 = dim_connect(TALLINN, [], "Metsa 1, Raplamaa küla")
    assert v4 == 15


def test_water_rail_urban_bands():
    v, r = dim_water(TALLINN, POIS)
    assert v == 75 and "meri" in r
    v2, _ = dim_water(TALLINN, [])
    assert v2 == 20
    v3, r3 = dim_water(None, POIS)
    assert v3 is None and "puudub" in r3
    w, r = dim_rail(TALLINN, POIS)
    assert w == 100 and "rongipeatus" in r
    w2, _ = dim_rail(TALLINN, [])
    assert w2 == 20
    u, r = dim_urban(TALLINN, POIS)
    assert u == 40 and "7 huvipunkti" in r  # 7 POIs in fixture
    u2, _ = dim_urban(TALLINN, [])
    assert u2 == 10
    u3, r3 = dim_urban(None, POIS)
    assert u3 is None and "puudub" in r3


def test_combine_renormalizes_over_available():
    assert combine({"schools": 100, "transit": None, "services": None,
                    "green": None, "water": None, "rail": None,
                    "urban": None, "safety": None, "connect": None}) == 100
    assert combine({k: None for k in livability.WEIGHTS}) is None
    assert set(livability.WEIGHTS) == {
        "schools", "transit", "services", "green", "water", "rail",
        "urban", "safety", "connect",
    }
    assert abs(sum(livability.WEIGHTS.values()) - 1.0) < 1e-9


def test_parse_overpass_maps_tags_and_centers():
    payload = {"elements": [
        {"type": "node", "lat": 59.1, "lon": 24.1,
         "tags": {"amenity": "school"}},
        {"type": "way", "center": {"lat": 59.2, "lon": 24.2},
         "tags": {"leisure": "park"}},
        {"type": "node", "lat": 59.3, "lon": 24.3,
         "tags": {"highway": "bus_stop"}},
        {"type": "node", "lat": 59.4, "lon": 24.4,
         "tags": {"shop": "supermarket"}},
        {"type": "node", "lat": 59.45, "lon": 24.45,
         "tags": {"railway": "station"}},
        {"type": "node", "lat": 59.46, "lon": 24.46,
         "tags": {"natural": "water"}},
        {"type": "node", "lat": 59.5, "lon": 24.5, "tags": {"foo": "bar"}},
    ]}
    pois = parse_overpass(payload)
    assert [(p["kind"], p["lat"]) for p in pois] == [
        ("school", 59.1), ("park", 59.2), ("bus_stop", 59.3),
        ("supermarket", 59.4), ("rail_station", 59.45), ("water", 59.46),
    ]


def fake_geo(address):
    return {"lat": TALLINN[0], "lon": TALLINN[1], "pois": POIS}


def test_enrich_row_scores_with_injected_geo():
    score, reasons, dims = enrich_row("Kotzebue 12, Tallinn", "Harju maakond",
                                      resolver=fake_geo)
    assert 60 <= score <= 100
    assert any("kool" in r for r in reasons)
    assert any("riiklikud ülevaated" in r for r in reasons)
    assert not any("arvutamata" in r for r in reasons)
    assert set(dims) == set(livability.WEIGHTS)
    assert dims["schools"] == 100 and dims["connect"] == 100
    assert any("min" in r for r in reasons)  # travel-time options present


def test_geocode_falls_back_to_nominatim(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("photon down")

    monkeypatch.setattr(livability, "fetch_geocode_photon", boom)
    monkeypatch.setattr(
        livability, "fetch_geocode_nominatim", lambda a, timeout=20.0: (59.1, 24.1)
    )
    assert livability.fetch_geocode("Metsa 1, Tallinn") == (59.1, 24.1)


def test_simplify_address_strips_hierarchy():
    assert livability.simplify_address("Pärnu linn, Pärnu linn, Ravi tn 1a") == [
        "Pärnu linn, Pärnu linn, Ravi tn 1a",
        "Ravi tn 1a, Pärnu linn",
        "Ravi tn 1a",
    ]
    assert livability.simplify_address("Tallinn") == ["Tallinn"]
    assert livability.simplify_address("") == []


def test_simplify_address_handles_brittle_portal_strings():
    """#81: apartment suffixes, junk segments, missing numbers."""
    cands = livability.simplify_address(
        "Astangu tn 68-19, Harku järve lähedal, Haabersti, Tallinn"
    )
    assert cands[0].startswith("Astangu tn 68-19")
    assert "Astangu tn 68, Tallinn" in cands
    cands = livability.simplify_address("Tähetorni tn , Nõmme, Tallinn, Harjumaa")
    assert "Tähetorni tn, Tallinn" in cands
    cands = livability.simplify_address("Mäepealse tn 9/1-25, Nõmmemäe, Nõmme, Tallinn")
    assert "Mäepealse tn 9, Tallinn" in cands


def test_geocode_falls_back_on_photon_miss(monkeypatch):
    """#81: a Photon empty (not just errors) reaches Nominatim."""
    calls = []
    monkeypatch.setattr(livability, "fetch_geocode_photon", lambda a, timeout=20.0: None)
    monkeypatch.setattr(
        livability, "fetch_geocode_nominatim",
        lambda a, timeout=20.0: calls.append(a) or (59.1, 24.1),
    )
    assert livability.fetch_geocode("Metsa 1, Tallinn") == (59.1, 24.1)
    assert calls, "Nominatim must run after a Photon miss"


def test_air_stub_returns_null_with_reason():
    v, reason = livability.dim_air()
    assert v is None
    assert "puuduvad" in reason
    assert "air" not in livability.WEIGHTS


def test_transient_geocode_errors_are_not_cached(tmp_path, monkeypatch):
    import httpx

    calls = []

    def boom(address, timeout=20.0):
        calls.append(address)
        raise httpx.ConnectError("down")

    monkeypatch.setattr(livability, "fetch_geocode", boom)
    cache = str(tmp_path)
    assert livability.resolve("Metsa 1, Tallinn", cache) is None
    assert livability.resolve("Metsa 1, Tallinn", cache) is None
    assert len(calls) == 2, "transport errors must not be cached as negatives"
    assert list(tmp_path.iterdir()) == [], "no cache file on transient failure"


def test_enrich_row_honest_fallback_without_geo():
    score, reasons, dims = enrich_row("Metsa 1, Tundmatu küla", "Rapla maakond",
                                      resolver=lambda a: None)
    assert score == 50
    assert reasons == ["Elamiskvaliteet arvutamata – asukoha andmed puuduvad"]
    assert set(dims) == set(livability.WEIGHTS)
    assert all(v is None for v in dims.values())
