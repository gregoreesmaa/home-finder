"""Overturn re-check for G16 EMTA/KOV tax-table params (issue #242): tests.

Hermetic: no network here (the openness probes live in
docs/overturn_emta.md with /tmp/hf-emta242/ as the one-off PR
record). The guide-URL builder is covered by pure shape tests;
the per-KOV join contract -- parse/index/lookup -- is covered on
SYNTHETIC fixtures (invented KOV names, rates, years -- never a
real pull; repo hygiene: fixtures only, no scraped dumps, no
personal data). The five dims are tested NULL for every input
with the Estonian honesty markers pinned.
"""

import dims_overturn_emta as overturn
from dims_overturn_emta import (
    ELAMUMAA_BAND,
    EMTA_BASE_URL,
    EMTA_MAAMAKS_GUIDE_PATH,
    EMTA_OVERTURN_DIMS,
    KOV_TABLE_YEARS,
    MAATULUNDUSMAA_BAND,
    MUU_BAND,
    RATE_JOINABLE,
    RATE_NEVER,
    RECHECK_AFTER,
    STATUTORY_YEAR,
    VERDICT_DATE,
    build_guide_url,
    build_kov_index,
    dim_assessment_district_overturn,
    dim_property_taxes_overturn,
    dim_special_tax_overturn,
    dim_supplemental_tax_overturn,
    dim_tax_reassessment_overturn,
    lookup_kov_rate,
    parse_kov_row,
    score_overturn_emta,
)

TALLINN = (59.437, 24.7536)

# ---------------------------------------------------------------------------
# Fixtures: synthetic per-KOV table rows (invented names/rates).
# ---------------------------------------------------------------------------

GOOD_2026 = {"kov": "Näidisvald", "year": 2026, "elamumaa_pct": 0.8,
             "maatulundusmaa_pct": 0.4, "muu_pct": 1.5}

GOOD_2025 = {"kov": "Näidisvald", "year": 2025, "elamumaa_pct": 0.7,
             "maatulundusmaa_pct": 0.3, "muu_pct": 1.2}


# ---------------------------------------------------------------------------
# Verdict constants.
# ---------------------------------------------------------------------------

def test_verdict_dates_pinned():
    assert VERDICT_DATE == "2026-09-13"
    assert RECHECK_AFTER > VERDICT_DATE


def test_statutory_bands_match_observed_2026_guide():
    assert STATUTORY_YEAR == 2026
    assert ELAMUMAA_BAND == (0.1, 1.0)
    assert MAATULUNDUSMAA_BAND == (0.1, 0.5)
    assert MUU_BAND == (0.1, 2.0)


def test_table_years_cover_linked_editions():
    assert KOV_TABLE_YEARS == ("2022", "2023", "2024", "2025", "2026")


def test_joinable_never_partition_covers_scope():
    assert RATE_JOINABLE == ("p2",)
    assert set(RATE_NEVER) == {"p73", "p151", "p422", "p423"}
    scoped = {param for _, param, _ in EMTA_OVERTURN_DIMS}
    assert scoped == set(RATE_JOINABLE) | set(RATE_NEVER)


def test_guide_url_shape():
    url = build_guide_url()
    assert url == EMTA_BASE_URL + EMTA_MAAMAKS_GUIDE_PATH
    assert url.startswith("https://www.emta.ee/eraklient/")


# ---------------------------------------------------------------------------
# parse_kov_row: the pinned join contract (fail closed).
# ---------------------------------------------------------------------------

def test_parse_valid_2026_row():
    rec = parse_kov_row(dict(GOOD_2026))
    assert rec == {"kov": "näidisvald", "year": 2026,
                   "elamumaa_pct": 0.8, "maatulundusmaa_pct": 0.4,
                   "muu_pct": 1.5}


def test_parse_other_year_skips_band_check():
    # Bands move yearly and only 2026 was observed: a 2025 row
    # outside the 2026 bands still parses (year-stamped, honest).
    row = dict(GOOD_2025, muu_pct=2.6)
    rec = parse_kov_row(row)
    assert rec is not None and rec["year"] == 2025


def test_parse_2026_out_of_band_rejected():
    assert parse_kov_row(dict(GOOD_2026, elamumaa_pct=1.5)) is None
    assert parse_kov_row(dict(GOOD_2026, maatulundusmaa_pct=0.9)) is None
    assert parse_kov_row(dict(GOOD_2026, muu_pct=2.5)) is None


def test_parse_unjoinable_rows_rejected():
    assert parse_kov_row(None) is None
    assert parse_kov_row("Näidisvald") is None
    assert parse_kov_row(dict(GOOD_2026, kov="   ")) is None
    assert parse_kov_row(dict(GOOD_2026, kov=None)) is None
    assert parse_kov_row(dict(GOOD_2026, year="2026")) is None
    assert parse_kov_row(dict(GOOD_2026, muu_pct=None)) is None
    del_row = dict(GOOD_2026)
    del del_row["elamumaa_pct"]
    assert parse_kov_row(del_row) is None


# ---------------------------------------------------------------------------
# build_kov_index / lookup_kov_rate: exact (kov, year) join.
# ---------------------------------------------------------------------------

def test_index_first_wins_and_skips_bad_rows():
    dup = dict(GOOD_2026, elamumaa_pct=0.5)
    index = build_kov_index([dict(GOOD_2026), dup, {"kov": ""},
                             dict(GOOD_2025)])
    assert index[("näidisvald", 2026)]["elamumaa_pct"] == 0.8
    assert ("näidisvald", 2025) in index
    assert len(index) == 2


def test_index_empty_without_table():
    assert build_kov_index([]) == {}
    assert build_kov_index(None) == {}


def test_lookup_exact_hit_normalised():
    index = build_kov_index([dict(GOOD_2026)])
    hit = lookup_kov_rate("  NÄIDISVALD ", 2026, index)
    assert hit is not None and hit["elamumaa_pct"] == 0.8


def test_lookup_never_falls_back():
    index = build_kov_index([dict(GOOD_2026), dict(GOOD_2025)])
    # Wrong year is a different decree, not a fallback.
    assert lookup_kov_rate("Näidisvald", 2024, index) is None
    # Wrong KOV is a different decree, not a fallback.
    assert lookup_kov_rate("Naabervald", 2026, index) is None
    assert lookup_kov_rate("", 2026, index) is None
    assert lookup_kov_rate("Näidisvald", "2026", index) is None
    assert lookup_kov_rate("Näidisvald", 2026, {}) is None
    assert lookup_kov_rate("Näidisvald", 2026, None) is None


# ---------------------------------------------------------------------------
# The five dims: NULL for every input, dated, buyer-check reasons.
# ---------------------------------------------------------------------------

DIMS = [dim_property_taxes_overturn, dim_special_tax_overturn,
        dim_tax_reassessment_overturn, dim_supplemental_tax_overturn,
        dim_assessment_district_overturn]


def test_all_dims_null_for_listing_and_missing_origin():
    for dim in DIMS:
        for origin in (TALLINN, None):
            score, reason = dim(origin, None)
            assert score is None
            assert "EI OLE" in reason
            assert "hinnang" in reason
            assert VERDICT_DATE in reason


def test_p2_reason_names_kov_table_and_personal_discount():
    _, reason = dim_property_taxes_overturn(TALLINN, None)
    assert "KOV" in reason and "Nextcloud" in reason
    assert "§ 11" in reason  # koduomaniku soodustus isikupõhine


def test_p73_reason_names_riigiteataja_without_scraping_it():
    _, reason = dim_special_tax_overturn(TALLINN, None)
    assert "Riigi Teataja" in reason


def test_p151_reason_names_law_text():
    _, reason = dim_tax_reassessment_overturn(TALLINN, None)
    assert "maamaksuseadus" in reason


def test_p422_reason_names_deal_notice():
    _, reason = dim_supplemental_tax_overturn(TALLINN, None)
    assert "e-MTA" in reason


def test_p423_reason_names_missing_register():
    _, reason = dim_assessment_district_overturn(TALLINN, None)
    assert "keskregistrit EI OLE" in reason


# ---------------------------------------------------------------------------
# Registry + entry point.
# ---------------------------------------------------------------------------

def test_registry_keys_and_param_ids():
    assert [key for key, _, _ in EMTA_OVERTURN_DIMS] == [
        "property_taxes_overturn", "special_tax_overturn",
        "tax_reassessment_overturn", "supplemental_tax_overturn",
        "assessment_district_overturn"]
    assert [param for _, param, _ in EMTA_OVERTURN_DIMS] == [
        "p2", "p73", "p151", "p422", "p423"]
    assert all(callable(fn) for _, _, fn in EMTA_OVERTURN_DIMS)


def test_score_entry_point_all_none():
    assert score_overturn_emta(TALLINN, None) == {
        key: None for key, _, _ in EMTA_OVERTURN_DIMS}
    assert score_overturn_emta(None, None) == {
        key: None for key, _, _ in EMTA_OVERTURN_DIMS}


def test_module_documents_no_overlap_with_p4_emta():
    assert "dims_p4_emta" in overturn.__doc__
    assert "NOT edited, NOT imported" in overturn.__doc__
