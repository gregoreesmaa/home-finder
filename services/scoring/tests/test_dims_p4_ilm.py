"""P4 ilm dims (issues #308, #374): hermetic tests.

No network: parsing runs on a fixture XML string, aggregation and all
five scorers run on fixture records/baselines, politeness constants are
asserted as values, and the one live pull is env-gated (HF_LIVE_ILM=1)
so the default suite never touches the network.
Run: python3 -m pytest services/scoring/tests/test_dims_p4_ilm.py -q
"""

import calendar
import os

import pytest

import dims_p4_ilm as ilm
from dims_p4_ilm import (
    DARKNESS_BANDS,
    ILM_CACHE_TTL_S,
    ILM_OBSERVATIONS_URL,
    ILM_STATION_NAME,
    ILM_STATION_WMO,
    ODOUR_EMITTER_KIND,
    OVERHEAT_BANDS,
    P4ILM_DIMS,
    P4ILM_PARAM_IDS,
    aggregate_baseline,
    bearing_deg,
    dim_backyard_weather,
    dim_courtyard_trap,
    dim_december_darkness,
    dim_odour_rose,
    dim_overheat_risk,
    fetch_harku_observation,
    parse_harku_observation,
    score_p4_ilm,
    sector_of_bearing,
)

TALLINN = (59.4372, 24.7536)
JUL = calendar.timegm((2026, 7, 15, 12, 0, 0, 0, 0, 0))
DEC = calendar.timegm((2026, 12, 10, 12, 0, 0, 0, 0, 0))

FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<observations timestamp="1789305511">
<station>
<name>Tallinn-Harku</name>
<wmocode>26038</wmocode>
<longitude>24.6028</longitude>
<latitude>59.3981</latitude>
<phenomenon>Cloudy with clear spells</phenomenon>
<visibility>35</visibility>
<precipitations>0</precipitations>
<airpressure>1012.9</airpressure>
<relativehumidity>82.5</relativehumidity>
<airtemperature>16</airtemperature>
<winddirection>259</winddirection>
<windspeed>3.7</windspeed>
<windspeedmax>4.6</windspeedmax>
<sunshineduration>0</sunshineduration>
<globalradiation>184</globalradiation>
</station>
<station>
<name>Tartu-Toravere</name>
<wmocode>26242</wmocode>
<airtemperature>15.1</airtemperature>
<winddirection>240</winddirection>
<windspeed>2.9</windspeed>
</station>
</observations>
"""


def _rec(ts, t, wdir, wsp, sun):
    return {"station": ILM_STATION_NAME, "wmo": ILM_STATION_WMO, "ts": ts,
            "t": t, "winddir": wdir, "windspeed": wsp, "sun": sun,
            "cdd18": max(0.0, t - 18.0)}


# July mean 17.4 -> band 65; December sun 18.5 h -> band 35;
# rose E:3 WSW:2 S:2; calm 2/7.
RECORDS = [
    _rec(JUL, 16.0, 90, 3.0, 2.0),
    _rec(JUL, 17.0, 90, 4.0, 3.0),
    _rec(JUL, 18.0, 250, 0.2, 1.0),
    _rec(JUL, 18.6, 250, 2.0, 0.5),
    _rec(DEC, -2.0, 90, 5.0, 6.0),
    _rec(DEC, -3.0, 180, 0.1, 7.5),
    _rec(DEC, -1.0, 180, 3.0, 5.0),
]

BASELINE = aggregate_baseline(RECORDS)

ROSE = {s: 0.055 for s in ilm.SECTORS_16}
ROSE.update({"E": 0.12, "N": 0.05})
ROSE["W"] = 1.0 - sum(v for k, v in ROSE.items() if k != "W")
ROSE_BASELINE = {"station": ILM_STATION_NAME, "wmo": ILM_STATION_WMO,
                 "n": 720, "monthly": {}, "wind_rose": ROSE,
                 "calm_share": 0.05, "source": "fixture"}


def _emitter(dlat=0.0, dlon=0.02, name="Paljassaare"):
    return {"kind": ODOUR_EMITTER_KIND, "lat": TALLINN[0] + dlat,
            "lon": TALLINN[1] + dlon, "name": name}


# ---------------------------------------------------------------------------
# Ingestion: parse + aggregate (pure, fixture-based).
# ---------------------------------------------------------------------------

def test_parse_harku_picks_station_and_fields():
    rec = parse_harku_observation(FIXTURE_XML)
    assert rec is not None
    assert rec["station"] == "Tallinn-Harku"
    assert rec["wmo"] == "26038"
    assert rec["ts"] == 1789305511
    assert rec["t"] == 16.0
    assert rec["winddir"] == 259.0
    assert rec["windspeed"] == 3.7
    assert rec["humidity"] == 82.5
    assert rec["pressure"] == 1012.9
    assert rec["sun"] == 0.0
    assert rec["radiation"] == 184.0
    assert rec["phenomenon"] == "Cloudy with clear spells"


def test_parse_missing_station_is_none_and_garbage_raises():
    no_harku = FIXTURE_XML.replace("Tallinn-Harku", "Tallinn-Harku-x")
    assert parse_harku_observation(no_harku) is None
    with pytest.raises(ValueError):
        parse_harku_observation("this is not xml <")


def test_aggregate_monthly_buckets_rose_and_calm():
    assert BASELINE["station"] == "Tallinn-Harku"
    assert BASELINE["wmo"] == "26038"
    assert BASELINE["n"] == 7
    assert set(BASELINE["monthly"]) == {7, 12}
    july = BASELINE["monthly"][7]
    assert july["n"] == 4
    assert july["t_mean"] == pytest.approx(17.4)
    assert july["cdd18"] == pytest.approx(0.6)
    dec = BASELINE["monthly"][12]
    assert dec["n"] == 3
    assert dec["sun_hours"] == pytest.approx(18.5)
    rose = BASELINE["wind_rose"]
    assert sum(rose.values()) == pytest.approx(1.0)
    assert rose["E"] == pytest.approx(3 / 7)
    assert rose["WSW"] == pytest.approx(2 / 7)
    assert rose["S"] == pytest.approx(2 / 7)
    assert BASELINE["calm_share"] == pytest.approx(2 / 7)


def test_aggregate_empty_is_honest_empty():
    b = aggregate_baseline([])
    assert b["monthly"] == {} and b["wind_rose"] == {}
    assert b["calm_share"] is None and b["n"] == 0


def test_sector_and_bearing_conventions():
    assert sector_of_bearing(0) == "N"
    assert sector_of_bearing(11.24) == "N"
    assert sector_of_bearing(11.25) == "NNE"
    assert sector_of_bearing(90) == "E"
    assert sector_of_bearing(180) == "S"
    assert sector_of_bearing(270) == "W"
    assert sector_of_bearing(348.74) == "NNW"
    assert sector_of_bearing(348.75) == "N"
    assert bearing_deg((0.0, 0.0), (0.0, 1.0)) == pytest.approx(90.0)
    assert bearing_deg((0.0, 0.0), (1.0, 0.0)) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# P4-031: always NULL, baseline-aware reason.
# ---------------------------------------------------------------------------

def test_backyard_weather_always_none_with_sensor_pointer():
    for baseline in (BASELINE, None):
        v, reason = dim_backyard_weather(TALLINN, [], baseline)
        assert v is None
        assert "EI OLE" in reason and "hinnang" in reason
        assert "andur" in reason  # DIY sensor-density check, never a station score
        assert "mõõdetud" not in reason and "garanteeritud" not in reason
    v, reason = dim_backyard_weather(TALLINN, [], BASELINE)
    assert "Harku linnabaas" in reason  # end-to-end: ingestion reaches the reason
    assert dim_backyard_weather(None, None, BASELINE)[0] is None


# ---------------------------------------------------------------------------
# P4-034: July baseline band, capped.
# ---------------------------------------------------------------------------

def test_overheat_july_band_and_reason():
    v, reason = dim_overheat_risk(TALLINN, [], BASELINE)
    assert v == 65  # July mean 17.4 C
    assert "juuli" in reason and "+17.4" in reason and "hinnang" in reason
    assert "läbiv tuulutus" in reason  # missing listing-fact check named


def test_overheat_missing_july_or_baseline_is_none():
    dec_only = aggregate_baseline([r for r in RECORDS if r["ts"] == DEC])
    for baseline in (dec_only, None):
        v, reason = dim_overheat_risk(TALLINN, [], baseline)
        assert v is None
        assert "EI OLE" in reason and "juuli" in reason


def test_overheat_bands_and_floor():
    assert OVERHEAT_BANDS == ((16.0, 80), (18.0, 65), (20.0, 50), (22.0, 35))

    def band(t):
        b = {"monthly": {7: {"n": 5, "t_mean": t, "sun_hours": 0.0, "cdd18": 0.0}}}
        return dim_overheat_risk(TALLINN, [], b)[0]

    assert band(15.9) == 80
    assert band(18.0) == 50  # exact boundary takes the warmer band
    assert band(21.9) == 35
    assert band(30.0) == 20  # capped: baseline alone never scores the extreme


# ---------------------------------------------------------------------------
# P4-035: December baseline band, capped.
# ---------------------------------------------------------------------------

def test_darkness_december_band_and_reason():
    v, reason = dim_december_darkness(TALLINN, [], BASELINE)
    assert v == 35  # December sun 18.5 h
    assert "detsembri" in reason and "18.5" in reason and "hinnang" in reason
    assert "tänavavalgustus" in reason


def test_darkness_missing_december_or_baseline_is_none():
    jul_only = aggregate_baseline([r for r in RECORDS if r["ts"] == JUL])
    for baseline in (jul_only, None):
        v, reason = dim_december_darkness(TALLINN, [], baseline)
        assert v is None
        assert "EI OLE" in reason and "detsembri" in reason


def test_darkness_bands_and_cap():
    assert DARKNESS_BANDS == ((10.0, 20), (20.0, 35), (35.0, 50), (50.0, 65))

    def band(sun):
        b = {"monthly": {12: {"n": 5, "t_mean": -2.0, "sun_hours": sun, "cdd18": 0.0}}}
        return dim_december_darkness(TALLINN, [], b)[0]

    assert band(9.9) == 20
    assert band(200.0) == 80  # capped: baseline alone never claims bright


# ---------------------------------------------------------------------------
# P4-053: sector dim, never a buffer.
# ---------------------------------------------------------------------------

def test_odour_rose_sector_score_and_reason():
    v, reason = dim_odour_rose(TALLINN, [_emitter()], ROSE_BASELINE)
    assert v == 40  # E freq 0.12 -> round(100*(1-0.6))
    assert "E" in reason and "12.0%" in reason and "~44" in reason
    assert "Paljassaare" in reason and "hinnang" in reason
    assert "korstna-täpsus" in reason  # never doorway precision


def test_odour_rose_nearest_emitter_wins():
    pois = [_emitter(dlon=0.02, name="ida-heide"),  # E sector, farther
            _emitter(dlat=0.005, dlon=0.0, name="pohja-heide")]  # N, nearer
    v, reason = dim_odour_rose(TALLINN, pois, ROSE_BASELINE)
    assert v == 75  # N freq 0.05 -> round(100*0.75)
    assert "pohja-heide" in reason


def test_odour_rose_nulls_stay_null():
    v, r = dim_odour_rose(TALLINN, [_emitter()], None)
    assert v is None and "EI OLE" in r and "tuuleroosi" in r
    v, r = dim_odour_rose(TALLINN, [], ROSE_BASELINE)
    assert v is None and "EI OLE" in r and "inventuur" in r
    v, r = dim_odour_rose(TALLINN, [{"kind": "cafe", "lat": 59.44, "lon": 24.75}],
                          ROSE_BASELINE)
    assert v is None and "inventuur" in r  # other POI kinds ignored
    v, r = dim_odour_rose(None, [_emitter()], ROSE_BASELINE)
    assert v is None
    thin = {"wind_rose": {"N": 1.0}}
    v, r = dim_odour_rose(TALLINN, [_emitter()], thin)
    assert v is None and "EI OLE" in r  # sector missing from rose: never faked


def test_odour_rose_saturation():
    sat = {"wind_rose": {"E": 0.25}}
    v, _ = dim_odour_rose(TALLINN, [_emitter()], sat)
    assert v == 0
    calm = {"wind_rose": {"E": 0.0}}
    assert dim_odour_rose(TALLINN, [_emitter()], calm)[0] == 100


# ---------------------------------------------------------------------------
# P4-056: always NULL, ventilation context.
# ---------------------------------------------------------------------------

def test_courtyard_trap_always_none_with_lidar_pointer():
    v, reason = dim_courtyard_trap(TALLINN, [], BASELINE)
    assert v is None
    assert "EI OLE" in reason and "LiDAR" in reason
    assert "28.6%" in reason  # Harku calm-share ventilation context end-to-end
    v, reason = dim_courtyard_trap(TALLINN, [], None)
    assert v is None and "LiDAR" in reason
    assert dim_courtyard_trap(None, None, BASELINE)[0] is None


# ---------------------------------------------------------------------------
# Registry, rollup, politeness constants, live gate.
# ---------------------------------------------------------------------------

def test_registry_and_rollup_shape():
    assert set(P4ILM_DIMS) == {"backyard_weather", "overheat_risk",
                               "december_darkness", "odour_rose",
                               "courtyard_trap"}
    assert P4ILM_PARAM_IDS == {"backyard_weather": 31, "overheat_risk": 34,
                               "december_darkness": 35, "odour_rose": 53,
                               "courtyard_trap": 56}
    assert P4ILM_DIMS["overheat_risk"][0] == "P4-034"
    dims, reasons = score_p4_ilm(TALLINN, [], BASELINE)
    assert dims == {"backyard_weather": None, "overheat_risk": 65,
                    "december_darkness": 35, "odour_rose": None,
                    "courtyard_trap": None}
    assert len(reasons) == 2  # NULL dims contribute no reasons (no fake evidence)
    dims2, _ = score_p4_ilm(TALLINN, [_emitter()], ROSE_BASELINE)
    assert dims2["odour_rose"] == 40
    assert ilm.P4ILM_DIMS is P4ILM_DIMS


def test_politeness_contract_as_values():
    assert ILM_OBSERVATIONS_URL.startswith("https://")
    assert "observations.php" in ILM_OBSERVATIONS_URL
    assert ILM_STATION_NAME == "Tallinn-Harku"
    assert ILM_STATION_WMO == "26038"
    assert ILM_CACHE_TTL_S == 24 * 3600  # daily max, baseline moves slowly
    assert "home-finder" in ilm.ILM_USER_AGENT
    assert ilm.ILM_CACHE_NAME.endswith(".xml")


@pytest.mark.skipif(not os.environ.get("HF_LIVE_ILM"),
                    reason="live network only with HF_LIVE_ILM=1")
def test_live_harku_pull_explicit_flag_only(tmp_path):
    rec, provenance = fetch_harku_observation(cache_dir=str(tmp_path))
    assert rec["station"] == "Tallinn-Harku"
    assert rec["t"] is not None and rec["winddir"] is not None
    assert provenance in ("live", "cache")
