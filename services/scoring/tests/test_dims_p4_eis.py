"""P4 EIS (ex-KredEx) demo + coverage dims (issues #260, #341): hermetic tests.

No network: fetch_eis_csv is never called here (its contract — single
polite GET, file cache, TTL, transport errors raise — is covered via
the pure cache_is_fresh helper plus fixture-fed parse tests). Every
dim is tested on fixture EIS records through the per-building join
shape: joined record -> bands, missing record/slice -> NULL with
Estonian honesty markers.
"""

import os

import dims_p4_eis as eis
from dims_p4_eis import (
    EIS_TTL_DAYS,
    P4_EIS_DIMS,
    cache_is_fresh,
    dim_eis_grant_status,
    dim_ku_loan_guarantee,
    dim_stormwater_subsidy_queue,
    index_by_ehr_code,
    index_by_eis_id,
    parse_eis_grants,
    score_p4_eis,
)

# ---------------------------------------------------------------------------
# Fixtures: EIS register layout (semicolon, BOM, sparse columns) plus
# canonical joined records.
# ---------------------------------------------------------------------------

FIXTURE_CSV = (
    "\ufeffeis_id;address;kov;ehr_code;grant_status;queue_pos;"
    "grant_amount_eur;decision_date;guarantee_status;"
    "guarantee_amount_eur;subsidy_queue_pos\n"
    "EIS-2026-001;Tallinn, Pärnu mnt 1;Tallinn;101012345;eraldatud;;45000;"
    "2026-03-14;kehtiv;120000;\n"
    "EIS-2026-002;Tallinn, Kalamaja 13;Tallinn;101067890;järjekorras;17;;;"
    "taotletud;;17\n"
    ";puuduv kirje ilma võtmeta;;;;;;; ;;\n"
)

FULL_EIS = {
    "eis_id": "EIS-2026-001",
    "address": "Tallinn, Pärnu mnt 1",
    "kov": "Tallinn",
    "ehr_code": "101012345",
    "grant_status": "eraldatud",
    "queue_pos": None,
    "grant_amount_eur": 45000,
    "decision_date": "2026-03-14",
    "guarantee_status": "kehtiv",
    "guarantee_amount_eur": 120000,
    "subsidy_queue_pos": None,
}

QUEUED_EIS = {
    "eis_id": "EIS-2026-002",
    "address": "Tallinn, Kalamaja 13",
    "kov": "Tallinn",
    "ehr_code": "101067890",
    "grant_status": "järjekorras",
    "queue_pos": 17,
    "grant_amount_eur": None,
    "decision_date": None,
    "guarantee_status": "taotletud",
    "guarantee_amount_eur": None,
    "subsidy_queue_pos": 17,
}

EXPECTED_KEYS = [
    "eis_grant_status",
    "ku_loan_guarantee",
    "stormwater_subsidy_queue",
]

EXPECTED_PNUMS = ["P4-010", "P4-007", "P4-060"]


# ---------------------------------------------------------------------------
# Ingestion helpers: parse + indexes + cache freshness (no network).
# ---------------------------------------------------------------------------

def test_parse_fixture_layout_and_keyless_rows_skipped():
    recs = parse_eis_grants(FIXTURE_CSV)
    assert len(recs) == 2
    first, second = recs
    assert first["ehr_code"] == "101012345"
    assert first["eis_id"] == "EIS-2026-001"
    assert first["grant_status"] == "eraldatud"
    assert first["queue_pos"] is None
    assert first["grant_amount_eur"] == 45000
    assert first["guarantee_status"] == "kehtiv"
    assert second["queue_pos"] == 17
    assert second["subsidy_queue_pos"] == 17
    assert second["grant_amount_eur"] is None


def test_parse_missing_columns_become_none():
    recs = parse_eis_grants("eis_id;ehr_code;grant_status\nEIS-9;101099999;\n")
    assert len(recs) == 1
    assert recs[0]["grant_status"] is None
    assert recs[0]["guarantee_status"] is None
    assert recs[0]["subsidy_queue_pos"] is None


def test_parse_eis_id_only_row_kept_for_fallback_index():
    recs = parse_eis_grants("eis_id;address;grant_status\nEIS-7;Tallinn, x;ootel\n")
    assert len(recs) == 1
    assert recs[0]["ehr_code"] is None
    assert index_by_eis_id(recs)["EIS-7"]["grant_status"] == "ootel"
    assert index_by_ehr_code(recs) == {}


def test_indexes_first_row_wins_on_duplicates():
    recs = parse_eis_grants(
        "eis_id;ehr_code;grant_status\n"
        "EIS-1;101011111;eraldatud\n"
        "EIS-1;101011111;järjekorras\n")
    by_code = index_by_ehr_code(recs)
    by_id = index_by_eis_id(recs)
    assert by_code["101011111"]["grant_status"] == "eraldatud"
    assert by_id["EIS-1"]["grant_status"] == "eraldatud"


def test_cache_is_fresh_pure_contract(tmp_path):
    probe = tmp_path / "eis-probe.csv"
    probe.write_text("x", encoding="utf-8")
    assert cache_is_fresh(str(probe), ttl_days=EIS_TTL_DAYS) is True
    assert cache_is_fresh(str(probe), ttl_days=EIS_TTL_DAYS,
                          now=os.path.getmtime(str(probe))
                          + (EIS_TTL_DAYS + 1) * 86400.0) is False
    assert cache_is_fresh(str(tmp_path / "missing.csv")) is False
    assert EIS_TTL_DAYS == 91


# ---------------------------------------------------------------------------
# P4-010 demo: grant status + queue bands.
# ---------------------------------------------------------------------------

def test_grant_granted_scores_85():
    v, reason = dim_eis_grant_status(FULL_EIS)
    assert v == 85
    assert "EIS" in reason


def test_grant_queue_names_position():
    v, reason = dim_eis_grant_status(QUEUED_EIS)
    assert v == 60
    assert "17" in reason
    v, reason = dim_eis_grant_status(dict(QUEUED_EIS, queue_pos=None))
    assert v == 60 and "järjekorras" in reason


def test_grant_applied_and_missing_bands():
    v, _ = dim_eis_grant_status(dict(FULL_EIS, grant_status="menetluses"))
    assert v == 50
    v, reason = dim_eis_grant_status(dict(FULL_EIS, grant_status="puudub"))
    assert v == 35 and "5-kohaline" in reason
    v, reason = dim_eis_grant_status(dict(FULL_EIS, grant_status="tagasi lükatud"))
    assert v == 35


def test_grant_missing_record_and_slice_stay_null():
    v, reason = dim_eis_grant_status(None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_eis_grant_status({"ehr_code": "x"})
    assert v is None and "EI OLE" in reason
    v, reason = dim_eis_grant_status(
        dict(FULL_EIS, grant_status="müstiline olek"))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-007 coverage: EIS loan-guarantee slice only.
# ---------------------------------------------------------------------------

def test_guarantee_active_scores_70_with_amount():
    v, reason = dim_ku_loan_guarantee(FULL_EIS)
    assert v == 70
    assert "120000" in reason
    assert "aruannetest" in reason


def test_guarantee_pending_and_absent_are_neutral_50():
    v, reason = dim_ku_loan_guarantee(QUEUED_EIS)
    assert v == 50 and "aruannetest" in reason
    v, reason = dim_ku_loan_guarantee(dict(FULL_EIS, guarantee_status="puudub"))
    assert v == 50 and "tavaseis" in reason


def test_guarantee_missing_record_and_slice_stay_null():
    v, reason = dim_ku_loan_guarantee(None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_ku_loan_guarantee({"ehr_code": "x"})
    assert v is None and "EI OLE" in reason
    v, reason = dim_ku_loan_guarantee(
        dict(FULL_EIS, guarantee_status="müstiline"))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-060 coverage: subsidy queue slice; fee zones stay NULL.
# ---------------------------------------------------------------------------

def test_queue_position_scores_55_with_zone_pointer():
    v, reason = dim_stormwater_subsidy_queue(QUEUED_EIS)
    assert v == 55
    assert "17" in reason
    assert "Tallinna Vesi" in reason


def test_granted_status_scores_70_without_queue_number():
    v, reason = dim_stormwater_subsidy_queue(FULL_EIS)
    assert v == 70 and "Tallinna Vesi" in reason
    v, reason = dim_stormwater_subsidy_queue(
        dict(FULL_EIS, grant_status="taotletud", subsidy_queue_pos=None))
    assert v == 50 and "Tallinna Vesi" in reason


def test_queue_missing_record_and_slice_stay_null():
    v, reason = dim_stormwater_subsidy_queue(None)
    assert v is None and "EI OLE" in reason
    v, reason = dim_stormwater_subsidy_queue({"ehr_code": "x"})
    assert v is None and "EI OLE" in reason
    assert "Tallinna Vesi" in reason


# ---------------------------------------------------------------------------
# Registry + aggregator cover all 3.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_all_3():
    assert [k for k, _, _ in P4_EIS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_EIS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_EIS_DIMS}) == 3
    out = score_p4_eis(FULL_EIS)
    assert set(out) == set(EXPECTED_KEYS)
    assert out["eis_grant_status"] == 85
    assert out["ku_loan_guarantee"] == 70
    assert out["stormwater_subsidy_queue"] == 70
    out = score_p4_eis(QUEUED_EIS)
    assert out["eis_grant_status"] == 60
    assert out["ku_loan_guarantee"] == 50
    assert out["stormwater_subsidy_queue"] == 55
    assert score_p4_eis(None) == {k: None for k in EXPECTED_KEYS}
    assert eis.P4_EIS_DIMS is P4_EIS_DIMS
