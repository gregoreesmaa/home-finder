"""P4 EMTA (new uses) demo + coverage dims (issues #256, #337): tests.

Hermetic: fetch_emta_page is never called against the network here
(its contract — single polite GET, file cache, TTL, transport
errors raise — is covered via the pure cache_is_fresh helper, the
pure build_emta_url shape test, and a fresh-cache read that fails
the test if urlopen is reached). Every dim is tested on fixture
EMTA records through the join shapes: joined slices -> bands,
missing slice -> NULL with Estonian honesty markers.

Fixtures mirror the real page layout observed 2026-09-13 (maamaks
guide bands, yearly KOV-table references, volaparing floor rule)
but every entity, rate row, and band label is SYNTHETIC — never a
real pull (repo hygiene: fixtures only, no scraped dumps).
"""

import os

import dims_p4_emta as emta
from dims_p4_emta import (
    AUTOMAKS_CALCULATOR_URL,
    EMTA_BASE_URL,
    EMTA_TTL_DAYS,
    MAAMAKS_PAGE_PATH,
    P4_EMTA_DIMS,
    build_emta_url,
    cache_is_fresh,
    dim_fiscal_health,
    dim_kinnistus_debt,
    dim_policy_exposure,
    fetch_emta_page,
    parse_maamaks_page,
    score_p4_emta,
)

# ---------------------------------------------------------------------------
# Fixtures: real-shape page excerpt (synthetic) + joined records.
# ---------------------------------------------------------------------------

FIXTURE_MAAMAKS_EXCERPT = """
<html><body>
<p>2026. aasta maksumäärade vahemikud on: elamumaale ja
maatulundusmaa õuemaa kõlvikule 0,1–1% maatulundusmaale 0,1–0,5%
muu sihtotstarbega maale 0,1–2% maa maksustamishinnast aastas.</p>
<p>Maamaksumäärad kohalikes omavalitsustes * 2026 | pdf
2025 | pdf 2024 | pdf</p>
<p>Võlapäring: päringu tegemiseks tuleb sisestada isiku
registrikood või isikukood. Arvestuslikku intressi ja alla
100 eurost võlga päring ei kajasta.</p>
</body></html>
"""

FIXTURE_SPARSE_PAGE = "<html><body><p>Maamaksu juhend.</p></body></html>"


def _kov(trend="sama", rate=0.8, **extra):
    rec = {
        "kov": "Tallinn",
        "tallinn": True,
        "maamaksu_maar_pct": rate,
        "maamaksu_aasta": 2026,
        "maamaksu_trend": trend,
    }
    rec.update(extra)
    return rec


def _debt(debt=False, entity="12345678", checked="2026-09-13"):
    return {
        "tallinn": True,
        "entity": entity,
        "volaparing": {"debt": debt, "checked": checked},
    }


def _exposure(dependent=True, band="keskmine"):
    return {"tallinn": True, "car_dependent": dependent, "co2_band": band}


FULL_EMTA = {
    "kov": "Tallinn",
    "tallinn": True,
    "maamaksu_maar_pct": 0.8,
    "maamaksu_aasta": 2026,
    "maamaksu_trend": "sama",
    "entity": "12345678",
    "volaparing": {"debt": True, "checked": "2026-09-13"},
    "car_dependent": True,
    "co2_band": "keskmine",
}

ALL_FNS = [fn for _, _, fn in P4_EMTA_DIMS]

EXPECTED_KEYS = ["fiscal_health", "kinnistus_debt", "policy_exposure"]
EXPECTED_PNUMS = ["P4-019", "P4-004", "P4-037"]


# ---------------------------------------------------------------------------
# Ingestion: parse + URL shape + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_full_shape_maamaks_facts():
    facts = parse_maamaks_page(FIXTURE_MAAMAKS_EXCERPT)
    assert facts["elamumaa_band"] == (0.1, 1.0)
    assert facts["maatulundusmaa_band"] == (0.1, 0.5)
    assert facts["muu_band"] == (0.1, 2.0)
    assert facts["rate_table_years"] == ["2024", "2025", "2026"]
    assert facts["volaparing_floor_eur"] == 100
    assert facts["volaparing_needs_code"] is True


def test_parse_sparse_page_missing_is_none():
    facts = parse_maamaks_page(FIXTURE_SPARSE_PAGE)
    assert facts["elamumaa_band"] is None
    assert facts["maatulundusmaa_band"] is None
    assert facts["muu_band"] is None
    assert facts["rate_table_years"] is None
    assert facts["volaparing_floor_eur"] is None
    assert facts["volaparing_needs_code"] is None


def test_build_emta_url_paths():
    assert build_emta_url(MAAMAKS_PAGE_PATH) == (
        "https://www.emta.ee/eraklient/maksud-ja-tasumine/"
        "muud-maksud/maamaks")
    assert EMTA_BASE_URL == "https://www.emta.ee"
    assert AUTOMAKS_CALCULATOR_URL == \
        "https://avalik.emta.ee/mootorsoidukimaks"


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert EMTA_TTL_DAYS == 30  # monthly pulls per docs/p4_emta.md
    missing = os.path.join(str(tmp_path), "emta-x.html")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "emta-x.html"
    p.write_text("<html/>", encoding="utf-8")
    assert cache_is_fresh(str(p), ttl_days=30) is True
    aged = 31 * 86400.0
    assert cache_is_fresh(str(p), ttl_days=30,
                          now=os.path.getmtime(str(p)) + aged) is False


def test_fetch_uses_fresh_cache_without_network(tmp_path, monkeypatch):
    url = build_emta_url(MAAMAKS_PAGE_PATH)
    seed = emta._cache_path(str(tmp_path), url)
    with open(seed, "w", encoding="utf-8") as f:
        f.write("<html>maamaks</html>")

    def _boom(*args, **kwargs):
        raise AssertionError("network reached in hermetic test")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    assert fetch_emta_page(url, cache_dir=str(tmp_path)) == \
        "<html>maamaks</html>"


# ---------------------------------------------------------------------------
# NULL contracts: missing record / scope is always NULL.
# ---------------------------------------------------------------------------

def test_all_dims_null_without_record_and_name_source():
    for fn in ALL_FNS:
        v, reason = fn(None)
        assert v is None, fn.__name__
        assert "EMTA" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_all_dims_accept_missing_listing_side():
    for fn in ALL_FNS:
        v, reason = fn(_kov())  # listing=None must never crash
        assert isinstance(reason, str) and reason, fn.__name__
        assert v is None or isinstance(v, int)


def test_tallinn_gate_nulls_non_tallinn_joins():
    for fn, rec in ((dim_fiscal_health, _kov(tallinn=False)),
                    (dim_kinnistus_debt,
                     {"tallinn": False, "entity": "12345678",
                      "volaparing": {"debt": True}}),
                    (dim_policy_exposure, {"tallinn": False,
                                           "car_dependent": True,
                                           "co2_band": "keskmine"})):
        v, reason = fn(rec)
        assert v is None, fn.__name__
        assert "Tallinn" in reason, fn.__name__


def test_scored_reasons_trace_to_emta_and_disclaim():
    scored = [
        (dim_fiscal_health, _kov(), None),
        (dim_kinnistus_debt, _debt(debt=True), None),
        (dim_policy_exposure, _exposure(), None),
    ]
    for fn, rec, listing in scored:
        v, reason = fn(rec, listing)
        assert isinstance(v, int), fn.__name__
        assert 0 <= v <= 100, fn.__name__
        assert "EMTA" in reason, fn.__name__
        assert "mitte hinnang" in reason, fn.__name__


# ---------------------------------------------------------------------------
# P4-019 demo bands.
# ---------------------------------------------------------------------------

def test_p4019_stable_low_rate_is_capped_good():
    v, reason = dim_fiscal_health(_kov(trend="sama", rate=0.8))
    assert v == 70
    assert "stabiilne" in reason
    assert "ülempiir 70" in reason  # capped, eelarve unjoined
    v, _ = dim_fiscal_health(_kov(trend="langenud", rate=0.5))
    assert v == 70


def test_p4019_stable_high_rate_is_capped_mid():
    v, reason = dim_fiscal_health(_kov(trend="sama", rate=1.5))
    assert v == 55
    assert "kõrge tase" in reason
    v, _ = dim_fiscal_health(_kov(trend="sama", rate=1.0))  # boundary
    assert v == 55


def test_p4019_rising_rate_is_hike_warning():
    v, reason = dim_fiscal_health(_kov(trend="tõusnud", rate=0.8))
    assert v == 45
    assert "tõusuteel" in reason


def test_p4019_incomplete_rows_stay_null():
    v, reason = dim_fiscal_health({"tallinn": True, "maamaksu_trend": "sama"})
    assert v is None and "määr" in reason and "EI OLE" in reason
    v, reason = dim_fiscal_health(_kov(trend=None))
    assert v is None and "trend" in reason and "EI OLE" in reason
    v, reason = dim_fiscal_health(_kov(trend="teadmata"))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-004 coverage bands (EMTA debt slice; AT slice separate).
# ---------------------------------------------------------------------------

def test_p4004_active_debt_points_to_notary():
    v, reason = dim_kinnistus_debt(_debt(debt=True))
    assert v == 20
    assert "maksuvõlg" in reason and "notar" in reason


def test_p4004_clean_is_capped_with_floor_caveat():
    v, reason = dim_kinnistus_debt(_debt(debt=False))
    assert v == 75
    assert "100-eurost" in reason  # documented volaparing blind spot
    assert "EI OLE puhta tiitli" in reason  # capped, never proof


def test_p4004_missing_slice_stays_null():
    v, reason = dim_kinnistus_debt({"tallinn": True,
                                    "volaparing": {"debt": False}})
    assert v is None and "registrikood" in reason  # name is not enough
    v, reason = dim_kinnistus_debt({"tallinn": True, "entity": "12345678"})
    assert v is None and "EI OLE" in reason
    v, reason = dim_kinnistus_debt(
        {"tallinn": True, "entity": "12345678",
         "volaparing": {"checked": "2026-09-13"}})
    assert v is None and "kehtivus teadmata" in reason


# ---------------------------------------------------------------------------
# P4-037 coverage bands (joined CO2 labels; cutoffs never computed here).
# ---------------------------------------------------------------------------

def test_p4037_car_free_is_capped_good():
    v, reason = dim_policy_exposure(_exposure(dependent=False))
    assert v == 70
    assert "ühistransport" in reason
    assert "ülempiir 70" in reason  # ummikumaks unjoined


def test_p4037_car_bound_bands():
    v, reason = dim_policy_exposure(_exposure(band="madal"))
    assert v == 60 and "Madal" in reason
    v, reason = dim_policy_exposure(_exposure(band="keskmine"))
    assert v == 45 and "Keskmine" in reason
    v, reason = dim_policy_exposure(_exposure(band="kõrge"))
    assert v == 30 and "Kõrge" in reason
    for _, reason in (dim_policy_exposure(_exposure(band=b))
                      for b in ("madal", "keskmine", "kõrge")):
        assert "avalik.emta.ee" in reason


def test_p4037_missing_slice_stays_null():
    v, reason = dim_policy_exposure({"tallinn": True, "co2_band": "madal"})
    assert v is None and "EI OLE" in reason
    v, reason = dim_policy_exposure(_exposure(band="tundmatu"))
    assert v is None and "kalkulaator" in reason  # calculator named


# ---------------------------------------------------------------------------
# Registry + aggregator cover all 3.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_all_3():
    assert [k for k, _, _ in P4_EMTA_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_EMTA_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_EMTA_DIMS}) == 3
    out = score_p4_emta(FULL_EMTA)
    assert set(out) == set(EXPECTED_KEYS)
    assert out["fiscal_health"] == 70
    assert out["kinnistus_debt"] == 20
    assert out["policy_exposure"] == 45
    assert score_p4_emta(None) == {k: None for k in EXPECTED_KEYS}
    assert emta.P4_EMTA_DIMS is P4_EMTA_DIMS
