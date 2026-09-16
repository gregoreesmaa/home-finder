"""P4 official-air adapter (issue #524): hermetic tests.

No network: fetch_ohuseire_dump is never called for a live pull here
(its contract — single polite GET, file cache, TTL, transport errors
raise — is covered via the pure cache_is_fresh helper plus a
cache-hit fetch test that performs no GET). Parsing, the L-EST97
conversion, the Tallinn extract, bands, and the EI-OLE invariant run
on fully synthetic register fixtures.
"""

import math

import dims_p4_ohuseire as ohu
from dims_p4_ohuseire import (
    OHUSEIRE_RADIUS_M,
    OHUSEIRE_TTL_S,
    cache_is_fresh,
    dim_official_air,
    fetch_ohuseire_dump,
    lest_to_wgs84,
    parse_ohuseire_dump,
    tallinn_extract,
)

#: Synthetic register payload (models the OBSERVED 2026-09-16 field
#: shape only: nimi/kesk_x/kesk_y/seisund/sr_programm_nimi/ehak_tekst/
#: kkr_kood). Never ingested.
SYNTH_DUMP = """[
 {"nimi": "Tallinn Test 1", "kesk_x": 540568, "kesk_y": 6590159,
  "seisund": "Kasutusel",
  "sr_programm_nimi": "V\\u00e4lis\\u00f5hu kvaliteedi seire",
  "ehak_tekst": "Harju maakond, Tallinn, P\\u00f5hja-Tallinna linnaosa",
  "keht_staatus": "Kehtiv", "kkr_kood": "SJA0000001"},
 {"nimi": "Tallinn Test 2", "kesk_x": 541500, "kesk_y": 6591000,
  "seisund": "Kasutusel",
  "sr_programm_nimi": "V\\u00e4lis\\u00f5hu kvaliteedi seire linnades",
  "ehak_tekst": "Harju maakond, Tallinn, Kesklinna linnaosa",
  "keht_staatus": "Kehtiv", "kkr_kood": "SJA0000002"},
 {"nimi": "Peatatud jaam", "kesk_x": 542000, "kesk_y": 6592000,
  "seisund": "Peatatud",
  "sr_programm_nimi": "V\\u00e4lis\\u00f5hu kvaliteedi seire",
  "ehak_tekst": "Harju maakond, Tallinn, Lasnam\\u00e4e linnaosa",
  "keht_staatus": "Kehtiv", "kkr_kood": "SJA0000003"},
 {"nimi": "Mullajaam", "kesk_x": 650158, "kesk_y": 6473416,
  "seisund": "Kasutusel",
  "sr_programm_nimi": "P\\u00f5llumuldade seire",
  "ehak_tekst": "Tartu maakond, Tartu linn, T\\u00fcki k\\u00fcla",
  "keht_staatus": "Kehtiv", "kkr_kood": "SJA0000004"},
 {"nimi": "Koordinaadita", "kesk_x": null, "kesk_y": null,
  "seisund": "Kasutusel",
  "sr_programm_nimi": "V\\u00e4lis\\u00f5hu kvaliteedi seire",
  "ehak_tekst": null,
  "keht_staatus": "Kehtiv", "kkr_kood": "SJA0000005"}
]"""

TLL = tallinn_extract(parse_ohuseire_dump(SYNTH_DUMP), fetched="2026-09-16")


def test_parse_keeps_coord_rows_skips_coordless():
    rows = parse_ohuseire_dump(SYNTH_DUMP)
    assert len(rows) == 4  # coordless row skipped at parse


def test_parse_rejects_garbage():
    for bad in ("not json", '{"a": 1}', "[1, 2"):
        try:
            parse_ohuseire_dump(bad)
        except ValueError:
            continue
        raise AssertionError("no ValueError for %r" % bad)


def test_extract_keeps_only_active_tallinn_air():
    assert TLL["fetched"] == "2026-09-16"
    assert TLL["n_stations"] == 2
    assert TLL["n_skipped"] == 2  # suspended + soil programme
    names = sorted(s["name"] for s in TLL["stations"])
    assert names == ["Tallinn Test 1", "Tallinn Test 2"]


def test_conversion_lands_in_tallinn_bbox():
    for station in TLL["stations"]:
        assert 59.3 <= station["lat"] <= 59.6
        assert 24.3 <= station["lon"] <= 25.1
        assert "teisendatud" in station["converted"]


def test_conversion_matches_live_reference_shape():
    # Live L-EST values observed 2026-09-16 convert to Tallinn; the
    # exact PROJ agreement (<0.01 m) was verified in dev — here we pin
    # the district, not the centimetre (hermetic, no PROJ dependency).
    lon, lat = lest_to_wgs84(540568, 6590159)
    assert abs(lat - 59.447) < 0.01
    assert abs(lon - 24.715) < 0.01


def test_lest_round_trip_is_sub_metre():
    from dims_p4_ohuseire import (
        _LEST_A, _LEST_F, _LEST_FE, _LEST_FN, _LEST_N, _LEST_RHO0,
    )
    lon, lat = 24.71513, 59.44729
    phi = math.radians(lat)
    import dims_p4_ohuseire as m
    tval = m._lest_t(phi)
    rho = _LEST_A * _LEST_F * tval ** _LEST_N
    theta = _LEST_N * (math.radians(lon) - m._LEST_LON0)
    x = _LEST_FE + rho * math.sin(theta)
    y = _LEST_FN + _LEST_RHO0 - rho * math.cos(theta)
    lon2, lat2 = lest_to_wgs84(x, y)
    assert abs(lon2 - lon) < 1e-6
    assert abs(lat2 - lat) < 1e-6


def test_bands_one_and_two_stations():
    one = {"fetched": "2026-09-16", "stations": TLL["stations"][:1]}
    two = {"fetched": "2026-09-16", "stations": TLL["stations"]}
    near = (TLL["stations"][0]["lat"], TLL["stations"][0]["lon"])
    score1, reason1 = dim_official_air(near, [], one)
    score2, reason2 = dim_official_air(near, [], two)
    assert score1 == 60
    assert score2 == 70
    for reason in (reason1, reason2):
        assert "hinnang" in reason
        assert "EI OLE" not in reason
        assert "teisendatud" in reason
        assert "2026-09-16" in reason


def test_null_no_origin_no_snapshot_empty_far():
    score, reason = dim_official_air(None, [], TLL)
    assert score is None and "EI OLE" in reason
    score, reason = dim_official_air((59.44, 24.75), [], None)
    assert score is None and "EI OLE" in reason
    score, reason = dim_official_air(
        (59.44, 24.75), [],
        {"fetched": "2026-09-16", "stations": []})
    assert score is None and "EI OLE" in reason
    score, reason = dim_official_air((58.0, 24.0), [], TLL)
    assert score is None and "EI OLE" in reason


def test_scored_reasons_name_siblings_never_ei_ole():
    near = (TLL["stations"][0]["lat"], TLL["stations"][0]["lon"])
    _score, reason = dim_official_air(near, [], TLL)
    assert "sensor.community" in reason
    assert "Harku" in reason


def test_ttl_is_weekly():
    assert OHUSEIRE_TTL_S == 7 * 24 * 3600
    assert OHUSEIRE_RADIUS_M == 2000.0


def test_fetch_cache_hit_performs_no_request(tmp_path):
    from dims_p4_ohuseire import _cache_path
    dest = _cache_path(str(tmp_path))
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(SYNTH_DUMP)
    body, provenance = fetch_ohuseire_dump(cache_dir=str(tmp_path))
    assert provenance == "cache"
    assert "Tallinn Test 1" in body
    assert cache_is_fresh(dest) is True


def test_cache_is_fresh_false_when_missing(tmp_path):
    assert cache_is_fresh(str(tmp_path / "nope.json")) is False


def test_module_touches_no_shared_files():
    import inspect
    src = inspect.getsource(ohu)
    assert "import livability" not in src
    assert "import dims_p4_senscom" not in src
    assert "from dims_p4_senscom import" not in src
    assert "WEIGHTS =" not in src
    assert "WEIGHTS[" not in src
