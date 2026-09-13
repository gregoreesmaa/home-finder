"""P4 Statamet tables dims (issues #292 demo + #365 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory table row (plain dicts —
no scraped data, no literal KK11 pulls). fetch_cached is covered only on
its cache-hit path; freshness/expiry uses tmp_path. The live probes are
manual DoD evidence (pasted in the PR + docs/p4_stat.md), not unit runs.
"""

import os
import time

import dims_p4_stat as p4
from dims_p4_stat import (
    P4_STAT_DIMS,
    cache_path,
    dim_bargaining_margin_stat,
    dim_kov_fiscal_stat,
    dim_last_shop_spiral_stat,
    dim_micro_liquidity_stat,
    dim_number13_baseline_stat,
    dim_permit_glut_stat,
    dim_price_history_dom_stat,
    dim_rent_reality_stat,
    dim_stat_micro_comp_anchor,
    dim_zero_consumption_stat,
    is_fresh,
    latest_rows,
    normalise_area,
    score_p4_stat,
)

TODAY = "2026-09-13"

# Synthetic Tallinn fixtures (invented numbers, never scraped data,
# KK11-shaped area medians — labelled as such, not literal KK11 pulls).
MEDIANS = [
    {"area": "Kesklinn", "quarter": "2026-Q1", "median_eur_m2": 3300.0},
    {"area": "Kesklinn", "quarter": "2026-Q2", "median_eur_m2": 3400.0},
    {"area": "Lasnamäe", "quarter": "2026-Q2", "median_eur_m2": 2400.0},
    {"area": "Tallinn", "quarter": "2026-Q2", "median_eur_m2": 2900.0},
]
RENTS = [
    {"area": "Kesklinn", "year": 2024, "median_rent_eur": 600.0},
    {"area": "Kesklinn", "year": 2025, "median_rent_eur": 650.0},
    {"area": "Lasnamäe", "year": 2025, "median_rent_eur": 450.0},
]
KOV = [
    {"kov": "Tallinn", "year": 2024, "debt_burden_pct": 38.0,
     "investment_per_capita": 400.0, "operating_result_per_capita": 40.0},
    {"kov": "Tallinn", "year": 2025, "debt_burden_pct": 35.0,
     "investment_per_capita": 420.0, "operating_result_per_capita": 60.0},
]
MIGR = [
    {"area": "Lasnamäe", "year": 2024, "in_migrants": 4800,
     "out_migrants": 5000, "population": 120000},
    {"area": "Lasnamäe", "year": 2025, "in_migrants": 5200,
     "out_migrants": 4800, "population": 120000},
    {"area": "Kesklinn", "year": 2025, "in_migrants": 7000,
     "out_migrants": 5000, "population": 65000},
]
INDEX = [
    {"area": "Tallinn", "quarter": "2026-Q2", "index_qoq_pct": -1.5},
    {"area": "Kesklinn", "quarter": "2026-Q2", "index_qoq_pct": 3.0},
]
PERMITS = [
    {"area": "Lasnamäe", "quarter": "2026-Q2", "permits": 240,
     "completions": 80},
    {"area": "Kesklinn", "quarter": "2026-Q2", "permits": 60,
     "completions": 80},
]
EMPTY = [
    {"area": "Lasnamäe", "year": 2025, "empty_dwellings": 300,
     "dwellings": 10000},
    {"area": "Kesklinn", "year": 2025, "empty_dwellings": 900,
     "dwellings": 10000},
]
FRINGE = [
    {"settlement": "Maardu", "pop_change_pct": -1.2, "deals_12mo": 25},
    {"settlement": "Saue", "pop_change_pct": 0.8, "deals_12mo": 45},
]

ALL_FNS = [fn for _, _, fn in P4_STAT_DIMS]
EXPECTED_KEYS = ["micro_comp_anchor", "price_history_dom_stat",
                 "rent_reality_stat", "kov_fiscal_stat",
                 "micro_liquidity_stat", "bargaining_margin_stat",
                 "number13_baseline_stat", "permit_glut_stat",
                 "zero_consumption_stat", "last_shop_spiral_stat"]
EXPECTED_PNUMS = ["P4-002", "P4-001", "P4-003", "P4-019", "P4-025",
                  "P4-038", "P4-043", "P4-050", "P4-051", "P4-061"]


def rich_listing(**kw):
    base = {"eur_m2": 3200.0, "price_eur": 160000.0, "area": "Kesklinn",
            "kov": "Tallinn", "settlement": "Saue",
            "floor": 4, "house_number": "25",
            "first_seen": "2026-05-01", "price_cuts": 2}
    base.update(kw)
    return base


def tables(**kw):
    base = {"area_medians": MEDIANS, "rents": RENTS, "kov_finance": KOV,
            "migration": MIGR, "price_index": INDEX, "permits": PERMITS,
            "empty": EMPTY, "fringe": FRINGE}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Helpers: normalisation, latest-period join, cache/fetch hermetic paths.
# ---------------------------------------------------------------------------

def test_normalise_exact_match_only():
    assert normalise_area("  KesklinN  ") == "kesklinn"
    assert normalise_area(None) is None
    assert normalise_area("   ") is None


def test_latest_rows_latest_period_and_exact_area_only():
    rows = latest_rows(MEDIANS, "Kesklinn")
    assert [r["quarter"] for r in rows] == ["2026-Q2"]
    assert latest_rows(MEDIANS, "kesklinn") == rows  # case-insensitive
    assert latest_rows(MEDIANS, "Kesklinn osa") == []  # no fuzzy leak
    assert latest_rows(MEDIANS, "Lasna") == []  # no prefix leak
    assert latest_rows(MEDIANS, None) == []
    assert latest_rows(MIGR, "Lasnamäe", period_key="year") == [MIGR[1]]
    # Neighbouring areas never leak: Lasnamäe rows exclude Kesklinn.
    assert {r["area"] for r in latest_rows(MEDIANS, "Lasnamäe")} == \
        {"Lasnamäe"}


def test_cache_path_and_freshness_hermetic(tmp_path):
    p = cache_path(str(tmp_path), "x.json")
    assert p == os.path.join(str(tmp_path), p4.CACHE_SUBDIR, "x.json")
    assert is_fresh(p, 91) is False  # missing file is never fresh
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{}")
    assert is_fresh(p, 91) is True
    old = time.time() - 400 * 86400
    os.utime(p, (old, old))
    assert is_fresh(p, 365) is False  # annual TTL expires too


def test_fetch_cached_cache_hit_never_touches_network(tmp_path):
    p = cache_path(str(tmp_path), "RVR02.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"cached")
    # Unreachable URL + fresh cache: must return without raising.
    assert p4.fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                           "RVR02.json", 365) == p


def test_source_urls_and_ttls_cover_all_legs():
    for key in ("px_root", "px_hinnad", "px_permits", "px_ranne",
                "px_RVR02", "px_eluruumid", "px_kov_eelarve"):
        assert p4.SOURCE_URLS[key].startswith("https://andmed.stat.ee/")
    assert p4.TTL_DAYS["stat_quarterly"] == 91
    assert p4.TTL_DAYS["stat_annual"] == 365
    assert p4.USER_AGENT.startswith("home-finder-research/0.1")


# ---------------------------------------------------------------------------
# Demo dim: P4-002 Stat-table anchor.
# ---------------------------------------------------------------------------

def test_demo_anchor_fair_and_overpriced():
    v, reason = dim_stat_micro_comp_anchor(rich_listing(eur_m2=3200.0),
                                           MEDIANS)
    assert v == 100  # 3400/3200 capped: at/under median
    assert "hinnang" in reason
    v, reason = dim_stat_micro_comp_anchor(rich_listing(eur_m2=4250.0),
                                           MEDIANS)
    assert v == 80  # 3400/4250
    assert "Kesklinn" in reason


def test_demo_anchor_latest_quarter_only():
    # Q1 median 3300 must NOT dilute the Q2 anchor 3400.
    v, _ = dim_stat_micro_comp_anchor(rich_listing(eur_m2=3400.0), MEDIANS)
    assert v == 100


def test_demo_anchor_nulls_stay_null_with_estonian_reason():
    v, reason = dim_stat_micro_comp_anchor(rich_listing(eur_m2=None),
                                           MEDIANS)
    assert v is None and "EI OLE" in reason and "hinnang" in reason
    v, reason = dim_stat_micro_comp_anchor(rich_listing(area="Pirita"),
                                           MEDIANS)
    assert v is None and "EI OLE" in reason
    assert "hoone" in reason or "maaklerilt" in reason  # finer-check pointer
    v, reason = dim_stat_micro_comp_anchor(rich_listing(), [])
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Coverage dims (issue #365): one honest Stat leg per param.
# ---------------------------------------------------------------------------

def test_p4_001_stale_anchored_fresh_stays_null():
    v, reason = dim_price_history_dom_stat(rich_listing(), MEDIANS, TODAY)
    assert v == 85  # stale (134 d, 2 cuts) + 3200 under Stat median 3400
    assert "hinnang" in reason and "EI OLE" in reason
    v, reason = dim_price_history_dom_stat(
        rich_listing(eur_m2=3500.0), MEDIANS, TODAY)
    assert v == 40 and "EI OLE" in reason  # stale but over Stat median
    v, reason = dim_price_history_dom_stat(
        rich_listing(first_seen="2026-09-01", price_cuts=0), MEDIANS, TODAY)
    assert v is None and "Värske" in reason and "EI OLE" in reason
    v, reason = dim_price_history_dom_stat(
        rich_listing(first_seen=None), MEDIANS, TODAY)
    assert v is None and "first_seen" in reason and "EI OLE" in reason
    v, reason = dim_price_history_dom_stat(
        rich_listing(first_seen="not-a-date"), MEDIANS, TODAY)
    assert v is None and "EI OLE" in reason
    v, reason = dim_price_history_dom_stat(rich_listing(area="Pirita"),
                                           MEDIANS, TODAY)
    assert v is None and "EI OLE" in reason  # stale but no Stat anchor


def test_p4_003_yield_bands_and_nulls():
    # 12*650/160000 = 4.875% -> 65.
    v, reason = dim_rent_reality_stat(rich_listing(), RENTS)
    assert v == 65 and "4.9%" in reason and "hinnang" in reason
    v, _ = dim_rent_reality_stat(rich_listing(price_eur=120000.0), RENTS)
    assert v == 80  # 6.5% -> strong
    v, _ = dim_rent_reality_stat(rich_listing(price_eur=400000.0), RENTS)
    assert v == 35  # 1.95% -> weak
    v, reason = dim_rent_reality_stat(rich_listing(price_eur=None), RENTS)
    assert v is None and "EI OLE" in reason
    v, reason = dim_rent_reality_stat(rich_listing(area="Pirita"), RENTS)
    assert v is None and "EI OLE" in reason
    assert "KV" in reason  # missing leg named, not faked
    v, scored_reason = dim_rent_reality_stat(rich_listing(), RENTS)
    assert "Airbnb" in scored_reason  # scored leg names the rest


def test_p4_019_fiscal_bands_and_nulls():
    v, reason = dim_kov_fiscal_stat(rich_listing(), KOV)
    assert v == 75 and "35%" in reason and "hinnang" in reason
    bad = [{"kov": "Tallinn", "year": 2025, "debt_burden_pct": 75.0,
            "investment_per_capita": 200.0,
            "operating_result_per_capita": -20.0}]
    v, reason = dim_kov_fiscal_stat(rich_listing(), bad)
    assert v == 35 and "miinuses" in reason
    v, reason = dim_kov_fiscal_stat(rich_listing(), [])
    assert v is None and "EI OLE" in reason and "RR300" in reason
    v, reason = dim_kov_fiscal_stat(rich_listing(kov="Tartu"), KOV)
    assert v is None and "EI OLE" in reason


def test_p4_025_migration_bands_and_nulls():
    # Lasnamäe 2025: +400/120000 = +3.3/1000 -> 60.
    v, reason = dim_micro_liquidity_stat(rich_listing(area="Lasnamäe"),
                                         MIGR)
    assert v == 60 and "hinnang" in reason
    # Kesklinn 2025: +2000/65000 = +30.8/1000 -> 75.
    v, _ = dim_micro_liquidity_stat(rich_listing(area="Kesklinn"), MIGR)
    assert v == 75
    outflow = [{"area": "Lasnamäe", "year": 2025, "in_migrants": 3000,
                "out_migrants": 7000, "population": 120000}]
    v, reason = dim_micro_liquidity_stat(rich_listing(area="Lasnamäe"),
                                         outflow)
    assert v == 30 and "väljavool" in reason
    v, reason = dim_micro_liquidity_stat(rich_listing(area="Pirita"), MIGR)
    assert v is None and "RVR02" in reason and "EI OLE" in reason
    v, scored_reason = dim_micro_liquidity_stat(
        rich_listing(area="Lasnamäe"), MIGR)
    assert "ruudustiku" in scored_reason  # scored leg names sibling grid


def test_p4_038_heat_bands_and_city_fallback():
    v, reason = dim_bargaining_margin_stat(rich_listing(), INDEX)
    assert v == 35 and "+3.0%" in reason  # Kesklinn hot
    v, reason = dim_bargaining_margin_stat(rich_listing(area="Lasnamäe"),
                                           INDEX)
    assert v == 65 and "linna-koondrida" in reason  # Tallinn fallback -1.5%
    assert "TABELI" in reason  # gap table named EI OLE
    v, reason = dim_bargaining_margin_stat(rich_listing(), [])
    assert v is None and "EI OLE" in reason


def test_p4_043_baseline_flag_and_taste_match():
    v, reason = dim_number13_baseline_stat(
        rich_listing(floor=13, eur_m2=3300.0), MEDIANS)
    assert v == 80 and "maitse-sobivus" in reason
    assert "väärtushinnang" in reason  # never a worth judgement
    v, _ = dim_number13_baseline_stat(
        rich_listing(floor=13, eur_m2=3500.0), MEDIANS)
    assert v == 45  # 13-mark but over median: no discount
    v, reason = dim_number13_baseline_stat(rich_listing(floor=4), MEDIANS)
    assert v is None and "13-märki" in reason
    v, reason = dim_number13_baseline_stat(
        rich_listing(floor=None, house_number=None), MEDIANS)
    assert v is None and "EI OLE" in reason
    v, reason = dim_number13_baseline_stat(
        rich_listing(floor=13, area="Pirita"), MEDIANS)
    assert v is None and "EI OLE" in reason


def test_p4_050_pipeline_ratio_and_nulls():
    v, reason = dim_permit_glut_stat(rich_listing(area="Lasnamäe"), PERMITS)
    assert v == 35 and "3.0" in reason  # 240/80 glut
    v, _ = dim_permit_glut_stat(rich_listing(area="Kesklinn"), PERMITS)
    assert v == 75  # 60/80 scarce
    v, reason = dim_permit_glut_stat(rich_listing(area="Pirita"), PERMITS)
    assert v is None and "EI OLE" in reason and "EH" in reason
    zero = [{"area": "Lasnamäe", "quarter": "2026-Q2", "permits": 5,
             "completions": 0}]
    v, reason = dim_permit_glut_stat(rich_listing(area="Lasnamäe"), zero)
    assert v is None and "EI OLE" in reason  # never divide by zero


def test_p4_051_area_grain_only_never_addresses():
    v, reason = dim_zero_consumption_stat(rich_listing(area="Lasnamäe"),
                                          EMPTY)
    assert v == 70 and "3.0%" in reason
    assert "mitte aadress" in reason  # privacy shape pinned
    v, _ = dim_zero_consumption_stat(rich_listing(area="Kesklinn"), EMPTY)
    assert v == 35  # 9% -> dead-stairwell risk
    v, reason = dim_zero_consumption_stat(rich_listing(area="Pirita"),
                                          EMPTY)
    assert v is None and "EI OLE" in reason
    assert "FEIGITA" in reason  # no fake precision at finer grain


def test_p4_061_spiral_check_and_nulls():
    v, reason = dim_last_shop_spiral_stat(rich_listing(settlement="Maardu"),
                                          FRINGE)
    assert v == 35 and "spiraali" in reason
    v, scored_reason = dim_last_shop_spiral_stat(
        rich_listing(settlement="Saue"), FRINGE)
    assert v == 70
    assert "kontrollnimekirja" in scored_reason  # checklist leg named
    v, reason = dim_last_shop_spiral_stat(rich_listing(settlement="Harku"),
                                          FRINGE)
    assert v is None and "EI OLE" in reason
    assert "ääreasula rida" in reason
    half = [{"settlement": "Maardu", "pop_change_pct": -1.2}]
    v, reason = dim_last_shop_spiral_stat(rich_listing(settlement="Maardu"),
                                          half)
    assert v is None and "poolik" in reason


# ---------------------------------------------------------------------------
# Honesty markers, registry, aggregator.
# ---------------------------------------------------------------------------

def test_all_reasons_carry_honesty_markers():
    scored = [
        dim_stat_micro_comp_anchor(rich_listing(), MEDIANS),
        dim_price_history_dom_stat(rich_listing(), MEDIANS, TODAY),
        dim_rent_reality_stat(rich_listing(), RENTS),
        dim_kov_fiscal_stat(rich_listing(), KOV),
        dim_micro_liquidity_stat(rich_listing(area="Lasnamäe"), MIGR),
        dim_bargaining_margin_stat(rich_listing(), INDEX),
        dim_number13_baseline_stat(rich_listing(floor=13), MEDIANS),
        dim_permit_glut_stat(rich_listing(area="Lasnamäe"), PERMITS),
        dim_zero_consumption_stat(rich_listing(area="Lasnamäe"), EMPTY),
        dim_last_shop_spiral_stat(rich_listing(), FRINGE),
    ]
    assert len(scored) == 10
    for (v, reason), (key, _, _) in zip(scored, P4_STAT_DIMS):
        assert v is not None, key
        assert "hinnang" in reason, key
        assert "EI OLE" in reason, key
        assert "garanteeritud" not in reason and "mõõdetud" not in reason


def test_thin_inputs_all_null_without_numbers():
    listing = {"area": "Nowhere", "kov": "Nowhere", "settlement": "Nowhere"}
    for (v, _reason), (key, _, _) in zip(
            [dim_stat_micro_comp_anchor(listing, []),
             dim_price_history_dom_stat(
                 {"first_seen": "2026-01-01", "price_cuts": 3,
                  "eur_m2": 3000.0, "area": "Nowhere"}, [], TODAY),
             dim_rent_reality_stat({"price_eur": 1.0, "area": "Nowhere"},
                                   []),
             dim_kov_fiscal_stat(listing, []),
             dim_micro_liquidity_stat(listing, []),
             dim_bargaining_margin_stat(listing, []),
             dim_number13_baseline_stat(
                 {"floor": 13, "eur_m2": 1.0, "area": "Nowhere"}, []),
             dim_permit_glut_stat(listing, []),
             dim_zero_consumption_stat(listing, []),
             dim_last_shop_spiral_stat(listing, [])],
            P4_STAT_DIMS):
        assert v is None, key


def test_registry_and_aggregator_cover_all_ten():
    assert [k for k, _, _ in P4_STAT_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_STAT_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_STAT_DIMS}) == 10
    out = score_p4_stat(rich_listing(), tables(), TODAY)
    assert out == {"micro_comp_anchor": 100,
                   "price_history_dom_stat": 85,
                   "rent_reality_stat": 65,
                   "kov_fiscal_stat": 75,
                   "micro_liquidity_stat": 75,
                   "bargaining_margin_stat": 35,
                   "number13_baseline_stat": None,
                   "permit_glut_stat": 75,
                   "zero_consumption_stat": 35,
                   "last_shop_spiral_stat": 70}
    thin = score_p4_stat({"area": None}, {}, TODAY)
    assert thin == {k: None for k in EXPECTED_KEYS}
    assert set(out) == set(EXPECTED_KEYS)
