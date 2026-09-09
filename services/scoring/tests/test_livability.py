"""Livability dimensions: pure scorers offline, network behind injectables."""

import livability
from livability import (
    combine,
    commute_target,
    dim_commute,
    dim_green,
    dim_schools,
    dim_services,
    dim_transit,
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
    v, reason = dim_commute(TALLINN, "Kotzebue 12, Tallinn")
    assert v == 100 and "linnulennult" in reason
    v2, r2 = dim_commute(None, "Kotzebue 12, Tallinn")
    assert v2 is None


def test_combine_renormalizes_over_available():
    assert combine({"schools": 100, "transit": None, "services": None,
                    "green": None, "commute": None, "safety": None}) == 100
    assert combine({k: None for k in livability.WEIGHTS}) is None
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
        {"type": "node", "lat": 59.5, "lon": 24.5, "tags": {"foo": "bar"}},
    ]}
    pois = parse_overpass(payload)
    assert [(p["kind"], p["lat"]) for p in pois] == [
        ("school", 59.1), ("park", 59.2), ("bus_stop", 59.3),
        ("supermarket", 59.4),
    ]


def fake_geo(address):
    return {"lat": TALLINN[0], "lon": TALLINN[1], "pois": POIS}


def test_enrich_row_scores_with_injected_geo():
    score, reasons = enrich_row("Kotzebue 12, Tallinn", "Harju maakond",
                                resolver=fake_geo)
    assert 60 <= score <= 100
    assert any("kool" in r for r in reasons)
    assert any("riiklikud ülevaated" in r for r in reasons)
    assert not any("arvutamata" in r for r in reasons)


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
    score, reasons = enrich_row("Metsa 1, Tundmatu küla", "Rapla maakond",
                                resolver=lambda a: None)
    assert score == 50
    assert reasons == ["Elamiskvaliteet arvutamata – asukoha andmed puuduvad"]
