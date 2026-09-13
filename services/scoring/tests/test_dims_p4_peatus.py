"""P4 peatus dims (issues #314 + #376): hermetic tests.

No network: the GTFS feed is closed (2026-09-13 "Rakendus on suletud",
see dims_p4_peatus docstring), so every test runs on fixture row-dicts
and hand-built POIs. The polite fetcher is covered via a stubbed
urlopen (cache-hit performs no request; transport errors return None
and cache nothing); scorers are proven network-free by running them
with urlopen stubbed to raise.
"""

import urllib.error
import zipfile

import dims_p4_peatus as p4p
import pytest
from dims_p4_peatus import (
    EVENING_FROM,
    GTFS_TABLES,
    GTFS_TTL_S,
    GTFS_URL,
    P4_PEATUS_DIMS,
    P4_PEATUS_OVERPASS_FRAGMENT,
    departures_per_stop,
    dim_bus_cut,
    dim_delights_access,
    dim_guest_arrival,
    dim_policy_exposure,
    dim_third_places,
    fetch_gtfs_zip,
    kinds_from_tags,
    read_gtfs_tables,
    score_p4_peatus,
    services_with,
    stop_coords,
    stop_pois_from_counts,
)

# Tallinn centre: hand-built stops sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)


def mkpoi(lat=59.4372, lon=24.7546, **kw):
    poi = {"kind": "stop_p4", "lat": lat, "lon": lon,
           "deps_wed": None, "deps_prev": None,
           "deps_eve": None, "deps_sat": None}
    poi.update(kw)
    return poi


def full_poi(**kw):
    base = {"deps_wed": 140, "deps_cur": 100, "deps_prev": 100,
            "deps_eve": 12, "deps_sat": 30}
    base.update(kw)
    return mkpoi(**base)


ALL_FNS = [dim_bus_cut, dim_policy_exposure, dim_third_places,
           dim_delights_access, dim_guest_arrival]

# ---------------------------------------------------------------------------
# Fixture GTFS tables (row-dicts, no zip needed except the roundtrip test).
# ---------------------------------------------------------------------------

CAL = [
    {"service_id": "W", "wednesday": "1", "saturday": "0"},
    {"service_id": "S", "wednesday": "0", "saturday": "1"},
]
TRIPS = [
    {"trip_id": "t1", "route_id": "r1", "service_id": "W"},
    {"trip_id": "t2", "route_id": "r1", "service_id": "W"},
    {"trip_id": "t3", "route_id": "r1", "service_id": "S"},
]
STOP_TIMES = [
    {"trip_id": "t1", "stop_id": "s1", "departure_time": "08:00:00"},
    {"trip_id": "t1", "stop_id": "s1", "departure_time": "19:30:00"},
    {"trip_id": "t1", "stop_id": "s2", "departure_time": "08:05:00"},
    {"trip_id": "t1", "stop_id": "s2", "departure_time": "25:30:00"},
    {"trip_id": "t2", "stop_id": "s1", "departure_time": "09:00:00"},
    {"trip_id": "t3", "stop_id": "s1", "departure_time": "10:00:00"},
    {"trip_id": "t3", "stop_id": "s1", "departure_time": "20:00:00"},
]
STOPS = [
    {"stop_id": "s1", "stop_lon": "24.7546", "stop_lat": "59.4372"},
    {"stop_id": "s2", "stop_lon": "24.8000", "stop_lat": "59.4500"},
    {"stop_id": "bad", "stop_lat": "59.43"},  # no lon: skipped, never faked
]
GTFS = {"calendar.txt": CAL, "trips.txt": TRIPS,
        "stop_times.txt": STOP_TIMES, "stops.txt": STOPS,
        "routes.txt": [{"route_id": "r1"}]}


def test_ingestion_wednesday_and_evening_counts():
    wed = services_with(CAL, "wednesday")
    assert wed == {"W"}
    assert departures_per_stop(GTFS, wed) == {"s1": 3, "s2": 2}
    eve = departures_per_stop(GTFS, wed, after=EVENING_FROM)
    # 19:30 + past-midnight 25:30:00 both count as evening service.
    assert eve == {"s1": 1, "s2": 1}


def test_ingestion_saturday_counts():
    sat = services_with(CAL, "saturday")
    assert sat == {"S"}
    assert departures_per_stop(GTFS, sat) == {"s1": 2}


def test_ingestion_coords_skip_malformed():
    coords = stop_coords(STOPS)
    assert set(coords) == {"s1", "s2"}
    assert coords["s1"] == (24.7546, 59.4372)


def test_ingestion_pois_carry_all_windows_with_none_gaps():
    coords = stop_coords(STOPS)
    wed = departures_per_stop(GTFS, services_with(CAL, "wednesday"))
    pois = stop_pois_from_counts(coords, wed, prev={"s1": 4},
                                 eve={"s1": 1}, sat={"s1": 2})
    by_lat = {p["lat"]: p for p in pois}
    s1 = by_lat[59.4372]
    assert (s1["deps_wed"], s1["deps_prev"], s1["deps_eve"],
            s1["deps_sat"]) == (3, 4, 1, 2)
    s2 = by_lat[59.45]
    assert s2["deps_prev"] is None and s2["deps_sat"] is None


def test_read_gtfs_tables_roundtrip_offline(tmp_path):
    zp = str(tmp_path / "gtfs.zip")
    with zipfile.ZipFile(zp, "w") as zf:
        zf.writestr("calendar.txt", "service_id,wednesday,saturday\nW,1,0\n")
        zf.writestr("trips.txt", "trip_id,route_id,service_id\nt1,r1,W\n")
        zf.writestr("stop_times.txt",
                    "trip_id,stop_id,departure_time\nt1,s1,08:00:00\n")
        zf.writestr("stops.txt",
                    "stop_id,stop_lon,stop_lat\ns1,24.75,59.43\n")
        zf.writestr("routes.txt", "route_id\nr1\n")
    out = read_gtfs_tables(zp)
    assert set(out) == set(GTFS_TABLES)
    assert out["calendar.txt"] == [
        {"service_id": "W", "wednesday": "1", "saturday": "0"}]


# ---------------------------------------------------------------------------
# Polite fetcher: TTL default, cache-hit silence, honest errors. No network.
# ---------------------------------------------------------------------------

def test_ttl_default_is_24h_and_url_is_documented_feed():
    assert GTFS_TTL_S == 86400
    assert GTFS_URL == "https://peatus.ee/gtfs/gtfs.zip"


def test_fetch_cache_hit_makes_no_request(tmp_path, monkeypatch):
    dest = tmp_path / "peatus-gtfs.zip"
    dest.write_bytes(b"PK" + b"\x00" * 2000)

    def _boom(*a, **k):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_gtfs_zip(str(tmp_path)) == str(dest)


class _FakeResp:
    def __init__(self, body, ctype="application/zip"):
        self.status = 200
        self.headers = {"Content-Type": ctype}
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def test_fetch_transport_error_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    def _fail(*a, **k):
        raise urllib.error.URLError("closed")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    assert fetch_gtfs_zip(str(tmp_path)) is None
    assert not (tmp_path / "peatus-gtfs.zip").exists()


def test_fetch_non_zip_body_is_not_cached_as_data(tmp_path, monkeypatch):
    # The live 2026-09-13 verdict: HTTP 200 text/html "Rakendus on suletud".
    html = ("<!DOCTYPE html><html><head><title>Rakendus on suletud"
            "</title></head></html>").encode()
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: _FakeResp(html, "text/html"))
    assert fetch_gtfs_zip(str(tmp_path)) is None
    assert not (tmp_path / "peatus-gtfs.zip").exists()


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    pois = [full_poi()]
    for fn in ALL_FNS:
        fn(TALLINN, pois)
    score_p4_peatus(TALLINN, pois)


# ---------------------------------------------------------------------------
# P4-061 bus-cut bands (fraction boundaries pinned).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cur,expected", [
    (70, 20),    # exactly -30% -> strong cut
    (71, 45),    # -29% -> noticeable cut
    (90, 45),    # exactly -10% -> noticeable cut
    (91, 70),    # -9% -> stable
    (100, 70),   # unchanged -> stable
    (110, 70),   # exactly +10% -> stable
    (111, 90),   # +11% -> growing
])
def test_bus_cut_bands(cur, expected):
    v, reason = dim_bus_cut(TALLINN, [mkpoi(deps_cur=cur, deps_prev=100)])
    assert v == expected, reason
    assert "hinnang" in reason and "%" in reason


def test_bus_cut_new_service_and_persistent_gap():
    v, r = dim_bus_cut(TALLINN, [mkpoi(deps_cur=12, deps_prev=0)])
    assert v == 90 and "uus teenus" in r
    v, r = dim_bus_cut(TALLINN, [mkpoi(deps_cur=0, deps_prev=0)])
    assert v == 20 and "hinnang" in r


def test_bus_cut_null_without_both_vintages():
    for poi in (mkpoi(deps_cur=50),
                mkpoi(deps_prev=50),
                mkpoi(deps_cur=True, deps_prev=50),   # bool is not a count
                mkpoi(deps_cur=-3, deps_prev=50),     # negative impossible
                mkpoi(deps_cur="x", deps_prev=50)):   # garbage
        v, r = dim_bus_cut(TALLINN, [poi])
        assert v is None, poi
        assert "EI OLE" in r and "võrdlusvintsi" in r


# ---------------------------------------------------------------------------
# Coverage params: bands + NULLs.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("deps,expected", [
    (0, 20), (1, 40), (29, 40), (30, 60), (79, 60),
    (80, 80), (149, 80), (150, 100), (500, 100),
])
def test_policy_exposure_bands(deps, expected):
    v, r = dim_policy_exposure(TALLINN, [mkpoi(deps_wed=deps)])
    assert v == expected, r
    assert "hinnang" in r


@pytest.mark.parametrize("eve,expected", [
    (0, 20), (1, 40), (3, 40), (4, 60), (9, 60),
    (10, 80), (19, 80), (20, 100), (60, 100),
])
def test_third_places_evening_bands(eve, expected):
    v, r = dim_third_places(TALLINN, [mkpoi(deps_eve=eve)])
    assert v == expected, r
    assert "18:00" in r and "hinnang" in r


@pytest.mark.parametrize("sat,expected", [
    (0, 20), (1, 40), (7, 40), (8, 60), (19, 60),
    (20, 80), (39, 80), (40, 100), (200, 100),
])
def test_guest_arrival_saturday_bands(sat, expected):
    v, r = dim_guest_arrival(TALLINN, [mkpoi(deps_sat=sat)])
    assert v == expected, r
    assert "laupäev" in r and "hinnang" in r


@pytest.mark.parametrize("dlat,expected", [
    (0.002, 100),   # ~222 m
    (0.004, 85),    # ~445 m
    (0.007, 70),    # ~778 m
    (0.0095, 55),   # ~1056 m, inside the 15 min window
])
def test_delights_walk_bands(dlat, expected):
    v, r = dim_delights_access(
        TALLINN, [mkpoi(lat=TALLINN[0] + dlat, lon=TALLINN[1])])
    assert v == expected, r
    assert "hinnang" in r and "marsruutimata" in r


def test_delights_scores_on_positions_before_frequency_join():
    # Judgment call pinned: <15 min access is a walk fact, no counts needed.
    v, _ = dim_delights_access(TALLINN, [mkpoi()])
    assert v == 100


def test_count_dims_null_without_their_window():
    v, r = dim_policy_exposure(TALLINN, [mkpoi()])
    assert v is None and "EI OLE" in r and "GTFS-liidestust" in r
    v, r = dim_third_places(TALLINN, [mkpoi()])
    assert v is None and "EI OLE" in r and "õhtuakent" in r
    v, r = dim_guest_arrival(TALLINN, [mkpoi()])
    assert v is None and "EI OLE" in r and "laupäevaakent" in r


def test_windows_far_stop_is_unknown_not_bad():
    # ~800 m east: inside the 1500 m cut window, outside the 750 m windows.
    far = full_poi(lat=TALLINN[0], lon=TALLINN[1] + 0.014)
    v, r = dim_bus_cut(TALLINN, [far])
    assert v == 70, r
    v, r = dim_delights_access(TALLINN, [far])
    assert v == 70, r
    for fn in (dim_policy_exposure, dim_third_places, dim_guest_arrival):
        v, r = fn(TALLINN, [full_poi(lat=TALLINN[0],
                                     lon=TALLINN[1] + 0.014)])
        assert v is None, fn.__name__
        assert "EI OLE" in r
    # ~2.9 km east: outside every window, including delights + cut.
    rural = mkpoi(lat=TALLINN[0], lon=TALLINN[1] + 0.05)
    for fn in ALL_FNS:
        v, r = fn(TALLINN, [dict(rural, deps_wed=140, deps_cur=100,
                                 deps_prev=100, deps_eve=12, deps_sat=30)])
        assert v is None, fn.__name__
        assert "EI OLE" in r


def test_all_null_for_missing_inputs_and_malformed_pois():
    bad_pois = [[{"kind": "stop_wday", "lat": 59.4372, "lon": 24.7546}],
                [{"kind": "stop_p4"}], [],
                [{"kind": "stop_p4", "lat": None, "lon": 24.75}],
                [{"kind": "stop_p4", "lat": 59.43, "lon": "x"}]]
    for fn in ALL_FNS:
        for origin, pois in [(None, [full_poi()]), (TALLINN, None),
                             (None, None)] + [(TALLINN, p) for p in bad_pois]:
            v, r = fn(origin, pois)
            assert v is None, (fn.__name__, origin, pois)
            assert "EI OLE" in r, fn.__name__


def test_honesty_markers():
    for fn in ALL_FNS:
        _, r = fn(TALLINN, [full_poi(
            lat=TALLINN[0], lon=TALLINN[1] + 0.05)])
        assert "EI OLE" in r, fn.__name__
        assert "hinnang" not in r or "pole" in r
    for fn, poi in [(dim_bus_cut, full_poi()),
                    (dim_policy_exposure, full_poi()),
                    (dim_third_places, full_poi()),
                    (dim_delights_access, full_poi()),
                    (dim_guest_arrival, full_poi())]:
        v, r = fn(TALLINN, [poi])
        assert v is not None
        assert "hinnang" in r and "EI OLE" not in r, fn.__name__
        assert "garanteeritud" not in r


def test_kinds_and_fragment():
    assert kinds_from_tags({"highway": "bus_stop"}) == "stop_p4"
    assert kinds_from_tags({"public_transport": "platform"}) == "stop_p4"
    assert kinds_from_tags({"public_transport": "stop_position"}) == "stop_p4"
    assert kinds_from_tags({"amenity": "cafe"}) is None
    assert kinds_from_tags("bus_stop") is None
    assert 'node["highway"="bus_stop"]' in P4_PEATUS_OVERPASS_FRAGMENT
    assert "{lat}" in P4_PEATUS_OVERPASS_FRAGMENT


def test_registry_and_aggregator_cover_all_five():
    assert [k for k, _, _ in P4_PEATUS_DIMS] == [
        "bus_cut", "policy_exposure", "third_places",
        "delights_access", "guest_arrival"]
    assert [p for _, p, _ in P4_PEATUS_DIMS] == [
        "P4-061", "P4-037", "P4-045", "P4-048", "P4-049"]
    assert len({fn for _, _, fn in P4_PEATUS_DIMS}) == 5
    out = score_p4_peatus(TALLINN, [full_poi()])
    assert out == {"bus_cut": 70, "policy_exposure": 80,
                   "third_places": 80, "delights_access": 100,
                   "guest_arrival": 80}
    assert score_p4_peatus(None, None) == {
        k: None for k, _, _ in P4_PEATUS_DIMS}
    assert p4p.P4_PEATUS_DIMS is P4_PEATUS_DIMS
