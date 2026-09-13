"""P4 kudocs demo + coverage dims (issues #258, #339): hermetic tests.

No network: fetch_kudocs_csv is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus fixture-fed parse
tests). Every dim is tested on fixture KÜ-bundle records through the
per-ku_code join shape: joined record -> bands, missing
record/slice -> NULL with Estonian honesty markers.
"""

import os
import time

import dims_p4_kudocs as kudocs
from dims_p4_kudocs import (
    KUDOCS_DIMS,
    KUDOCS_TTL_DAYS,
    cache_is_fresh,
    dim_horrors_ku,
    dim_ku_finance,
    index_by_ku_code,
    parse_kudocs,
    score_kudocs,
)

FULL_CSV = (
    "ku_code;address;has_loan;loan_balance_eur;loan_maturity_year;"
    "remondifond_eur_m2_month;heating_eur_m2_year;"
    "decisions_total;decisions_open;complaints_12m;record_date\n"
    "80012345;Tallinn, Sõpruse pst 12;jah;125 000;2031;0,65;11,40;9;2;5;2026-06-01\n"
    "80099999;Tallinn, Vaikne tn 1;ei;;;0,80;9,20;4;0;0;2026-05-15\n"
    ";puuduv kood;rida;jäetakse;vahele;;;;;;;\n"
)

THIN_CSV = (
    "ku_code;has_loan;complaints_12m\n"
    "80011111;ei;\n"
    "80022222;;2\n"
)

LOAN_BARE = {"ku_code": "8001", "has_loan": True}
LOAN_FULL = {"ku_code": "8001", "has_loan": True, "loan_balance_eur": 125000,
             "loan_maturity_year": 2031, "heating_eur_m2_year": 11.4,
             "decisions_open": 2}
NO_LOAN_FUND = {"ku_code": "8002", "has_loan": False,
                "remondifond_eur_m2_month": 0.8,
                "heating_eur_m2_year": 9.2, "decisions_open": 0}
NO_LOAN_THIN = {"ku_code": "8003", "has_loan": False}
FUND_UNKNOWN_LOAN = {"ku_code": "8004",
                     "remondifond_eur_m2_month": 0.5}
HEAT_ONLY = {"ku_code": "8005", "heating_eur_m2_year": 10.0}
EMPTY_SLICE = {"ku_code": "8006", "address": "Tallinn"}


# ---------------------------------------------------------------------------
# Ingestion: parse + index + cache freshness (no network).
# ---------------------------------------------------------------------------

def test_parse_full_rows_comma_decimals_and_thousands_space():
    recs = parse_kudocs(FULL_CSV)
    assert len(recs) == 2  # ku_code-less row skipped
    first = recs[0]
    assert first["ku_code"] == "80012345"
    assert first["has_loan"] is True
    assert first["loan_balance_eur"] == 125000
    assert first["loan_maturity_year"] == 2031
    assert first["remondifond_eur_m2_month"] == 0.65
    assert first["heating_eur_m2_year"] == 11.4
    assert first["decisions_total"] == 9
    assert first["decisions_open"] == 2
    assert first["complaints_12m"] == 5
    assert first["record_date"] == "2026-06-01"
    second = recs[1]
    assert second["has_loan"] is False
    assert second["loan_balance_eur"] is None
    assert second["complaints_12m"] == 0


def test_parse_thin_layout_missing_columns_are_none():
    recs = parse_kudocs(THIN_CSV)
    assert len(recs) == 2
    assert recs[0]["has_loan"] is False
    assert recs[0]["complaints_12m"] is None
    assert recs[0]["heating_eur_m2_year"] is None
    assert recs[1]["has_loan"] is None
    assert recs[1]["complaints_12m"] == 2


def test_parse_bom_tolerant_and_bool_variants():
    recs = parse_kudocs("﻿ku_code;has_loan\n8001;kehtib\n8002;puudub\n")
    assert [r["ku_code"] for r in recs] == ["8001", "8002"]
    assert recs[0]["has_loan"] is True
    assert recs[1]["has_loan"] is False
    recs = parse_kudocs("ku_code;has_loan\n8003;maybe\n")
    assert recs[0]["has_loan"] is None


def test_index_first_row_wins_and_ttl_is_quarterly():
    recs = parse_kudocs(FULL_CSV)
    index = index_by_ku_code(recs + [{"ku_code": "80012345",
                                      "complaints_12m": 99}])
    assert set(index) == {"80012345", "80099999"}
    assert index["80012345"]["complaints_12m"] == 5
    assert KUDOCS_TTL_DAYS == 90


def test_cache_is_fresh_missing_stale_and_fresh(tmp_path):
    missing = os.path.join(str(tmp_path), "nope.csv")
    assert cache_is_fresh(missing) is False
    stale = os.path.join(str(tmp_path), "stale.csv")
    with open(stale, "w", encoding="utf-8") as f:
        f.write("x")
    old = time.time() - (KUDOCS_TTL_DAYS + 1) * 86400.0
    os.utime(stale, (old, old))
    assert cache_is_fresh(stale) is False
    fresh = os.path.join(str(tmp_path), "fresh.csv")
    with open(fresh, "w", encoding="utf-8") as f:
        f.write("x")
    assert cache_is_fresh(fresh) is True


# ---------------------------------------------------------------------------
# P4-007: loan/fund bands.
# ---------------------------------------------------------------------------

def test_p4007_missing_record_and_nondict_are_null():
    for bad in (None, [], "80012345"):
        v, reason = dim_ku_finance(bad)
        assert v is None
        assert "EI OLE" in reason and "KÜ dokumendid" in reason


def test_p4007_empty_slice_is_null():
    v, reason = dim_ku_finance(EMPTY_SLICE)
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason


def test_p4007_active_loan_is_weak_bad_with_balance_echo():
    v, reason = dim_ku_finance(LOAN_FULL)
    assert v == 35
    assert "laenuotsus" in reason and "125000" in reason
    assert "2031" in reason and "mitte hinnang" in reason
    v, _ = dim_ku_finance(LOAN_BARE)
    assert v == 35


def test_p4007_no_loan_with_fund_is_weak_good():
    v, reason = dim_ku_finance(NO_LOAN_FUND)
    assert v == 70
    assert "0,80" in reason and "mitte hinnang" in reason
    assert "9,20" in reason  # heating echoed, P4-008 owns the tariff


def test_p4007_no_loan_thin_file_stays_neutral_good():
    v, reason = dim_ku_finance(NO_LOAN_THIN)
    assert v == 60
    assert "õhuke toimik" in reason


def test_p4007_unknown_loan_with_fund_states_the_gap():
    v, reason = dim_ku_finance(FUND_UNKNOWN_LOAN)
    assert v == 60
    assert "teadmata" in reason and "EI OLE" in reason


def test_p4007_heating_only_is_null_with_echo():
    v, reason = dim_ku_finance(HEAT_ONLY)
    assert v is None
    assert "10,00" in reason and "EI OLE hinnangut" in reason


def test_p4007_open_decisions_echoed_only_when_positive():
    _, with_open = dim_ku_finance(LOAN_FULL)
    assert "täitmata haldusotsuseid 2" in with_open
    _, without_open = dim_ku_finance(NO_LOAN_FUND)
    assert "täitmata" not in without_open


# ---------------------------------------------------------------------------
# P4-047: complaint-log bands (counts only).
# ---------------------------------------------------------------------------

def test_p4047_missing_record_is_null():
    v, reason = dim_horrors_ku(None)
    assert v is None
    assert "EI OLE" in reason and "kaebuste logi" in reason


def test_p4047_missing_or_invalid_count_is_null_not_quiet():
    for bad in ({"ku_code": "x"}, {"ku_code": "x", "complaints_12m": -1},
                {"ku_code": "x", "complaints_12m": True}):
        v, reason = dim_horrors_ku(bad)
        assert v is None, bad
        assert "EI OLE" in reason


def test_p4047_zero_is_quiet_single_is_neutral_many_is_weak_bad():
    v, reason = dim_horrors_ku({"ku_code": "x", "complaints_12m": 0})
    assert v == 75 and "mitte hinnang" in reason
    for count in (1, 3):
        v, reason = dim_horrors_ku({"ku_code": "x",
                                    "complaints_12m": count})
        assert v == 60, count
        assert str(count) in reason and "kalendrit" in reason
    for count in (4, 9):
        v, reason = dim_horrors_ku({"ku_code": "x",
                                    "complaints_12m": count})
        assert v == 40, count
        assert str(count) in reason


def test_all_reasons_carry_ku_marker_and_no_fake_precision():
    fixtures = (LOAN_FULL, NO_LOAN_FUND, NO_LOAN_THIN, FUND_UNKNOWN_LOAN,
                HEAT_ONLY, EMPTY_SLICE, None,
                {"ku_code": "x", "complaints_12m": 0},
                {"ku_code": "x", "complaints_12m": 5},
                {"ku_code": "x"})
    for fix in fixtures:
        for fn in (dim_ku_finance, dim_horrors_ku):
            _, reason = fn(fix)
            assert "KÜ" in reason, (fn.__name__, fix)
            assert "hinnang" in reason, (fn.__name__, fix)
            assert "mõõdetud" not in reason
            assert "garanteeritud" not in reason


def test_registry_and_aggregator_cover_both_params():
    assert [k for k, _, _ in KUDOCS_DIMS] == ["ku_finance", "horrors_ku"]
    assert [p for _, p, _ in KUDOCS_DIMS] == ["P4-007", "P4-047"]
    out = score_kudocs(LOAN_FULL)
    assert out == {"ku_finance": 35, "horrors_ku": None}
    out = score_kudocs({"ku_code": "x", "has_loan": False,
                        "remondifond_eur_m2_month": 0.8,
                        "complaints_12m": 0})
    assert out == {"ku_finance": 70, "horrors_ku": 75}
    assert score_kudocs(None) == {"ku_finance": None, "horrors_ku": None}
    assert kudocs.KUDOCS_DIMS is KUDOCS_DIMS
