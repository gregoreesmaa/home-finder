"""P4 ppa dims (issues #278, #352): hermetic tests.

No network: parsing runs on fixture TSV strings mirroring the live
schema (tab-separated, quoted, ValdLinnNimetus/KohtNimetus geography),
both scorers run on fixture coverage dicts, the fetch path is proven
via file:// URLs (live/cache/garbage/stale) without touching the
network, politeness constants are asserted as values, and the one real
pull is env-gated (HF_LIVE_PPA=1) so the default suite stays offline.
Run: python3 -m pytest services/scoring/tests/test_dims_p4_ppa.py -q
"""

import os

import pytest

import dims_p4_ppa as ppa
from dims_p4_ppa import (
    KOLMANDIK_ET,
    P4PPA_DIMS,
    P4PPA_PARAM_IDS,
    PPA_AVAANDMED_URL,
    PPA_CACHE_NAMES,
    PPA_CACHE_TTL_S,
    PPA_DATASETS,
    PPA_STATS_URL,
    PPA_THEFT_CSV_URL,
    PPA_TRAFFIC_CSV_URL,
    THEFT_BANDS,
    TRAFFIC_BANDS,
    _tertile_band,
    dim_theft_tariff_proxy,
    dim_traffic_supervision,
    fetch_ppa_snapshot,
    normalize_linnaosa,
    parse_ppa_snapshot,
    score_p4_ppa,
)

TALLINN = (59.4372, 24.7536)

# Fixture TSVs mirror the live schema observed 2026-09-13 (quoted,
# TAB-separated; theft rows carry SyndmusLiik + damage band, traffic
# rows carry street + offender brackets). Only the geography columns
# drive the parser; the rest proves the reader skips what it ignores.
FIXTURE_THEFT = (
    '"JuhtumId"\t"ToimKpv"\t"SyndmusLiik"\t"MaakondNimetus"\t'
    '"ValdLinnNimetus"\t"KohtNimetus"\t"Kahjusumma"\t"SyyteoLiik"\n'
    '"id-1"\t"2026-09-09"\t"VARGUS"\t"Harju maakond"\t"Tallinn"\t'
    '"Põhja-Tallinna linnaosa"\t"0-499"\t"KT"\n'
    '"id-2"\t"2026-09-08"\t"VARGUS"\t"Harju maakond"\t"Tallinn"\t'
    '"Põhja-Tallinna linnaosa"\t"500-4999"\t"VT"\n'
    '"id-3"\t"2026-09-08"\t"VANDALISM"\t"Harju maakond"\t"Tallinn"\t'
    '"Kesklinna linnaosa"\t"0-499"\t"VT"\n'
    '"id-4"\t"2026-09-08"\t"VARGUS"\t"Ida-Viru maakond"\t"Narva linn"\t'
    '"Narva linn"\t"0-499"\t"VT"\n'
    '"id-5"\t"2026-09-07"\t"VARGUS"\t"Harju maakond"\t"Tallinn"\t'
    '""\t"0-499"\t"VT"\n'
    '"short"\t"2026-09-07"\n'
)

FIXTURE_TRAFFIC = (
    '"JuhtumId"\t"ToimKpv"\t"Paragrahv"\t"MaakondNimetus"\t'
    '"ValdLinnNimetus"\t"KohtNimetus"\t"MntTanavNimetus"\t'
    '"RikkujaVanus"\t"SyyteoLiik"\n'
    '"t-1"\t"2026-09-09"\t"§ 242."\t"Harju maakond"\t"Tallinn"\t'
    '"Lasnamäe linnaosa"\t"Läänemere tee"\t"35-44"\t"VT"\n'
    '"t-2"\t"2026-09-08"\t"§ 227."\t"Harju maakond"\t"Tallinn"\t'
    '"Lasnamäe linnaosa"\t"Pae tn"\t"18-25"\t"VT"\n'
    '"t-3"\t"2026-09-08"\t"§ 242."\t"Harju maakond"\t"Tallinn"\t'
    '"Nõmme linnaosa"\t"Pärnu mnt"\t"26-34"\t"VT"\n'
    '"t-4"\t"2026-09-08"\t"§ 242."\t"Tartu maakond"\t"Tartu linn"\t'
    '"Tartu linn"\t"Riia tn"\t"26-34"\t"VT"\n'
)

# Eight-linnaosa ranking tables: sorted asc, thirds split 3/3/2.
TRAFFIC_COUNTS = {"Pirita": 10, "Nõmme": 30, "Kristiine": 50,
                  "Haabersti": 60, "Mustamäe": 70, "Kesklinn": 90,
                  "Lasnamäe": 100, "Põhja-Tallinn": 120}
THEFT_COUNTS = {"Pirita": 5, "Nõmme": 20, "Haabersti": 40,
                "Kristiine": 60, "Mustamäe": 80, "Lasnamäe": 120,
                "Põhja-Tallinn": 180, "Kesklinn": 200}


def _cov(linnaosa, traffic=None, theft=None):
    return {"source": "fixture", "linnaosa": linnaosa,
            "ppa_traffic_counts": traffic if traffic is not None
            else dict(TRAFFIC_COUNTS),
            "ppa_theft_counts": theft if theft is not None
            else dict(THEFT_COUNTS),
            "ppa_window": "fixture _1 (jooksev+eelmine aasta)"}


# ---------------------------------------------------------------------------
# Parse: pure TSV reader, Tallinn filter, linnaosa normalisation.
# ---------------------------------------------------------------------------

def test_parse_theft_counts_tallinn_linnaosad_only():
    out = parse_ppa_snapshot(FIXTURE_THEFT, "theft")
    assert out["kind"] == "theft"
    assert out["counts"] == {"Põhja-Tallinn": 2, "Kesklinn": 1}
    assert out["tallinn_rows"] == 3
    # Narva row ignored (not Tallinn); empty-Koht + short rows skipped.
    assert out["skipped_rows"] == 2
    assert "opendata.smit.ee" in out["source"]


def test_parse_traffic_counts_and_skips_non_tallinn():
    out = parse_ppa_snapshot(FIXTURE_TRAFFIC, "traffic")
    assert out["counts"] == {"Lasnamäe": 2, "Nõmme": 1}
    assert out["tallinn_rows"] == 3
    assert out["skipped_rows"] == 0  # Tartu row ignored, not skipped


def test_parse_empty_payload_reads_empty_never_errors():
    for text in ("", "   \n  \n"):
        out = parse_ppa_snapshot(text, "traffic")
        assert out["counts"] == {} and out["tallinn_rows"] == 0


def test_parse_missing_geo_columns_raises_visibly():
    with pytest.raises(ValueError):
        parse_ppa_snapshot('"A"\t"B"\n"1"\t"2"\n', "theft")


def test_parse_unknown_kind_raises():
    with pytest.raises(ValueError):
        parse_ppa_snapshot(FIXTURE_THEFT, "noise")


def test_normalize_linnaosa_observed_genitives_and_passthrough():
    assert normalize_linnaosa("Põhja-Tallinna linnaosa") == "Põhja-Tallinn"
    assert normalize_linnaosa("Kesklinna linnaosa") == "Kesklinn"
    assert normalize_linnaosa("Lasnamäe linnaosa") == "Lasnamäe"
    assert normalize_linnaosa("  Nõmme linnaosa  ") == "Nõmme"
    # Unmapped stems pass through (never guessed); non-strings read empty.
    assert normalize_linnaosa("Tartu linn") == "Tartu linn"
    assert normalize_linnaosa("") == ""
    assert normalize_linnaosa(None) == ""


# ---------------------------------------------------------------------------
# Tertiles: relative ranking, ties, degenerate tables.
# ---------------------------------------------------------------------------

def test_tertile_bands_split_thirds_by_count_then_name():
    assert _tertile_band("Pirita", TRAFFIC_COUNTS) == ("madal", 1, 8)
    assert _tertile_band("Kristiine", TRAFFIC_COUNTS) == ("madal", 3, 8)
    assert _tertile_band("Haabersti", TRAFFIC_COUNTS) == ("keskmine", 4, 8)
    assert _tertile_band("Kesklinn", TRAFFIC_COUNTS) == ("keskmine", 6, 8)
    assert _tertile_band("Lasnamäe", TRAFFIC_COUNTS) == ("korge", 7, 8)
    assert _tertile_band("Põhja-Tallinn", TRAFFIC_COUNTS) == ("korge", 8, 8)


def test_tertile_ties_break_by_name_deterministically():
    counts = {"B-linn": 5, "A-linn": 5, "C-linn": 5}
    assert _tertile_band("A-linn", counts) == ("madal", 1, 3)
    assert _tertile_band("B-linn", counts) == ("keskmine", 2, 3)
    assert _tertile_band("C-linn", counts) == ("korge", 3, 3)


def test_tertile_degenerate_tables():
    assert _tertile_band("Kesklinn", {"Kesklinn": 9}) == ("keskmine", 1, 1)
    assert _tertile_band("Tundmatu", TRAFFIC_COUNTS) is None
    assert _tertile_band(None, TRAFFIC_COUNTS) is None
    assert _tertile_band("Kesklinn", {}) is None
    assert _tertile_band("Kesklinn", None) is None


# ---------------------------------------------------------------------------
# P4-012 demo dim: supervision tertile, weak compressed bands.
# ---------------------------------------------------------------------------

def test_traffic_bands_are_weak_and_compressed():
    v, _ = dim_traffic_supervision(TALLINN, [], _cov("Pirita"))
    assert v == 60
    v, _ = dim_traffic_supervision(TALLINN, [], _cov("Mustamäe"))
    assert v == 50
    v, _ = dim_traffic_supervision(TALLINN, [], _cov("Põhja-Tallinn"))
    assert v == 40


def test_traffic_reason_names_activity_not_danger_plus_unjoined_legs():
    v, reason = dim_traffic_supervision(TALLINN, [], _cov("Lasnamäe"))
    assert v == 40
    assert "hinnang" in reason
    assert "järelevalve aktiivsus, mitte ristmiku ohu tõend" in reason
    assert "100 juhtumit" not in reason and "100 avastatud" in reason
    assert "7. koht 8 linnaosast" in reason
    assert "Transpordiameti õnnetuspunktid" in reason
    assert "Tark Tee" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_traffic_single_linnaosa_scores_neutral_with_note():
    v, reason = dim_traffic_supervision(
        TALLINN, [], _cov("Kesklinn", traffic={"Kesklinn": 4}))
    assert v == 50
    assert "võrdlusbaas üks linnaosa" in reason


def test_traffic_choropleth_needs_no_origin_but_needs_table():
    v, _ = dim_traffic_supervision(None, None, _cov("Pirita"))
    assert v == 60  # zone join: coverage resolves, origin unused
    for cov in (None, {}, {"linnaosa": "Pirita"},
                _cov("Tundmatu"), _cov("Pirita", traffic={})):
        v, reason = dim_traffic_supervision(TALLINN, [], cov)
        assert v is None
        assert "hinnang" in reason and "EI OLE" in reason
        assert "Transpordiameti" in reason or "liiklusfail" in reason


# ---------------------------------------------------------------------------
# P4-015 coverage dim: theft tertile + illiquidity flag on top third.
# ---------------------------------------------------------------------------

def test_theft_bands_mirror_paaste_fire_slice_scale():
    assert dim_theft_tariff_proxy(TALLINN, [], _cov("Pirita"))[0] == 70
    assert dim_theft_tariff_proxy(TALLINN, [], _cov("Mustamäe"))[0] == 50
    assert dim_theft_tariff_proxy(TALLINN, [], _cov("Kesklinn"))[0] == 25


def test_theft_reason_is_tariff_proxy_not_tariff():
    v, reason = dim_theft_tariff_proxy(TALLINN, [], _cov("Nõmme"))
    assert v == 70
    assert "hinnang" in reason
    assert "ainult varguse jalg, mitte tariif" in reason
    assert "20" in reason and "2. koht 8 linnaosast" in reason
    assert "üleujutusjalg" in reason and "kindlustusandjalt" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_theft_top_third_carries_illiquidity_flag():
    v, reason = dim_theft_tariff_proxy(TALLINN, [], _cov("Kesklinn"))
    assert v == 25
    assert "ÜLEMINE kolmandik" in reason
    assert "mittelikviidsuse lipp" in reason
    assert "kindlustus-keeldumise" in reason


def test_theft_nulls_name_missing_table_and_insurer_check():
    for cov in (None, {}, {"linnaosa": "Kesklinn"},
                _cov("Tundmatu"), _cov("Kesklinn", theft={})):
        v, reason = dim_theft_tariff_proxy(TALLINN, [], cov)
        assert v is None
        assert "hinnang" in reason and "EI OLE" in reason
        assert "PZU/ERGO/If" in reason
        assert "garanteeritud" not in reason and "mõõdetud" not in reason


# ---------------------------------------------------------------------------
# Registry, rollup, constants, fetch (hermetic file:// + gated live).
# ---------------------------------------------------------------------------

def test_band_constants_pinned():
    assert TRAFFIC_BANDS == {"madal": 60, "keskmine": 50, "korge": 40}
    assert THEFT_BANDS == {"madal": 70, "keskmine": 50, "korge": 25}
    assert KOLMANDIK_ET == {"madal": "alumine", "keskmine": "keskmine",
                            "korge": "ülemine"}


def test_registry_and_rollup_shape():
    assert set(P4PPA_DIMS) == {"traffic_supervision", "theft_tariff"}
    assert P4PPA_PARAM_IDS == {"traffic_supervision": 12, "theft_tariff": 15}
    assert P4PPA_DIMS["traffic_supervision"][0] == "P4-012"
    assert P4PPA_DIMS["theft_tariff"][0] == "P4-015"
    dims, reasons = score_p4_ppa(TALLINN, [], _cov("Pirita"))
    assert dims == {"traffic_supervision": 60, "theft_tariff": 70}
    assert len(reasons) == 2
    dims, reasons = score_p4_ppa(TALLINN, [], _cov("Kesklinn"))
    assert dims == {"traffic_supervision": 50, "theft_tariff": 25}
    empty, no_reasons = score_p4_ppa(TALLINN, [], None)
    assert empty == {k: None for k in P4PPA_DIMS}
    assert no_reasons == []  # NULL dims contribute no reasons
    assert ppa.P4PPA_DIMS is P4PPA_DIMS


def test_politeness_contract_as_values():
    assert PPA_DATASETS == {"traffic": PPA_TRAFFIC_CSV_URL,
                            "theft": PPA_THEFT_CSV_URL}
    assert PPA_TRAFFIC_CSV_URL == (
        "https://opendata.smit.ee/ppa/csv/liiklusjarelevalve_1.csv")
    assert PPA_THEFT_CSV_URL == (
        "https://opendata.smit.ee/ppa/csv/vara_1.csv")
    assert PPA_STATS_URL == "https://www.politsei.ee/et/statistika"
    assert PPA_AVAANDMED_URL == ("https://www.politsei.ee/et/juhend/"
                                 "politseitoeoega-seotud-avaandmed")
    assert PPA_CACHE_TTL_S == 7 * 86400  # weekly max per Thursday refresh
    assert PPA_CACHE_NAMES == {"traffic": "ppa-liiklusjarelevalve_1.csv",
                               "theft": "ppa-vara_1.csv"}
    assert "home-finder" in ppa.PPA_USER_AGENT


def test_fetch_unknown_kind_raises_without_touching_disk(tmp_path):
    with pytest.raises(ValueError):
        fetch_ppa_snapshot("noise", cache_dir=str(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_fetch_file_url_hermetic_live_then_cache_then_stale(tmp_path):
    src = tmp_path / "vara_1.csv"
    src.write_text(FIXTURE_THEFT, encoding="utf-8")
    real = dict(ppa.PPA_DATASETS)
    ppa.PPA_DATASETS["theft"] = src.as_uri()
    try:
        cache = tmp_path / "cache"
        body, provenance = fetch_ppa_snapshot("theft",
                                              cache_dir=str(cache))
        assert provenance == "live" and "KohtNimetus" in body
        body2, provenance2 = fetch_ppa_snapshot("theft",
                                                cache_dir=str(cache))
        assert (body2, provenance2) == (body, "cache")
        import time as _time
        old = _time.time() - ppa.PPA_CACHE_TTL_S - 10
        os.utime(str(cache / "ppa-vara_1.csv"), (old, old))
        src.write_text(FIXTURE_TRAFFIC, encoding="utf-8")
        body3, provenance3 = fetch_ppa_snapshot("theft",
                                                cache_dir=str(cache))
        assert provenance3 == "live" and "Paragrahv" in body3
    finally:
        ppa.PPA_DATASETS.clear()
        ppa.PPA_DATASETS.update(real)


def test_fetch_garbage_body_raises_and_leaves_cache_untouched(tmp_path):
    src = tmp_path / "vara_1.csv"
    src.write_text("<html>oops</html>", encoding="utf-8")
    real = dict(ppa.PPA_DATASETS)
    ppa.PPA_DATASETS["theft"] = src.as_uri()
    try:
        with pytest.raises(RuntimeError):
            fetch_ppa_snapshot("theft", cache_dir=str(tmp_path / "c"))
        assert not (tmp_path / "c" / "ppa-vara_1.csv").exists()
    finally:
        ppa.PPA_DATASETS.clear()
        ppa.PPA_DATASETS.update(real)


@pytest.mark.skipif(not os.environ.get("HF_LIVE_PPA"),
                    reason="live network only with HF_LIVE_PPA=1")
def test_live_theft_pull_explicit_flag_only(tmp_path):
    text, provenance = fetch_ppa_snapshot("theft", cache_dir=str(tmp_path))
    assert "KohtNimetus" in text
    assert provenance in ("live", "cache")
