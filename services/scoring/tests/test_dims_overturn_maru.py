"""MARU/Stat/ECB overturn dims (issue #241): hermetic tests.

No network: every KOV/ECB row is a synthetic invented fixture (plain
dicts -- never scraped data, never a MARU dump). fetch_cached is covered
only on its cache-hit path; freshness/expiry uses tmp_path. The live
probes are manual DoD evidence (pasted in the PR + docs/overturn_maru.md),
not unit runs. Fixture ECB csvdata pins the live-verified TIME_PERIOD /
OBS_VALUE column contract.
"""

import os

import dims_overturn_maru as maru
from dims_overturn_maru import (
    OVERTURN_MARU_DIMS,
    OVERTURN_MARU_PARAM_IDS,
    RECHECK_AFTER,
    VERDICT_DATE,
    dim_appraisal_gap_p421,
    dim_absorption_p484,
    dim_appreciation_p41,
    dim_market_liquidity_p149,
    dim_resale_appeal_p43,
    ecb_latest_6m,
    fetch_cached,
    is_fresh,
    kov_latest_map,
    kov_quarters,
    latest_rows,
    normalise_kov,
    parse_ecb_csv,
    parse_maru_kov_csv,
    score_overturn_maru,
)

# Synthetic MARU-shaped quarterly KOV fixture (invented numbers -- the
# join SHAPE is what is pinned, never real MARU medians).
MARU_KOV = [
    {"kov": "Tallinn", "quarter": "2025-Q1", "median_eur_m2": 3200,
     "deals": 1700},
    {"kov": "Tallinn", "quarter": "2025-Q2", "median_eur_m2": 3300,
     "deals": 1900},
    {"kov": "Tallinn", "quarter": "2026-Q1", "median_eur_m2": 3450,
     "deals": 1800},
    {"kov": "Tallinn", "quarter": "2026-Q2", "median_eur_m2": 3500,
     "deals": 2100},
    # Viimsi: latest quarter only -- depth scores, history NULLs.
    {"kov": "Viimsi", "quarter": "2026-Q2", "median_eur_m2": 3100,
     "deals": 140},
    # Kose: thin market, falling median.
    {"kov": "Kose", "quarter": "2025-Q2", "median_eur_m2": 1500,
     "deals": 14},
    {"kov": "Kose", "quarter": "2026-Q2", "median_eur_m2": 1400,
     "deals": 12},
]

TALLINN = {"kov": "Tallinn", "eur_m2": 3600}
VIIMSI = {"kov": "Viimsi", "eur_m2": 3000}
KOSE = {"kov": "Kose", "eur_m2": 1500}


def test_exact_kov_match_only_no_neighbour_leak():
    # Case/whitespace variants join; near-miss names never do -- even
    # though Tallinn has full history, "Tallinna" stays NULL.
    assert kov_latest_map(MARU_KOV, "median_eur_m2")["tallinn"] == 3500.0
    v, reason = dim_appreciation_p41({"kov": "  TALLINN "}, MARU_KOV)
    assert v == 40  # (3500-3300)/3300 = +6.06% -> kiire kasv
    assert "hinnang" in reason
    v, reason = dim_appreciation_p41({"kov": "Tallinna"}, MARU_KOV)
    assert v is None
    assert "EI OLE" in reason and "ära feigi" in reason


def test_latest_quarter_only_never_trended():
    # Tallinn latest is 2026-Q2 (3500), not an average over quarters.
    assert latest_rows(MARU_KOV, "Tallinn")[0]["quarter"] == "2026-Q2"
    v, _ = dim_market_liquidity_p149({"kov": "Tallinn"}, MARU_KOV)
    assert v == 80  # 2100 deals -> deep
    v, _ = dim_market_liquidity_p149({"kov": "Viimsi"}, MARU_KOV)
    assert v == 65  # 140 deals, its OWN latest quarter
    v, reason = dim_market_liquidity_p149({"kov": "Kose"}, MARU_KOV)
    assert v == 35  # 12 deals -> thin
    assert "hinnang" in reason


def test_p41_yoy_bands_and_missing_pair_null():
    v, _ = dim_appreciation_p41(KOSE, MARU_KOV)
    assert v == 75  # (1400-1500)/1500 = -6.7% -> langus
    v, reason = dim_appreciation_p41(VIIMSI, MARU_KOV)
    assert v is None  # no year-ago row for Viimsi: no annualised guess
    assert "EI OLE" in reason and "hinnang" in reason
    v, reason = dim_appreciation_p41({"kov": "Nissi"}, MARU_KOV)
    assert v is None
    assert "EI OLE" in reason


def test_p421_asking_vs_kov_median_lives_here_not_in_p1():
    v, reason = dim_appraisal_gap_p421({"kov": "Tallinn", "eur_m2": 3400},
                                       MARU_KOV)
    assert v == 80  # under the 3500 median
    assert "hinnang" in reason
    assert "p1" in reason  # the issue contract: p1 stays a listing fact
    v, _ = dim_appraisal_gap_p421(TALLINN, MARU_KOV)  # 3600/3500 = 1.029
    assert v == 60
    v, _ = dim_appraisal_gap_p421({"kov": "Tallinn", "eur_m2": 4200},
                                  MARU_KOV)  # 1.20x
    assert v == 45
    v, reason = dim_appraisal_gap_p421({"kov": "Tallinn", "eur_m2": 4600},
                                       MARU_KOV)  # 1.31x
    assert v == 30
    assert "lõhe-risk" in reason
    v, reason = dim_appraisal_gap_p421({"kov": "Tallinn"}, MARU_KOV)
    assert v is None  # no asking: no gap to score
    assert "EI OLE" in reason
    v, reason = dim_appraisal_gap_p421({"kov": "Nissi", "eur_m2": 2000},
                                       MARU_KOV)
    assert v is None
    assert "EI OLE" in reason


def test_p43_composite_needs_both_legs():
    v, reason = dim_resale_appeal_p43(TALLINN, MARU_KOV)
    assert v == 70  # deep (2100) + rising (+6.06%)
    assert "hinnang" in reason
    v, _ = dim_resale_appeal_p43(KOSE, MARU_KOV)
    assert v == 35  # thin (12) + falling (-6.7%)
    v, reason = dim_resale_appeal_p43(VIIMSI, MARU_KOV)
    assert v is None  # depth without direction: no half-comp
    assert "EI OLE" in reason
    assert "suuna-jalga" in reason


def test_p484_weak_velocity_capped_at_70():
    v, reason = dim_absorption_p484(TALLINN, MARU_KOV)
    assert v == 70  # (2100-1800)/1800 = +16.7%, capped weak leg
    assert "NÕRK" in reason and "lagi 70" in reason
    assert "hinnang" in reason
    v, _ = dim_absorption_p484(KOSE, MARU_KOV)
    assert v == 40  # (12-14)/14 = -14.3% -> falling
    assert v <= 70
    v, reason = dim_absorption_p484(VIIMSI, MARU_KOV)
    assert v is None  # single quarter: no QoQ pair to trend
    assert "EI OLE" in reason


def test_choropleth_map_is_per_kov_latest_never_smoothed():
    paint = kov_latest_map(MARU_KOV, "deals")
    assert paint == {"tallinn": 2100.0, "viimsi": 140.0, "kose": 12.0}
    # Kose paints its OWN latest (2026-Q2), never Tallinn's depth.
    assert paint["kose"] != paint["tallinn"]
    assert kov_quarters("Kose", MARU_KOV) == ["2025-Q2", "2026-Q2"]
    assert kov_quarters("Nissi", MARU_KOV) == []


def test_ecb_series_stays_unmapped_display_only():
    rows = parse_ecb_csv(
        "KEY,TIME_PERIOD,OBS_VALUE,UNIT\n"
        "FM.M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA,2026-06,2.5955,PCPA\n"
        "FM.M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA,2026-07,2.6467391,PCPA\n"
        "FM.M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA,2026-08,2.7133333,PCPA\n"
        "FM.M.U2.EUR.RT.MM.EURIBOR6MD_.HSTA,2026-09,-,PCPA\n")
    assert ecb_latest_6m(rows) == (2.7133333, "2026-08")
    assert ecb_latest_6m([]) == (None, None)
    # The national constant has no dim, no param id, no map band.
    assert "ecb_latest_6m" not in [k for k, _, _ in OVERTURN_MARU_DIMS]
    assert set(OVERTURN_MARU_PARAM_IDS.values()) == {41, 149, 421, 43, 484}


def test_parse_maru_kov_csv_contract():
    rows = parse_maru_kov_csv(
        "\ufeffkov;quarter;median_eur_m2;deals;extra\n"
        "Tallinn;2026-Q2;3 500,0;2100;ignored\n"
        "Tallinn;2026-Q2;9999;9999;duplicate-first-wins\n"
        ";2026-Q2;1000;10;no-kov-skipped\n"
        "Nissi;2026-QX;1000;10;bad-quarter-skipped\n"
        "Kose;2026-Q2;;12;missing-median-kept\n")
    assert len(rows) == 2
    assert rows[0] == {"kov": "Tallinn", "quarter": "2026-Q2",
                       "median_eur_m2": 3500.0, "deals": 2100.0}
    assert rows[1]["median_eur_m2"] is None  # kept row, NULL leg downstream
    v, reason = dim_appraisal_gap_p421({"kov": "Kose", "eur_m2": 1400},
                                       rows)
    assert v is None
    assert "EI OLE" in reason


def test_registry_and_aggregator_cover_the_five_dims():
    assert [k for k, _, _ in OVERTURN_MARU_DIMS] == [
        "appreciation_maru", "market_liquidity_maru", "appraisal_gap_maru",
        "resale_appeal_maru", "absorption_maru"]
    assert [p for _, p, _ in OVERTURN_MARU_DIMS] == [
        "p41", "p149", "p421", "p43", "p484"]
    assert len({fn for _, _, fn in OVERTURN_MARU_DIMS}) == 5
    out = score_overturn_maru(TALLINN, {"maru_kov": MARU_KOV})
    assert out == {"appreciation_maru": 40, "market_liquidity_maru": 80,
                   "appraisal_gap_maru": 60, "resale_appeal_maru": 70,
                   "absorption_maru": 70}
    assert score_overturn_maru(TALLINN, {}) == {
        k: None for k, _, _ in OVERTURN_MARU_DIMS}
    assert score_overturn_maru(TALLINN, None) == {
        k: None for k, _, _ in OVERTURN_MARU_DIMS}
    assert maru.OVERTURN_MARU_DIMS is OVERTURN_MARU_DIMS


def test_all_reasons_carry_honesty_markers():
    probed = [
        dim_appreciation_p41(TALLINN, MARU_KOV),
        dim_market_liquidity_p149(TALLINN, MARU_KOV),
        dim_appraisal_gap_p421(TALLINN, MARU_KOV),
        dim_resale_appeal_p43(TALLINN, MARU_KOV),
        dim_absorption_p484(TALLINN, MARU_KOV),
        dim_appreciation_p41({"kov": "Nissi"}, MARU_KOV),
        dim_market_liquidity_p149({"kov": "Nissi"}, MARU_KOV),
        dim_appraisal_gap_p421({"kov": "Nissi"}, MARU_KOV),
        dim_resale_appeal_p43({"kov": "Nissi"}, MARU_KOV),
        dim_absorption_p484({"kov": "Nissi"}, MARU_KOV),
    ]
    for _, reason in probed:
        assert "hinnang" in reason
        assert "mõõdetud" not in reason and "garanteeritud" not in reason
    for _, reason in [p for p in probed if p[0] is None]:
        assert "EI OLE" in reason and "ära feigi" in reason


def test_verdict_is_dated_with_recheck_note():
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER == "2027-03-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_fetch_cache_hit_path_needs_no_network(tmp_path):
    dest = os.path.join(str(tmp_path), "hf-overturn-maru", "ecb.csv")
    os.makedirs(os.path.dirname(dest))
    with open(dest, "w") as fh:
        fh.write("cached")
    assert fetch_cached("https://example.invalid/x", str(tmp_path),
                        "ecb.csv", 7) == dest
    assert is_fresh(dest, 7) is True
    assert is_fresh(os.path.join(str(tmp_path), "missing.csv"), 7) is False
    assert normalise_kov("  Tallinna  Linn ") == "tallinna linn"
    assert normalise_kov(None) is None
