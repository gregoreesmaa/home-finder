"""P4 sensor.community dims (issue #306): hermetic tests.

No network: fetch_senscom_dump is never called for a live pull
here (its contract — single polite GET, file cache, TTL,
transport errors raise — is covered via the pure cache_is_fresh
helper plus a cache-hit fetch test that performs no GET).
Fixtures are fully synthetic (clearly labelled) and model only
the observed 2026-09-13 field names (`location{latitude,
longitude, indoor}`, `sensor{sensor_type{name}}`); real observed
values appear only in docs/p4_senscom.md section 1, never as
ingested data.
"""

import json

import dims_p4_senscom as senscom
from dims_p4_senscom import (
    P4_SENSCOM_DIMS,
    P4_SENSCOM_PARAM_IDS,
    SENSCOM_RADIUS_M,
    SENSCOM_TTL_S,
    SENSCOM_CACHE_NAME,
    SENSCOM_DATA_URL,
    SENSCOM_SNAPSHOT_NAME,
    cache_is_fresh,
    dim_backyard_air,
    fetch_senscom_dump,
    load_senscom_snapshot,
    parse_senscom_dump,
    score_p4_senscom,
    snapshot_cache_path,
    tallinn_extract,
)

TALLINN = (59.4372, 24.7536)
TARTU = (58.3780, 26.7280)  # far outside the Tallinn extract
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]


def _rec(loc_id, lat, lon, indoor, stype, rec_id=1):
    """One synthetic observation record shaped like the live feed."""
    loc = {"id": loc_id, "country": "EE", "exact_location": 1}
    if lat is not None:
        loc["latitude"] = lat
    if lon is not None:
        loc["longitude"] = lon
    if indoor != "missing":
        loc["indoor"] = indoor
    return {"id": rec_id, "timestamp": "2026-09-13 12:00:00",
            "location": loc,
            "sensor": {"id": 10 + rec_id,
                       "sensor_type": {"id": 14, "name": stype,
                                       "manufacturer": "synthetic"}},
            "sensordatavalues": [{"value_type": "P1", "value": "8.4"}]}


#: Synthetic dump: loc 901 at the origin with TWO boards (dedup ->
#: one witness, two types); 902 ~300 m away; 903 indoor Tallinn
#: (skipped); 904 coordless (skipped); 905 flagless (skipped
#: fail-closed); 906 outdoor Tartu (parsed, extract-dropped);
#: plus junk rows (skipped).
SYNTH_DUMP = json.dumps([
    _rec(901, "59.4372", "24.7536", 0, "SDS011", rec_id=1),
    _rec(901, "59.4372", "24.7536", 0, "BME280", rec_id=2),
    _rec(902, "59.4395", "24.7555", 0, "PMS5003", rec_id=3),
    _rec(903, "59.4372", "24.7536", 1, "SDS011", rec_id=4),
    _rec(904, None, None, 0, "SDS011", rec_id=5),
    _rec(905, "59.4372", "24.7536", "missing", "SDS011", rec_id=6),
    _rec(906, "58.3780", "26.7280", 0, "SDS011", rec_id=7),
    "junk-row",
    {"id": 8, "location": {"id": 907, "latitude": "999.0",
                           "longitude": "24.75", "indoor": 0},
     "sensor": {"sensor_type": {"name": "SDS011"}}},
])

TLL = tallinn_extract(parse_senscom_dump(SYNTH_DUMP), fetched="2026-09-13")


def _loc(lid, lat, lon, types=("SDS011",)):
    return {"id": lid, "lat": lat, "lon": lon, "types": list(types)}


# ---------------------------------------------------------------------------
# Ingestion: parse + join + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_dedups_boards_into_one_witness():
    locs = {loc["id"]: loc for loc in parse_senscom_dump(SYNTH_DUMP)}
    assert locs[901]["lat"] == 59.4372
    assert sorted(locs[901]["types"]) == ["BME280", "SDS011"]


def test_parse_skips_indoor_flagless_coordless_and_junk():
    ids = {loc["id"] for loc in parse_senscom_dump(SYNTH_DUMP)}
    assert ids == {901, 902, 906}


def test_parse_raises_on_garbage_never_a_location_list():
    for bad in ("not json{{", '{"a": 1}', "42", "null"):
        try:
            parse_senscom_dump(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("no ValueError for %r" % (bad,))
    assert parse_senscom_dump("[]") == []


def test_extract_keeps_tallinn_bbox_and_fetch_date():
    assert TLL["fetched"] == "2026-09-13"
    assert TLL["n_sensors"] == 2
    assert {s["id"] for s in TLL["sensors"]} == {901, 902}
    defaulted = tallinn_extract(parse_senscom_dump(SYNTH_DUMP))
    assert len(defaulted["fetched"]) == 10  # YYYY-MM-DD travel date


def test_ingestion_constants_stated():
    assert SENSCOM_DATA_URL == "https://data.sensor.community/static/v2/data.json"
    assert SENSCOM_TTL_S == 24 * 3600
    assert SENSCOM_RADIUS_M == 500.0
    assert SENSCOM_CACHE_NAME == "sensor-community-data.json"
    assert SENSCOM_SNAPSHOT_NAME == "sensor-community-tallinn.json"


def test_fetch_cache_hit_performs_no_request(tmp_path):
    from dims_p4_senscom import _cache_path
    dest = _cache_path(str(tmp_path))
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(SYNTH_DUMP)
    body, provenance = fetch_senscom_dump(cache_dir=str(tmp_path))
    assert provenance == "cache"
    assert body == SYNTH_DUMP
    assert cache_is_fresh(dest) is True
    assert cache_is_fresh(str(tmp_path / "missing.json")) is False
    assert load_senscom_snapshot(str(tmp_path)) is None  # no snapshot file yet
    with open(snapshot_cache_path(str(tmp_path)), "w", encoding="utf-8") as fh:
        json.dump(TLL, fh)
    assert load_senscom_snapshot(str(tmp_path))["n_sensors"] == 2
    with open(snapshot_cache_path(str(tmp_path)), "w", encoding="utf-8") as fh:
        fh.write("corrupt{{")
    assert load_senscom_snapshot(str(tmp_path)) is None


# ---------------------------------------------------------------------------
# Scorer: coarse density bands, capped; thin network stays NULL.
# ---------------------------------------------------------------------------

def test_density_bands_60_70_80_capped():
    one = tallinn_extract([_loc(901, *TALLINN)], fetched="2026-09-13")
    assert dim_backyard_air(TALLINN, POIS, one)[0] == 60
    assert dim_backyard_air(TALLINN, POIS, TLL)[0] == 70  # 901 + 902
    four = tallinn_extract([_loc(901, *TALLINN),
                            _loc(902, 59.4395, 24.7555),
                            _loc(907, 59.4360, 24.7520),
                            _loc(908, 59.4380, 24.7560)],
                           fetched="2026-09-13")
    assert dim_backyard_air(TALLINN, POIS, four)[0] == 80
    assert dim_backyard_air(TALLINN, POIS, four)[0] != 100


def test_zero_nearby_is_null_thin_network_unknown():
    v, reason = dim_backyard_air(TARTU, POIS, TLL)
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason
    assert "500 m" in reason


def test_null_contract_for_every_missing_input():
    cases = [
        (None, POIS, TLL),                       # no origin
        (TALLINN, POIS, None),                   # no snapshot
        (TALLINN, POIS, {"a": 1}),               # snapshot without sensors
        (TALLINN, POIS, {"fetched": "x", "sensors": []}),  # empty extract
    ]
    for origin, pois, snap in cases:
        v, reason = dim_backyard_air(origin, pois, snap)
        assert v is None, (origin, snap)
        assert "EI OLE" in reason, (origin, snap)
        assert "hinnang" in reason, (origin, snap)
        assert "sensor.community" in reason, (origin, snap)
    # POIs never move the dim (DIY sensors are not OSM POIs).
    assert (dim_backyard_air(TALLINN, None, TLL)[0]
            == dim_backyard_air(TALLINN, [{"kind": "x", "lat": 0.0, "lon": 0.0}],
                                TLL)[0] == 70)


def test_scored_reason_carries_count_radius_date_and_no_overclaim():
    v, reason = dim_backyard_air(TALLINN, POIS, TLL)
    assert v == 70
    assert "hinnang" in reason
    assert "2 tk" in reason and "500 m" in reason
    assert "2026-09-13" in reason
    assert "SDS011" in reason  # nearest-location board types
    assert "dims_p4_ilm" in reason  # sibling Harku leg named, never re-scored
    assert "EI OLE" not in reason  # invariant: EI OLE only in NULL reasons
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_scores_never_0_or_100_and_registry_wires_param():
    assert P4_SENSCOM_DIMS == (
        ("backyard_air_senscom", "P4-031", dim_backyard_air),)
    assert P4_SENSCOM_PARAM_IDS == {"backyard_air_senscom": 31}
    assert senscom.P4_SENSCOM_DIMS[0][2] is dim_backyard_air
    out = score_p4_senscom(TALLINN, POIS, TLL)
    assert out == {"backyard_air_senscom": 70}
    assert score_p4_senscom(TARTU, POIS, TLL) == {"backyard_air_senscom": None}
    assert score_p4_senscom(TALLINN, POIS, None) == {"backyard_air_senscom": None}
    for origin in (TALLINN, TARTU):
        for snap in (TLL, None):
            v = score_p4_senscom(origin, POIS, snap)["backyard_air_senscom"]
            assert v in (None, 60, 70, 80), (origin, snap)
