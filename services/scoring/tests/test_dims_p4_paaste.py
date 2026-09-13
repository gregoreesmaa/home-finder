"""P4 paaste dims (issues #276, #350): hermetic tests.

No network: parsing runs on a fixture HTML string, all seven scorers
run on fixture POIs/coverage dicts, politeness constants are asserted
as values, and the one live pull is env-gated (HF_LIVE_PAASTE=1) so
the default suite never touches the network.
Run: python3 -m pytest services/scoring/tests/test_dims_p4_paaste.py -q
"""

import os

import pytest

import dims_p4_paaste as paaste
from dims_p4_paaste import (
    BLACKSPOT_BANDS,
    BLACKSPOT_KIND,
    BLACKSPOT_RADIUS_M,
    BURN_BANDS,
    BURN_RULES,
    FIRE_BANDS,
    FIRE_CLASSES,
    HEX_RADIUS_M,
    HEX_WATCH_KIND,
    ICE_NOTICE_KIND,
    ICE_RADIUS_M,
    MONTH_ET,
    P4PAASTE_DIMS,
    P4PAASTE_PARAM_IDS,
    PAASTE_AVAANDMED_URL,
    PAASTE_CACHE_TTL_S,
    PAASTE_STATS_URL,
    RESCUE_STATION_KIND,
    SMOKE_NOTICE_KIND,
    SMOKE_RADIUS_M,
    STATION_FAR_KM,
    dim_blackspot_drive_time,
    dim_burn_restriction,
    dim_falling_ice,
    dim_hex_watch,
    dim_insurability,
    dim_small_horrors,
    dim_smoke_chorus,
    fetch_stats_snapshot,
    haversine_km,
    parse_stats_snapshot,
    score_p4_paaste,
)

TALLINN = (59.4372, 24.7536)
# ~111 m north / ~113 m east of TALLINN (inside every honesty radius).
NEAR_LAT = TALLINN[0] + 0.001
NEAR_LON = TALLINN[1] + 0.002
# ~5.6 km north (outside the 500/300 m radii, past the 5 km station line).
FAR_LAT = TALLINN[0] + 0.05


def _spot(lat=NEAR_LAT, lon=TALLINN[1]):
    return {"kind": BLACKSPOT_KIND, "lat": lat, "lon": lon}


def _station(lat=NEAR_LAT, lon=TALLINN[1], name="Lasnamäe komando"):
    return {"kind": RESCUE_STATION_KIND, "lat": lat, "lon": lon, "name": name}


def _smoke(lat=NEAR_LAT, lon=TALLINN[1], area="Nõmme"):
    return {"kind": SMOKE_NOTICE_KIND, "lat": lat, "lon": lon, "area": area}


def _ice(lat=NEAR_LAT, lon=TALLINN[1], street="Narva mnt",
         season="2025/26"):
    return {"kind": ICE_NOTICE_KIND, "lat": lat, "lon": lon,
            "street": street, "season": season}


def _hex(lat=NEAR_LAT, lon=TALLINN[1], hex_id="HEX-9-511",
         flags=("ice-fall warning",)):
    return {"kind": HEX_WATCH_KIND, "lat": lat, "lon": lon,
            "hex": hex_id, "flags": list(flags)}


COVERAGE = {
    "source": "fixture",
    "stats": {"tables": ["/et/statistika", "/et/paeaestesuendmuste-statistika"],
              "portal": "https://avaandmed.eesti.ee/datasets?ih=paasteamet",
              "dashboards": [], "source": "fixture"},
    "linnaosa": "Kesklinn",
    "season": "2025/26",
    "fire_zones": {"Kesklinn": "korge", "Nomme": "madal"},
    "burn_zones": {"Kesklinn": "keelatud", "Nomme": "lubatud"},
    "event_calendar": {6: ["jaanipäev"], 12: ["aastavahetus", "vana-aasta"]},
    "smoke_season": {"months": [10, 11, 12, 1, 2, 3],
                     "areas": ["Nõmme", "Merivälja"]},
}

ALL_FNS = [
    dim_blackspot_drive_time,
    dim_insurability,
    dim_smoke_chorus,
    dim_small_horrors,
    dim_falling_ice,
    dim_burn_restriction,
    dim_hex_watch,
]

FIXTURE_HTML = """
<html><head><title>Statistika - Päästeamet</title></head><body>
<a href="/et/paeaestesuendmuste-statistika">Päästesündmuste statistika</a>
<a href="/et/statistika-kohalikele-omavalitsustele">KOV stats</a>
<a href="https://avaandmed.eesti.ee/datasets?ih=paasteamet">Teabeväravas</a>
<a href="https://app.recommy.com/SI/SI.aspx?td=H0Xl6aZQw3M=">dashboard</a>
<a href="/et/uudised/pressiteated">press (not a table)</a>
</body></html>
"""


# ---------------------------------------------------------------------------
# Ingestion: pure parse of the hub catalogue.
# ---------------------------------------------------------------------------

def test_parse_stats_snapshot_extracts_tables_portal_dashboard():
    cat = parse_stats_snapshot(FIXTURE_HTML)
    assert "/et/paeaestesuendmuste-statistika" in cat["tables"]
    assert "/et/statistika-kohalikele-omavalitsustele" in cat["tables"]
    assert "/et/uudised/pressiteated" not in cat["tables"]
    assert cat["portal"] == "https://avaandmed.eesti.ee/datasets?ih=paasteamet"
    assert len(cat["dashboards"]) == 1 and "recommy.com" in cat["dashboards"][0]
    assert "Paasteamet" in cat["source"]


def test_parse_stats_snapshot_empty_is_negative_not_error():
    cat = parse_stats_snapshot("<html><body>tühi leht</body></html>")
    assert cat == {"tables": [], "portal": None, "dashboards": [],
                   "source": cat["source"]}
    assert parse_stats_snapshot("")["tables"] == []


def test_haversine_sanity():
    assert haversine_km(TALLINN, TALLINN) == 0.0
    near = haversine_km(TALLINN, (NEAR_LAT, TALLINN[1]))
    assert 0.05 < near < 0.25  # ~111 m
    far = haversine_km(TALLINN, (FAR_LAT, TALLINN[1]))
    assert far > STATION_FAR_KM  # ~5.6 km, past the penalty line


# ---------------------------------------------------------------------------
# P4-012 demo: point-buffer + komando penalty.
# ---------------------------------------------------------------------------

def test_p12_no_origin_is_none():
    v, reason = dim_blackspot_drive_time(None, [_spot(), _station()])
    assert v is None and "EI OLE" in reason and "aadress" in reason


def test_p12_empty_inventory_is_none_with_markers():
    v, reason = dim_blackspot_drive_time(TALLINN, [], None)
    assert v is None
    assert "hinnang" in reason and "EI OLE" in reason
    assert "komando" in reason or "Komando" in reason
    v2, _ = dim_blackspot_drive_time(TALLINN, None, None)
    assert v2 is None


def test_p12_blackspot_bands_without_stations():
    assert dim_blackspot_drive_time(TALLINN, [], None)[0] is None  # no data
    assert dim_blackspot_drive_time(TALLINN, [_station()], None)[0] == 75
    assert dim_blackspot_drive_time(TALLINN, [_spot()], None)[0] == 60
    assert dim_blackspot_drive_time(
        TALLINN, [_spot(), _spot(), _spot()], None)[0] == 40
    many = [_spot(lat=TALLINN[0] + 0.001 * i) for i in range(5)]
    assert dim_blackspot_drive_time(TALLINN, many, None)[0] == 20


def test_p12_outside_buffer_spots_do_not_count():
    far_spot = _spot(lat=FAR_LAT)
    assert dim_blackspot_drive_time(TALLINN, [far_spot], None)[0] == 75


def test_p12_far_station_penalty_and_name_in_reason():
    v, reason = dim_blackspot_drive_time(
        TALLINN, [_station(lat=FAR_LAT, name="Nõmme komando")], None)
    assert v == 65  # 75 - 10 drive-time penalty
    assert "Nõmme komando" in reason and "linnulennult" in reason
    assert "hinnang" in reason


def test_p12_coverage_stats_cited_when_present():
    v, reason = dim_blackspot_drive_time(TALLINN, [_station()], COVERAGE)
    assert v == 75 and "2 tabelit" in reason


# ---------------------------------------------------------------------------
# P4-015: zone join + illiquidity flag.
# ---------------------------------------------------------------------------

def test_p15_missing_is_none():
    for cov in (None, {}, {"linnaosa": "Kesklinn"},
                {"linnaosa": "Kesklinn", "fire_zones": {"Nomme": "madal"}},
                {"linnaosa": "Kesklinn",
                 "fire_zones": {"Kesklinn": "tundmatu"}}):
        v, reason = dim_insurability(TALLINN, [], cov)
        assert v is None, cov
        assert "EI OLE" in reason and "hinnang" in reason


def test_p15_bands_and_illiquidity_flag():
    assert dim_insurability(TALLINN, [], COVERAGE)[0] == 25  # Kesklinn korge
    _, reason = dim_insurability(TALLINN, [], COVERAGE)
    assert "KORGE" in reason and "mittelikviidsuse" in reason
    nomme = dict(COVERAGE, linnaosa="Nomme")
    v, reason = dim_insurability(TALLINN, [], nomme)
    assert v == 70 and "madal" in reason
    mid = dict(COVERAGE, fire_zones={"Kesklinn": "keskmine"})
    assert dim_insurability(TALLINN, [], mid)[0] == 50


# ---------------------------------------------------------------------------
# P4-042: coarse smoke cells (inside scores, outside NULLs).
# ---------------------------------------------------------------------------

def test_p42_missing_or_outside_is_none():
    v, reason = dim_smoke_chorus(TALLINN, [], COVERAGE)
    assert v is None and "EI OLE" in reason
    v, reason = dim_smoke_chorus(
        TALLINN, [_smoke(lat=FAR_LAT)], COVERAGE)
    assert v is None and "EI OLE" in reason  # no clean-air score from absence
    assert dim_smoke_chorus(None, [_smoke()], COVERAGE)[0] is None


def test_p42_inside_cell_is_capped_flag():
    v, reason = dim_smoke_chorus(TALLINN, [_smoke()], COVERAGE)
    assert v == 45
    assert "hinnang" in reason and "ukse-täpsus" in reason
    assert "Nõmme" in reason


# ---------------------------------------------------------------------------
# P4-047: city-wide event calendar.
# ---------------------------------------------------------------------------

def test_p47_missing_is_none():
    for cov in (None, {}, {"event_calendar": {}}):
        v, reason = dim_small_horrors(TALLINN, [], cov)
        assert v is None, cov
        assert "EI OLE" in reason


def test_p47_calendar_bands_and_peak_months():
    v, reason = dim_small_horrors(TALLINN, [], COVERAGE)  # 3 notices
    assert v == 45
    assert "juuni" in reason and "detsember" in reason
    quiet = {"event_calendar": {1: [], 2: []}}
    assert dim_small_horrors(TALLINN, [], quiet)[0] == 75
    busy = {"event_calendar": {m: ["x", "y"] for m in range(1, 7)}}
    v, _ = dim_small_horrors(None, None, busy)  # city-wide: origin-free
    assert v == 30


# ---------------------------------------------------------------------------
# P4-058: dated ice notices with season recency.
# ---------------------------------------------------------------------------

def test_p58_missing_or_outside_is_none():
    v, reason = dim_falling_ice(TALLINN, [], COVERAGE)
    assert v is None and "EI OLE" in reason
    v, reason = dim_falling_ice(TALLINN, [_ice(lat=FAR_LAT)], COVERAGE)
    assert v is None and "EI OLE" in reason
    assert dim_falling_ice(None, [_ice()], COVERAGE)[0] is None


def test_p58_season_recency_bands():
    v, reason = dim_falling_ice(TALLINN, [_ice(season="2025/26")], COVERAGE)
    assert v == 35 and "jooksev hooaeg" in reason
    v, reason = dim_falling_ice(TALLINN, [_ice(season="2024/25")], COVERAGE)
    assert v == 45 and "eelmine hooaeg" in reason
    v, _ = dim_falling_ice(TALLINN, [_ice(season="2022/23")], COVERAGE)
    assert v == 55
    v, reason = dim_falling_ice(TALLINN, [_ice(season=None)], COVERAGE)
    assert v == 45 and "dateerimata" in reason
    # No caller clock: every dated notice reads as undated (never fresh).
    v, _ = dim_falling_ice(TALLINN, [_ice(season="2025/26")], {})
    assert v == 45


# ---------------------------------------------------------------------------
# P4-059: rule join.
# ---------------------------------------------------------------------------

def test_p59_missing_or_unknown_is_none():
    for cov in (None, {},
                {"linnaosa": "Kesklinn"},
                {"linnaosa": "Kesklinn", "burn_zones": {"Nomme": "lubatud"}},
                {"linnaosa": "Kesklinn",
                 "burn_zones": {"Kesklinn": "ootel"}}):
        v, reason = dim_burn_restriction(TALLINN, [], cov)
        assert v is None, cov
        assert "EI OLE" in reason


def test_p59_rule_bands():
    v, reason = dim_burn_restriction(TALLINN, [], COVERAGE)
    assert v == 20 and "KEELATUD" in reason
    nomme = dict(COVERAGE, linnaosa="Nomme")
    assert dim_burn_restriction(TALLINN, [], nomme)[0] == 75
    mid = dict(COVERAGE, burn_zones={"Kesklinn": "piiratud"})
    assert dim_burn_restriction(TALLINN, [], mid)[0] == 50


# ---------------------------------------------------------------------------
# P4-062: hex flags (inside scores, outside NULLs).
# ---------------------------------------------------------------------------

def test_p62_missing_or_outside_is_none():
    v, reason = dim_hex_watch(TALLINN, [], COVERAGE)
    assert v is None and "EI OLE" in reason
    assert "rotikaebused" in reason  # unjoined leg is named
    v, reason = dim_hex_watch(TALLINN, [_hex(lat=FAR_LAT)], COVERAGE)
    assert v is None and "heks" in reason
    assert dim_hex_watch(None, [_hex()], COVERAGE)[0] is None


def test_p62_inside_flag_lists_flags():
    v, reason = dim_hex_watch(TALLINN, [_hex()], COVERAGE)
    assert v == 40
    assert "HEX-9-511" in reason and "ice-fall warning" in reason
    assert "hinnang" in reason


# ---------------------------------------------------------------------------
# Honesty markers, bands, registry, rollup, politeness, live gate.
# ---------------------------------------------------------------------------

def test_all_none_reasons_carry_honesty_markers():
    cases = [
        (dim_blackspot_drive_time, (TALLINN, [], None)),
        (dim_insurability, (TALLINN, [], None)),
        (dim_smoke_chorus, (TALLINN, [], None)),
        (dim_small_horrors, (TALLINN, [], None)),
        (dim_falling_ice, (TALLINN, [], None)),
        (dim_burn_restriction, (TALLINN, [], None)),
        (dim_hex_watch, (TALLINN, [], None)),
    ]
    for fn, args in cases:
        _, reason = fn(*args)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "garanteeritud" not in reason and "mõõdetud" not in reason


def test_band_constants_pinned():
    assert BLACKSPOT_BANDS == ((0, 75), (1, 60), (3, 40))
    assert BLACKSPOT_RADIUS_M == 500.0
    assert SMOKE_RADIUS_M == 800.0
    assert ICE_RADIUS_M == 300.0
    assert HEX_RADIUS_M == 500.0
    assert STATION_FAR_KM == 5.0
    assert FIRE_BANDS == {"madal": 70, "keskmine": 50, "korge": 25}
    assert set(FIRE_CLASSES) == set(FIRE_BANDS)
    assert BURN_BANDS == {"keelatud": 20, "piiratud": 50, "lubatud": 75}
    assert set(BURN_RULES) == set(BURN_BANDS)
    assert MONTH_ET[6] == "juuni" and MONTH_ET[12] == "detsember"


def test_registry_and_rollup_shape():
    assert set(P4PAASTE_DIMS) == {"blackspot_drive_time", "insurability",
                                  "smoke_chorus", "small_horrors",
                                  "falling_ice", "burn_restriction",
                                  "hex_watch"}
    assert P4PAASTE_PARAM_IDS == {"blackspot_drive_time": 12,
                                  "insurability": 15, "smoke_chorus": 42,
                                  "small_horrors": 47, "falling_ice": 58,
                                  "burn_restriction": 59, "hex_watch": 62}
    assert P4PAASTE_DIMS["blackspot_drive_time"][0] == "P4-012"
    pois = [_spot(), _spot(), _station(), _smoke(), _ice(), _hex()]
    dims, reasons = score_p4_paaste(TALLINN, pois, COVERAGE)
    assert dims == {"blackspot_drive_time": 40, "insurability": 25,
                    "smoke_chorus": 45, "small_horrors": 45,
                    "falling_ice": 35, "burn_restriction": 20,
                    "hex_watch": 40}
    assert len(reasons) == 7
    empty, no_reasons = score_p4_paaste(TALLINN, [], None)
    assert empty == {k: None for k in P4PAASTE_DIMS}
    assert no_reasons == []  # NULL dims contribute no reasons
    assert paaste.P4PAASTE_DIMS is P4PAASTE_DIMS


def test_politeness_contract_as_values():
    assert PAASTE_STATS_URL == "https://www.rescue.ee/et/statistika"
    assert PAASTE_AVAANDMED_URL == "https://www.rescue.ee/et/juhend/avaandmed"
    assert PAASTE_CACHE_TTL_S == 30 * 86400  # monthly max per P4-012 TTL
    assert "home-finder" in paaste.PAASTE_USER_AGENT
    assert paaste.PAASTE_CACHE_NAME.endswith(".html")


@pytest.mark.skipif(not os.environ.get("HF_LIVE_PAASTE"),
                    reason="live network only with HF_LIVE_PAASTE=1")
def test_live_stats_pull_explicit_flag_only(tmp_path):
    html, provenance = fetch_stats_snapshot(cache_dir=str(tmp_path))
    assert "Statistika" in html
    assert provenance in ("live", "cache")
