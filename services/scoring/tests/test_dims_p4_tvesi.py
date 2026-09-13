"""P4 tvesi demo + coverage dims (issues #263, #343): hermetic tests.

No network: fetch_tvesi_snapshot is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus fixture-fed parse
tests). Every dim is tested on fixture slices through the
zone/tariff-table join shape: joined slice -> bands, missing slice ->
NULL with Estonian honesty markers.
"""

import os

import dims_p4_tvesi as tvesi
from dims_p4_tvesi import (
    P4_TVESI_DIMS,
    TARIFF_CALM_EUR_M3,
    TARIFF_MID_EUR_M3,
    TVESI_TTL_S,
    ZEROFLOW_MIN_CONNECTIONS,
    cache_is_fresh,
    dim_stormwater_fee,
    dim_water_redundancy,
    dim_water_sewer_zone,
    dim_water_tariff,
    dim_zero_flow_hex,
    index_zones,
    parse_stormwater,
    parse_tariffs,
    parse_zeroflow,
    parse_zones,
    score_p4_tvesi,
)

# ---------------------------------------------------------------------------
# Fixtures: tvesi snapshot layouts (semicolon, BOM, sparse columns) plus
# canonical joined slices. The tariff row transcribes the live hinnakiri
# values verified 2026-09-13 (vesi 1,48 / kanal RG1 1,39 / RG2 2,78
# EUR/m3 KM-ga, kehtiv alates 01.07.2026, Konkurentsiamet 26.05.2026
# nr 9-3/2026-014). No personal data anywhere (AGENTS.md section 5 —
# fixtures only).
# ---------------------------------------------------------------------------

FIXTURE_TARIFFS = (
    "\ufeffpiirkond;vesi_eur_m3;kanal_rg1_eur_m3;kanal_rg2_eur_m3;"
    "kehtib_alates;otsus\n"
    "Tallinn ja Saue linn;1,48;1,39;2,78;2026-07-01;9-3/2026-014\n"
    "Testvald kõrge;2,50;3,10;;2026-01-01;\n"
)

FIXTURE_ZONES = (
    "\ufeffzone;vesi;kanal;liitumiskohustus\n"
    "kesklinn-central;CENTRAL;central;ei\n"
    "nõmme-puurkaev;puurkaev;omapuhasti;JAH\n"
    "pirita-sega;salvkaev;central;ei\n"
    "merivälja-poolik;central;;ei\n"
)

FIXTURE_ZEROFLOW = (
    "\ufeffhex_id;connections;zero_flow\n"
    "hex-dead;20;8\n"
    "hex-thin;12;2\n"
    "hex-calm;40;1\n"
)

FIXTURE_STORMWATER = (
    "\ufeffzone;sademeveetasu\n"
    "kesklinn-central;jah\n"
    "nõmme-puurkaev;EI\n"
)

TARIFFS = index_zones(parse_tariffs(FIXTURE_TARIFFS), key="piirkond")
ZONES = index_zones(parse_zones(FIXTURE_ZONES))
STORM = index_zones(parse_stormwater(FIXTURE_STORMWATER))

TALLINN_TARIFF = {"piirkond": "Tallinn ja Saue linn"}
CENTRAL_PARCEL = {"zone": "kesklinn-central"}
NOMME_PARCEL = {"zone": "nõmme-puurkaev"}
TALLINN_PARCEL = {"zone": "kesklinn-central",
                  "piirkond": "Tallinn ja Saue linn",
                  "city_water": True, "well": False}

EXPECTED_KEYS = ["water_sewer_zone", "water_tariff", "water_redundancy",
                 "zero_flow_hex", "stormwater_fee"]
EXPECTED_PNUMS = ["P4-017", "P4-008", "P4-046", "P4-051", "P4-060"]


# ---------------------------------------------------------------------------
# Ingestion: parse + join + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_tariffs_handles_bom_semicolons_and_comma_decimals():
    recs = parse_tariffs(FIXTURE_TARIFFS)
    assert len(recs) == 2
    tallinn = recs[0]
    assert tallinn["piirkond"] == "Tallinn ja Saue linn"
    assert tallinn["vesi_eur_m3"] == 1.48  # "1,48" comma form
    assert tallinn["kanal_rg1_eur_m3"] == 1.39
    assert tallinn["kanal_rg2_eur_m3"] == 2.78
    assert tallinn["kehtib_alates"] == "2026-07-01"
    assert tallinn["otsus"] == "9-3/2026-014"
    # Sparse row: empty cells become None, never guesses.
    assert recs[1]["kanal_rg2_eur_m3"] is None
    assert recs[1]["otsus"] is None


def test_parse_tariffs_skips_rows_without_join_key():
    recs = parse_tariffs("piirkond;vesi_eur_m3\n;1,48\nTallinn;1,48\n")
    assert [r["piirkond"] for r in recs] == ["Tallinn"]


def test_parse_tariffs_rejects_negative_and_garbage_rates():
    recs = parse_tariffs("piirkond;vesi_eur_m3;kanal_rg1_eur_m3\n"
                         "X;-1,00;hind\n")
    assert recs[0]["vesi_eur_m3"] is None
    assert recs[0]["kanal_rg1_eur_m3"] is None


def test_parse_zones_folds_case_and_estonian_booleans():
    recs = parse_zones(FIXTURE_ZONES)
    assert len(recs) == 4
    assert recs[0]["vesi"] == "central"  # CENTRAL folded
    assert recs[1]["liitumiskohustus"] is True  # JAH
    assert recs[0]["liitumiskohustus"] is False  # ei
    # Sparse row: missing kanal leg stays None.
    assert recs[3]["kanal"] is None


def test_parse_zones_never_guesses_unknown_tokens():
    recs = parse_zones("zone;vesi;kanal;liitumiskohustus\n"
                       "X;kosmos;tundmatu;ehk\n")
    assert recs[0]["vesi"] is None
    assert recs[0]["kanal"] is None
    assert recs[0]["liitumiskohustus"] is None


def test_parse_zones_skips_rows_without_join_key():
    recs = parse_zones("zone;vesi\n;central\nkesklinn;central\n")
    assert [r["zone"] for r in recs] == ["kesklinn"]


def test_parse_zeroflow_and_stormwater_layouts():
    zf = parse_zeroflow(FIXTURE_ZEROFLOW)
    assert [(r["hex_id"], r["connections"], r["zero_flow"]) for r in zf] == [
        ("hex-dead", 20, 8), ("hex-thin", 12, 2), ("hex-calm", 40, 1)]
    sw = parse_stormwater(FIXTURE_STORMWATER)
    assert [(r["zone"], r["sademeveetasu"]) for r in sw] == [
        ("kesklinn-central", True), ("nõmme-puurkaev", False)]
    assert parse_zeroflow("hex_id;connections\n;5\n") == []


def test_index_zones_groups_by_key():
    assert set(ZONES) == {"kesklinn-central", "nõmme-puurkaev",
                          "pirita-sega", "merivälja-poolik"}
    assert ZONES["nõmme-puurkaev"]["vesi"] == "puurkaev"
    assert set(TARIFFS) == {"Tallinn ja Saue linn", "Testvald kõrge"}


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert TVESI_TTL_S == 30 * 86400  # monthly poll per docs/p4_tvesi.md
    missing = os.path.join(str(tmp_path), "tvesi-x.csv")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "tvesi-x.csv"
    p.write_text("piirkond\nTallinn\n", encoding="utf-8")
    assert cache_is_fresh(str(p), ttl_s=TVESI_TTL_S) is True
    aged = 31 * 86400.0
    assert cache_is_fresh(str(p), ttl_s=TVESI_TTL_S,
                          now=os.path.getmtime(str(p)) + aged) is False


# ---------------------------------------------------------------------------
# NULL contracts: missing slice is always NULL with Estonian markers.
# ---------------------------------------------------------------------------

def test_all_dims_null_without_slices_and_carry_markers():
    cases = [
        (dim_water_sewer_zone, (None, None)),
        (dim_water_tariff, (None, None)),
        (dim_water_redundancy, (None,)),
        (dim_zero_flow_hex, (None,)),
        (dim_stormwater_fee, (None, None)),
    ]
    for fn, args in cases:
        v, reason = fn(*args)
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "hinnang" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__


def test_zone_dims_null_on_unknown_zone_and_name_check():
    v, reason = dim_water_sewer_zone({"zone": "tundmatu"}, ZONES)
    assert v is None
    assert "tsoonitabelis EI OLE" in reason and "iseteenindusest" in reason
    v, reason = dim_stormwater_fee({"zone": "tundmatu"}, STORM)
    assert v is None
    assert "sademevee-tabelis EI OLE" in reason


def test_tariff_dim_null_on_unknown_piirkond():
    v, reason = dim_water_tariff({"piirkond": "Tundmatu"}, TARIFFS)
    assert v is None
    assert "hinnakirja tabelis EI OLE" in reason


def test_half_truth_legs_stay_null():
    v, reason = dim_water_sewer_zone({"zone": "merivälja-poolik"}, ZONES)
    assert v is None and "poolik" in reason
    thin_tariffs = dict(TARIFFS)
    thin_tariffs["poolik"] = {"piirkond": "poolik", "vesi_eur_m3": 1.48,
                              "kanal_rg1_eur_m3": None}
    v, reason = dim_water_tariff({"piirkond": "poolik"}, thin_tariffs)
    assert v is None and "poolik" in reason


def test_unknown_tokens_stay_null():
    v, _ = dim_water_sewer_zone({"zone": "kesklinn-central",
                                 "kvaliteet": "kosmos"}, ZONES)
    assert v is None
    v, _ = dim_water_redundancy({"city_water": "jah", "well": False})
    assert v is None
    v, _ = dim_zero_flow_hex({"hex_id": "x", "connections": 10,
                              "zero_flow": 11})
    assert v is None
    v, _ = dim_stormwater_fee(
        {"zone": "kesklinn-central"},
        {"kesklinn-central": {"sademeveetasu": "ehk"}})
    assert v is None


def test_thin_zeroflow_cell_stays_null_for_privacy():
    assert ZEROFLOW_MIN_CONNECTIONS == 5
    v, reason = dim_zero_flow_hex({"hex_id": "thin", "connections": 4,
                                   "zero_flow": 4})
    assert v is None
    assert "õhuke" in reason


def test_dims_accept_missing_sides_without_crash():
    assert dim_water_sewer_zone(None, None)[0] is None
    assert dim_water_tariff("tallinn", None)[0] is None
    assert dim_water_redundancy("parcel")[0] is None
    assert dim_zero_flow_hex([])[0] is None
    assert dim_stormwater_fee({}, {})[0] is None


# ---------------------------------------------------------------------------
# Demo P4-017 bands (tvesi zone join).
# ---------------------------------------------------------------------------

def test_zone_central_central_is_calm():
    v, reason = dim_water_sewer_zone(CENTRAL_PARCEL, ZONES)
    assert v == 85
    assert "tsentraalne vesi + kanal" in reason
    assert "tsoonitabel" in reason


def test_zone_well_and_onsite_pull_down():
    v, reason = dim_water_sewer_zone(NOMME_PARCEL, ZONES)
    assert v == 40  # 45 base capped by liitumiskohustus
    assert "liitumiskohustus" in reason and "5-kohaline arve" in reason
    v, reason = dim_water_sewer_zone({"zone": "pirita-sega"}, ZONES)
    assert v == 55  # salvkaev + central, no duty
    assert "oma vee risk" in reason
    assert "ametlikke andmeid EI OLE" in reason  # kvaliteet unknown


def test_zone_bad_quality_caps_and_duty_only_caps_unconnected():
    v, reason = dim_water_sewer_zone(
        {"zone": "kesklinn-central", "kvaliteet": "halb"}, ZONES)
    assert v == 35
    assert "kvaliteet halb" in reason


# ---------------------------------------------------------------------------
# Coverage P4-008 bands (live-hinnakiri calibrated).
# ---------------------------------------------------------------------------

def test_tariff_tallinn_level_is_calm_and_names_heat_gap():
    v, reason = dim_water_tariff(TALLINN_TARIFF, TARIFFS)
    assert v == 75  # RG1 combined 2,87 <= 3,50
    assert "2.87" in reason and "Tallinna tase" in reason
    assert "kaugkütte-jalga" in reason and "EI OLE" in reason


def test_tariff_mid_and_high_bands():
    v, reason = dim_water_tariff({"piirkond": "Testvald kõrge"}, TARIFFS)
    assert v == 35  # 2,50 + 3,10 = 5,60 > 5,00
    assert "5.60" in reason
    mid = dict(TARIFFS["Tallinn ja Saue linn"])
    mid["kanal_rg1_eur_m3"] = 3.00  # combined 4,48
    v, reason = dim_water_tariff(
        TALLINN_TARIFF, {"Tallinn ja Saue linn": mid})
    assert v == 55


def test_tariff_band_thresholds_are_live_calibrated():
    assert TARIFF_CALM_EUR_M3 == 3.50  # above live RG1 2,87
    assert TARIFF_MID_EUR_M3 == 5.00  # above live RG2 4,26


# ---------------------------------------------------------------------------
# Coverage P4-046 bands (water-redundancy slice only).
# ---------------------------------------------------------------------------

def test_redundancy_both_feeds_is_calmest():
    v, reason = dim_water_redundancy({"city_water": True, "well": True})
    assert v == 80
    assert "Linnavesi + kaev" in reason
    assert "EHR/flood-moodulid" in reason


def test_redundancy_single_and_missing_feeds():
    assert dim_water_redundancy(
        {"city_water": True, "well": False})[0] == 60
    assert dim_water_redundancy(
        {"city_water": False, "well": True})[0] == 40
    v, reason = dim_water_redundancy(
        {"city_water": False, "well": False})
    assert v == 25
    assert "hätta" in reason


# ---------------------------------------------------------------------------
# Coverage P4-051 bands (hex aggregate, never addresses).
# ---------------------------------------------------------------------------

def test_zeroflow_dead_hex_flags_and_calm_hex_caps():
    v, reason = dim_zero_flow_hex({"hex_id": "hex-dead", "connections": 20,
                                   "zero_flow": 8})
    assert v == 25  # 40% share
    assert "surnud trepikoja risk" in reason
    assert "Elektrilevi" in reason and "EI OLE" in reason
    v, reason = dim_zero_flow_hex({"hex_id": "hex-thin", "connections": 12,
                                   "zero_flow": 2})
    assert v == 45  # ~17% share
    assert "KÜ aruannet" in reason
    v, reason = dim_zero_flow_hex({"hex_id": "hex-calm", "connections": 40,
                                   "zero_flow": 1})
    assert v == 70
    assert "ülempiir 70" in reason


# ---------------------------------------------------------------------------
# Coverage P4-060 bands (stormwater zone table).
# ---------------------------------------------------------------------------

def test_stormwater_fee_zone_bills_and_free_zone_caps():
    v, reason = dim_stormwater_fee(CENTRAL_PARCEL, STORM)
    assert v == 45
    assert "sademeveetasu kehtib" in reason
    assert "EIS" in reason and "EI OLE" in reason
    v, reason = dim_stormwater_fee(NOMME_PARCEL, STORM)
    assert v == 70
    assert "ülempiir 70" in reason


# ---------------------------------------------------------------------------
# Registry + aggregator cover all five.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_all_five():
    assert [k for k, _, _ in P4_TVESI_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_TVESI_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_TVESI_DIMS}) == 5
    assert tvesi.P4_TVESI_DIMS is P4_TVESI_DIMS
    out = score_p4_tvesi(TALLINN_PARCEL, ZONES, TARIFFS,
                         {"hex_id": "hex-calm", "connections": 40,
                          "zero_flow": 1},
                         STORM)
    assert out == {"water_sewer_zone": 85, "water_tariff": 75,
                   "water_redundancy": 60, "zero_flow_hex": 70,
                   "stormwater_fee": 45}
    empty = score_p4_tvesi(None, None, None, None, None)
    assert empty == {k: None for k in EXPECTED_KEYS}


def test_scores_never_zero_or_hundred():
    out = score_p4_tvesi(TALLINN_PARCEL, ZONES, TARIFFS,
                         {"hex_id": "hex-dead", "connections": 20,
                          "zero_flow": 8},
                         STORM)
    for v in out.values():
        assert v is None or (0 < v < 100)
