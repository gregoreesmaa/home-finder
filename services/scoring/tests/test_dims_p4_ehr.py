"""P4 EHR / E-ehitus demo + coverage dims (issues #249, #333): hermetic tests.

No network: fetch_ehr_csv is never called here (its contract — single
polite GET, file cache, TTL, transport errors raise — is covered via
the pure cache_is_fresh helper plus fixture-fed parse tests). Every
dim is tested on fixture EHR records through the per-ehr_code join
shape: joined record -> bands, missing record/slice -> NULL with
Estonian honesty markers.
"""

import os

import dims_p4_ehr as ehr
from dims_p4_ehr import (
    EHR_TTL_DAYS,
    P4_EHR_DIMS,
    cache_is_fresh,
    dim_backyard_weather,
    dim_change_flag,
    dim_courtyard_trap,
    dim_darkness,
    dim_developer_record,
    dim_dread_redundancy,
    dim_falling_ice,
    dim_geology,
    dim_glimpse,
    dim_heatpump_hum,
    dim_noise_zone,
    dim_number_thirteen,
    dim_overheating,
    dim_parking_ehr,
    dim_permit_bankable,
    dim_permit_glut,
    dim_renovation_grant,
    dim_roof_income,
    dim_small_delights,
    dim_turnover_wave,
    dim_woodburn_zone,
    index_by_ehr_code,
    parse_ehr_buildings,
    score_p4_ehr,
)

# ---------------------------------------------------------------------------
# Fixtures: EHR CSV-report layout (semicolon, BOM, sparse columns) plus
# canonical joined records.
# ---------------------------------------------------------------------------

FIXTURE_CSV = (
    "\ufeffehr_code;address;kov;floors_total;energy_class;"
    "has_ehitusluba;has_kasutusluba;permits_open;permits_finalized;"
    "heating_type;has_fireplace;roof_type;builder;renovation_grant_status;"
    "grant_queue_pos;parking_spaces;cooling_type;renovation_permits\n"
    "101012345;Tallinn, Pärnu mnt 1;Tallinn;5;C;jah;jah;0;4;"
    "kaugküte;jah;lame;OÜ Ehitaja;eraldatud;;12;puudub;1\n"
    "101067890;Tallinn, Kalamaja 13;Tallinn;2;E;jah;ei;2;1;"
    "ahi;ei;viilkatus;;;;0;;0\n"
)

FULL_EHR = {
    "ehr_code": "101012345",
    "floors_total": 5,
    "energy_class": "C",
    "has_ehitusluba": True,
    "has_kasutusluba": True,
    "permits_open": 0,
    "permits_finalized": 4,
    "renovation_permits": 1,
    "heating_type": "kaugküte",
    "has_fireplace": True,
    "water_supply": "tsentraalne",
    "roof_type": "lame",
    "builder": "OÜ Ehitaja",
    "renovation_grant_status": "eraldatud",
    "grant_queue_pos": None,
    "parking_spaces": 12,
    "cooling_type": "puudub",
}

STOVE_EHR = {
    "ehr_code": "101067890",
    "floors_total": 2,
    "energy_class": "E",
    "has_ehitusluba": True,
    "has_kasutusluba": False,
    "permits_open": 2,
    "permits_finalized": 1,
    "renovation_permits": 0,
    "heating_type": "ahi",
    "has_fireplace": False,
    "roof_type": "viilkatus",
    "builder": None,
    "developer": None,
    "renovation_grant_status": "puudub",
    "parking_spaces": 0,
    "cooling_type": None,
}

PUMP_EHR = dict(FULL_EHR, heating_type="õhksoojuspump",
                has_fireplace=False)

ALL_FNS = [fn for _, _, fn in P4_EHR_DIMS]

EXPECTED_KEYS = [
    "permit_bankable", "renovation_grant", "parking_ehr", "geology",
    "developer_record", "noise_zone", "change_flag", "backyard_weather",
    "overheating", "darkness", "roof_income", "glimpse",
    "number_thirteen", "dread_redundancy", "small_delights",
    "permit_glut", "turnover_wave", "courtyard_trap", "heatpump_hum",
    "falling_ice", "woodburn_zone",
]

EXPECTED_PNUMS = [
    "P4-005", "P4-010", "P4-013", "P4-016", "P4-021", "P4-023",
    "P4-030", "P4-031", "P4-034", "P4-035", "P4-036", "P4-041",
    "P4-043", "P4-046", "P4-048", "P4-050", "P4-052", "P4-056",
    "P4-057", "P4-058", "P4-059",
]


# ---------------------------------------------------------------------------
# Ingestion: parse + join + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_handles_bom_semicolons_and_sparse_rows():
    recs = parse_ehr_buildings(FIXTURE_CSV)
    assert len(recs) == 2
    first, second = recs
    assert first["ehr_code"] == "101012345"
    assert first["floors_total"] == 5
    assert first["has_kasutusluba"] is True
    assert first["parking_spaces"] == 12
    assert first["renovation_grant_status"] == "eraldatud"
    # Sparse row: empty cells become None, never guesses.
    assert second["builder"] is None
    assert second["renovation_grant_status"] is None
    assert second["has_kasutusluba"] is False
    assert second["parking_spaces"] == 0


def test_parse_skips_rows_without_join_key():
    csv_text = ("ehr_code;floors_total\n"
                ";5\n"
                "101099999;3\n")
    recs = parse_ehr_buildings(csv_text)
    assert [r["ehr_code"] for r in recs] == ["101099999"]


def test_parse_bool_and_int_tolerance():
    csv_text = ("ehr_code;has_ehitusluba;has_kasutusluba;permits_open\n"
                "1;JAH;ei; 2 \n"
                "2;1;0;abc\n")
    recs = parse_ehr_buildings(csv_text)
    assert recs[0]["has_ehitusluba"] is True
    assert recs[0]["has_kasutusluba"] is False
    assert recs[0]["permits_open"] == 2
    assert recs[1]["permits_open"] is None  # "abc" never guessed


def test_index_by_ehr_code_first_row_wins():
    recs = parse_ehr_buildings(FIXTURE_CSV)
    index = index_by_ehr_code(recs + [dict(recs[0], floors_total=9)])
    assert index["101012345"]["floors_total"] == 5
    assert index["101067890"]["roof_type"] == "viilkatus"


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert EHR_TTL_DAYS == 7  # weekly bulk per parameters4.md P4-005
    missing = os.path.join(str(tmp_path), "ehr-x.csv")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "ehr-x.csv"
    p.write_text("ehr_code\n1\n", encoding="utf-8")
    assert cache_is_fresh(str(p), ttl_days=7) is True
    aged = 8 * 86400.0
    assert cache_is_fresh(str(p), ttl_days=7,
                          now=os.path.getmtime(str(p)) + aged) is False


# ---------------------------------------------------------------------------
# NULL contracts: missing record is always NULL with Estonian markers.
# ---------------------------------------------------------------------------

def test_all_dims_null_without_record_and_name_ehr():
    for fn in ALL_FNS:
        v, reason = fn(None)
        assert v is None, fn.__name__
        assert "EHR" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_all_dims_accept_missing_listing_side():
    for fn in ALL_FNS:
        v, reason = fn(FULL_EHR)  # listing=None must never crash
        assert isinstance(reason, str) and reason, fn.__name__
        assert v is None or isinstance(v, int)


def test_scored_reasons_trace_to_ehr_not_estimates():
    scored = [
        (dim_permit_bankable, FULL_EHR, None),
        (dim_renovation_grant, FULL_EHR, None),
        (dim_parking_ehr, FULL_EHR, None),
        (dim_developer_record, FULL_EHR, None),
        (dim_roof_income, FULL_EHR, None),
        (dim_dread_redundancy, FULL_EHR, None),
        (dim_falling_ice, FULL_EHR, None),
        (dim_woodburn_zone, FULL_EHR, None),
    ]
    for fn, rec, listing in scored:
        v, reason = fn(rec, listing)
        assert isinstance(v, int), fn.__name__
        assert 0 <= v <= 100, fn.__name__
        assert "EHR" in reason, fn.__name__


def test_model_dims_label_hinnang_and_not_measured():
    model_cases = [
        (dim_overheating, FULL_EHR, {"floor": 5, "orientation": "lõuna"}),
        (dim_darkness, FULL_EHR, {"floor": 0, "orientation": "põhi"}),
        (dim_roof_income, FULL_EHR, None),
        (dim_glimpse, FULL_EHR, {"floor": 5}),
        (dim_heatpump_hum, PUMP_EHR, None),
        (dim_falling_ice, STOVE_EHR, None),
        (dim_small_delights, FULL_EHR, {"orientation": "ida"}),
    ]
    for fn, rec, listing in model_cases:
        v, reason = fn(rec, listing)
        assert isinstance(v, int), fn.__name__
        assert "hinnang" in reason, fn.__name__
        assert "mitte mõõdetud" in reason, fn.__name__


# ---------------------------------------------------------------------------
# Demo P4-005 bands.
# ---------------------------------------------------------------------------

def test_permit_bankable_bands():
    v, _ = dim_permit_bankable(FULL_EHR)
    assert v == 100
    v, reason = dim_permit_bankable(STOVE_EHR)  # ehitusluba, no kasutusluba
    assert v == 50
    assert "pooleli" in reason or "täiendavalt" in reason
    v, _ = dim_permit_bankable(dict(FULL_EHR, has_kasutusluba=False,
                                    has_ehitusluba=False))
    assert v == 20
    v, reason = dim_permit_bankable({"ehr_code": "x"})  # old stock, no keys
    assert v is None
    assert "EI OLE" in reason


# ---------------------------------------------------------------------------
# Coverage params: bands + NULL slices.
# ---------------------------------------------------------------------------

def test_renovation_grant_bands_and_queue_echo():
    v, _ = dim_renovation_grant(FULL_EHR)
    assert v == 85
    v, reason = dim_renovation_grant(
        dict(FULL_EHR, renovation_grant_status="järjekorras",
             grant_queue_pos=14))
    assert v == 60
    assert "14" in reason
    v, _ = dim_renovation_grant(STOVE_EHR)
    assert v == 35
    v, reason = dim_renovation_grant({"ehr_code": "x"})
    assert v is None and "EIS" in reason
    v, reason = dim_renovation_grant(
        dict(FULL_EHR, renovation_grant_status="kosmos"))
    assert v is None and "Tundmatu" in reason


def test_parking_ehr_slice():
    v, reason = dim_parking_ehr(FULL_EHR)
    assert v == 75 and "12" in reason
    v, _ = dim_parking_ehr(STOVE_EHR)
    assert v == 30
    v, reason = dim_parking_ehr({"ehr_code": "x"})
    assert v is None and "parkimiskorraldus" in reason


def test_pure_null_params_name_primary_source():
    v, reason = dim_geology(FULL_EHR)
    assert v is None and "EGT" in reason
    v, reason = dim_noise_zone(FULL_EHR)
    assert v is None and "EANS" in reason
    v, reason = dim_courtyard_trap(FULL_EHR)
    assert v is None and "LiDAR" in reason


def test_join_only_params_echo_ehr_fact_but_stay_null():
    v, reason = dim_change_flag(
        dict(FULL_EHR, permits_open=2))
    assert v is None and "2 avatud luba" in reason
    v, reason = dim_backyard_weather(FULL_EHR)
    assert v is None and "kaugküte" in reason
    v, reason = dim_permit_glut(FULL_EHR)
    assert v is None and "0 avatud / 4 l" in reason
    v, reason = dim_turnover_wave(FULL_EHR)
    assert v is None and "probleem vs gentrifikatsioon" in reason


def test_developer_record_caps_at_80_without_ttja():
    v, reason = dim_developer_record(FULL_EHR)
    assert v == 80
    assert "TTJA" in reason
    v, _ = dim_developer_record(
        dict(FULL_EHR, permits_open=2, permits_finalized=2))
    assert v == 50
    v, reason = dim_developer_record(STOVE_EHR)  # no builder named
    assert v is None and "EI OLE" in reason


def test_overheating_physics_bands():
    ehr_rec = dict(FULL_EHR, floors_total=5, cooling_type=None)
    v, _ = dim_overheating(ehr_rec, {"floor": 5, "orientation": "lõuna"})
    assert v == 30
    v, _ = dim_overheating(ehr_rec, {"floor": 5, "orientation": "ida"})
    assert v == 55
    v, _ = dim_overheating(ehr_rec, {"floor": 1, "orientation": "põhi"})
    assert v == 70
    v, _ = dim_overheating(
        dict(ehr_rec, cooling_type="konditsioneer"),
        {"floor": 5, "orientation": "lõuna"})
    assert v == 80
    v, reason = dim_overheating(ehr_rec, {"floor": 5})
    assert v is None and "EI OLE" in reason


def test_darkness_light_bands():
    v, _ = dim_darkness(FULL_EHR, {"floor": 0, "orientation": "põhi"})
    assert v == 35
    v, _ = dim_darkness(FULL_EHR, {"floor": 4, "orientation": "lõuna"})
    assert v == 80
    v, _ = dim_darkness(FULL_EHR, {"floor": 2, "orientation": "ida"})
    assert v == 60
    v, reason = dim_darkness(FULL_EHR, None)
    assert v is None and "EI OLE" in reason


def test_roof_income_upside_floor_50():
    v, _ = dim_roof_income(FULL_EHR)
    assert v == 70
    v, _ = dim_roof_income(STOVE_EHR)
    assert v == 55
    v, _ = dim_roof_income(dict(FULL_EHR, roof_type="rohekatus"))
    assert v == 50
    v, reason = dim_roof_income({"ehr_code": "x"})
    assert v is None and "Eleringi" in reason


def test_glimpse_caps_at_70_never_vaade():
    v, reason = dim_glimpse(FULL_EHR, {"floor": 5})
    assert v == 70
    assert "piilukas" in reason and "mitte mõõdetud" in reason
    assert "vaade" not in reason.replace("mõõdetud vaade", "")
    v, reason = dim_glimpse(FULL_EHR, {"floor": 1})
    assert v is None and "EI OLE" in reason
    v, reason = dim_glimpse(STOVE_EHR, {"floor": 2})  # total < 3
    assert v is None


def test_number_thirteen_flag_only():
    v, reason = dim_number_thirteen(
        FULL_EHR, {"floor": 13, "house_number": "8"})
    assert v == 65
    assert "maitsesobivale" in reason
    v, reason = dim_number_thirteen(
        FULL_EHR, {"floor": 5, "house_number": "13"})
    assert v == 65
    v, reason = dim_number_thirteen(FULL_EHR, {"floor": 5})
    assert v is None and "EI OLE" in reason
    v, reason = dim_number_thirteen(
        dict(FULL_EHR, floors_total=5), {"floor": 13})
    assert v == 65 and "kontrolli" in reason  # EHR cross-check mismatch


def test_dread_redundancy_bands():
    v, _ = dim_dread_redundancy(FULL_EHR)  # kamin + kaugküte
    assert v == 85
    v, _ = dim_dread_redundancy(dict(FULL_EHR, has_fireplace=False))
    assert v == 65
    v, _ = dim_dread_redundancy(
        dict(STOVE_EHR, has_fireplace=True))  # ahi + tahkeküte
    assert v == 75
    v, _ = dim_dread_redundancy(STOVE_EHR)  # stove heat, no fireplace
    assert v == 55
    v, reason = dim_dread_redundancy({"ehr_code": "x"})
    assert v is None and "EI OLE" in reason


def test_small_delights_breakfast_sun_only():
    v, _ = dim_small_delights(FULL_EHR, {"orientation": "ida"})
    assert v == 70
    v, reason = dim_small_delights(FULL_EHR, {"orientation": "lääs"})
    assert v is None and "EI OLE" in reason
    v, reason = dim_small_delights(FULL_EHR, None)
    assert v is None and "järjekorrad" in reason


def test_heatpump_hum_weak_only_for_pumps():
    v, reason = dim_heatpump_hum(PUMP_EHR)
    assert v == 55
    assert "naabrite" in reason
    v, reason = dim_heatpump_hum(FULL_EHR)
    assert v is None and "EI OLE" in reason
    v, reason = dim_heatpump_hum({"ehr_code": "x"})
    assert v is None


def test_falling_ice_bands_and_cliff_pointer():
    v, reason = dim_falling_ice(STOVE_EHR)
    assert v == 45
    assert "talihoolduse" in reason
    v, _ = dim_falling_ice(FULL_EHR)
    assert v == 75
    v, reason = dim_falling_ice({"ehr_code": "x"})
    assert v is None and "Maa-amet" in reason


def test_woodburn_zone_rule_join():
    v, _ = dim_woodburn_zone(
        dict(STOVE_EHR, heating_type="ahi"))
    assert v == 40
    v, _ = dim_woodburn_zone(FULL_EHR)
    assert v == 80
    v, _ = dim_woodburn_zone(PUMP_EHR)
    assert v == 80
    v, reason = dim_woodburn_zone({"ehr_code": "x"})
    assert v is None and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Registry + aggregator cover all 21.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_all_21():
    assert [k for k, _, _ in P4_EHR_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_EHR_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_EHR_DIMS}) == 21
    out = score_p4_ehr(FULL_EHR, {"floor": 5, "orientation": "lõuna",
                                  "house_number": "1"})
    assert set(out) == set(EXPECTED_KEYS)
    assert out["permit_bankable"] == 100
    assert out["geology"] is None
    assert out["noise_zone"] is None
    assert out["courtyard_trap"] is None
    assert score_p4_ehr(None) == {k: None for k in EXPECTED_KEYS}
    assert ehr.P4_EHR_DIMS is P4_EHR_DIMS
