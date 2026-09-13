"""P4 taitur demo + coverage dims (issues #255, #336): hermetic tests.

No network: fetch_taitur_csv is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus fixture-fed parse
tests). Every dim is tested on fixture case slices through the
per-subject join shape: joined slice -> bands, missing slice -> NULL
with Estonian honesty markers.
"""

import os

import dims_p4_taitur as taitur
from dims_p4_taitur import (
    P4_TAITUR_DIMS,
    TAITUR_TTL_S,
    cache_is_fresh,
    dim_enforcement,
    dim_kinnistus_checkpoint,
    index_by_subject,
    parse_taitur_cases,
    score_p4_taitur,
)

# ---------------------------------------------------------------------------
# Fixtures: taitur snapshot layout (semicolon, BOM, sparse columns) plus
# canonical joined slices. subject_key doubles as the join key (parcel
# id for kinnistu rows, registry code for arendaja rows). No personal
# data anywhere (AGENTS.md section 5 — fixtures only).
# ---------------------------------------------------------------------------

FIXTURE_CSV = (
    "\ufeffsubject_key;subject_kind;address;kov;stage;status;"
    "bailiff_office;updated\n"
    "79401:001:0001;KINNISTU;Tallinn, Pärnu mnt 1;Tallinn;arest;AKTIIVNE;"
    "Tallinna büroo;2026-09-01\n"
    "12345678;arendaja;Tallinn, Kalamaja 13;Tallinn;pankrot;aktiivne;;\n"
    "79401:002:0002;kinnistu;Tallinn, Tina 5;Tallinn;keelumärge;lõpetatud;;\n"
)

FREEZE_SLICE = [
    {"subject_key": "79401:001:0001", "subject_kind": "kinnistu",
     "address": "Tallinn, Pärnu mnt 1", "kov": "Tallinn",
     "stage": "arest", "status": "aktiivne",
     "bailiff_office": "Tallinna büroo", "updated": "2026-09-01"},
]

DEV_SLICE = [
    {"subject_key": "12345678", "subject_kind": "arendaja",
     "address": "Tallinn, Kalamaja 13", "kov": "Tallinn",
     "stage": "pankrot", "status": "aktiivne",
     "bailiff_office": None, "updated": None},
]

RESOLVED_SLICE = [
    {"subject_key": "79401:002:0002", "subject_kind": "kinnistu",
     "address": "Tallinn, Tina 5", "kov": "Tallinn",
     "stage": "keelumärge", "status": "lõpetatud",
     "bailiff_office": None, "updated": None},
]

ALL_FNS = [fn for _, _, fn in P4_TAITUR_DIMS]

EXPECTED_KEYS = ["enforcement", "kinnistus_checkpoint"]
EXPECTED_PNUMS = ["P4-020", "P4-004"]


# ---------------------------------------------------------------------------
# Ingestion: parse + join + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_handles_bom_semicolons_and_case_folding():
    recs = parse_taitur_cases(FIXTURE_CSV)
    assert len(recs) == 3
    first = recs[0]
    assert first["subject_key"] == "79401:001:0001"
    assert first["subject_kind"] == "kinnistu"  # KINNISTU folded
    assert first["stage"] == "arest"
    assert first["status"] == "aktiivne"  # AKTIIVNE folded
    assert first["bailiff_office"] == "Tallinna büroo"
    # Sparse row: empty cells become None, never guesses.
    assert recs[1]["bailiff_office"] is None
    assert recs[1]["updated"] is None


def test_parse_skips_rows_without_join_key():
    csv_text = ("subject_key;stage;status\n"
                ";arest;aktiivne\n"
                "79401:001:0001;arest;aktiivne\n")
    recs = parse_taitur_cases(csv_text)
    assert [r["subject_key"] for r in recs] == ["79401:001:0001"]


def test_parse_never_guesses_unknown_tokens():
    csv_text = ("subject_key;subject_kind;stage;status\n"
                "X;kosmos;tundmatu;ootel\n")
    recs = parse_taitur_cases(csv_text)
    assert recs[0]["subject_kind"] is None
    assert recs[0]["stage"] is None
    assert recs[0]["status"] is None


def test_parse_skips_rows_carrying_personal_data():
    csv_text = ("subject_key;stage;status;võlgnik;isikukood\n"
                "79401:001:0001;arest;aktiivne;Jaan T;;\n"
                "79401:002:0002;arest;aktiivne;;\n")
    recs = parse_taitur_cases(csv_text)
    assert [r["subject_key"] for r in recs] == ["79401:002:0002"]


def test_index_by_subject_groups_all_rows():
    recs = parse_taitur_cases(FIXTURE_CSV)
    index = index_by_subject(recs)
    assert set(index) == {"79401:001:0001", "12345678", "79401:002:0002"}
    assert index["79401:001:0001"][0]["stage"] == "arest"
    doubled = index_by_subject(recs + [dict(recs[0], stage="oksjon")])
    assert [r["stage"] for r in doubled["79401:001:0001"]] == [
        "arest", "oksjon"]


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert TAITUR_TTL_S == 86400  # daily pull per docs/p4_taitur.md
    missing = os.path.join(str(tmp_path), "taitur-x.csv")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "taitur-x.csv"
    p.write_text("subject_key\n1\n", encoding="utf-8")
    assert cache_is_fresh(str(p), ttl_s=86400) is True
    aged = 25 * 3600.0
    assert cache_is_fresh(str(p), ttl_s=86400,
                          now=os.path.getmtime(str(p)) + aged) is False


# ---------------------------------------------------------------------------
# NULL contracts: missing slice is always NULL with Estonian markers.
# ---------------------------------------------------------------------------

def test_both_dims_null_without_slice_and_name_register():
    for fn in ALL_FNS:
        v, reason = fn(None)
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_missing_slice_points_at_kinnistusraamat_and_notar():
    _, reason = dim_enforcement(None)
    assert "e-Kinnistusraamat" in reason and "notar" in reason
    _, reason = dim_kinnistus_checkpoint(None)
    assert "e-Kinnistusraamat" in reason and "notari" in reason


def test_both_dims_accept_missing_listing_side():
    for fn in ALL_FNS:
        for cases in (FREEZE_SLICE, DEV_SLICE, RESOLVED_SLICE, []):
            v, reason = fn(cases)  # listing=None must never crash
            assert isinstance(reason, str) and reason, fn.__name__
            assert v is None or isinstance(v, int)


def test_non_list_input_is_null_not_crash():
    for fn in ALL_FNS:
        v, reason = fn("arest")  # type: ignore[arg-type]
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__


# ---------------------------------------------------------------------------
# Demo P4-020 bands.
# ---------------------------------------------------------------------------

def test_enforcement_freezes_this_deal_on_property_arest():
    v, reason = dim_enforcement(FREEZE_SLICE)
    assert v == 15
    assert "arest/kinnistu" in reason
    assert "registriandmed" in reason and "mitte hinnang" in reason
    assert "külmutatud" in reason


def test_enforcement_clouds_developer_side_cases():
    v, reason = dim_enforcement(DEV_SLICE)
    assert v == 40
    assert "pankrot/arendaja" in reason
    assert "kinnistu ise" in reason and "vaba" in reason


def test_enforcement_weak_good_capped_never_clean_100():
    for cases in (RESOLVED_SLICE, []):
        v, reason = dim_enforcement(cases)
        assert v == 70
        assert "ülempiir 70" in reason
        assert "osaline" in reason


def test_enforcement_property_freeze_wins_over_developer_case():
    v, _ = dim_enforcement(FREEZE_SLICE + DEV_SLICE)
    assert v == 15


def test_enforcement_unknown_stage_without_status_is_weak_good():
    mystery = [{"subject_key": "X", "subject_kind": None,
                "stage": None, "status": None}]
    v, reason = dim_enforcement(mystery)
    assert v == 70 and "ülempiir 70" in reason


# ---------------------------------------------------------------------------
# Coverage P4-004 bands (taitur slice of the notary checkpoint).
# ---------------------------------------------------------------------------

def test_checkpoint_blocks_close_on_property_freeze():
    v, reason = dim_kinnistus_checkpoint(FREEZE_SLICE)
    assert v == 20
    assert "arest/kinnistu" in reason
    assert "notari" in reason and "ei sulgu" in reason


def test_checkpoint_flags_developer_side_for_notar():
    v, reason = dim_kinnistus_checkpoint(DEV_SLICE)
    assert v == 50
    assert "notar küsib täiendavalt" in reason
    assert "sulgumine" in reason and "võimalik" in reason


def test_checkpoint_weak_good_still_needs_kinnistusraamat():
    for cases in (RESOLVED_SLICE, []):
        v, reason = dim_kinnistus_checkpoint(cases)
        assert v == 70
        assert "ülempiir" in reason
        assert "kinnistusraamatu väljavõtet" in reason


def test_checkpoint_names_unjoined_rik_flow():
    _, reason = dim_kinnistus_checkpoint(None)
    assert "tasuline" in reason and "keelumärge/hüpoteek" in reason


# ---------------------------------------------------------------------------
# Caps + registry + aggregator cover both params.
# ---------------------------------------------------------------------------

def test_all_scores_capped_at_70():
    slices = (FREEZE_SLICE, DEV_SLICE, RESOLVED_SLICE, [],
              FREEZE_SLICE + DEV_SLICE)
    for fn in ALL_FNS:
        for cases in slices:
            v, _ = fn(cases, {"floor": 3})
            assert v is None or v <= 70, (fn.__name__, cases)
            assert v is None or v >= 0, (fn.__name__, cases)


def test_scored_reasons_trace_to_register_not_estimates():
    scored = [
        (dim_enforcement, FREEZE_SLICE),
        (dim_enforcement, DEV_SLICE),
        (dim_kinnistus_checkpoint, FREEZE_SLICE),
        (dim_kinnistus_checkpoint, DEV_SLICE),
    ]
    for fn, cases in scored:
        v, reason = fn(cases)
        assert isinstance(v, int), fn.__name__
        assert "registriandmed" in reason, fn.__name__
        assert "garanteeritud" not in reason and "mõõdetud" not in reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_TAITUR_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_TAITUR_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_TAITUR_DIMS}) == 2
    out = score_p4_taitur(FREEZE_SLICE, {"floor": 3})
    assert out == {"enforcement": 15, "kinnistus_checkpoint": 20}
    out = score_p4_taitur(DEV_SLICE)
    assert out == {"enforcement": 40, "kinnistus_checkpoint": 50}
    out = score_p4_taitur([])
    assert out == {"enforcement": 70, "kinnistus_checkpoint": 70}
    assert score_p4_taitur(None) == {k: None for k in EXPECTED_KEYS}
    assert taitur.P4_TAITUR_DIMS is P4_TAITUR_DIMS
