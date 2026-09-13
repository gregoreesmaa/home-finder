"""P4 REL2021 grid dims (issues #274 demo + #348 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory grid cell (plain dicts —
no scraped data, no real census microdata). fetch_cached is covered only on
its cache-hit path (a file:// URL that would fail if fetched); freshness /
expiry uses tmp_path. The live probes are manual DoD evidence (pasted in the
PR + docs/p4_rel2021.md), not unit runs.
"""

import os
import time

import dims_p4_rel2021 as rel
from dims_p4_rel2021 import (
    CHURN_WAVE_PER_1000,
    MIN_CELL_POP,
    P4_REL2021_DIMS,
    TTL_DAYS,
    cache_path,
    dim_herd_occupation_rel,
    dim_kindergarten_pressure_rel,
    dim_micro_liquidity_rel,
    dim_number13_prestige_rel,
    dim_rent_reality_rel,
    dim_third_place_demand_rel,
    dim_turnover_migration_rel,
    dim_zero_consumption_vacancy_rel,
    fetch_cached,
    get_cell,
    is_fresh,
    score_p4_rel2021,
)

# -- Synthetic Tallinn fixtures (NOT real census data) -----------------------

CELL_GOOD = {
    "cell_id": "TLL-1km-0042",  # Kalamaja-like settled cell
    "population": 3200,
    "age_0_6": 210, "age_7_17": 340, "age_65_plus": 540,
    "in_migrants_12mo": 180, "out_migrants_12mo": 150,
    "vacant_dwellings": 90, "dwellings": 1500,
    "rental_share": 0.32,
    "creative_occupations": 140, "employed": 1500,
    "higher_education_share": 0.41,
    "evening_population": 2900,
}

CELL_RISK = {
    "cell_id": "TLL-1km-0107",  # high-rent + high-vacancy cell
    "population": 4100,
    "age_0_6": 320, "age_7_17": 410, "age_65_plus": 700,
    "in_migrants_12mo": 400, "out_migrants_12mo": 380,
    "vacant_dwellings": 380, "dwellings": 1800,
    "rental_share": 0.45,
    "creative_occupations": 120, "employed": 1900,
    "higher_education_share": 0.28,
    "evening_population": 3000,
}

CELL_CALM = {
    "cell_id": "TLL-1km-0203",  # quiet owner-majority cell
    "population": 1500,
    "age_0_6": 90, "age_7_17": 150, "age_65_plus": 300,
    "in_migrants_12mo": 60, "out_migrants_12mo": 55,
    "vacant_dwellings": 60, "dwellings": 1200,
    "rental_share": 0.18,
    "creative_occupations": 200, "employed": 900,
    "higher_education_share": 0.52,
    "evening_population": 1450,
}

CELL_SUPPRESSED = dict(CELL_GOOD, cell_id="TLL-1km-0991", suppressed=True)
CELL_THIN = dict(CELL_GOOD, cell_id="TLL-1km-0992", population=45)
CELLS = [CELL_GOOD, CELL_RISK, CELL_CALM]

ASULA_ROWS = [
    {"asum": "Kalamaja", "age_group": "0-6", "value": 800},
    {"asum": "Kalamaja", "age_group": "7-17", "value": 900},
    {"asum": "Kalamaja", "age_group": "18-64", "value": 5200},
    {"asum": "Kalamaja", "age_group": "65+", "value": 1100},
]

ALL_FNS = [
    dim_micro_liquidity_rel,
    dim_rent_reality_rel,
    dim_kindergarten_pressure_rel,
    dim_number13_prestige_rel,
    dim_herd_occupation_rel,
    dim_third_place_demand_rel,
    dim_zero_consumption_vacancy_rel,
    dim_turnover_migration_rel,
]


def test_production_shape_all_null_without_grid():
    """Grid bulk missing (dated negative) -> every dim NULL, honest reason."""
    listing = {"cell_id": "TLL-1km-0000", "asum": "Kalamaja",
               "floor": 13, "street_residual_vs_median": -0.08}
    for fn in ALL_FNS:
        v, reason = fn(listing, [])
        assert v is None, fn.__name__
        assert "hinnang" in reason and "EI OLE" in reason, fn.__name__


def test_demo_p4_025_cell_scores_components():
    # vac 6% (+10), net +9.4/1000 (+0), young 17.2% (+10), senior ok -> 80.
    v, reason = dim_micro_liquidity_rel({"cell_id": "TLL-1km-0042"},
                                        CELLS)
    assert v == 80
    assert "vakants 6%" in reason and "rändesaldo +9/1000" in reason
    assert "kooli avamis/sulgemisplaanide jalga EI OLE" in reason


def test_demo_p4_025_asula_fallback_is_labelled():
    # No cell, but open-table asula rows: young 21.25% -> capped 60.
    v, reason = dim_micro_liquidity_rel({"asum": "Kalamaja"}, [], ASULA_ROWS)
    assert v == 60
    assert "AINULT asula-jalg" in reason
    assert "1 km ruudustiku-jalga" in reason and "EI OLE" in reason


def test_demo_p4_025_partial_cell_stays_null():
    thin = dict(CELL_GOOD, cell_id="TLL-1km-0500")
    del thin["vacant_dwellings"]
    v, reason = dim_micro_liquidity_rel({"cell_id": "TLL-1km-0500"}, [thin])
    assert v is None
    assert "puudulikud" in reason and "EI OLE" in reason


def test_privacy_floor_suppressed_and_thin_cells():
    for bad in (CELL_SUPPRESSED, CELL_THIN):
        listing = {"cell_id": bad["cell_id"], "asum": "Kalamaja",
                   "floor": 13, "street_residual_vs_median": -0.08}
        for fn in ALL_FNS:
            if fn is dim_micro_liquidity_rel:
                v, reason = fn(listing, [bad])  # no asula rows here
            else:
                v, reason = fn(listing, [bad])
            assert v is None, (fn.__name__, bad["cell_id"])
            assert "EI OLE" in reason, fn.__name__
    assert MIN_CELL_POP == 100


def test_no_gradient_leak_from_neighbour_cells():
    """An extreme neighbour cell must not leak into a missing-cell listing."""
    extreme = dict(CELL_RISK, cell_id="TLL-1km-9999", rental_share=0.95,
                   vacant_dwellings=1799)
    listing = {"cell_id": "TLL-1km-0043", "asum": "Nowhere"}
    for fn in ALL_FNS:
        if fn is dim_micro_liquidity_rel:
            v, _ = fn(listing, [extreme])
        elif fn is dim_number13_prestige_rel:
            v, _ = fn(dict(listing, floor=13,
                            street_residual_vs_median=-0.1), [extreme])
        else:
            v, _ = fn(listing, [extreme])
        assert v is None, fn.__name__
    assert get_cell([extreme], "TLL-1km-0043") is None


def test_cell_join_is_exact_but_case_and_space_tolerant():
    v, _ = dim_rent_reality_rel({"cell_id": "  tll-1KM-0042 "}, CELLS)
    assert v == 55  # same as the canonical id below
    v2, _ = dim_rent_reality_rel({"cell_id": "TLL-1km-0042"}, CELLS)
    assert v == v2
    v3, reason = dim_rent_reality_rel({"cell_id": "TLL-1km-004"}, CELLS)
    assert v3 is None and "EI OLE" in reason  # prefix is NOT a match


def test_p4_003_rent_bands():
    assert dim_rent_reality_rel({"cell_id": "TLL-1km-0107"},
                                CELLS)[0] == 35
    assert dim_rent_reality_rel({"cell_id": "TLL-1km-0042"},
                                CELLS)[0] == 55
    assert dim_rent_reality_rel({"cell_id": "TLL-1km-0203"},
                                CELLS)[0] == 75
    _, reason = dim_rent_reality_rel({"cell_id": "TLL-1km-0203"}, CELLS)
    assert "Airbnb-tiheduse" in reason and "EI OLE" in reason


def test_p4_011_kindergarten_bands():
    assert dim_kindergarten_pressure_rel({"cell_id": "TLL-1km-0107"},
                                         CELLS)[0] == 35
    assert dim_kindergarten_pressure_rel({"cell_id": "TLL-1km-0042"},
                                         CELLS)[0] == 55
    assert dim_kindergarten_pressure_rel({"cell_id": "TLL-1km-0203"},
                                         CELLS)[0] == 70
    _, reason = dim_kindergarten_pressure_rel({"cell_id": "TLL-1km-0203"},
                                              CELLS)
    assert "perearsti" in reason and "EI OLE" in reason


def test_p4_043_needs_mark_residual_and_cell():
    base = {"cell_id": "TLL-1km-0042", "floor": 13,
            "street_residual_vs_median": -0.08}
    v, reason = dim_number13_prestige_rel(base, CELLS)
    assert v == 80
    assert "prestiiži-kontroll" in reason and "EI OLE" in reason
    assert "mitte väärtushinnang" in reason
    v, _ = dim_number13_prestige_rel(
        dict(base, street_residual_vs_median=0.02), CELLS)
    assert v == 45
    v, reason = dim_number13_prestige_rel(
        {"cell_id": "TLL-1km-0042", "floor": 4,
         "street_residual_vs_median": -0.08}, CELLS)
    assert v is None and "13-märki" in reason and "EI OLE" in reason
    v, reason = dim_number13_prestige_rel({"cell_id": "TLL-1km-0042",
                                           "floor": 13}, CELLS)
    assert v is None and "hinna-jääki" in reason
    v, reason = dim_number13_prestige_rel({"cell_id": "TLL-1km-0042"}, CELLS)
    assert v is None and "numbrit" in reason
    v, reason = dim_number13_prestige_rel(
        dict(base, house_number="13", floor=None), CELLS)
    assert v == 80  # house-13 marks too


def test_p4_044_taste_match_only_never_worth_judgement():
    assert dim_herd_occupation_rel({"cell_id": "TLL-1km-0203"},
                                   CELLS)[0] == 70  # 22.2% creative
    assert dim_herd_occupation_rel({"cell_id": "TLL-1km-0042"},
                                   CELLS)[0] == 60  # 9.3% creative
    assert dim_herd_occupation_rel({"cell_id": "TLL-1km-0107"},
                                   CELLS)[0] == 60  # 6.3% creative
    for cell_id in ("TLL-1km-0042", "TLL-1km-0107", "TLL-1km-0203"):
        _, reason = dim_herd_occupation_rel({"cell_id": cell_id}, CELLS)
        assert "mitte vaartushinnang" in reason, cell_id
        assert "hinnang" in reason and "EI OLE" in reason, cell_id


def test_p4_045_evening_bands():
    assert dim_third_place_demand_rel({"cell_id": "TLL-1km-0203"},
                                      CELLS)[0] == 70  # 96.7%
    assert dim_third_place_demand_rel({"cell_id": "TLL-1km-0042"},
                                      CELLS)[0] == 60  # 90.6%
    assert dim_third_place_demand_rel({"cell_id": "TLL-1km-0107"},
                                      CELLS)[0] == 45  # 73.2%
    _, reason = dim_third_place_demand_rel({"cell_id": "TLL-1km-0042"},
                                           CELLS)
    assert "keeper" in reason and "EI OLE" in reason


def test_p4_051_vacancy_flag_is_cell_level_only():
    assert dim_zero_consumption_vacancy_rel({"cell_id": "TLL-1km-0107"},
                                            CELLS)[0] == 30  # 16.7%
    assert dim_zero_consumption_vacancy_rel({"cell_id": "TLL-1km-0042"},
                                            CELLS)[0] == 70  # 6.0%
    _, reason = dim_zero_consumption_vacancy_rel({"cell_id": "TLL-1km-0107"},
                                                 CELLS)
    assert "mitte aadressil" in reason  # privacy-safe by construction
    assert "Elektrilevi" in reason and "EI OLE" in reason


def test_p4_052_wave_neutral_with_both_readings():
    # churn 780/4100*1000 = 190.2 >= 150 -> wave, neutral 50.
    v, reason = dim_turnover_migration_rel({"cell_id": "TLL-1km-0107"},
                                           CELLS)
    assert v == 50
    assert "lugemine A" in reason and "lugemine B" in reason
    assert "EI OLE" in reason
    # normal churn 115/1500*1000 = 76.7 -> NULL, must not push the sort.
    v, reason = dim_turnover_migration_rel({"cell_id": "TLL-1km-0203"},
                                           CELLS)
    assert v is None and "tavaline käive" in reason
    assert CHURN_WAVE_PER_1000 == 150.0


def test_every_reason_carries_honesty_markers():
    """hinnang + EI OLE in EVERY reason (scored and NULL paths)."""
    scored = [
        (dim_micro_liquidity_rel, {"cell_id": "TLL-1km-0042"}, CELLS),
        (dim_rent_reality_rel, {"cell_id": "TLL-1km-0042"}, CELLS),
        (dim_kindergarten_pressure_rel, {"cell_id": "TLL-1km-0042"}, CELLS),
        (dim_number13_prestige_rel,
         {"cell_id": "TLL-1km-0042", "floor": 13,
          "street_residual_vs_median": -0.08}, CELLS),
        (dim_herd_occupation_rel, {"cell_id": "TLL-1km-0042"}, CELLS),
        (dim_third_place_demand_rel, {"cell_id": "TLL-1km-0042"}, CELLS),
        (dim_zero_consumption_vacancy_rel, {"cell_id": "TLL-1km-0042"},
         CELLS),
        (dim_turnover_migration_rel, {"cell_id": "TLL-1km-0107"}, CELLS),
    ]
    for fn, listing, cells in scored:
        _, reason = fn(listing, cells)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_registry_and_aggregator_cover_all_eight():
    assert [k for k, _, _ in P4_REL2021_DIMS] == [
        "micro_liquidity_rel", "rent_reality_rel", "kindergarten_pressure_rel",
        "number13_prestige_rel", "herd_occupation_rel",
        "third_place_demand_rel", "zero_consumption_vacancy_rel",
        "turnover_migration_rel",
    ]
    assert [p for _, p, _ in P4_REL2021_DIMS] == [
        "P4-025", "P4-003", "P4-011", "P4-043", "P4-044", "P4-045",
        "P4-051", "P4-052",
    ]
    assert len({fn for _, _, fn in P4_REL2021_DIMS}) == 8
    assert rel.P4_REL2021_DIMS is P4_REL2021_DIMS
    listing = {"cell_id": "TLL-1km-0042", "asum": "Kalamaja", "floor": 13,
               "street_residual_vs_median": -0.08}
    out = score_p4_rel2021(listing, CELLS)
    assert out == {
        "micro_liquidity_rel": 80,
        "rent_reality_rel": 55,
        "kindergarten_pressure_rel": 55,
        "number13_prestige_rel": 80,
        "herd_occupation_rel": 60,
        "third_place_demand_rel": 60,
        "zero_consumption_vacancy_rel": 70,
        "turnover_migration_rel": None,  # churn 103/1000 < wave
    }
    empty = score_p4_rel2021({"cell_id": "TLL-1km-0000"}, [])
    assert empty == {k: None for k, _, _ in P4_REL2021_DIMS}
    fallback = score_p4_rel2021({"asum": "Kalamaja"}, [], ASULA_ROWS)
    assert fallback["micro_liquidity_rel"] == 60
    assert all(v is None for k, v in fallback.items()
               if k != "micro_liquidity_rel")


def test_cache_path_and_freshness_hermetic(tmp_path):
    p = cache_path(str(tmp_path), "RL21003.json")
    assert p == os.path.join(str(tmp_path), rel.CACHE_SUBDIR, "RL21003.json")
    assert is_fresh(p, 365) is False  # missing file is never fresh
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{}")
    assert is_fresh(p, 365) is True
    old = time.time() - 400 * 86400
    os.utime(p, (old, old))
    assert is_fresh(p, 365) is False


def test_fetch_cached_cache_hit_never_touches_network(tmp_path):
    p = cache_path(str(tmp_path), "px_rel2021.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"cached")
    # Unreachable URL + fresh cache: must return without raising.
    assert rel.fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                            "px_rel2021.json", 365) == p


def test_fetch_cached_failure_raises_and_caches_nothing(tmp_path):
    try:
        fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                     "missing.json", 365, timeout_s=5)
    except Exception:
        pass
    else:
        raise AssertionError("transport error must raise, not return")
    # Transport errors are NEVER cached as data (AGENTS.md section 7.2).
    assert not os.path.exists(cache_path(str(tmp_path), "missing.json"))
    assert not os.path.exists(cache_path(str(tmp_path), "missing.json.part"))


def test_source_urls_contain_no_unverified_grid_bulk():
    """Dated negative is structural: no grid-bulk URL exists to fetch."""
    assert set(rel.SOURCE_URLS) == {"px_root", "px_rel2021", "px_RL21003"}
    assert all(u.startswith("https://andmed.stat.ee/api/v1/et")
               for u in rel.SOURCE_URLS.values())
    assert TTL_DAYS == {"rel_tables": 365, "grid_bulk": 91}
    assert rel.TTL_DAYS is TTL_DAYS
