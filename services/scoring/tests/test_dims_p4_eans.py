"""P4 EANS dims (issues #296 + #366): hermetic tests.

No network: EANS publishes no keyless machine-readable noise-zone feed
(dated negative - see the module docstring), so every test runs on
fixture CSV snapshots mirroring the documented layout plus hand-built
POIs (polygons are joined offline; street/area labels become
coordinates only via the documented ADS/Maa-amet step). The polite
fetcher is covered via a stubbed urlopen (cache-hit performs no
request; transport errors and short bodies return None and cache
nothing); scorers are proven network-free by running them with urlopen
stubbed to raise, on a fixed calendar cursor.
"""

import urllib.error

import dims_p4_eans as p4e
import pytest
from dims_p4_eans import (
    EANS_NUISANCES,
    EANS_URL,
    EANS_ZONES,
    MYRAKAART_URL,
    NOISE_TOPIC_URL,
    NOISE_ZONE_SCORES,
    NOTICES_TTL_S,
    NUISANCE_ACTIVE_SCORE,
    NUISANCE_WINDOW_M,
    SADAM_SCHEDULE_URL,
    ZONES_TTL_S,
    dim_airport_noise_zone,
    dim_harbour_air_calendar,
    fetch_cached,
    index_by_zone,
    parse_noise_zones,
    parse_schedule_notices,
    score_p4_eans,
)

# Tallinn centre: hand-built POIs sit ~57 m east unless stated.
TALLINN = (59.4372, 24.7536)
# Fixed calendar cursor: every expiry assertion is hermetic.
TODAY = "2026-09-13"

ALL_FNS = [dim_airport_noise_zone, dim_harbour_air_calendar]

ZONE_CSV = (
    "zone_key;zone;source;updated\n"
    "lasna-approach;lennumüra;EANS;2026-09-01\n"
    "sadam-heli;sadam;Sadam;2026-08-15\n"
    "soodla-edge;õppus;Kaitsevägi;2026-07-01\n"
)

NOTICE_CSV = (
    "notice_key;label;start;end;area\n"
    "f2026-38;udusignaal;2026-09-10;2026-09-20;Vanasadam\n"
    "ice-01;jäämurre;2026-01-05;2026-02-28;Tallinna laht\n"
    "amari-w38;ämari;2026-09-12;2026-09-14;Põhja-Tallinn\n"
)


def mkpoi(kind, lat=59.4372, lon=24.7546, **kw):
    poi = {"kind": kind, "lat": lat, "lon": lon}
    poi.update(kw)
    return poi


def zonepoi(zone="lennumüra", **kw):
    return mkpoi("noisezone_eans", zone=zone, **kw)


def nuisancepoi(label="udusignaal", start="2026-09-01",
                end="2026-09-30", **kw):
    return mkpoi("schednuisance_eans", label=label,
                 start=start, end=end, **kw)


# ---------------------------------------------------------------------------
# Ingestion: TTL defaults, cache-hit silence, honest errors. No network.
# ---------------------------------------------------------------------------

def test_ttl_defaults_are_stated():
    assert ZONES_TTL_S == 90 * 24 * 3600  # END 5-year cycle, quarterly check
    assert NOTICES_TTL_S == 7 * 24 * 3600  # weekly sailing/firing cadence


def test_source_urls_point_at_verified_pages():
    assert EANS_URL == "https://www.eans.ee/"
    assert NOISE_TOPIC_URL == "https://transpordiamet.ee/mura-ja-valisohk"
    assert MYRAKAART_URL == "https://xgis.maaamet.ee/xgis2/page/app/myrakaart"
    assert SADAM_SCHEDULE_URL == "https://www.ts.ee/saabuvad-liinireisid/"


def _boom(*a, **k):
    raise AssertionError("network touched")


def test_fetch_cache_hit_makes_no_request(tmp_path, monkeypatch):
    cached = tmp_path / "zones.csv"
    cached.write_text("x" * 128, encoding="utf-8")
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "zones.csv") == str(cached)


def test_fetch_transport_error_returns_none_and_caches_nothing(
        tmp_path, monkeypatch):
    def _fail(*a, **k):
        raise urllib.error.URLError("down")
    monkeypatch.setattr("urllib.request.urlopen", _fail)
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "zones.csv") is None
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
                        "zones.csv") is None
    assert list(tmp_path.iterdir()) == []


def test_scorers_never_touch_network(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _boom)
    pois = [zonepoi(), nuisancepoi()]
    assert dim_airport_noise_zone(TALLINN, pois)[0] == 35
    assert dim_harbour_air_calendar(TALLINN, pois, TODAY)[0] == \
        NUISANCE_ACTIVE_SCORE
    assert score_p4_eans(TALLINN, pois, TODAY) == {
        "airport_noise_eans": 35, "harbour_air_calendar": 45}


# ---------------------------------------------------------------------------
# Readers: documented layout, unknown tokens NULL, keyless rows skipped.
# ---------------------------------------------------------------------------

def test_parse_noise_zones_reads_documented_layout():
    recs = parse_noise_zones(ZONE_CSV)
    assert [r["zone_key"] for r in recs] == [
        "lasna-approach", "sadam-heli", "soodla-edge"]
    assert [r["zone"] for r in recs] == ["lennumüra", "sadam", "õppus"]
    assert recs[0]["source"] == "EANS" and recs[0]["updated"] == "2026-09-01"


def test_parse_noise_zones_never_guesses():
    recs = parse_noise_zones(
        "zone_key;zone;source;updated\n"
        "a;lennumüra;;\n"
        "b;AIRPORT;;\n"  # unknown token -> None, row kept (joinable key)
        ";lennumüra;;\n"  # keyless row skipped (would fake coverage)
        "c;;;\n")  # empty label -> None
    assert [(r["zone_key"], r["zone"]) for r in recs] == [
        ("a", "lennumüra"), ("b", None), ("c", None)]


def test_parse_noise_zones_tolerates_bom():
    recs = parse_noise_zones("\ufeffzone_key;zone;source;updated\na;lennumüra;;\n")
    assert recs == [{"zone_key": "a", "zone": "lennumüra",
                     "source": None, "updated": None}]


def test_parse_schedule_notices_reads_documented_layout():
    recs = parse_schedule_notices(NOTICE_CSV)
    assert [r["notice_key"] for r in recs] == ["f2026-38", "ice-01",
                                              "amari-w38"]
    assert [r["label"] for r in recs] == ["udusignaal", "jäämurre", "ämari"]
    assert recs[0]["area"] == "Vanasadam"


def test_parse_schedule_notices_keeps_dates_raw_and_skips_keyless():
    recs = parse_schedule_notices(
        "notice_key;label;start;end;area\n"
        "n1;udusignaal;10.09.2026;20.09.2026;\n"  # non-ISO kept raw
        "n2;foghorn;2026-09-10;2026-09-20;\n"  # unknown label -> None
        ";udusignaal;2026-09-10;2026-09-20;\n")  # keyless skipped
    assert [(r["notice_key"], r["label"], r["start"]) for r in recs] == [
        ("n1", "udusignaal", "10.09.2026"), ("n2", None, "2026-09-10")]


def test_index_by_zone_first_row_wins():
    idx = index_by_zone(parse_noise_zones(
        "zone_key;zone;source;updated\n"
        "a;lennumüra;EANS;\n"
        "a;sadam;Sadam;\n"))
    assert idx == {"a": {"zone_key": "a", "zone": "lennumüra",
                         "source": "EANS", "updated": None}}


# ---------------------------------------------------------------------------
# P4-023: zone join, never gradient.
# ---------------------------------------------------------------------------

def test_p23_zone_band_scores_label_not_distance():
    near = [zonepoi("lennumüra")]
    far = [zonepoi("lennumüra", lon=24.7620)]  # ~460 m east, still joined
    assert dim_airport_noise_zone(TALLINN, near)[0] == 35
    v, reason = dim_airport_noise_zone(TALLINN, far)
    assert v == 35  # farther but same label -> same score, no gradient
    assert "hinnang" in reason and "tsoon lennumüra" in reason


@pytest.mark.parametrize("zone,want", [
    ("lennumüra", 35), ("õppus", 50), ("sadam", 60)])
def test_p23_all_zone_labels_score_quieter_up(zone, want):
    assert NOISE_ZONE_SCORES == {"lennumüra": 35, "õppus": 50, "sadam": 60}
    v, reason = dim_airport_noise_zone(TALLINN, [zonepoi(zone)])
    assert v == want, zone
    assert "hinnang" in reason and "kaugusgradient" in reason


def test_p23_outside_mapped_zones_is_null_not_quiet():
    assert dim_airport_noise_zone(TALLINN, [])[0] is None
    far = [zonepoi("lennumüra", lat=59.50, lon=24.90)]  # ~9 km away
    v, reason = dim_airport_noise_zone(TALLINN, far)
    assert v is None
    assert "EI OLE" in reason and "mõõdetud vaikus" in reason


def test_p23_unknown_label_is_null():
    v, reason = dim_airport_noise_zone(TALLINN, [zonepoi("tundmatu")])
    assert v is None
    assert "EI OLE" in reason and "tsoonimärgis" in reason


def test_p23_missing_input_is_null():
    for origin, pois in [(None, [zonepoi()]), (TALLINN, None),
                         (None, None)]:
        v, reason = dim_airport_noise_zone(origin, pois)
        assert v is None
        assert "EI OLE" in reason


def test_p23_skips_malformed_and_foreign_pois():
    pois = [{"kind": "noisezone_eans", "lat": "x", "lon": 24.7546,
             "zone": "lennumüra"},
            {"kind": "noisezone_p4", "lat": 59.4372, "lon": 24.7546,
             "zone": "lennumüra"},  # trans slice: not this dim's kind
            {"kind": "noisezone_eans", "lat": True, "lon": 24.7546,
             "zone": "lennumüra"},
            zonepoi("sadam")]
    v, _ = dim_airport_noise_zone(TALLINN, pois)
    assert v == 60  # only the well-formed EANS slice POI counts


# ---------------------------------------------------------------------------
# P4-055: calendar dim with expiry.
# ---------------------------------------------------------------------------

def test_p55_active_notice_scores_flat_exposure():
    v, reason = dim_harbour_air_calendar(TALLINN, [nuisancepoi()], TODAY)
    assert v == NUISANCE_ACTIVE_SCORE == 45
    assert "hinnang" in reason and "kehtib kuni 2026-09-30" in reason


def test_p55_all_nuisance_labels_score_when_active():
    assert set(EANS_NUISANCES) == {"udusignaal", "jäämurre", "ämari",
                                   "männiku"}
    for label in EANS_NUISANCES:
        v, _ = dim_harbour_air_calendar(TALLINN, [nuisancepoi(label)], TODAY)
        assert v == 45, label


def test_p55_expired_future_and_dateless_stay_null():
    v, reason = dim_harbour_air_calendar(
        TALLINN, [nuisancepoi(end="2026-09-01")], TODAY)
    assert v is None and "EI OLE" in reason and "aegunud" in reason
    v, reason = dim_harbour_air_calendar(
        TALLINN, [nuisancepoi(start="2026-10-01", end="2026-10-07")], TODAY)
    assert v is None and "EI OLE" in reason and "2026-10-01" in reason
    v, reason = dim_harbour_air_calendar(
        TALLINN, [nuisancepoi(start=None, end=None)], TODAY)
    assert v is None and "EI OLE" in reason and "kuupäevata" in reason
    v, _ = dim_harbour_air_calendar(  # non-ISO dates can never score
        TALLINN, [nuisancepoi(start="10.09.2026", end="20.09.2026")], TODAY)
    assert v is None


def test_p55_no_join_is_null_not_quiet():
    v, reason = dim_harbour_air_calendar(TALLINN, [], TODAY)
    assert v is None
    assert "EI OLE" in reason and "mõõdetud vaikus" in reason
    far = [nuisancepoi(lat=59.50, lon=24.90)]  # ~9 km, beyond 2 km gate
    assert dim_harbour_air_calendar(TALLINN, far, TODAY)[0] is None


def test_p55_propagation_gate_is_two_km():
    assert NUISANCE_WINDOW_M == 2000.0
    edge = [nuisancepoi(lat=59.4372, lon=24.7850)]  # ~1.8 km east
    assert dim_harbour_air_calendar(TALLINN, edge, TODAY)[0] == 45


def test_p55_missing_input_is_null():
    for origin, pois in [(None, [nuisancepoi()]), (TALLINN, None),
                         (None, None)]:
        v, reason = dim_harbour_air_calendar(origin, pois, TODAY)
        assert v is None
        assert "EI OLE" in reason


def test_p55_mixed_states_prefer_active():
    pois = [nuisancepoi(end="2026-09-01"),  # expired
            nuisancepoi(label="ämari")]  # active
    v, reason = dim_harbour_air_calendar(TALLINN, pois, TODAY)
    assert v == 45 and "2 kehtivat" not in reason and "1 kehtivat" in reason


# ---------------------------------------------------------------------------
# Cross-cutting: registry, aggregator, honesty markers.
# ---------------------------------------------------------------------------

def test_scored_reasons_say_hinnang_never_guarantee():
    v, r1 = dim_airport_noise_zone(TALLINN, [zonepoi()])
    assert v is not None and "hinnang" in r1
    v, r2 = dim_harbour_air_calendar(TALLINN, [nuisancepoi()], TODAY)
    assert v is not None and "hinnang" in r2
    for r in (r1, r2):
        assert "mõõdetud" not in r and "garanteeritud" not in r


def test_null_reasons_name_the_missing_eans_input():
    _, r1 = dim_airport_noise_zone(None, None)
    assert "EANS" in r1 or "mürakaardi" in r1
    _, r2 = dim_harbour_air_calendar(None, None, TODAY)
    assert "teatekalendri" in r2


def test_registry_and_aggregator_cover_both():
    assert [(k, p) for k, p, _ in p4e.P4_EANS_DIMS] == [
        ("airport_noise_eans", "P4-023"),
        ("harbour_air_calendar", "P4-055")]
    assert len({fn for _, _, fn in p4e.P4_EANS_DIMS}) == 2
    out = score_p4_eans(TALLINN, [zonepoi("sadam"), nuisancepoi()], TODAY)
    assert out == {"airport_noise_eans": 60, "harbour_air_calendar": 45}
    assert score_p4_eans(TALLINN, [], TODAY) == {
        "airport_noise_eans": None, "harbour_air_calendar": None}
    assert score_p4_eans(None, None, TODAY) == {
        "airport_noise_eans": None, "harbour_air_calendar": None}
    assert p4e.P4_EANS_DIMS is p4e.P4_EANS_DIMS
