"""P4 kvagi dims (issues #297 + #367): hermetic tests.

No network: Kaitsevägi publishes the Brontos snapshots as open data
(CC 3.0 BY-SA - see the module docstring), so every test runs on
hand-written synthetic fixtures mirroring the observed layout (real
area names, invented polygons/entries - never the committed live
dump) plus hand-built POIs (area anchors are computed offline via
the documented polygon step). The polite fetcher is covered via a
stubbed urlopen (cache-hit performs no request; transport errors
and short bodies return None and cache nothing); scorers are proven
network-free by running them with urlopen stubbed to raise, on a
fixed calendar cursor (a Sunday, so weekend filters bite).
"""

import json
import math
import urllib.error

import dims_p4_kvagi as p4k
import pytest
from dims_p4_kvagi import (
    AUDIBLE_WINDOW_M,
    AVAANDMED_URL,
    EXERCISE_CALENDAR_SCORE,
    EXERCISE_ZONE_SCORE,
    KVAGI_UA,
    MAPDATA_TTL_S,
    MAPDATA_URL,
    SCHEDULE_TTL_S,
    SCHEDULE_URL,
    SCORING_NOISES,
    TALLINN_AUDIBLE_AREAS,
    _overlaps_weekend,
    _window_state,
    dim_exercise_noise_zone,
    dim_exercise_season_calendar,
    dim_manniku_weekend_calendar,
    fetch_cached,
    index_by_area_month,
    mercator_to_wgs84,
    parse_mapdata,
    parse_schedule,
    score_p4_kvagi,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)
# Fixed calendar cursor: 2026-09-13, a Sunday - every expiry and
# weekend assertion is hermetic.
TODAY = "2026-09-13"

ALL_FNS = [dim_exercise_noise_zone, dim_exercise_season_calendar,
           dim_manniku_weekend_calendar]

# Synthetic schedule fixture: real area names (public geography),
# invented entries/polygons - never the live dump.
SCHEDULE_JSON = json.dumps([
    {"trainingAreaId": 8, "trainingAreaName": "MÄNNIKU harjutusväli",
     "year": 2026, "month": 9, "approvedAt": "2026-09-11T09:17:55Z",
     "additionalInfo": "MÜRATASEMED: Madal müra - Käsitulirelvade laskmine",
     "exercises": [
         {"id": 1, "startDate": "2026-09-12T05:00:00Z",
          "endDate": "2026-09-14T15:00:00Z", "exerciseType": "TACTICS",
          "trainingObjects": ["LA1"], "noiseLevel": "LOW",
          "status": "STATUS_OLD"},
         {"id": 2, "startDate": "2026-09-12T05:00:00Z",
          "endDate": "2026-09-14T15:00:00Z", "exerciseType": "TACTICS",
          "trainingObjects": [], "noiseLevel": "ABSENT",
          "status": "STATUS_OLD"},
         {"id": 3, "startDate": "2026-09-01T05:00:00Z",
          "endDate": "2026-09-05T20:59:59Z", "exerciseType": "SHOOTING",
          "trainingObjects": ["LP1"], "noiseLevel": "HIGH",
          "status": "STATUS_OLD"},
         {"id": 4, "startDate": "2026-09-19T06:20:00Z",
          "endDate": "2026-09-19T13:00:00Z", "exerciseType": "SHOOTING",
          "trainingObjects": ["LV"], "noiseLevel": "LOW",
          "status": "STATUS_OLD"},
         {"id": 5, "startDate": "12.09.2026",
          "endDate": "14.09.2026", "exerciseType": "SHOOTING",
          "trainingObjects": [], "noiseLevel": "LOW",
          "status": "STATUS_OLD"},
         {"id": 6, "startDate": "2026-09-12T05:00:00Z",
          "endDate": "2026-09-14T15:00:00Z", "exerciseType": "TRAINING",
          "trainingObjects": [], "noiseLevel": "ULTRA",
          "status": "STATUS_NEW"}]},
    {"trainingAreaId": 12, "trainingAreaName": "SOODLA harjutusväli",
     "year": 2026, "month": 9, "approvedAt": "2026-09-10T08:00:00Z",
     "additionalInfo": "", "exercises": [
         {"id": 7, "startDate": "2026-09-10T05:00:00Z",
          "endDate": "2026-09-20T20:59:59Z", "exerciseType": "BLASTING",
          "trainingObjects": [], "noiseLevel": "AVERAGE",
          "status": "STATUS_NEW"}]},
    {"trainingAreaId": 13, "trainingAreaName": "NURSIPALU harjutusväli",
     "year": 2026, "month": 9, "approvedAt": "2026-09-10T08:00:00Z",
     "additionalInfo": "", "exercises": [
         {"id": 8, "startDate": "2026-09-10T05:00:00Z",
          "endDate": "2026-09-20T20:59:59Z", "exerciseType": "SHOOTING",
          "trainingObjects": [], "noiseLevel": "HIGH",
          "status": "STATUS_NEW"}]},
    {"trainingAreaId": 99, "trainingAreaName": "",
     "year": 2026, "month": 9, "approvedAt": None,
     "additionalInfo": "", "exercises": [
         {"id": 9, "startDate": "2026-09-12T05:00:00Z",
          "endDate": "2026-09-14T15:00:00Z", "exerciseType": "SHOOTING",
          "trainingObjects": [], "noiseLevel": "HIGH",
          "status": "STATUS_NEW"}]},
])

# Synthetic mapdata fixture: invented squares near the real Männiku
# magnitude (projection math needs realistic input) - never live rings.
# Built programmatically so the nesting stays obviously balanced.
def _sq(x0, y0, size=1000.0):
    return [[x0, y0], [x0 + size, y0], [x0 + size, y0 + size],
            [x0, y0 + size], [x0, y0]]


def _map_area(area_id, area, x0, y0, phone=None, email=None,
              n_objects=0, rings=True):
    geoms = ([{"type": "Polygon", "coordinates": [_sq(x0, y0)]}]
             if rings else [])
    return {"trainingAreaId": area_id, "trainingAreaName": area,
            "contactPhone": phone, "contactEmail": email,
            "shape": {"type": "GeometryCollection",
                      "crs": {"type": "name",
                              "properties": {"name": "EPSG:3857"}},
                      "geometries": geoms},
            "trainingObjects": [
                {"id": 11, "name": "fixture", "code": "LP1",
                 "shape": {"type": "GeometryCollection",
                           "geometries": []}}][:n_objects]}


MAPDATA_JSON = json.dumps([
    _map_area(8, "MÄNNIKU harjutusväli", 2750000.0, 8250000.0,
              phone="+372 0000 0000", email="fixture@example.invalid",
              n_objects=1),
    _map_area(12, "SOODLA harjutusväli", 2760000.0, 8230000.0),
    _map_area(77, "TÜHI ALA", 0.0, 0.0, rings=False),
    {"trainingAreaId": 98, "trainingAreaName": "",
     "contactPhone": None, "contactEmail": None,
     "shape": {"type": "GeometryCollection", "geometries": []},
     "trainingObjects": []},
])


def mkpoi(kind, lat=59.4372, lon=24.7546, **kw):
    poi = {"kind": kind, "lat": lat, "lon": lon}
    poi.update(kw)
    return poi


def expoi(area="MÄNNIKU harjutusväli", start="2026-09-12",
          end="2026-09-14", noise="LOW", exkind="TACTICS", **kw):
    return mkpoi("exercisenoise_kvagi", area=area, start=start,
                 end=end, noise=noise, exkind=exkind, **kw)


# ---------------------------------------------------------------------------
# Ingestion: TTL defaults, source URLs, cache-hit silence, honest errors.
# ---------------------------------------------------------------------------

def test_ttl_defaults_are_stated():
    assert SCHEDULE_TTL_S == 24 * 3600  # ~1 week ahead, live changes
    assert MAPDATA_TTL_S == 90 * 24 * 3600  # polygons/contacts stable


def test_source_urls_point_at_verified_snapshots():
    assert SCHEDULE_URL == ("https://mil.ee/wp-content/uploads/"
                            "training-grounds/training_ground_schedule.json")
    assert MAPDATA_URL == ("https://mil.ee/wp-content/uploads/"
                           "training-grounds/training_ground_mapdata.json")
    assert AVAANDMED_URL == ("https://mil.ee/kaitsevagi/harjutusvaljad/"
                             "valjaoppealade-avaandmed/")
    assert "#297" in KVAGI_UA


def _boom(*a, **k):
    raise AssertionError("network touched")


def test_fetch_cache_hit_makes_no_request(tmp_path, monkeypatch):
    cached = tmp_path / "training_ground_schedule.json"
    cached.write_text("x" * 8192, encoding="utf-8")
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "training_ground_schedule.json") == str(cached)


def test_fetch_transport_error_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    def _fail(*a, **k):
        raise urllib.error.URLError("down")
    monkeypatch.setattr("urllib.request.urlopen", _fail)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "training_ground_schedule.json") is None
    assert list(tmp_path.iterdir()) == []


def test_fetch_short_body_is_not_cached_as_data(tmp_path, monkeypatch):
    class _Resp:
        status = 200

        def read(self):
            return b"tiny"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _Resp())
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "training_ground_schedule.json") is None
    assert list(tmp_path.iterdir()) == []


def test_scorers_never_touch_network(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    pois = [expoi()]
    assert dim_exercise_noise_zone(TALLINN, pois, TODAY)[0] == 50
    assert dim_exercise_season_calendar(TALLINN, pois, TODAY)[0] == 45
    assert dim_manniku_weekend_calendar(TALLINN, pois, TODAY)[0] == 45
    assert score_p4_kvagi(TALLINN, pois, TODAY) == {
        "exercise_noise_zone": 50, "exercise_season_calendar": 45,
        "manniku_weekend_calendar": 45}


# ---------------------------------------------------------------------------
# Readers: observed layout, dateless malformed, keyless rows skipped.
# ---------------------------------------------------------------------------

def test_parse_schedule_reads_observed_layout():
    recs = parse_schedule(json.loads(SCHEDULE_JSON))
    assert [r["area"] for r in recs] == [
        "MÄNNIKU harjutusväli", "SOODLA harjutusväli",
        "NURSIPALU harjutusväli"]
    man = recs[0]
    assert (man["area_id"], man["year"], man["month"]) == (8, 2026, 9)
    assert man["approved_at"] == "2026-09-11T09:17:55Z"
    first = man["entries"][0]
    assert first["start_day"] == "2026-09-12"  # day grain, time dropped
    assert first["end_day"] == "2026-09-14"
    assert first["kind"] == "TACTICS" and first["noise"] == "LOW"
    assert first["objects"] == ["LA1"]
    assert man["entries"][1]["noise"] == "ABSENT"  # kept raw, scorer filters


def test_parse_schedule_keeps_malformed_dateless_and_skips_keyless():
    recs = parse_schedule(json.loads(SCHEDULE_JSON))
    man = recs[0]
    malformed = next(e for e in man["entries"] if e["id"] == 5)
    assert malformed["start_day"] is None  # non-ISO stays dateless
    assert malformed["end_day"] is None
    unknown = next(e for e in man["entries"] if e["id"] == 6)
    assert unknown["noise"] == "ULTRA"  # unknown token kept raw, never mapped
    assert parse_schedule("not-a-list") == []
    assert parse_schedule([{"trainingAreaName": "  "}]) == []


def test_parse_mapdata_anchors_through_inverse_mercator():
    recs = parse_mapdata(json.loads(MAPDATA_JSON))
    assert [r["area"] for r in recs] == [
        "MÄNNIKU harjutusväli", "SOODLA harjutusväli", "TÜHI ALA"]
    man = recs[0]
    assert man["area_id"] == 8 and man["n_objects"] == 1
    assert man["contact"] == {"phone": "+372 0000 0000",
                              "email": "fixture@example.invalid"}
    # Golden bbox-centre values (independent check below pins the math).
    assert man["anchor"] == pytest.approx((59.32286472537928,
                                           24.70816189314684), abs=1e-9)
    assert recs[1]["anchor"] == pytest.approx((59.23107700461846,
                                               24.797993421571295), abs=1e-9)
    assert recs[2]["anchor"] is None  # no rings: never guessed
    assert parse_mapdata({"not": "a list"}) == []


def test_inverse_mercator_matches_definition():
    # Exact origin case needs no oracle.
    assert mercator_to_wgs84(0.0, 0.0) == (0.0, 0.0)
    # Forward definition re-derived here (different expression from the
    # inverse): roundtrip must hold to sub-metre precision.
    half = 20037508.34
    for lat, lon in [(59.4372, 24.7536), (59.32286472, 24.70816189),
                     (-33.8688, 151.2093)]:
        x = lon / 180.0 * half
        y = half / math.pi * math.log(math.tan(
            math.pi / 4 + math.radians(lat) / 2))
        back = mercator_to_wgs84(x, y)
        assert back == pytest.approx((lat, lon), abs=1e-9)


def test_index_by_area_month_first_row_wins():
    recs = parse_schedule(json.loads(SCHEDULE_JSON))
    idx = index_by_area_month(recs)
    assert set(idx) == {("MÄNNIKU harjutusväli", 2026, 9),
                        ("SOODLA harjutusväli", 2026, 9),
                        ("NURSIPALU harjutusväli", 2026, 9)}
    dup = recs[0].copy()
    assert index_by_area_month([dup, recs[0]])[
        ("MÄNNIKU harjutusväli", 2026, 9)] is dup


def test_window_state_and_weekend_helpers():
    assert _window_state("2026-09-12", "2026-09-14", TODAY) == "active"
    assert _window_state("2026-09-01", "2026-09-05", TODAY) == "expired"
    assert _window_state("2026-09-19", "2026-09-20", TODAY) == "future"
    assert _window_state(None, "2026-09-14", TODAY) is None
    assert _window_state("12.09.2026", "14.09.2026", TODAY) is None
    assert _overlaps_weekend("2026-09-12", "2026-09-14") is True  # Sat-Mon
    assert _overlaps_weekend("2026-09-13", "2026-09-13") is True  # Sun only
    assert _overlaps_weekend("2026-09-14", "2026-09-18") is False  # Mon-Fri
    assert _overlaps_weekend("2026-09-11", "2026-09-14") is True  # Fri-Mon
    assert _overlaps_weekend("2026-09-10", "2026-09-20") is True
    assert _overlaps_weekend("bad", "2026-09-14") is False
    assert _overlaps_weekend("2026-09-14", "2026-09-12") is False


# ---------------------------------------------------------------------------
# P4-023: zone join over the exercise leg, never gradient.
# ---------------------------------------------------------------------------

def test_p23_active_entry_scores_flat_band():
    near = [expoi()]
    far = [expoi(lon=24.7620)]  # ~460 m east, still joined
    assert dim_exercise_noise_zone(TALLINN, near, TODAY)[0] == 50
    v, reason = dim_exercise_noise_zone(TALLINN, far, TODAY)
    assert v == 50  # farther but same zone hit -> same score, no gradient
    assert "hinnang" in reason and "MÄNNIKU" in reason
    assert "kaugusgradient" in reason


def test_p23_band_and_gate_constants():
    assert EXERCISE_ZONE_SCORE == 50  # mirrors the EANS/trans õppus band
    assert AUDIBLE_WINDOW_M == 3000.0
    assert set(TALLINN_AUDIBLE_AREAS) == {
        "MÄNNIKU harjutusväli", "SOODLA harjutusväli",
        "SIRGALA harjutusväli", "KAITSEVÄE KESKPOLÜGOON"}
    assert set(SCORING_NOISES) == {"LOW", "AVERAGE", "HIGH", "VERY_HIGH"}


def test_p23_soodla_leg_scores_nursipalu_never():
    v, reason = dim_exercise_noise_zone(
        TALLINN, [expoi(area="SOODLA harjutusväli", start="2026-09-10",
                        end="2026-09-20", noise="AVERAGE")], TODAY)
    assert v == 50 and "SOODLA" in reason
    v, reason = dim_exercise_noise_zone(
        TALLINN, [expoi(area="NURSIPALU harjutusväli", start="2026-09-10",
                        end="2026-09-20", noise="HIGH")], TODAY)
    assert v is None  # outside the audible set: no join, never quiet
    assert "EI OLE" in reason


def test_p23_silent_expired_future_dateless_stay_null():
    silent = [expoi(noise="ABSENT")]
    v, reason = dim_exercise_noise_zone(TALLINN, silent, TODAY)
    assert v is None and "EI OLE" in reason  # silent tactics, not quiet
    expired = [expoi(start="2026-09-01", end="2026-09-05", noise="HIGH")]
    assert dim_exercise_noise_zone(TALLINN, expired, TODAY)[0] is None
    future = [expoi(start="2026-09-19", end="2026-09-20")]
    v, reason = dim_exercise_noise_zone(TALLINN, future, TODAY)
    assert v is None and "EI OLE" in reason
    dateless = [expoi(start=None, end=None)]
    assert dim_exercise_noise_zone(TALLINN, dateless, TODAY)[0] is None
    unknown = [expoi(noise="ULTRA")]
    assert dim_exercise_noise_zone(TALLINN, unknown, TODAY)[0] is None


def test_p23_no_join_and_missing_input_are_null():
    assert dim_exercise_noise_zone(TALLINN, [], TODAY)[0] is None
    far = [expoi(lat=59.50, lon=24.90)]  # ~9 km, beyond the 3 km gate
    v, reason = dim_exercise_noise_zone(TALLINN, far, TODAY)
    assert v is None
    assert "EI OLE" in reason and "mõõdetud vaikus" in reason
    for origin, pois in [(None, [expoi()]), (TALLINN, None), (None, None)]:
        v, reason = dim_exercise_noise_zone(origin, pois, TODAY)
        assert v is None
        assert "EI OLE" in reason


def test_p23_skips_malformed_and_foreign_pois():
    pois = [{"kind": "exercisenoise_kvagi", "lat": "x", "lon": 24.7546,
             "area": "MÄNNIKU harjutusväli", "start": "2026-09-12",
             "end": "2026-09-14", "noise": "LOW"},
            {"kind": "schednuisance_eans", "lat": 59.4372, "lon": 24.7546,
             "label": "männiku", "start": "2026-09-12",
             "end": "2026-09-14"},  # EANS slice: not this dim's kind
            {"kind": "exercisenoise_kvagi", "lat": True, "lon": 24.7546,
             "area": "MÄNNIKU harjutusväli", "start": "2026-09-12",
             "end": "2026-09-14", "noise": "LOW"},
            expoi(noise="AVERAGE")]
    v, _ = dim_exercise_noise_zone(TALLINN, pois, TODAY)
    assert v == 50  # only the well-formed kvagi slice POI counts


# ---------------------------------------------------------------------------
# P4-033: seasonal exercise-week calendar with dates.
# ---------------------------------------------------------------------------

def test_p33_active_week_scores_flat_with_dates():
    v, reason = dim_exercise_season_calendar(TALLINN, [expoi()], TODAY)
    assert v == EXERCISE_CALENDAR_SCORE == 45
    assert "hinnang" in reason and "2026-09-14" in reason  # prints dates


def test_p33_silent_and_stale_entries_stay_null():
    assert dim_exercise_season_calendar(
        TALLINN, [expoi(noise="ABSENT")], TODAY)[0] is None
    assert dim_exercise_season_calendar(
        TALLINN, [expoi(start="2026-09-01", end="2026-09-05",
                        noise="HIGH")], TODAY)[0] is None
    assert dim_exercise_season_calendar(
        TALLINN, [expoi(start="2026-09-19", end="2026-09-20")],
        TODAY)[0] is None
    v, reason = dim_exercise_season_calendar(TALLINN, [], TODAY)
    assert v is None
    assert "EI OLE" in reason and "mõõdetud vaikus" in reason


def test_p33_missing_input_is_null():
    for origin, pois in [(None, [expoi()]), (TALLINN, None), (None, None)]:
        v, reason = dim_exercise_season_calendar(origin, pois, TODAY)
        assert v is None
        assert "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-055: Männiku weekend-pops calendar.
# ---------------------------------------------------------------------------

def test_p55_weekend_manniku_scores_flat():
    v, reason = dim_manniku_weekend_calendar(TALLINN, [expoi()], TODAY)
    assert v == EXERCISE_CALENDAR_SCORE == 45
    assert "hinnang" in reason and "Männiku" in reason


def test_p55_weekday_only_entry_stays_null():
    weekday = [expoi(start="2026-09-14", end="2026-09-18")]  # Mon-Fri
    v, reason = dim_manniku_weekend_calendar(TALLINN, weekday, TODAY)
    assert v is None and "EI OLE" in reason


def test_p55_non_manniku_audible_area_stays_null():
    soodla = [expoi(area="SOODLA harjutusväli", start="2026-09-12",
                    end="2026-09-14", noise="AVERAGE")]  # Sat-Mon, not Männiku
    v, reason = dim_manniku_weekend_calendar(TALLINN, soodla, TODAY)
    assert v is None and "EI OLE" in reason


def test_p55_future_weekend_pops_stay_null_until_start_day():
    future = [expoi(start="2026-09-19", end="2026-09-20")]  # Sat-Sun ahead
    v, reason = dim_manniku_weekend_calendar(TALLINN, future, TODAY)
    assert v is None and "EI OLE" in reason
    v, _ = dim_manniku_weekend_calendar(TALLINN, future, "2026-09-19")
    assert v == 45  # impact starts on the start day


def test_p55_missing_input_is_null():
    for origin, pois in [(None, [expoi()]), (TALLINN, None), (None, None)]:
        v, reason = dim_manniku_weekend_calendar(origin, pois, TODAY)
        assert v is None
        assert "EI OLE" in reason


# ---------------------------------------------------------------------------
# Cross-cutting: registry, aggregator, honesty markers.
# ---------------------------------------------------------------------------

def test_scored_reasons_say_hinnang_never_guarantee():
    for fn in ALL_FNS:
        v, reason = fn(TALLINN, [expoi()], TODAY)
        assert v is not None and "hinnang" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_null_reasons_name_the_missing_kvagi_input():
    _, r1 = dim_exercise_noise_zone(None, None, TODAY)
    assert "Brontose" in r1
    _, r2 = dim_exercise_season_calendar(None, None, TODAY)
    assert "Brontose" in r2
    _, r3 = dim_manniku_weekend_calendar(None, None, TODAY)
    assert "Männiku" in r3


def test_registry_and_aggregator_cover_all_three():
    assert [(k, p) for k, p, _ in p4k.P4_KVAGI_DIMS] == [
        ("exercise_noise_zone", "P4-023"),
        ("exercise_season_calendar", "P4-033"),
        ("manniku_weekend_calendar", "P4-055")]
    assert len({fn for _, _, fn in p4k.P4_KVAGI_DIMS}) == 3
    out = score_p4_kvagi(TALLINN, [expoi()], TODAY)
    assert out == {"exercise_noise_zone": 50,
                   "exercise_season_calendar": 45,
                   "manniku_weekend_calendar": 45}
    assert score_p4_kvagi(TALLINN, [], TODAY) == {
        "exercise_noise_zone": None, "exercise_season_calendar": None,
        "manniku_weekend_calendar": None}
    assert score_p4_kvagi(None, None, TODAY) == {
        "exercise_noise_zone": None, "exercise_season_calendar": None,
        "manniku_weekend_calendar": None}
    assert p4k.P4_KVAGI_DIMS is p4k.P4_KVAGI_DIMS


def test_network_lives_only_in_fetch_cached():
    import inspect
    src = inspect.getsource(p4k)
    assert src.count("urlopen") == 1  # the fetch_cached pull, nowhere else
    assert "httpx" not in src
    assert "requests.get" not in src
