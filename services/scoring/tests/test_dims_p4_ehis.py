"""P4 EHIS / HaridusSilm demo + coverage dims (issues #271, #347): hermetic tests.

No network: fetch_ehis_table is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus fixture-fed parse
tests). Every dim is tested on fixture per-linnaosa rows through
the join shape: joined row -> bands, missing row/slice -> NULL with
Estonian honesty markers.
"""

import os

import dims_p4_ehis as ehis
from dims_p4_ehis import (
    EHIS_TTL_DAYS,
    P4_EHIS_DIMS,
    cache_is_fresh,
    dim_artschool_density,
    dim_school_pressure,
    index_by_linnaosa,
    parse_linnaosa_table,
    score_p4_ehis,
)

# ---------------------------------------------------------------------------
# Fixtures: per-linnaosa snapshot-table layout (semicolon, BOM, sparse
# columns) plus canonical joined rows.
# ---------------------------------------------------------------------------

FIXTURE_CSV = (
    "\ufefflinnaosa;schools;pupil_places;pupils;queue_len;"
    "art_music_schools;catchment_note\n"
    "Kesklinn;12;8500;6800;320;4;Vanalinna piirkond\n"
    "Lasnamäe;15;12000;12960;;0;Laagna–Priisle\n"
    "Nõmme;6;3000;;45;1;\n"
)

KESKLINN = {
    "linnaosa": "Kesklinn",
    "schools": 12,
    "pupil_places": 8500,
    "pupils": 6800,
    "queue_len": 320,
    "art_music_schools": 4,
    "catchment_note": "Vanalinna piirkond",
}

LASNAMAE = {
    "linnaosa": "Lasnamäe",
    "schools": 15,
    "pupil_places": 12000,
    "pupils": 12960,
    "queue_len": None,
    "art_music_schools": 0,
    "catchment_note": "Laagna–Priisle",
}

NOMME = {
    "linnaosa": "Nõmme",
    "schools": 6,
    "pupil_places": 3000,
    "pupils": None,
    "queue_len": 45,
    "art_music_schools": 1,
    "catchment_note": None,
}

ALL_FNS = [fn for _, _, fn in P4_EHIS_DIMS]

EXPECTED_KEYS = ["school_pressure", "artschool_density"]

EXPECTED_PNUMS = ["P4-011", "P4-044"]


# ---------------------------------------------------------------------------
# Ingestion: parse + join + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_handles_bom_semicolons_and_sparse_rows():
    recs = parse_linnaosa_table(FIXTURE_CSV)
    assert len(recs) == 3
    kesk, las, nom = recs
    assert kesk["linnaosa"] == "Kesklinn"
    assert kesk["pupil_places"] == 8500
    assert kesk["pupils"] == 6800
    assert kesk["queue_len"] == 320
    assert kesk["art_music_schools"] == 4
    assert kesk["catchment_note"] == "Vanalinna piirkond"
    # Sparse row: empty cells become None, never guesses.
    assert las["queue_len"] is None
    assert las["art_music_schools"] == 0
    assert nom["pupils"] is None
    assert nom["catchment_note"] is None


def test_parse_skips_rows_without_join_key():
    csv_text = ("linnaosa;pupil_places\n"
                ";8500\n"
                "Pirita;2100\n")
    recs = parse_linnaosa_table(csv_text)
    assert [r["linnaosa"] for r in recs] == ["Pirita"]


def test_parse_int_tolerance():
    csv_text = ("linnaosa;pupil_places;pupils\n"
                "Mustamäe; 9 000 ;abc\n")
    recs = parse_linnaosa_table(csv_text)
    assert recs[0]["pupil_places"] == 9000
    assert recs[0]["pupils"] is None  # "abc" never guessed


def test_index_by_linnaosa_first_row_wins_casefolded():
    recs = parse_linnaosa_table(FIXTURE_CSV)
    index = index_by_linnaosa(recs + [dict(KESKLINN, pupil_places=1)])
    assert index["kesklinn"]["pupil_places"] == 8500
    assert index["lasnamäe"]["catchment_note"] == "Laagna–Priisle"
    assert index["nõmme"]["queue_len"] == 45


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert EHIS_TTL_DAYS == 90  # quarterly per parameters4.md P4-011
    missing = os.path.join(str(tmp_path), "ehis-x.csv")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "ehis-x.csv"
    p.write_text("linnaosa\nKesklinn\n", encoding="utf-8")
    assert cache_is_fresh(str(p), ttl_days=90) is True
    aged = 91 * 86400.0
    assert cache_is_fresh(str(p), ttl_days=90,
                          now=os.path.getmtime(str(p)) + aged) is False


# ---------------------------------------------------------------------------
# NULL contracts: missing row/slice is always NULL with Estonian markers.
# ---------------------------------------------------------------------------

def test_both_dims_null_without_row_and_name_source():
    for fn in ALL_FNS:
        v, reason = fn(None)
        assert v is None, fn.__name__
        assert "HaridusSilm" in reason or "EHIS" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_both_dims_accept_missing_listing_side():
    for fn in ALL_FNS:
        v, reason = fn(KESKLINN)  # listing=None must never crash
        assert isinstance(reason, str) and reason, fn.__name__
        assert v is None or isinstance(v, int)


def test_scored_reasons_trace_to_registry_not_estimates():
    v, reason = dim_school_pressure(KESKLINN)
    assert isinstance(v, int) and 0 <= v <= 100
    assert "HaridusSilm/EHIS" in reason
    v, reason = dim_artschool_density(KESKLINN)
    assert isinstance(v, int) and 0 <= v <= 100
    assert "HaridusSilm/EHIS" in reason


# ---------------------------------------------------------------------------
# Demo P4-011: utilization bands + echoes + sibling legs named.
# ---------------------------------------------------------------------------

def test_school_pressure_bands():
    v, _ = dim_school_pressure(KESKLINN)  # 6800/8500 = 80%
    assert v == 75
    v, _ = dim_school_pressure(dict(KESKLINN, pupils=7820))
    assert v == 60  # 92%
    v, _ = dim_school_pressure(dict(KESKLINN, pupils=8500))
    assert v == 45  # 100%
    v, _ = dim_school_pressure(LASNAMAE)  # 12960/12000 = 108%
    assert v == 30


def test_school_pressure_echoes_queue_and_catchment():
    _, reason = dim_school_pressure(KESKLINN)
    assert "320" in reason and "Haridusamet" in reason
    assert "Vanalinna piirkond" in reason


def test_school_pressure_names_sibling_legs():
    _, reason = dim_school_pressure(LASNAMAE)
    assert "Haridusamet" in reason
    assert "Tervisekassa" in reason


def test_school_pressure_null_without_capacity_numbers():
    v, reason = dim_school_pressure(NOMME)  # pupils missing
    assert v is None and "EI OLE" in reason
    v, reason = dim_school_pressure({"linnaosa": "Pirita"})
    assert v is None and "EI OLE" in reason
    v, reason = dim_school_pressure(dict(KESKLINN, pupil_places=0))
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Coverage P4-044: taste-match cap/floor, never worth judgement.
# ---------------------------------------------------------------------------

def test_artschool_density_bands_capped():
    v, reason = dim_artschool_density(KESKLINN)  # 4 schools
    assert v == 70
    assert "maitsesobivus" in reason
    v, _ = dim_artschool_density(NOMME)  # 1 school
    assert v == 60
    v, reason = dim_artschool_density(LASNAMAE)  # 0 schools: neutral
    assert v == 50
    assert "neutraalne" in reason


def test_artschool_density_never_worth_judgement():
    for row in (KESKLINN, LASNAMAE, NOMME):
        _, reason = dim_artschool_density(row)
        assert "mitte väärtushinnang" in reason
        assert "hinnang" in reason


def test_artschool_density_null_without_slice():
    v, reason = dim_artschool_density({"linnaosa": "Pirita"})
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Registry + aggregator cover both params.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_EHIS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_EHIS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_EHIS_DIMS}) == 2
    out = score_p4_ehis(KESKLINN)
    assert out == {"school_pressure": 75, "artschool_density": 70}
    assert score_p4_ehis(None) == {k: None for k in EXPECTED_KEYS}
    assert ehis.P4_EHIS_DIMS is P4_EHIS_DIMS
