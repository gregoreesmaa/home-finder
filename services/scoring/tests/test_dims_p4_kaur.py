"""P4 KAUR dims (issues #285 + #359): hermetic tests.

No network: the per-parcel zone/station bulk endpoint does not exist
(2026-09-13 dated negative on the zone bulk; the open PostgREST host
is the re-pull anchor, not a joined slice), so every test runs on
fixture row-dicts and hand-built POIs. The polite fetcher is covered
via a stubbed urlopen (cache-hit performs no request; no-endpoint and
transport-error paths return None and cache nothing); scorers are
proven network-free by running them with urlopen stubbed to raise.
"""

import json
import os
import urllib.request

import dims_p4_kaur as p4k
from dims_p4_kaur import (
    BAN_ENFORCED_SCORE,
    BAN_QUIET_SCORE,
    CACHE_FILENAME,
    FLOOD_CLEAR_SCORE,
    COURT_OPEN_SCORE,
    COURT_VALIDATED_SCORE,
    COURT_WEAK_SCORE,
    DENSE_STATIONS_SCORE,
    DRY_GROUND_SCORE,
    EPISODE_QUIET_SCORE,
    EPISODE_SCORE,
    FEW_STATIONS_SCORE,
    FLOOD_SCORES,
    GW_CLEAR_SCORE,
    GW_SCORES,
    HARKU_ONLY_SCORE,
    KAUR_BULK_URL,
    KAUR_TTL_S,
    KAUR_UA,
    LIMIT_ENFORCED_SCORE,
    LIMIT_QUIET_SCORE,
    P4_KAUR_DIMS,
    POLLEN_SCORES,
    RATTLE_QUIET_SCORE,
    RATTLE_SCORE,
    SECTOR_OFTEN_SCORE,
    SECTOR_RARE_SCORE,
    SECTOR_SOMETIMES_SCORE,
    SURGE_CLEAR_SCORE,
    SURGE_EDGE_SCORE,
    BAD_GROUND_SCORE,
    MILD_GROUND_SCORE,
    dim_jaapurikas_kaur,
    dim_kindlustatavus_kaur,
    dim_louna_kaur,
    dim_lounarose_kaur,
    dim_mikrokliima_kaur,
    dim_mura_kaur,
    dim_pinnas_kaur,
    dim_sisehoov_kaur,
    dim_tahkekyte_kaur,
    dim_tervis_kaur,
    dim_varu_kaur,
    fetch_kaur_snapshot,
    parse_kaur_snapshot,
    score_p4_kaur,
    snapshot_to_pois,
    stations_to_pois,
    zones_to_pois,
)

TALLINN = (59.4372, 24.7536)
FAR = (58.3800, 26.7200)  # Tartu: outside every Tallinn window
NEAR_LAT = 59.4380  # ~90 m north of TALLINN (inside 300/500 m windows)
NEAR_LON = 24.7536
MID_LAT = 59.4472  # ~1.1 km north (inside station windows only)


def zone(lat, lon, zone, name="Tsoon"):
    return {"kind": "kaur_zone_p4", "lat": lat, "lon": lon,
            "zone_id": "z1", "name": name, "zone": zone}


def station(lat, lon, s_kind, name="Jaam", level=None, episode=None,
            rattle=None):
    return {"kind": "kaur_station_p4", "lat": lat, "lon": lon,
            "station_id": "s1", "name": name, "s_kind": s_kind,
            "level": level, "episode": episode, "rattle": rattle}


def ctx(ctx_kind, lat, lon, name="Kärg", **extra):
    poi = {"kind": "kaur_ctx_p4", "lat": lat, "lon": lon,
           "name": name, "ctx": ctx_kind}
    poi.update(extra)
    return poi


FLOOD_ROW = {"zone_id": "f1", "name": "Pirita T100", "zone": "t100",
             "lat": NEAR_LAT, "lon": NEAR_LON}
STATION_ROW = {"station_id": "s1", "name": "Tallinn-Harku", "s_kind": "met",
               "lat": 59.3986, "lon": 24.6029, "level": None,
               "episode": None, "rattle": None}


def write_snapshot(tmpdir, payload):
    path = os.path.join(str(tmpdir), CACHE_FILENAME)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
    return path


# ---------------------------------------------------------------------------
# Fetcher: polite, cached, TTL-stated; never the network in tests.
# ---------------------------------------------------------------------------

def test_fetch_cache_hit_performs_no_request(tmpdir, monkeypatch):
    payload = {"zones": [FLOOD_ROW], "stations": [STATION_ROW]}
    dest = write_snapshot(tmpdir, payload)

    def _boom(req, timeout=None):
        raise AssertionError("network used on cache hit")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert fetch_kaur_snapshot(str(tmpdir)) == dest


def test_fetch_no_endpoint_returns_none_and_caches_nothing(tmpdir,
                                                           monkeypatch):
    def _boom(req, timeout=None):
        raise AssertionError("network used without bulk endpoint")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert KAUR_BULK_URL is None
    assert fetch_kaur_snapshot(str(tmpdir)) is None
    assert os.listdir(str(tmpdir)) == []


def test_fetch_transport_error_caches_nothing(tmpdir, monkeypatch):
    class _Bad:
        def __enter__(self):
            raise IOError("down")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Bad())
    assert fetch_kaur_snapshot(str(tmpdir),
                               bulk_url="https://example.invalid/x") is None
    assert os.listdir(str(tmpdir)) == []


def test_fetch_non_json_body_caches_nothing(tmpdir, monkeypatch):
    class _Resp:
        status = 200
        headers = {"Content-Type": "text/html"}

        def read(self):
            return b"<html>pole json</html>"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: _Resp())
    assert fetch_kaur_snapshot(str(tmpdir),
                               bulk_url="https://example.invalid/x") is None
    assert os.listdir(str(tmpdir)) == []


def test_ttl_is_annual_and_ua_identifies(tmpdir):
    assert KAUR_TTL_S == 365 * 24 * 3600
    assert "home-finder" in KAUR_UA


# ---------------------------------------------------------------------------
# Offline readers: malformed rows skipped, missing file is unknown.
# ---------------------------------------------------------------------------

def test_parse_missing_and_garbage_is_none(tmpdir):
    assert parse_kaur_snapshot(os.path.join(str(tmpdir), "nope.json")) is None
    bad = os.path.join(str(tmpdir), "bad.json")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("{pole json")
    assert parse_kaur_snapshot(bad) is None
    lst = os.path.join(str(tmpdir), "lst.json")
    with open(lst, "w", encoding="utf-8") as fh:
        fh.write("[1,2]")
    assert parse_kaur_snapshot(lst) is None


def test_parse_keeps_dict_rows_for_converters(tmpdir):
    snap = {"zones": [FLOOD_ROW, "praht", None], "stations": [STATION_ROW]}
    parsed = parse_kaur_snapshot(write_snapshot(tmpdir, snap))
    assert parsed == {"zones": [FLOOD_ROW], "stations": [STATION_ROW]}
    assert parse_kaur_snapshot(write_snapshot(tmpdir, {})) == {
        "zones": [], "stations": []}


def test_zones_skip_unknown_tokens_and_bad_coords():
    rows = [dict(FLOOD_ROW),
            dict(FLOOD_ROW, zone="t5000"),  # unknown class: out
            dict(FLOOD_ROW, lat="mujal"),  # bad coord: out
            dict(FLOOD_ROW, lat=True),  # bool coord: out
            "praht"]
    pois = zones_to_pois(rows)
    assert len(pois) == 1 and pois[0]["zone"] == "t100"


def test_stations_skip_unknown_kinds_and_string_flags():
    rows = [dict(STATION_ROW),
            dict(STATION_ROW, s_kind="radar"),  # unknown kind: out
            dict(STATION_ROW, episode="jah", rattle="ei",  # not bools
                 level="väga kõrge")]  # unknown level -> None
    pois = stations_to_pois(rows)
    assert len(pois) == 2
    assert pois[1]["episode"] is None and pois[1]["rattle"] is None
    assert pois[1]["level"] is None


def test_snapshot_to_pois_none_is_empty():
    assert snapshot_to_pois(None) == []
    snap = {"zones": [FLOOD_ROW], "stations": [STATION_ROW]}
    assert len(snapshot_to_pois(snap)) == 2


# ---------------------------------------------------------------------------
# P4-015 demo: flood-zone bands + measured clear.
# ---------------------------------------------------------------------------

def test_p4_015_flood_bands_and_clear():
    assert dim_kindlustatavus_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "t10", "Pirita T10")])[0] == 25
    assert dim_kindlustatavus_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "t100")])[0] == FLOOD_SCORES["t100"]
    assert dim_kindlustatavus_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "surge")])[0] == 50
    assert dim_kindlustatavus_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "t1000")])[0] == 65
    v, reason = dim_kindlustatavus_kaur(
        TALLINN, [zone(*FAR, "t100", "Tartu T100")])
    assert v == FLOOD_CLEAR_SCORE and "hinnang" in reason
    v, reason = dim_kindlustatavus_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "t10", "Pirita T10")])
    assert "hinnang" in reason and "Pirita T10" in reason


def test_p4_015_null_without_snapshot_or_window():
    v, reason = dim_kindlustatavus_kaur(None, None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_kindlustatavus_kaur(TALLINN, None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_kindlustatavus_kaur(TALLINN, [])
    assert v is None and "EI OLE" in reason
    # groundwater-only snapshot is not a flood slice: still NULL
    v, reason = dim_kindlustatavus_kaur(
        TALLINN, [zone(*FAR, "gw_strict", "Kaitseala")])
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Coverage: zone-leg dims (P4-016, P4-046, P4-058).
# ---------------------------------------------------------------------------

def test_p4_016_groundwater_bands_and_clear():
    assert dim_pinnas_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "gw_strict")])[0] == 30
    assert dim_pinnas_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "gw_mild")])[0] == GW_SCORES[
        "gw_mild"]
    v, reason = dim_pinnas_kaur(
        TALLINN, [zone(*FAR, "gw_strict", "Kauge")])
    assert v == GW_CLEAR_SCORE and "hinnang" in reason
    assert "EGT" in reason  # sibling turvas/karst leg named
    v, reason = dim_pinnas_kaur(TALLINN, [])
    assert v is None and "EI OLE" in reason


def test_p4_046_bad_mild_and_dry():
    bad = [zone(NEAR_LAT, NEAR_LON, "t100")]
    v, reason = dim_varu_kaur(TALLINN, bad)
    assert v == BAD_GROUND_SCORE and "hinnang" in reason
    assert "varuväljapääsu" in reason  # sibling legs named
    v, _ = dim_varu_kaur(TALLINN, [zone(NEAR_LAT, NEAR_LON, "gw_strict")])
    assert v == BAD_GROUND_SCORE
    v, _ = dim_varu_kaur(TALLINN, [zone(NEAR_LAT, NEAR_LON, "t1000")])
    assert v == MILD_GROUND_SCORE
    v, reason = dim_varu_kaur(TALLINN, [zone(*FAR, "t10", "Kauge")])
    assert v == DRY_GROUND_SCORE and "hinnang" in reason
    v, reason = dim_varu_kaur(None, bad)
    assert v is None and "EI OLE" in reason


def test_p4_058_surge_edge_and_clear():
    v, reason = dim_jaapurikas_kaur(
        TALLINN, [zone(NEAR_LAT, NEAR_LON, "surge", "Kakumäe serv")])
    assert v == SURGE_EDGE_SCORE and "hinnang" in reason
    assert "Pääste" in reason  # ice-fall sibling named
    v, reason = dim_jaapurikas_kaur(
        TALLINN, [zone(*FAR, "surge", "Kauge serv")])
    assert v == SURGE_CLEAR_SCORE and "hinnang" in reason
    # T10 alone is not the surge slice: NULL, never clear
    v, reason = dim_jaapurikas_kaur(
        TALLINN, [zone(*FAR, "t10", "Kauge")])
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Coverage: station-leg dims (P4-023, P4-024, P4-031, P4-042).
# ---------------------------------------------------------------------------

def test_p4_023_rattle_quiet_and_unknown():
    v, reason = dim_mura_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "air", "Õhujaam", rattle=True)])
    assert v == RATTLE_SCORE and "hinnang" in reason
    assert "trans" in reason  # zone-gradient owner named
    v, _ = dim_mura_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "air", rattle=False)])
    assert v == RATTLE_QUIET_SCORE
    v, reason = dim_mura_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "air", rattle=None)])
    assert v is None and "EI OLE" in reason
    v, reason = dim_mura_kaur(
        TALLINN, [station(*FAR, "air", rattle=False)])
    assert v is None and "EI OLE" in reason


def test_p4_024_pollen_levels_and_unknown_label():
    assert dim_tervis_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "pollen", level="korge")]
    )[0] == POLLEN_SCORES["korge"]
    assert dim_tervis_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "pollen", level="keskmine")]
    )[0] == 55
    assert dim_tervis_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "pollen", level="madal")]
    )[0] == 70
    v, reason = dim_tervis_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "pollen", level=None)])
    assert v is None and "EI OLE" in reason
    v, reason = dim_tervis_kaur(TALLINN, None)
    assert v is None and "EI OLE" in reason


def test_p4_031_density_counts_with_sensor_reason():
    harku_far = [station(*FAR, "met", "Tallinn-Harku")]
    v, reason = dim_mikrokliima_kaur(TALLINN, harku_far)
    assert v == HARKU_ONLY_SCORE and "andurite arv 0" in reason
    one = [station(MID_LAT, NEAR_LON, "met", "Kalamaja"),
           station(*FAR, "wind", "Tallinn-Harku")]
    v, reason = dim_mikrokliima_kaur(TALLINN, one)
    assert v == FEW_STATIONS_SCORE and "andurite arv 1" in reason
    three = [station(MID_LAT, NEAR_LON, "met", "A"),
             station(59.4500, NEAR_LON, "wind", "B"),
             station(59.4520, NEAR_LON, "met", "C")]
    v, reason = dim_mikrokliima_kaur(TALLINN, three)
    assert v == DENSE_STATIONS_SCORE and "andurite arv 3" in reason
    v, reason = dim_mikrokliima_kaur(TALLINN, [])
    assert v is None and "EI OLE" in reason


def test_p4_042_episode_quiet_and_unknown():
    v, reason = dim_louna_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "air", episode=True)])
    assert v == EPISODE_SCORE and "hinnang" in reason
    assert "ukse-täpsus" in reason  # never doorway precision
    v, _ = dim_louna_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "air", episode=False)])
    assert v == EPISODE_QUIET_SCORE
    v, reason = dim_louna_kaur(
        TALLINN, [station(MID_LAT, NEAR_LON, "air", episode=None)])
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Coverage: context-cell dims (P4-053, P4-056, P4-059).
# ---------------------------------------------------------------------------

def test_p4_053_sector_calendar_never_circle():
    mk = lambda days: [ctx("sector", NEAR_LAT, NEAR_LON, "Paljassaare",
                           emitter="reoveepuhasti", downwind_days=days)]
    assert dim_lounarose_kaur(TALLINN, mk(20))[0] == SECTOR_OFTEN_SCORE
    assert dim_lounarose_kaur(TALLINN, mk(10))[0] == SECTOR_SOMETIMES_SCORE
    v, reason = dim_lounarose_kaur(TALLINN, mk(3))
    assert v == SECTOR_RARE_SCORE and "sektor" in reason
    assert "ringpuhver" in reason
    v, reason = dim_lounarose_kaur(
        TALLINN, [ctx("sector", NEAR_LAT, NEAR_LON, downwind_days="palju")])
    assert v is None and "EI OLE" in reason
    v, reason = dim_lounarose_kaur(
        TALLINN, [ctx("sector", NEAR_LAT, NEAR_LON, downwind_days=-2)])
    assert v is None and "EI OLE" in reason
    v, reason = dim_lounarose_kaur(
        TALLINN, [ctx("sector", *FAR, downwind_days=20)])
    assert v is None and "EI OLE" in reason


def test_p4_056_court_validated_weak_and_open():
    court = lambda enc: [ctx("court", NEAR_LAT, NEAR_LON, "Hoov",
                             enclosure=enc)]
    v, reason = dim_sisehoov_kaur(
        TALLINN, court("korge") + [station(MID_LAT, NEAR_LON, "air",
                                           episode=True)])
    assert v == COURT_VALIDATED_SCORE and "hinnang" in reason
    v, reason = dim_sisehoov_kaur(TALLINN, court("korge"))
    assert v == COURT_WEAK_SCORE and "hinnang" in reason
    assert "LiDAR" in reason  # morphology owner named
    v, _ = dim_sisehoov_kaur(TALLINN, court("keskmine"))
    assert v == COURT_OPEN_SCORE
    v, reason = dim_sisehoov_kaur(
        TALLINN, [ctx("court", NEAR_LAT, NEAR_LON, enclosure="avatud")])
    assert v is None and "EI OLE" in reason


def test_p4_059_enforcement_recency_not_the_rule():
    rule = lambda r: [ctx("burn_rule", NEAR_LAT, NEAR_LON, "Kesklinn", rule=r)]
    air_ep = [station(MID_LAT, NEAR_LON, "air", episode=True)]
    air_ok = [station(MID_LAT, NEAR_LON, "air", episode=False)]
    assert dim_tahkekyte_kaur(TALLINN, rule("keelatud") + air_ep)[0] == \
        BAN_ENFORCED_SCORE
    assert dim_tahkekyte_kaur(TALLINN, rule("keelatud") + air_ok)[0] == \
        BAN_QUIET_SCORE
    assert dim_tahkekyte_kaur(TALLINN, rule("piiratud") + air_ep)[0] == \
        LIMIT_ENFORCED_SCORE
    v, reason = dim_tahkekyte_kaur(TALLINN, rule("piiratud") + air_ok)
    assert v == LIMIT_QUIET_SCORE and "hinnang" in reason
    assert "pääste" in reason  # rule owner named
    # rule without a monitor: enforcement unjudgeable -> NULL
    v, reason = dim_tahkekyte_kaur(TALLINN, rule("keelatud"))
    assert v is None and "EI OLE" in reason
    v, reason = dim_tahkekyte_kaur(
        TALLINN, [ctx("burn_rule", NEAR_LAT, NEAR_LON, rule="soovitus")])
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Cross-cutting: honesty markers, registry, network-free scorers.
# ---------------------------------------------------------------------------

ALL_FNS = [fn for _, _, fn in P4_KAUR_DIMS]

EXPECTED_KEYS = ["kindlustatavus_kaur", "pinnas_kaur", "mura_kaur",
                 "tervis_kaur", "mikrokliima_kaur", "louna_kaur",
                 "varu_kaur", "lounarose_kaur", "sisehoov_kaur",
                 "jaapurikas_kaur", "tahkekyte_kaur"]

EXPECTED_PNUMS = ["P4-015", "P4-016", "P4-023", "P4-024", "P4-031", "P4-042",
                  "P4-046", "P4-053", "P4-056", "P4-058", "P4-059"]

RICH_POIS = [
    zone(NEAR_LAT, NEAR_LON, "t100", "Pirita T100"),
    zone(59.4385, NEAR_LON, "surge", "Kakumäe serv"),
    zone(59.4390, NEAR_LON, "gw_mild", "Mild"),
    station(MID_LAT, NEAR_LON, "air", "Õhujaam", episode=False,
            rattle=False),
    station(59.4480, NEAR_LON, "pollen", "Õietolm", level="madal"),
    station(59.4490, NEAR_LON, "met", "Kalamaja"),
    station(59.4500, NEAR_LON, "wind", "Tuul"),
    ctx("sector", NEAR_LAT, NEAR_LON, "Paljassaare",
        emitter="reoveepuhasti", downwind_days=3),
    ctx("court", NEAR_LAT, NEAR_LON, "Hoov", enclosure="keskmine"),
    ctx("burn_rule", NEAR_LAT, NEAR_LON, "Kesklinn", rule="piiratud"),
]


def test_all_null_reasons_carry_estonian_markers():
    for fn in ALL_FNS:
        _, reason = fn(None, None)
        assert "EI OLE" in reason, fn.__name__
        # a missing join is unknown, never an estimate: no hinnang claim
        assert "hinnang" not in reason, fn.__name__


def test_all_scored_reasons_say_hinnang_and_never_overclaim():
    for fn in ALL_FNS:
        v, reason = fn(TALLINN, RICH_POIS)
        assert v is not None, fn.__name__  # rich fixtures score everywhere
        assert "hinnang" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason
        assert v != 0 and v != 100, fn.__name__


def test_scores_stay_bounded_on_rich_fixtures():
    out = score_p4_kaur(TALLINN, RICH_POIS)
    assert set(out) == set(EXPECTED_KEYS)
    assert all(v is not None for v in out.values())


def test_registry_and_aggregator_cover_all_eleven():
    assert [k for k, _, _ in P4_KAUR_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_KAUR_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_KAUR_DIMS}) == 11
    assert all(k.endswith("_kaur") for k in EXPECTED_KEYS)
    out = score_p4_kaur(TALLINN, RICH_POIS)
    assert out == {k: fn(TALLINN, RICH_POIS)[0]
                   for k, _, fn in P4_KAUR_DIMS}
    assert score_p4_kaur(None, None) == {k: None for k in EXPECTED_KEYS}
    assert p4k.P4_KAUR_DIMS is P4_KAUR_DIMS


def test_scorers_use_no_network(monkeypatch):
    def _boom(req, timeout=None):
        raise AssertionError("network used by scorer")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    assert score_p4_kaur(TALLINN, RICH_POIS)["kindlustatavus_kaur"] == 45
    assert score_p4_kaur(None, None) == {k: None for k in EXPECTED_KEYS}

