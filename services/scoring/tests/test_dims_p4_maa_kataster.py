"""P4 maa-kataster dims (issues #245 demo + #329 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory parcel/plan/parking/
enforcement dict (invented numbers, never scraped data). fetch_cached is
covered only on its cache-hit path; freshness/expiry uses tmp_path. The
live probes are manual DoD evidence (pasted in the PR +
docs/p4_maa_kataster.md), not unit runs.
"""

import dims_p4_maa_kataster as p4
from dims_p4_maa_kataster import (
    BUFFER_M,
    P4_MAA_KATASTER_DIMS,
    PIPELINE_STAGES,
    TTL_DAYS,
    WEAK_GOOD_CAP,
    cache_path,
    dim_enforcement,
    dim_kinnistus_syva,
    dim_naaber_planeering,
    dim_parkimine_hoov,
    fetch_cached,
    is_fresh,
    normalise_liik,
    parcel_id,
    score_p4_maa_kataster,
    split_restrictions,
)

KID = "78401:101:0123"


def parcel(**kw):
    base = {"katastritunnus": KID, "pindala_m2": 1200.0, "kitsendused": []}
    base.update(kw)
    return base


def restr(liik):
    return {"liik": liik, "allikas": "KKIS"}


def plan(nimetus="Tähe kvartali DP", staadium="menetluses", kaugus_m=250.0):
    return {"nimetus": nimetus, "staadium": staadium, "kaugus_m": kaugus_m}


CLEAN = parcel()
FULL = parcel(
    kitsendused=[restr("arest"), restr("hüpoteek")],
    at_teated=[],
)
ENF_CLEAN = {"nimi": "OÜ Ehitaja", "kontrollitud": "2026-09-13",
             "at_teated": []}


# -- helpers ---------------------------------------------------------------

def test_parcel_id_trims_and_rejects_blank():
    assert parcel_id(parcel(katastritunnus=" 78401:101:0123 ")) == KID
    assert parcel_id(None) is None
    assert parcel_id({}) is None
    assert parcel_id({"katastritunnus": "   "}) is None
    assert parcel_id("78401:101:0123") is None


def test_normalise_liik_case_and_space():
    assert normalise_liik("  KeeluMÄRGE ") == "keelumärge"
    assert normalise_liik(None) is None
    assert normalise_liik("   ") is None


def test_split_restrictions_buckets_and_ignores_junk():
    blocking, hypo, other = split_restrictions(
        parcel(kitsendused=[restr("Arest"), restr("HÜPOTEEK"),
                            restr("servituut"), "junk", {"liik": None},
                            {"liik": "  "}]))
    assert blocking == ["Arest"]
    assert hypo == ["HÜPOTEEK"]
    assert other == ["servituut"]


def test_split_restrictions_missing_list_is_empty():
    assert split_restrictions(parcel(kitsendused=None)) == ([], [], [])


def test_buffer_and_pipeline_constants():
    assert BUFFER_M == 500.0
    assert PIPELINE_STAGES == frozenset({"menetluses", "algatatud"})
    assert WEAK_GOOD_CAP == 70
    assert TTL_DAYS == {"kataster_geometry": 91, "kkis_restrictions": 30,
                        "tpr_pipeline": 7, "parking_zones": 365,
                        "at_notices": 7}


# -- P4-004 demo ------------------------------------------------------------

def test_p4_004_blocking_scores_25_with_checkpoint():
    v, reason = dim_kinnistus_syva(
        parcel(kitsendused=[restr("keelumärge")]))
    assert v == 25
    assert "keelumärge" in reason and "notari" in reason


def test_p4_004_arest_and_hypotheek_blocking_wins():
    v, reason = dim_kinnistus_syva(FULL)
    assert v == 25
    assert "arest" in reason


def test_p4_004_lone_hypotheek_scores_55():
    v, reason = dim_kinnistus_syva(parcel(kitsendused=[restr("hüpoteek")]))
    assert v == 55
    assert "hinnang" in reason and "notariaalne" in reason


def test_p4_004_clean_public_layer_capped_weak_good():
    v, reason = dim_kinnistus_syva(CLEAN)
    assert v == WEAK_GOOD_CAP
    assert "nõrk-hea lagi" in reason and "RIK" in reason


def test_p4_004_other_restrictions_named_not_hidden():
    v, reason = dim_kinnistus_syva(
        parcel(kitsendused=[restr("servituut"), restr("kaitsevöönd")]))
    assert v == WEAK_GOOD_CAP
    assert "servituut" in reason and "kaitsevöönd" in reason


def test_p4_004_null_without_parcel_or_snapshot():
    for bad in (None, {}, {"pindala_m2": 5},
                parcel(katastritunnus=None),
                parcel(kitsendused=None)):
        v, reason = dim_kinnistus_syva(bad)
        assert v is None, bad
        assert "EI OLE" in reason and "hinnang" in reason


# -- P4-006 -----------------------------------------------------------------

def test_p4_006_pipeline_in_buffer_scores_45():
    v, reason = dim_naaber_planeering(
        CLEAN, [plan(), plan("Kauge DP", "kehtestatud", 900.0)],
        snapshot="2026-09-13")
    assert v == 45
    assert "Tähe kvartali DP" in reason and "250 m" in reason
    assert "2026-09-13" in reason


def test_p4_006_algatatud_counts_as_pipeline():
    v, _ = dim_naaber_planeering(CLEAN, [plan(staadium="ALGATATUD")])
    assert v == 45


def test_p4_006_plan_beyond_buffer_ignored():
    v, reason = dim_naaber_planeering(CLEAN, [plan(kaugus_m=501.0)])
    assert v == 70
    assert "EI OLE" in reason


def test_p4_006_only_kehtestatud_scores_65():
    v, reason = dim_naaber_planeering(
        CLEAN, [plan(staadium="kehtestatud", kaugus_m=120.0)])
    assert v == 65
    assert "kehtestatud" in reason


def test_p4_006_empty_buffer_scores_70_snapshot_dated():
    v, reason = dim_naaber_planeering(CLEAN, [], snapshot="2026-09-13")
    assert v == 70
    assert "2026-09-13" in reason and "garantii" in reason


def test_p4_006_null_without_parcel_or_snapshot():
    v, r1 = dim_naaber_planeering(None, [])
    assert v is None and "EI OLE" in r1
    v, r2 = dim_naaber_planeering(CLEAN, None)
    assert v is None and "TPR" in r2 and "EI OLE" in r2


# -- P4-013 -----------------------------------------------------------------

def test_p4_013_zone_a_with_yard_math():
    v, reason = dim_parkimine_hoov(
        CLEAN, {"tsoon": "A", "hooviala_osakaal": 0.05})
    assert v == 45  # 70 - 20 - 5
    assert "tsoon A" in reason and "hooviala" in reason


def test_p4_013_free_zone_roomy_yard_capped():
    v, reason = dim_parkimine_hoov(
        CLEAN, {"tsoon": None, "hooviala_osakaal": 0.4})
    assert v == 80  # 70 + 10
    assert "tasuta" in reason


def test_p4_013_zone_b_no_yard_leg_named():
    v, reason = dim_parkimine_hoov(CLEAN, {"tsoon": "B"})
    assert v == 60
    assert "EI OLE" in reason  # courtyard leg named missing, still scored


def test_p4_013_zone_c_scores_65():
    v, _ = dim_parkimine_hoov(
        CLEAN, {"tsoon": "C", "hooviala_osakaal": 0.2})
    assert v == 65


def test_p4_013_null_without_zone_leg():
    for bad in (None, {}, {"tsoon": "teadmata"},
                {"tsoon": None, "hooviala_osakaal": None},
                {"hooviala_osakaal": 0.5}):
        v, reason = dim_parkimine_hoov(CLEAN, bad)
        assert v is None, bad
        assert "EI OLE" in reason


def test_p4_013_unknown_zone_value_is_null():
    v, reason = dim_parkimine_hoov(CLEAN, {"tsoon": "Z"})
    assert v is None
    assert "EI OLE" in reason


def test_p4_013_needs_parcel_join():
    v, reason = dim_parkimine_hoov(None, {"tsoon": "A"})
    assert v is None and "EI OLE" in reason


# -- P4-020 -----------------------------------------------------------------

def test_p4_020_active_bankruptcy_scores_20():
    v, reason = dim_enforcement(
        CLEAN, {"nimi": "OÜ Ehitaja", "pankrot": True})
    assert v == 20
    assert "pankrot" in reason and "külmunud" in reason


def test_p4_020_active_bailiff_scores_20():
    v, reason = dim_enforcement(
        CLEAN, {"nimi": "OÜ Ehitaja", "taitementlus_aktiivne": True})
    assert v == 20
    assert "täitemenetlus" in reason


def test_p4_020_historical_notices_score_55():
    v, reason = dim_enforcement(
        CLEAN, {"nimi": "OÜ Ehitaja", "kontrollitud": "2026-09-13",
                "at_teated": [{"liik": "arest", "aasta": 2021}]})
    assert v == 55
    assert "ajaloolist" in reason


def test_p4_020_clean_check_capped_weak_good():
    v, reason = dim_enforcement(CLEAN, ENF_CLEAN)
    assert v == WEAK_GOOD_CAP
    assert "Creditinfo" in reason and "EI OLE" in reason


def test_p4_020_null_without_entity_or_check():
    for bad in (None, {}, {"kontrollitud": "2026-09-13"},
                {"nimi": "OÜ Ehitaja"}):
        v, reason = dim_enforcement(CLEAN, bad)
        assert v is None, bad
        assert "EI OLE" in reason and "hinnang" in reason


def test_p4_020_needs_parcel_join():
    v, reason = dim_enforcement(None, ENF_CLEAN)
    assert v is None and "EI OLE" in reason


# -- registry / aggregator / cache ------------------------------------------

def test_registry_and_aggregator_cover_all_four():
    assert [k for k, _, _ in P4_MAA_KATASTER_DIMS] == [
        "kinnistus_syva", "naaber_planeering", "parkimine_hoov",
        "enforcement"]
    assert [p for _, p, _ in P4_MAA_KATASTER_DIMS] == [
        "P4-004", "P4-006", "P4-013", "P4-020"]
    assert p4.P4_MAA_KATASTER_DIMS is P4_MAA_KATASTER_DIMS


def test_aggregator_unwraps_scores_and_marks_empty_snapshot():
    out = score_p4_maa_kataster(
        CLEAN, plans=[], parking={"tsoon": "C", "hooviala_osakaal": 0.2},
        enforcement=ENF_CLEAN, snapshot="2026-09-13")
    assert out == {"kinnistus_syva": 70, "naaber_planeering": 70,
                   "parkimine_hoov": 65, "enforcement": 70}


def test_aggregator_all_null_without_joins():
    out = score_p4_maa_kataster(None)
    assert out == {"kinnistus_syva": None, "naaber_planeering": None,
                   "parkimine_hoov": None, "enforcement": None}
    # plans=None means "no TPR snapshot", never "empty buffer".
    out2 = score_p4_maa_kataster(CLEAN)
    assert out2["naaber_planeering"] is None


def test_all_null_reasons_carry_honesty_markers():
    nulls = [dim_kinnistus_syva(None),
             dim_naaber_planeering(None, None),
             dim_parkimine_hoov(None, None),
             dim_enforcement(None, None)]
    for v, reason in nulls:
        assert v is None
        assert "hinnang" in reason and "EI OLE" in reason
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_cache_path_and_freshness(tmp_path):
    dest = cache_path(str(tmp_path), "kkis.json")
    assert dest.endswith("hf-p4-maa-kataster/kkis.json")
    assert is_fresh(dest, 30) is False  # missing file is never fresh
    dest_path = cache_path(str(tmp_path), "wfs.xml")
    import os
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with open(dest_path, "w") as fh:
        fh.write("<xml/>")
    assert is_fresh(dest_path, 30) is True
    assert is_fresh(dest_path, 0) in (True, False)  # boundary, no crash


def test_fetch_cached_cache_hit_never_touches_network(tmp_path):
    import os
    dest = cache_path(str(tmp_path), "hit.json")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as fh:
        fh.write("{}")
    assert fetch_cached("https://example.invalid/nope", str(tmp_path),
                        "hit.json", 30) == dest
