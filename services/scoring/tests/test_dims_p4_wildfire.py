"""P4 wildfire dims (issue #529): hermetic tests.

No network: parsing runs on synthetic fixture TSV strings, the dim
runs on synthetic snapshots, politeness constants are asserted as
values, and the live pull is env-gated (HF_LIVE_WILDFIRE=1) so the
default suite never touches the network.
Run: python3 -m pytest services/scoring/tests/test_dims_p4_wildfire.py -q
"""

import os

import pytest

import dims_p4_wildfire as wildfire
from dims_p4_wildfire import (
    FAR_M,
    NEAR_M,
    P4_WILDFIRE_DIMS,
    RECENT_YEARS,
    WILDFIRE_BANDS,
    WILDFIRE_CACHE_NAME,
    WILDFIRE_CACHE_TTL_S,
    WILDFIRE_URL,
    asof_year,
    dim_wildfire_recency,
    fetch_wildfire_snapshot,
    haversine_km,
    incident_year,
    parse_metsa_tsv,
    score_p4_wildfire,
    summarize_snapshot,
)

TALLINN = (59.4372, 24.7536)

#: Synthetic register payload (TAB-separated like the live CSV;
#: invented rows — real observed values appear only in
#: docs/p4_wildfire.md, never as ingested data).
TSV_FIXTURE = (
    '"sundmuse_number"\t"sundmuse_kuupaev_dt"\t"tulekahju_liik"\t'
    '"mis_poles"\t"wgs_latitude"\t"wgs_longitude"\t"maakond"\t"kov"\n'
    '"SYN1"\t"2025-06-12"\t"Metsa-ja maastikutulekahju"\t"Maastik"\t'
    '"59.4375"\t"24.7540"\t"Harju maakond"\t"Tallinn"\n'
    '"SYN2"\t"2018-07-01"\t"Metsa-ja maastikutulekahju"\t"Mets"\t'
    '"59.4500"\t"24.7600"\t"Harju maakond"\t"Tallinn"\n'
    '"SYN3"\t"2024-05-20"\t"Metsa-ja maastikutulekahju"\t""\t'
    '""\t""\t"Harju maakond"\t"Saue vald"\n'
)


def _incident(lat, lon, year, kov="Tallinn", fuel="Maastik"):
    return {"id": "SYN", "year": year, "fuel": fuel,
            "maakond": "Harju maakond", "kov": kov,
            "lat": lat, "lon": lon}


def _snap(incidents, as_of="2026-09-16"):
    return {"incidents": incidents, "as_of": as_of, "source": "sünteetiline"}


def _moved(north_m=0.0, east_m=0.0):
    return (TALLINN[0] + north_m / 111320.0,
            TALLINN[1] + east_m / 57100.0)


# ---------------------------------------------------------------------------
# Date + distance helpers.
# ---------------------------------------------------------------------------

def test_incident_year_parsing_fail_closed():
    assert incident_year("2026-09-07") == 2026
    assert incident_year("2014-04-01") == 2014
    assert incident_year("") is None
    assert incident_year(None) is None
    assert incident_year("07.09.2026") is None
    assert incident_year("999-01-01") is None
    assert asof_year("2026-09-16") == 2026


def test_haversine_sanity():
    assert haversine_km(TALLINN, TALLINN) == 0.0
    assert 0.4 < haversine_km(TALLINN, _moved(500)) < 0.6


# ---------------------------------------------------------------------------
# Pure parser on the synthetic fixture.
# ---------------------------------------------------------------------------

def test_parse_tsv_keeps_coordinated_dated_rows():
    incidents = parse_metsa_tsv(TSV_FIXTURE)
    assert len(incidents) == 2  # SYN3 (no coords) skipped, counted below
    assert incidents[0]["year"] == 2025 and incidents[0]["fuel"] == "Maastik"
    assert incidents[1]["fuel"] == "Mets"
    assert parse_metsa_tsv("") == []


def test_summarize_counts_and_year_span():
    assert summarize_snapshot(TSV_FIXTURE) == {
        "rows": 3, "incidents": 2, "skipped": 1, "harju": 2,
        "year_min": 2018, "year_max": 2025}


# ---------------------------------------------------------------------------
# Dim: recency kernel matrix.
# ---------------------------------------------------------------------------

def test_no_origin_is_none():
    v, reason = dim_wildfire_recency(None, None, _snap([_incident(*TALLINN, 2025)]))
    assert v is None and "EI OLE" in reason and "aadress" in reason


def test_empty_or_undated_snapshot_is_none():
    for snap in (None, {}, {"incidents": []},
                 {"incidents": [_incident(*TALLINN, 2025)]}):
        v, reason = dim_wildfire_recency(TALLINN, None, snap)
        assert v is None, snap
        assert "EI OLE" in reason and "hinnang" in reason


def test_band_matrix():
    near_recent = _snap([_incident(*_moved(300), 2025)])
    assert dim_wildfire_recency(TALLINN, None, near_recent)[0] == 35
    near_old = _snap([_incident(*_moved(300), 2018)])
    assert dim_wildfire_recency(TALLINN, None, near_old)[0] == 55
    far_recent = _snap([_incident(*_moved(1200), 2025)])
    assert dim_wildfire_recency(TALLINN, None, far_recent)[0] == 55
    far_old = _snap([_incident(*_moved(1200), 2018)])
    assert dim_wildfire_recency(TALLINN, None, far_old)[0] == 65


def test_recency_boundary_five_years():
    assert dim_wildfire_recency(
        TALLINN, None, _snap([_incident(*_moved(300), 2021)]))[0] == 35
    assert dim_wildfire_recency(
        TALLINN, None, _snap([_incident(*_moved(300), 2020)]))[0] == 55


def test_nearest_decides():
    snap = _snap([_incident(*_moved(1200), 2018, kov="Kauge"),
                  _incident(*_moved(300), 2025, kov="Lähedane")])
    v, reason = dim_wildfire_recency(TALLINN, None, snap)
    assert v == 35 and "Lähedane" in reason


def test_reason_names_year_fuel_buyer_check_and_caveat():
    v, reason = dim_wildfire_recency(
        TALLINN, None, _snap([_incident(*_moved(300), 2025, fuel="Maastik")]))
    assert v == 35
    assert "2025" in reason and "Maastik" in reason
    assert "kindlustus" in reason and "tuleohukaardi" in reason
    assert "Keskkonnaagentuuri" in reason  # statistics caveat


def test_beyond_far_is_none_never_safe():
    v, reason = dim_wildfire_recency(
        TALLINN, None, _snap([_incident(*_moved(5000), 2025)]))
    assert v is None
    assert "EI OLE" in reason
    assert "ei ole tuleohu puudumise" in reason
    assert "ohutu" not in reason and "tuleohutu" not in reason


# ---------------------------------------------------------------------------
# Registry, rollup, constants, politeness, live gate.
# ---------------------------------------------------------------------------

def test_band_constants_pinned():
    assert RECENT_YEARS == 5 and NEAR_M == 500.0 and FAR_M == 2000.0
    assert WILDFIRE_BANDS == {(True, True): 35, (True, False): 55,
                              (False, True): 55, (False, False): 65}


def test_all_none_reasons_carry_honesty_markers():
    for snap in (None, {}, {"incidents": []}):
        _, reason = dim_wildfire_recency(TALLINN, None, snap)
        assert "hinnang" in reason and "EI OLE" in reason
        assert "garanteeritud" not in reason and "mõõdetud" not in reason
    _, far = dim_wildfire_recency(
        TALLINN, None, _snap([_incident(*_moved(5000), 2025)]))
    assert "EI OLE" in far


def test_registry_and_rollup_shape():
    assert [k for k, _, _ in P4_WILDFIRE_DIMS] == ["wildfire_recency"]
    dims, reasons = score_p4_wildfire(
        TALLINN, None, _snap([_incident(*_moved(300), 2025)]))
    assert dims == {"wildfire_recency": 35} and len(reasons) == 1
    empty, no_reasons = score_p4_wildfire(TALLINN, None, None)
    assert empty == {"wildfire_recency": None} and no_reasons == []
    assert wildfire.P4_WILDFIRE_DIMS is P4_WILDFIRE_DIMS


def test_politeness_contract_as_values():
    assert WILDFIRE_URL == ("https://opendata.smit.ee/paa/csv/"
                            "metsa_ja_maastikutulekahjud_jooksev_aasta.csv")
    assert WILDFIRE_CACHE_TTL_S == 1 * 86400  # daily per publisher cadence
    assert "home-finder" in wildfire.WILDFIRE_USER_AGENT
    assert WILDFIRE_CACHE_NAME.endswith(".csv")


def test_end_to_end_parse_then_score():
    incidents = parse_metsa_tsv(TSV_FIXTURE)
    v, reason = dim_wildfire_recency(TALLINN, None, _snap(incidents))
    assert v == 35 and "2025" in reason  # SYN1 is ~40 m away, recent


@pytest.mark.skipif(not os.environ.get("HF_LIVE_WILDFIRE"),
                    reason="live network only with HF_LIVE_WILDFIRE=1")
def test_live_snapshot_pull_explicit_flag_only(tmp_path):
    snapshot, provenance = fetch_wildfire_snapshot(cache_dir=str(tmp_path))
    assert snapshot["incidents"]
    assert provenance in ("live", "cache")
