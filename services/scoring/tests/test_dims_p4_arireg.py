"""P4 e-Äriregister KÜ reports demo + coverage dims (issues #257, #338): tests.

Hermetic: fetch_arireg_snapshot is never called against the network
here (its contract - single polite GET, file cache, TTL, transport
errors never cached - is covered via the cache-hit and no-endpoint
paths with a stubbed opener that raises if touched). Every dim is
tested on fixture KÜ records through the per-record join shape:
joined rows -> bands, missing record/slice -> NULL with Estonian
honesty markers.

Fixtures mirror the RIK open-data report layout observed 2026-09-13
(majandusaastaAruanneteLoetelu_v1 list + arireg.majandusaastaAruannete
Kirjed_v1 rows: current + previous fund periods) but every company,
registry code, and number is SYNTHETIC - never a real pull (repo
hygiene: fixtures only, no scraped dumps).
"""

import json
import os

import dims_p4_arireg as arireg
from dims_p4_arireg import (
    ARIREG_BULK_URL,
    ARIREG_TTL_S,
    P4_ARIREG_DIMS,
    dim_commons_echo,
    dim_dead_stairwell_arireg,
    dim_developer_age_arireg,
    dim_enforcement_arireg,
    dim_grant_fund_echo,
    dim_heating_cost,
    dim_heatpump_echo,
    dim_herd_arireg,
    dim_ku_loan,
    dim_maintenance_echo,
    dim_repair_fund,
    dim_roof_echo,
    dim_smell_arireg,
    dim_stormwater_echo,
    dim_turnover_echo,
    dim_waste_echo,
    fetch_arireg_snapshot,
    index_by_registry_code,
    parse_arireg_snapshot,
    score_p4_arireg,
)


def _base(**over):
    rec = {
        "registry_code": "81234567",
        "name": "Näidis KÜ",
        "tallinn": True,
        "report_year": 2024,
        "area_m2": 3000.0,
        "loan_balance": 0.0,
        "repair_fund_balance": 60000.0,
        "repair_fund_prev": 50000.0,
        "heating_cost_annual": 30000.0,
        "maintenance_cost_annual": 12000.0,
        "waste_cost_annual": 3000.0,
        "stormwater_cost_annual": 900.0,
        "heating_capex_note": "katlamaja renoveeritud 2023",
        "roof_state": "katus rahuldav, soojustus puudulik",
        "payment_defaults": 0,
        "report_debts": False,
        "founded_year": 1998,
        "turnover_annual": 45000.0,
    }
    rec.update(over)
    return rec


FULL = _base()  # loan 0.00/m2, fund 20.00/m2, heat 10.00/m2, age 26

EXPECTED_KEYS = [
    "ku_loan_per_m2",
    "repair_fund_per_m2",
    "heating_cost_per_m2",
    "grant_fund_cover_arireg",
    "enforcement_arireg",
    "developer_age_arireg",
    "fixit_cost_arireg",
    "overheat_roof_arireg",
    "civic_commons_arireg",
    "smell_arireg",
    "herd_arireg",
    "dead_stairwell_arireg",
    "turnover_fund_arireg",
    "heatpump_capex_arireg",
    "stormwater_cost_arireg",
    "waste_cost_arireg",
]

EXPECTED_PNUMS = [
    "P4-007", "P4-007", "P4-007",
    "P4-010", "P4-020", "P4-021", "P4-026", "P4-034", "P4-039",
    "P4-042", "P4-044", "P4-051", "P4-052", "P4-057", "P4-060",
    "P4-062",
]

SCORED_FNS = (
    dim_ku_loan,
    dim_repair_fund,
    dim_heating_cost,
    dim_enforcement_arireg,
    dim_developer_age_arireg,
    dim_dead_stairwell_arireg,
)

ECHO_FNS = (
    dim_grant_fund_echo,
    dim_maintenance_echo,
    dim_roof_echo,
    dim_commons_echo,
    dim_smell_arireg,
    dim_herd_arireg,
    dim_turnover_echo,
    dim_heatpump_echo,
    dim_stormwater_echo,
    dim_waste_echo,
)

ALL_FNS = SCORED_FNS + ECHO_FNS


# ---------------------------------------------------------------------------
# Ingestion contract: TTL stated, no endpoint performs no requests.
# ---------------------------------------------------------------------------

def test_ttl_is_quarterly_and_bulk_url_stays_none():
    assert ARIREG_TTL_S == 90 * 24 * 3600
    assert ARIREG_BULK_URL is None


def test_fetch_without_endpoint_performs_no_request(tmp_path):
    def _boom(req, timeout=None):
        raise AssertionError("network must not be touched")
    import urllib.request
    real = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        assert fetch_arireg_snapshot(str(tmp_path)) is None
    finally:
        urllib.request.urlopen = real


def test_fetch_cache_hit_returns_path_without_request(tmp_path):
    dest = os.path.join(str(tmp_path), "arireg-ku-snapshot.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump({"reports": []}, fh)
    def _boom(req, timeout=None):
        raise AssertionError("network must not be touched")
    import urllib.request
    real = urllib.request.urlopen
    urllib.request.urlopen = _boom
    try:
        assert fetch_arireg_snapshot(str(tmp_path)) == dest
    finally:
        urllib.request.urlopen = real


# ---------------------------------------------------------------------------
# Offline readers: schema sanitising, join index.
# ---------------------------------------------------------------------------

def test_parse_round_trip_and_index(tmp_path):
    path = os.path.join(str(tmp_path), "snap.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"reports": [
            {"registry_code": " 81234567 ", "name": "Näidis KÜ",
             "tallinn": True, "report_year": "2024",
             "area_m2": "3000", "loan_balance": 0,
             "repair_fund_balance": 60000.5, "repair_fund_prev": None,
             "heating_cost_annual": "30000", "payment_defaults": "2",
             "report_debts": 0, "founded_year": 1998,
             "turnover_annual": "45000", "heating_capex_note": "  ",
             "roof_state": "katus rahuldav"},
            {"name": " ilma koodita "},  # skipped: no join key
            "prügi",  # skipped: not a row
            {"registry_code": "81234567", "loan_balance": 1},  # dup
        ]}, fh)
    snap = parse_arireg_snapshot(path)
    assert snap is not None and len(snap["reports"]) == 2
    rec = snap["reports"][0]
    assert rec["registry_code"] == "81234567"
    assert rec["area_m2"] == 3000.0
    assert rec["report_year"] == 2024
    assert rec["payment_defaults"] == 2
    assert rec["report_debts"] is False
    assert rec["heating_capex_note"] is None  # blank -> None, never faked
    idx = index_by_registry_code(snap["reports"])
    assert idx["81234567"]["loan_balance"] == 0  # first row wins


def test_parse_rejects_garbage_money_and_missing_file(tmp_path):
    path = os.path.join(str(tmp_path), "snap.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"reports": [
            {"registry_code": "80000001", "loan_balance": -5,
             "repair_fund_balance": "teadmata", "area_m2": True,
             "payment_defaults": -1, "turnover_annual": "inf"},
        ]}, fh)
    rec = parse_arireg_snapshot(path)["reports"][0]
    assert rec["loan_balance"] is None
    assert rec["repair_fund_balance"] is None
    assert rec["area_m2"] is None
    assert rec["payment_defaults"] is None
    assert rec["turnover_annual"] is None
    assert parse_arireg_snapshot(os.path.join(str(tmp_path), "puudu.json")) is None
    bad = os.path.join(str(tmp_path), "bad.json")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("{ei ole json")
    assert parse_arireg_snapshot(bad) is None
    assert parse_arireg_snapshot(bad.replace("bad", "bad2")) is None


# ---------------------------------------------------------------------------
# Demo P4-007: loan + fund + heating bands.
# ---------------------------------------------------------------------------

def test_demo_bands_cover_all_three_fields():
    assert dim_ku_loan(_base(loan_balance=0.0))[0] == 85
    assert dim_ku_loan(_base(loan_balance=150000.0))[0] == 65  # 50.00/m2
    assert dim_ku_loan(_base(loan_balance=450000.0))[0] == 40  # 150.00/m2
    assert dim_ku_loan(_base(loan_balance=600000.0))[0] == 20  # 200.00/m2
    assert dim_repair_fund(_base(repair_fund_balance=0.0))[0] == 25
    assert dim_repair_fund(_base(repair_fund_balance=6000.0))[0] == 25  # 2.00
    assert dim_repair_fund(_base(repair_fund_balance=6300.0))[0] == 40  # 2.10
    assert dim_repair_fund(_base(repair_fund_balance=24000.0))[0] == 40  # 8.00
    assert dim_repair_fund(_base(repair_fund_balance=24300.0))[0] == 60  # 8.10
    assert dim_repair_fund(_base(repair_fund_balance=90000.0))[0] == 80  # 30.00
    assert dim_heating_cost(_base(heating_cost_annual=24000.0))[0] == 80  # 8.00
    assert dim_heating_cost(_base(heating_cost_annual=42000.0))[0] == 60  # 14.00
    assert dim_heating_cost(_base(heating_cost_annual=66000.0))[0] == 40  # 22.00
    assert dim_heating_cost(_base(heating_cost_annual=90000.0))[0] == 25  # 30.00


def test_demo_fields_fail_independently():
    only_loan = {"registry_code": "80000002", "tallinn": True,
                 "report_year": 2024, "area_m2": 1000.0, "loan_balance": 0.0}
    assert dim_ku_loan(only_loan)[0] == 85
    assert dim_repair_fund(only_loan)[0] is None
    assert dim_heating_cost(only_loan)[0] is None
    # no area: per-m2 dims stay NULL, never divided by a guess
    assert dim_ku_loan(_base(area_m2=None))[0] is None
    assert dim_ku_loan(_base(area_m2=0))[0] is None
    assert dim_repair_fund(_base(area_m2=0))[0] is None


def test_demo_scored_reasons_carry_components_and_cap():
    v, reason = dim_ku_loan(FULL)
    assert v == 85 and "hinnang" in reason
    assert "0.00 EUR/m2" in reason and "81234567" in reason
    assert "ülempiir 85" in reason
    v, reason = dim_repair_fund(FULL)
    assert v == 60 and "20.00 EUR/m2" in reason
    v, reason = dim_heating_cost(FULL)
    assert v == 60 and "10.00 EUR/m2" in reason


# ---------------------------------------------------------------------------
# Missing record / Tallinn gate: NULL stays NULL for every dim.
# ---------------------------------------------------------------------------

def test_missing_record_and_gate_stay_null_for_all_sixteen():
    for fn in ALL_FNS:
        v, reason = fn(None)
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        v, reason = fn({"registry_code": "80000003", "tallinn": False,
                        "report_year": 2024, "area_m2": 100.0,
                        "loan_balance": 0.0})
        assert v is None, fn.__name__
        assert "väljaspool Tallinna" in reason, fn.__name__
    # missing tallinn flag defaults to relevant (absence is not evidence)
    assert dim_ku_loan({"registry_code": "80000004", "area_m2": 100.0,
                        "loan_balance": 0.0})[0] == 85


# ---------------------------------------------------------------------------
# Coverage scored legs: P4-020 enforcement, P4-021 age, P4-051 stairwell.
# ---------------------------------------------------------------------------

def test_enforcement_active_is_strong_bad_never_zero():
    v, reason = dim_enforcement_arireg(_base(payment_defaults=3))
    assert v == 20 and "hinnang" in reason and "maksehäireid 3" in reason
    v, reason = dim_enforcement_arireg(
        _base(payment_defaults=None, report_debts=True))
    assert v == 20 and "aruandevõlad" in reason
    assert "Creditinfo" in reason  # unjoined checks named


def test_enforcement_clean_caps_at_70_and_missing_stays_null():
    v, reason = dim_enforcement_arireg(FULL)
    assert v == 70 and "ülempiir 70" in reason
    assert "teadaanded" in reason and "täitur" in reason
    v, reason = dim_enforcement_arireg(
        _base(payment_defaults=None, report_debts=None))
    assert v is None and "EI OLE" in reason


def test_developer_age_bands_and_turnover_tail():
    assert dim_developer_age_arireg(
        _base(founded_year=2023, report_year=2024))[0] == 45
    v, reason = dim_developer_age_arireg(
        _base(founded_year=2018, report_year=2024))
    assert v == 60 and "6 a" in reason and "käive 45000 EUR/a" in reason
    v, reason = dim_developer_age_arireg(FULL)
    assert v == 75 and "26 a" in reason and "ülempiir 75" in reason
    assert "TTJA" in reason
    v, reason = dim_developer_age_arireg(_base(founded_year=None))
    assert v is None and "EI OLE" in reason
    # no turnover on record: age still scores, tail says so
    v, reason = dim_developer_age_arireg(_base(turnover_annual=None))
    assert v == 75 and "käive teadmata" in reason


def test_dead_stairwell_is_bad_side_only():
    v, reason = dim_dead_stairwell_arireg(_base(payment_defaults=2))
    assert v == 30 and "heksilipp" in reason and "mitte hoone-otsus" in reason
    v, reason = dim_dead_stairwell_arireg(
        _base(payment_defaults=None, report_debts=True))
    assert v == 30
    # clean ledger does NOT clear the hex: NULL, never a high score
    v, reason = dim_dead_stairwell_arireg(FULL)
    assert v is None and "EI OLE" in reason
    assert "heksi puhtaks ei pese" in reason


# ---------------------------------------------------------------------------
# Coverage NULL-echoes: each names its consumed slice with figures.
# ---------------------------------------------------------------------------

def test_echo_dims_carry_their_consumed_slice():
    v, reason = dim_grant_fund_echo(FULL)
    assert v is None and "kogutud fond 20.00 EUR/m2" in reason
    assert "EIS register liitmata" in reason
    v, reason = dim_maintenance_echo(FULL)
    assert v is None and "hoolduskulu 4.00 EUR/m2/a" in reason
    v, reason = dim_roof_echo(FULL)
    assert v is None and "katus rahuldav, soojustus puudulik" in reason
    v, reason = dim_commons_echo(FULL)
    assert v is None and "kogutud fond 20.00 EUR/m2" in reason
    assert "valimisaktiivsus" in reason
    v, reason = dim_turnover_echo(FULL)
    assert v is None and "fondidünaamika 50000 -> 60000 EUR" in reason
    assert "mõlemad lugemid lahtised" in reason
    v, reason = dim_heatpump_echo(FULL)
    assert v is None and "katlamaja renoveeritud 2023" in reason
    v, reason = dim_stormwater_echo(FULL)
    assert v is None and "sademevee kulu 0.30 EUR/m2/a" in reason
    v, reason = dim_waste_echo(FULL)
    assert v is None and "prügivedu 1.00 EUR/m2/a" in reason
    assert "hooldus 4.00 EUR/m2/a" in reason


def test_address_cluster_params_name_the_missing_join():
    v, reason = dim_smell_arireg(FULL)
    assert v is None and "EI OLE" in reason
    assert "aadressiklaster" in reason and "Keskkonnaameti" in reason
    v, reason = dim_herd_arireg(FULL)
    assert v is None and "EI OLE" in reason
    assert "aadressiklaster" in reason and "REL2021" in reason


def test_echo_dims_without_their_slice_still_null_with_gap_named():
    thin = {"registry_code": "80000005", "tallinn": True, "report_year": 2024}
    for fn in ECHO_FNS:
        v, reason = fn(thin)
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__
    _, reason = dim_grant_fund_echo(thin)
    assert "fondirida aruandes puudu" in reason
    _, reason = dim_turnover_echo(thin)
    assert "A1/A2" in reason


# ---------------------------------------------------------------------------
# Honesty markers + registry coverage.
# ---------------------------------------------------------------------------

def test_scored_reasons_say_hinnang_and_nulls_say_ei_ole():
    for fn in SCORED_FNS:
        _, reason = fn(FULL)
        if fn is dim_dead_stairwell_arireg:
            continue  # clean side is NULL by shape (pinned above)
        assert "hinnang" in reason, fn.__name__
    for fn in ALL_FNS:
        _, reason = fn(None)
        assert "EI OLE" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_registry_and_aggregator_cover_all_sixteen():
    assert [k for k, _, _ in P4_ARIREG_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_ARIREG_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_ARIREG_DIMS}) == 16
    out = score_p4_arireg(FULL)
    assert out == {
        "ku_loan_per_m2": 85,
        "repair_fund_per_m2": 60,
        "heating_cost_per_m2": 60,
        "grant_fund_cover_arireg": None,
        "enforcement_arireg": 70,
        "developer_age_arireg": 75,
        "fixit_cost_arireg": None,
        "overheat_roof_arireg": None,
        "civic_commons_arireg": None,
        "smell_arireg": None,
        "herd_arireg": None,
        "dead_stairwell_arireg": None,
        "turnover_fund_arireg": None,
        "heatpump_capex_arireg": None,
        "stormwater_cost_arireg": None,
        "waste_cost_arireg": None,
    }
    assert score_p4_arireg(None) == {k: None for k in EXPECTED_KEYS}
    assert arireg.P4_ARIREG_DIMS is P4_ARIREG_DIMS
