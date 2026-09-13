"""P4 Maa-tehingud dims (issues #244 demo + #328 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory deal row (plain dicts —
no scraped data). fetch_cached is covered only on its cache-hit path;
freshness/expiry uses tmp_path. The live probes are manual DoD evidence
(pasted in the PR + docs/p4_maa_tehingud.md), not unit runs.
"""

import os
import time

import dims_p4_maa_tehingud as p4
from dims_p4_maa_tehingud import (
    P4_MAA_TEHINGUD_DIMS,
    WAVE_DEALS_12MO,
    MIN_COMPS,
    cache_path,
    dim_bargaining_margin,
    dim_closed_deal_micro_comp,
    dim_developer_broker_track,
    dim_herd_gentrification_front,
    dim_last_shop_tracker,
    dim_listing_demand_exhaust,
    dim_micro_liquidity,
    dim_number13_arbitrage,
    dim_permit_glut_price_leg,
    dim_price_history_dom,
    dim_turnover_wave,
    is_fresh,
    median_eur_m2,
    micro_comp,
    normalise_address,
    score_p4_maa_tehingud,
)

TODAY = "2026-09-13"

# Synthetic Tallinn fixtures (invented numbers, never scraped data).
BUILDING = "Tartu mnt 25-12, Tallinn"
STREET = "Tartu mnt"


def deal(address=BUILDING, street=STREET, eur_m2=3200.0, quarter="2026-Q1",
         asum="Veerenni", developer="YIT", months_ago=2):
    return {"address": address, "street": street, "eur_m2": eur_m2,
            "quarter": quarter, "asum": asum, "developer": developer,
            "months_ago": months_ago}


BUILDING_DEALS = [deal(eur_m2=v) for v in (3100.0, 3200.0, 3300.0, 3400.0)]
# building median = (3200+3300)/2 = 3250.
STREET_DEALS = [deal(address="Tartu mnt 99-%d, Tallinn" % i, eur_m2=v)
                for i, v in enumerate((3000.0, 3100.0, 3200.0))]
THIN_DEALS = [deal(eur_m2=3200.0), deal(eur_m2=3300.0)]

ALL_FNS = [fn for _, _, fn in P4_MAA_TEHINGUD_DIMS]
EXPECTED_KEYS = ["micro_comp", "price_history_dom", "developer_track",
                 "micro_liquidity", "demand_exhaust", "bargaining_margin",
                 "number13_arbitrage", "herd_front", "permit_glut_price",
                 "turnover_wave", "last_shop"]
EXPECTED_PNUMS = ["P4-002", "P4-001", "P4-021", "P4-025", "P4-028", "P4-038",
                  "P4-043", "P4-044", "P4-050", "P4-052", "P4-061"]


def rich_listing(**kw):
    base = {"eur_m2": 3200.0, "address": BUILDING, "street": STREET,
            "asum": "Veerenni", "area_type": "kesklinn",
            "floor": 4, "house_number": "25",
            "first_seen": "2026-05-01", "price_cuts": 2,
            "views_per_day": 0.4, "dom_days": 120, "updates_30d": 1,
            "developer": "YIT",
            "settlement_checklist": {"shop": True, "pharmacy": True,
                                     "atm": True, "bus_cuts_12mo": 0}}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Helpers: median, normalisation, freshness, micro-comp join.
# ---------------------------------------------------------------------------

def test_median_odd_even_empty_and_filters_junk():
    assert median_eur_m2([3000.0, 1000.0, 2000.0]) == 2000.0
    assert median_eur_m2([3100.0, 3200.0, 3300.0, 3400.0]) == 3250.0
    assert median_eur_m2([]) is None
    assert median_eur_m2([0, -5, None, "x"]) is None
    assert median_eur_m2([0, 3000.0]) == 3000.0


def test_normalise_exact_match_only():
    assert normalise_address("  Tartu MNT  25-12 ") == "tartu mnt 25-12"
    assert normalise_address(None) is None
    assert normalise_address("   ") is None


def test_cache_path_and_freshness_hermetic(tmp_path):
    p = cache_path(str(tmp_path), "x.json")
    assert p == os.path.join(str(tmp_path), p4.CACHE_SUBDIR, "x.json")
    assert is_fresh(p, 91) is False  # missing file is never fresh
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("{}")
    assert is_fresh(p, 91) is True
    old = time.time() - 100 * 86400
    os.utime(p, (old, old))
    assert is_fresh(p, 91) is False


def test_fetch_cached_cache_hit_never_touches_network(tmp_path):
    p = cache_path(str(tmp_path), "pub.pdf")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"cached")
    # Unreachable URL + fresh cache: must return without raising.
    assert p4.fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                           "pub.pdf", 91) == p


def test_micro_comp_building_then_street_then_none():
    med, n, level = micro_comp(BUILDING, STREET, BUILDING_DEALS)
    assert (med, n, level) == (3250.0, 4, "building")
    med, n, level = micro_comp("Tartu mnt 25-14, Tallinn", STREET,
                               BUILDING_DEALS + STREET_DEALS)
    # street level aggregates the whole street (incl. the other building):
    # sorted [3000,3100,3100,3200,3200,3300,3400] -> median 3200, n 7.
    assert (med, n, level) == (3200.0, 7, "street")
    med, n, level = micro_comp(BUILDING, STREET, THIN_DEALS)
    assert med is None and level is None and n == 4  # 2 building + 2 street
    med, n, level = micro_comp(None, None, BUILDING_DEALS)
    assert (med, n, level) == (None, 0, None)


def test_micro_comp_exact_address_never_leaks_across_buildings():
    # Same street, different house: building level must NOT match.
    med, n, level = micro_comp("Tartu mnt 25-14, Tallinn", None,
                               BUILDING_DEALS)
    assert (med, level) == (None, None)


def test_min_comps_gate_single_deal_never_sets_median():
    med, n, level = micro_comp(BUILDING, STREET, [deal(eur_m2=9999.0)])
    assert med is None and level is None


# ---------------------------------------------------------------------------
# P4-002 demo dim.
# ---------------------------------------------------------------------------

def test_p4_002_at_and_below_median_scores_100():
    v, reason = dim_closed_deal_micro_comp(rich_listing(eur_m2=3250.0),
                                           BUILDING_DEALS)
    assert v == 100 and "hinnang" in reason
    v, _ = dim_closed_deal_micro_comp(rich_listing(eur_m2=3000.0),
                                      BUILDING_DEALS)
    assert v == 100


def test_p4_002_overpay_scales_down():
    v, reason = dim_closed_deal_micro_comp(rich_listing(eur_m2=4062.5),
                                           BUILDING_DEALS)
    assert v == 80  # 100 * 3250/4062.5
    assert "hoone mediaan 3250" in reason


def test_p4_002_null_paths_carry_markers():
    v, r = dim_closed_deal_micro_comp(rich_listing(eur_m2=None),
                                      BUILDING_DEALS)
    assert v is None and "EI OLE" in r
    v, r = dim_closed_deal_micro_comp(rich_listing(), THIN_DEALS)
    assert v is None and "EI OLE" in r and "hindaja" in r
    v, r = dim_closed_deal_micro_comp(rich_listing(address=None, street=None),
                                      BUILDING_DEALS)
    assert v is None and "EI OLE" in r


# ---------------------------------------------------------------------------
# Coverage dims (#328).
# ---------------------------------------------------------------------------

def test_p4_001_stale_bands_and_nulls():
    v, _ = dim_price_history_dom(rich_listing(), BUILDING_DEALS, TODAY)
    assert v == 85  # stale (DOM 135 d, 2 cuts) + asking under median
    v, r = dim_price_history_dom(rich_listing(eur_m2=4000.0), BUILDING_DEALS,
                                 TODAY)
    assert v == 40 and "üle sulgunud mediaani" in r
    v, r = dim_price_history_dom(rich_listing(first_seen="2026-09-01",
                                              price_cuts=0),
                                 BUILDING_DEALS, TODAY)
    assert v is None and "EI OLE" in r  # fresh ad
    v, r = dim_price_history_dom(rich_listing(first_seen=None),
                                 BUILDING_DEALS, TODAY)
    assert v is None and "EI OLE" in r
    v, r = dim_price_history_dom(rich_listing(first_seen="not-a-date"),
                                 BUILDING_DEALS, TODAY)
    assert v is None and "EI OLE" in r
    v, r = dim_price_history_dom(rich_listing(first_seen="2026-10-01"),
                                 BUILDING_DEALS, TODAY)
    assert v is None and "EI OLE" in r  # future first_seen
    v, r = dim_price_history_dom(rich_listing(), THIN_DEALS, TODAY)
    assert v is None and "EI OLE" in r  # stale but no anchor


def test_p4_021_developer_bands_and_nulls():
    dev_deals = ([deal(developer="YIT", eur_m2=v)
                  for v in (3300.0, 3400.0, 3500.0)]
                 + [deal(developer="Muu", eur_m2=v)
                    for v in (2000.0, 2100.0, 2200.0)])
    v, r = dim_developer_broker_track(rich_listing(), dev_deals)
    assert v == 70 and "hoiab turgu" in r
    mid = ([deal(developer="YIT", eur_m2=v) for v in (2600.0, 2650.0, 2700.0)]
           + [deal(developer="Muu", eur_m2=v)
              for v in (2600.0, 2700.0, 2800.0)])
    v, _ = dim_developer_broker_track(rich_listing(), mid)
    assert v == 55
    low = ([deal(developer="YIT", eur_m2=v) for v in (2000.0, 2100.0, 2200.0)]
           + [deal(developer="Muu", eur_m2=v)
              for v in (3000.0, 3100.0, 3200.0)])
    v, _ = dim_developer_broker_track(rich_listing(), low)
    assert v == 40
    v, r = dim_developer_broker_track(rich_listing(developer=None), dev_deals)
    assert v is None and "EI OLE" in r
    v, r = dim_developer_broker_track(rich_listing(), THIN_DEALS)
    assert v is None and "EI OLE" in r


def test_p4_025_liquidity_bands_and_nulls():
    many = [deal(asum="Veerenni", quarter=q)
            for q in ("2026-Q1", "2026-Q2") for _ in range(11)]
    v, r = dim_micro_liquidity(rich_listing(), many)
    assert v == 80 and "EI OLE" in r  # REL2021/school legs named missing
    mid = [deal(asum="Veerenni", quarter=q)
           for q in ("2026-Q1", "2026-Q2") for _ in range(5)]
    v, _ = dim_micro_liquidity(rich_listing(), mid)
    assert v == 60
    thin = [deal(asum="Veerenni", quarter="2026-Q2") for _ in range(4)]
    v, _ = dim_micro_liquidity(rich_listing(), thin)
    assert v == 45
    v, r = dim_micro_liquidity(rich_listing(), [deal(asum="Veerenni")])
    assert v is None and "EI OLE" in r
    v, r = dim_micro_liquidity(rich_listing(asum="Kalamaja"), many)
    assert v is None and "EI OLE" in r


def test_p4_028_demand_exhaust_bands_and_nulls():
    v, _ = dim_listing_demand_exhaust(rich_listing(), [])
    assert v == 80  # exhausted: 0.4 views/day, DOM 120
    v, r = dim_listing_demand_exhaust(rich_listing(views_per_day=8.0,
                                                   dom_days=10), [])
    assert v == 30 and "Kuum" in r
    v, _ = dim_listing_demand_exhaust(rich_listing(views_per_day=2.0,
                                                   dom_days=20), [])
    assert v == 55
    v, r = dim_listing_demand_exhaust(rich_listing(views_per_day=None,
                                                   dom_days=None), [])
    assert v is None and "EI OLE" in r


def test_p4_038_gap_bands_and_nulls():
    gaps = {"kesklinn": 0.04, "magala": 0.06, "aedlinn": 0.005}
    v, r = dim_bargaining_margin(rich_listing(), [], gaps)
    assert v == 65 and "4.0%" in r
    v, _ = dim_bargaining_margin(rich_listing(area_type="magala"), [], gaps)
    assert v == 80
    v, _ = dim_bargaining_margin(rich_listing(area_type="aedlinn"), [], gaps)
    assert v == 35
    v, r = dim_bargaining_margin(rich_listing(), [], None)
    assert v is None and "EI OLE" in r
    v, r = dim_bargaining_margin(rich_listing(area_type="tundmatu"), [],
                                 gaps)
    assert v is None and "EI OLE" in r
    v, r = dim_bargaining_margin(rich_listing(), [], {"kesklinn": -1})
    assert v is None and "EI OLE" in r


def test_p4_043_number13_flag_and_nulls():
    marked = rich_listing(floor=13, eur_m2=3000.0)
    v, r = dim_number13_arbitrage(marked, STREET_DEALS)
    assert v == 80 and "maitse-sobivus" in r
    v, r = dim_number13_arbitrage(rich_listing(floor=13, eur_m2=3300.0),
                                  STREET_DEALS)
    assert v == 50
    v, r = dim_number13_arbitrage(rich_listing(floor=4), STREET_DEALS)
    assert v is None and "EI OLE" in r
    v, r = dim_number13_arbitrage(rich_listing(floor=None, house_number=None),
                                  STREET_DEALS)
    assert v is None and "EI OLE" in r
    v, r = dim_number13_arbitrage(marked, THIN_DEALS)
    assert v is None and "EI OLE" in r


def _window_deals(windows):
    out = []
    for q, vals in windows:
        out.extend(deal(asum="Veerenni", quarter=q, eur_m2=v) for v in vals)
    return out


def test_p4_044_front_drift_and_nulls():
    rising = _window_deals([("2025-Q3", (2900.0, 3000.0, 3100.0)),
                            ("2025-Q4", (2950.0, 3050.0, 3100.0)),
                            ("2026-Q1", (3250.0, 3350.0, 3400.0)),
                            ("2026-Q2", (3300.0, 3400.0, 3450.0))])
    v, r = dim_herd_gentrification_front(rich_listing(), rising)
    assert v == 70 and "EI OLE" in r  # REL2021 grid named missing
    falling = _window_deals([("2025-Q3", (3300.0, 3400.0, 3450.0)),
                             ("2025-Q4", (3250.0, 3350.0, 3400.0)),
                             ("2026-Q1", (2950.0, 3050.0, 3100.0)),
                             ("2026-Q2", (2900.0, 3000.0, 3100.0))])
    v, _ = dim_herd_gentrification_front(rich_listing(), falling)
    assert v == 40
    v, r = dim_herd_gentrification_front(rich_listing(), BUILDING_DEALS)
    assert v is None and "EI OLE" in r  # single window only


def test_p4_050_falling_price_leg_and_nulls():
    down = _window_deals([("2025-Q2", (3350.0, 3400.0, 3450.0)),
                          ("2026-Q2", (3150.0, 3200.0, 3250.0))])
    v, r = dim_permit_glut_price_leg(rich_listing(), down)
    assert v == 30 and "EI OLE" in r  # EHR counts named missing
    up = _window_deals([("2025-Q2", (2950.0, 3000.0, 3050.0)),
                        ("2026-Q2", (3250.0, 3300.0, 3350.0))])
    v, _ = dim_permit_glut_price_leg(rich_listing(), up)
    assert v == 70
    v, _ = dim_permit_glut_price_leg(
        rich_listing(),
        _window_deals([("2025-Q2", (3000.0, 3050.0, 3100.0)),
                       ("2026-Q2", (3000.0, 3050.0, 3100.0))]))
    assert v == 55
    v, r = dim_permit_glut_price_leg(rich_listing(), BUILDING_DEALS)
    assert v is None and "EI OLE" in r


def test_p4_052_wave_neutral_with_both_readings():
    wave = [deal(months_ago=m) for m in (0, 1, 2, 4, 7, 11)]
    v, r = dim_turnover_wave(rich_listing(), wave)
    assert v == 50
    assert "lugemine A" in r and "lugemine B" in r
    v, r = dim_turnover_wave(rich_listing(), [deal(), deal()])
    assert v is None and "EI OLE" in r
    v, r = dim_turnover_wave(rich_listing(address=None), wave)
    assert v is None and "EI OLE" in r


def test_p4_061_checklist_maths_and_nulls():
    v, r = dim_last_shop_tracker(rich_listing(), [])
    assert v == 80 and "hinnang" in r
    v, _ = dim_last_shop_tracker(rich_listing(
        settlement_checklist={"shop": False, "pharmacy": True, "atm": True,
                              "bus_cuts_12mo": 1}), [])
    assert v == 55  # 80 - 15 - 10
    v, r = dim_last_shop_tracker(rich_listing(settlement_checklist=None), [])
    assert v is None and "EI OLE" in r


# ---------------------------------------------------------------------------
# Cross-cutting contracts.
# ---------------------------------------------------------------------------

def test_all_null_reasons_carry_honesty_markers():
    thin_listing = rich_listing(eur_m2=None, address=None, street=None,
                                asum="Tühi", floor=None, house_number=None,
                                first_seen=None, views_per_day=None,
                                dom_days=None, developer=None,
                                area_type="tundmatu", settlement_checklist=None)
    for key, pnum, fn in P4_MAA_TEHINGUD_DIMS:
        if fn is dim_bargaining_margin:
            v, reason = fn(thin_listing, [], None)
        elif fn is dim_price_history_dom:
            v, reason = fn(thin_listing, [], TODAY)
        else:
            v, reason = fn(thin_listing, [], TODAY) \
                if fn is dim_price_history_dom else fn(thin_listing, [])
        assert v is None, key
        assert "hinnang" in reason, key
        assert "EI OLE" in reason, key
        assert "mõõdetud" not in reason and "garanteeritud" not in reason, key


def test_all_scored_reasons_say_hinnang_never_measured():
    listing = rich_listing()
    gap_deals = BUILDING_DEALS + STREET_DEALS
    wave = [deal(months_ago=m) for m in (0, 1, 2, 4, 7, 11)]
    trend = _window_deals([("2025-Q2", (2900.0, 3000.0, 3100.0)),
                           ("2025-Q3", (2950.0, 3050.0, 3100.0)),
                           ("2026-Q1", (3250.0, 3350.0, 3400.0)),
                           ("2026-Q2", (3300.0, 3400.0, 3450.0))])
    many = [deal(asum="Veerenni", quarter=q)
            for q in ("2026-Q1", "2026-Q2") for _ in range(11)]
    scored = [
        dim_closed_deal_micro_comp(listing, BUILDING_DEALS),
        dim_price_history_dom(listing, BUILDING_DEALS, TODAY),
        dim_developer_broker_track(
            listing, [deal(developer="YIT", eur_m2=v)
                      for v in (3300.0, 3400.0, 3500.0)]),
        dim_micro_liquidity(listing, many),
        dim_listing_demand_exhaust(listing, []),
        dim_bargaining_margin(listing, [], {"kesklinn": 0.04}),
        dim_number13_arbitrage(rich_listing(floor=13, eur_m2=3000.0),
                               STREET_DEALS),
        dim_herd_gentrification_front(listing, trend),
        dim_permit_glut_price_leg(listing, trend),
        dim_turnover_wave(listing, wave),
        dim_last_shop_tracker(listing, []),
    ]
    assert len(scored) == 11
    for (v, reason), (key, _, _) in zip(scored, P4_MAA_TEHINGUD_DIMS):
        assert v is not None, key
        assert 0 <= v <= 100, key
        assert "hinnang" in reason, key
        assert "mõõdetud" not in reason and "garanteeritud" not in reason, key


def test_registry_and_aggregator_cover_all_eleven():
    assert [k for k, _, _ in P4_MAA_TEHINGUD_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_MAA_TEHINGUD_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_MAA_TEHINGUD_DIMS}) == 11
    assert MIN_COMPS == 3 and WAVE_DEALS_12MO == 6
    out = score_p4_maa_tehingud(rich_listing(), BUILDING_DEALS,
                                {"kesklinn": 0.04}, TODAY)
    assert set(out) == set(EXPECTED_KEYS)
    assert out["micro_comp"] == 100  # asking 3200 < median 3250
    thin = score_p4_maa_tehingud(rich_listing(eur_m2=None, address=None,
                                              street=None, asum="Tühi",
                                              floor=None, house_number=None,
                                              first_seen=None,
                                              views_per_day=None, dom_days=None,
                                              developer=None,
                                              area_type="tundmatu",
                                              settlement_checklist=None),
                                 [], None, TODAY)
    assert thin["micro_comp"] is None and thin["last_shop"] is None
    assert p4.P4_MAA_TEHINGUD_DIMS is P4_MAA_TEHINGUD_DIMS

