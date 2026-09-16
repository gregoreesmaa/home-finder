"""P4 ratings + price tiers dims (issue #556): hermetic tests.

No network and no live key: every test runs on fixture Nearby
Search bodies and hand-built POIs (no live key in tests, ever).
The keyed fetcher is covered via a stubbed urlopen (no key ->
None with no request; spent quota -> None; transport errors and
short bodies return None and cache nothing); scorers are proven
network-free by running them with urlopen stubbed to raise. The
rating floor (userRatingCount >= 10), the price bands, and the
no-key NULL path are pinned here.
"""

import json
import urllib.error

import dims_p4_ratings as p4r
import pytest
from dims_p4_ratings import (
    JOIN_WINDOW_M,
    PLACES_MONTHLY_MAX_CALLS,
    PLACES_TTL_S,
    PRICE_BANDS,
    RATED_WINDOW_M,
    RATING_MIN_N,
    dim_dining_delight,
    dim_price_character,
    fetch_places,
    link_places_to_records,
    parse_places_response,
    rating_pois_from_places,
    score_p4_ratings,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)


def mkpoi(rating=4.5, n=120, price_level=2, lat=59.4372, lon=24.7546,
          **kw):
    poi = {"kind": "place_rating_p4", "lat": lat, "lon": lon,
           "rating": rating, "n": n, "price_level": price_level,
           "place_id": "ChIJtest"}
    poi.update(kw)
    return poi


ALL_FNS = [dim_dining_delight, dim_price_character]

NEARBY_FIXTURE = {
    "places": [
        {"id": "ChIJgood",
         "displayName": {"text": "Hea Kohvik"},
         "location": {"latitude": 59.4372, "longitude": 24.7546},
         "rating": 4.6, "userRatingCount": 231,
         "priceLevel": "PRICE_LEVEL_MODERATE"},
        {"id": "ChIJthin",
         "displayName": {"text": "Uus Baar"},
         "location": {"latitude": 59.4375, "longitude": 24.7550},
         "rating": 5.0, "userRatingCount": 3,
         "priceLevel": "PRICE_LEVEL_INEXPENSIVE"},
        {"id": "ChIJcheap",
         "displayName": "Odav Söökla",
         "location": {"latitude": 59.4380, "longitude": 24.7560},
         "rating": 3.9, "userRatingCount": 45,
         "priceLevel": 1},
        {"id": "ChIJbroken",
         "displayName": {"text": "???"},
         "location": {"latitude": "x", "longitude": None},
         "rating": "hea", "userRatingCount": -2,
         "priceLevel": "PRICE_LEVEL_LUXURY"},
    ]
}


def write_places(tmp_path):
    p = tmp_path / "places.json"
    p.write_text(json.dumps(NEARBY_FIXTURE), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Keyed fetcher: no key / quota / errors. No network.
# ---------------------------------------------------------------------------

def test_key_model_constants():
    assert PLACES_TTL_S == 30 * 24 * 3600  # re-pull, don't hoard
    assert PLACES_MONTHLY_MAX_CALLS == 500
    assert RATING_MIN_N == 10  # review-count floor is load-bearing
    assert p4r.PLACES_KEY_ENV == "GOOGLE_PLACES_API_KEY"


def test_fetch_without_key_makes_no_request(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)

    def _boom(*a, **k):
        raise AssertionError("network used without a key")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_places(59.43, 24.75, 500, str(tmp_path),
                        "places.json") is None


def test_fetch_spent_quota_makes_no_request(tmp_path, monkeypatch):
    (tmp_path / "places_quota.json").write_text(
        json.dumps({"window_start": 9999999999, "used": 500}),
        encoding="utf-8")

    def _boom(*a, **k):
        raise AssertionError("network used on spent quota")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_places(59.43, 24.75, 500, str(tmp_path), "places.json",
                        api_key="test-key", ttl_s=0) is None


class _FakeResp:
    def __init__(self, body, status=200):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def test_fetch_caches_hit_makes_no_request(tmp_path, monkeypatch):
    dest = tmp_path / "places.json"
    dest.write_bytes(b"x" * 200)

    def _boom(*a, **k):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_places(59.43, 24.75, 500, str(tmp_path), "places.json",
                        api_key="test-key") == str(dest)


def test_fetch_transport_error_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    def _fail(*a, **k):
        raise urllib.error.URLError("down")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    assert fetch_places(59.43, 24.75, 500, str(tmp_path), "places.json",
                        api_key="test-key", ttl_s=0) is None
    assert not (tmp_path / "places.json").exists()


def test_fetch_429_returns_none_and_caches_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(b"x" * 200, 429))
    assert fetch_places(59.43, 24.75, 500, str(tmp_path), "places.json",
                        api_key="test-key", ttl_s=0) is None
    assert not (tmp_path / "places.json").exists()


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    for fn in ALL_FNS:
        fn(TALLINN, [mkpoi()])
    score_p4_ratings(TALLINN, [mkpoi()])


# ---------------------------------------------------------------------------
# Offline readers on the fixture body.
# ---------------------------------------------------------------------------

def test_parse_reads_ratings_and_price_levels(tmp_path):
    places = parse_places_response(write_places(tmp_path))
    assert len(places) == 4
    good = next(p for p in places if p["place_id"] == "ChIJgood")
    assert good["rating"] == pytest.approx(4.6) and good["n"] == 231
    assert good["price_level"] == 2 and good["name"] == "Hea Kohvik"
    cheap = next(p for p in places if p["place_id"] == "ChIJcheap")
    assert cheap["price_level"] == 1  # numeric levels pass through
    broken = next(p for p in places if p["place_id"] == "ChIJbroken")
    assert broken["rating"] is None and broken["n"] == 0
    assert broken["price_level"] is None  # unknown enum, never guessed
    assert broken["lat"] is None


def test_floor_drops_thin_places_but_keeps_them_unscored(tmp_path):
    places = parse_places_response(write_places(tmp_path))
    pois = rating_pois_from_places(places)
    ids = {p["place_id"] for p in pois}
    assert "ChIJgood" in ids and "ChIJcheap" in ids
    assert "ChIJthin" not in ids  # 5.0 stars but n=3: ignored, never 0
    assert "ChIJbroken" not in ids


def test_join_window_documented():
    assert JOIN_WINDOW_M == 50.0
    assert RATED_WINDOW_M == 500.0


def test_link_matches_by_distance_and_name():
    places = [{"place_id": "A", "name": "Hea Kohvik",
               "lat": 59.4372, "lon": 24.7546}]
    records = [{"name": "Hea kohvik", "lat": 59.4373, "lon": 24.7547}]
    links = link_places_to_records(places, records)
    assert links == {"A": records[0]}


def test_link_leaves_mismatches_unmatched_never_forced():
    places = [{"place_id": "A", "name": "Hea Kohvik",
               "lat": 59.4372, "lon": 24.7546},
              {"place_id": "B", "name": "Tundmatu Koht",
               "lat": 59.4372, "lon": 24.7546},
              {"place_id": "C", "name": "Hea Kohvik",
               "lat": 59.4372, "lon": 24.7546}]  # double claim
    records = [{"name": "Hea kohvik", "lat": 59.4373, "lon": 24.7547}]
    links = link_places_to_records(places, records)
    assert links["A"] == records[0]
    assert links["B"] is None  # name mismatch: unmatched
    assert links["C"] is None  # ambiguous double claim: unmatched
    far = [{"place_id": "D", "name": "Hea Kohvik",
            "lat": 59.4372, "lon": 24.7546}]
    far_recs = [{"name": "Hea kohvik", "lat": 59.45, "lon": 24.80}]
    assert link_places_to_records(far, far_recs) == {"D": None}


# ---------------------------------------------------------------------------
# Legs: delight threshold + price bands + no-key NULL pinned.
# ---------------------------------------------------------------------------

def test_no_key_null_path_is_never_a_guess():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, None), (None, None)]:
            v, r = fn(origin, pois)
            assert v is None, fn.__name__
            assert "EI OLE" in r and "võti" in r, fn.__name__


def test_dining_delight_threshold():
    v, r = dim_dining_delight(TALLINN, [mkpoi(rating=4.3, n=10)])
    assert v == 70, r
    assert "hinnang" in r and "maitse" in r
    v, _ = dim_dining_delight(TALLINN, [mkpoi(rating=4.2, n=500)])
    assert v is None  # below 4.3 even with 500 reviews
    v, _ = dim_dining_delight(TALLINN, [mkpoi(rating=5.0, n=9)])
    assert v is None  # floor: 5.0 with 9 reviews is not a verdict
    v, r = dim_dining_delight(TALLINN, [mkpoi(rating=4.9, n=40)])
    assert v == 70 and "4.9" in r


@pytest.mark.parametrize("tier,expected", [
    (0, 75), (1, 65), (2, 55), (3, 40), (4, 30),
])
def test_price_bands(tier, expected):
    v, r = dim_price_character(TALLINN, [mkpoi(price_level=tier)])
    assert v == expected, r
    assert "hinnang" in r and "kulukarakter" in r


def test_price_uses_cheapest_tiered_place():
    pois = [mkpoi(price_level=4), mkpoi(price_level=1, lon=24.7556)]
    v, r = dim_price_character(TALLINN, pois)
    assert v == 65, r  # cheapest tier nearby sets the tone


def test_untiered_places_stay_null():
    v, r = dim_price_character(TALLINN, [mkpoi(price_level=None)])
    assert v is None and "EI OLE" in r
    v, r = dim_dining_delight(TALLINN, [mkpoi(price_level=None)])
    assert v == 70  # delight needs no price tier


def test_dims_ignore_other_kinds_and_garbage():
    # Rating garbage kills only the delight leg (price tiers are
    # independent of stars); price garbage kills only the price leg.
    for poi in ({"kind": "cafe", "lat": 59.4372, "lon": 24.7546},
                mkpoi(rating="hea"), mkpoi(rating=True),
                mkpoi(rating=6.0), mkpoi(n=5), mkpoi(n=True),
                {"kind": "place_rating_p4", "lat": None, "lon": 24.75}):
        v, r = dim_dining_delight(TALLINN, [poi])
        assert v is None, poi
        assert "EI OLE" in r
    for poi in ({"kind": "cafe", "lat": 59.4372, "lon": 24.7546},
                mkpoi(n=5), mkpoi(n=True),
                mkpoi(price_level=9), mkpoi(price_level="kallis"),
                mkpoi(price_level=True),
                {"kind": "place_rating_p4", "lat": None, "lon": 24.75}):
        v, r = dim_price_character(TALLINN, [poi])
        assert v is None, poi
        assert "EI OLE" in r


def test_window_boundary():
    far = mkpoi(lat=TALLINN[0], lon=TALLINN[1] + 0.05)  # ~2.9 km
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [far])
        assert v is None, fn.__name__
        assert "EI OLE" in r


def test_all_null_for_missing_inputs():
    for fn in ALL_FNS:
        for origin, pois in [(None, [mkpoi()]), (TALLINN, [])]:
            v, r = fn(origin, pois)
            assert v is None, (fn.__name__, origin, pois)
            assert "EI OLE" in r, fn.__name__


def test_honesty_markers():
    v, r = dim_dining_delight(TALLINN, [mkpoi()])
    assert v == 70 and "hinnang" in r and "EI OLE" not in r
    assert "edetabel" in r  # taste stays buyer-side
    v, r = dim_price_character(TALLINN, [mkpoi()])
    assert v == 55 and "ostukorv" in r  # tiers only, never baskets


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in p4r.P4_RATINGS_DIMS] == [
        "dining_delight", "price_character"]
    assert PRICE_BANDS == {0: 75, 1: 65, 2: 55, 3: 40, 4: 30}
    out = score_p4_ratings(TALLINN, [mkpoi()])
    assert out == {"dining_delight": 70, "price_character": 55}
    assert score_p4_ratings(None, None) == {
        k: None for k, _, _ in p4r.P4_RATINGS_DIMS}
    assert p4r.P4_RATINGS_DIMS is p4r.P4_RATINGS_DIMS
