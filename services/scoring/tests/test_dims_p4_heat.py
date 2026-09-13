"""P4 heat demo + coverage dims (issues #261, #342): hermetic tests.

No network: fetch_heat_csv is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus fixture-fed parse
tests). Every dim is tested on fixture zone records through the
per-address join shape: joined record -> bands, missing record ->
NULL with Estonian honesty markers.
"""

import os

import dims_p4_heat as heat
from dims_p4_heat import (
    HEAT_TTL_S,
    P4_HEAT_DIMS,
    cache_is_fresh,
    dim_heating_tariff,
    dim_roof_bonus,
    index_by_zone,
    parse_heat_zones,
    score_p4_heat,
)

# ---------------------------------------------------------------------------
# Fixtures: heat tariff-zone snapshot layout (semicolon, BOM, sparse
# columns, comma decimals) plus canonical joined zone records.
# zone_key doubles as the per-address join key. No personal data
# anywhere (AGENTS.md section 5 — zone-level tariffs, fixtures only).
# ---------------------------------------------------------------------------

FIXTURE_CSV = (
    "\ufeffzone_key;operator;tariff_zone;tariff_eur_mwh;tariff_status;"
    "water_zone;return_bonus;updated\n"
    "tallinn-kesklinn;UTILITAS;Tallinn kesklinn;123,45;KEHTIV;"
    "tallinna-vesi-tsoon-1;jah;2026-08-01\n"
    "lasnamae-katlamaja;adven;Lasnamäe katlamaja;;kooskõlastamisel;;ei;\n"
    "nomme-muu;kinnistu-väline;Nõmme;;;tallinna-vesi-tsoon-3;;\n"
)

KEHTIV_ZONE = {
    "zone_key": "tallinn-kesklinn", "operator": "utilitas",
    "tariff_zone": "Tallinn kesklinn", "tariff_eur_mwh": 123.45,
    "tariff_status": "kehtiv", "water_zone": "tallinna-vesi-tsoon-1",
    "return_bonus": True, "updated": "2026-08-01",
}

PENDING_ZONE = {
    "zone_key": "lasnamae-katlamaja", "operator": "adven",
    "tariff_zone": "Lasnamäe katlamaja", "tariff_eur_mwh": None,
    "tariff_status": "kooskõlastamisel", "water_zone": None,
    "return_bonus": False, "updated": None,
}

ALL_FNS = [fn for _, _, fn in P4_HEAT_DIMS]

EXPECTED_KEYS = ["heating_tariff", "roof_bonus"]
EXPECTED_PNUMS = ["P4-008", "P4-036"]


# ---------------------------------------------------------------------------
# Ingestion: parse + join + cache-freshness (hermetic, fixture-fed).
# ---------------------------------------------------------------------------

def test_parse_handles_bom_semicolons_case_and_comma_decimals():
    recs = parse_heat_zones(FIXTURE_CSV)
    assert len(recs) == 3
    first = recs[0]
    assert first["zone_key"] == "tallinn-kesklinn"
    assert first["operator"] == "utilitas"  # UTILITAS folded
    assert first["tariff_eur_mwh"] == 123.45  # comma decimal parsed
    assert first["tariff_status"] == "kehtiv"  # KEHTIV folded
    assert first["water_zone"] == "tallinna-vesi-tsoon-1"
    assert first["return_bonus"] is True
    # Sparse row: empty cells become None, never guesses.
    assert recs[1]["tariff_eur_mwh"] is None
    assert recs[1]["return_bonus"] is False
    assert recs[1]["updated"] is None


def test_parse_skips_rows_without_join_key():
    csv_text = ("zone_key;operator;tariff_eur_mwh\n"
                ";utilitas;100\n"
                "tallinn-kesklinn;utilitas;100\n")
    recs = parse_heat_zones(csv_text)
    assert [r["zone_key"] for r in recs] == ["tallinn-kesklinn"]


def test_parse_never_guesses_unknown_tokens_or_tariffs():
    csv_text = ("zone_key;operator;tariff_eur_mwh;tariff_status;"
                "return_bonus\n"
                "X;kosmos;tasuta;ootel;võib-olla\n")
    recs = parse_heat_zones(csv_text)
    assert recs[0]["operator"] is None
    assert recs[0]["tariff_eur_mwh"] is None  # "tasuta" is not zero heat
    assert recs[0]["tariff_status"] is None
    assert recs[0]["return_bonus"] is None


def test_parse_dot_decimals_and_bonus_no_forms():
    csv_text = ("zone_key;tariff_eur_mwh;return_bonus\n"
                "A;99.5;ei\n"
                "B;10;pole\n")
    recs = parse_heat_zones(csv_text)
    assert recs[0]["tariff_eur_mwh"] == 99.5
    assert recs[0]["return_bonus"] is False
    assert recs[1]["return_bonus"] is False


def test_index_by_zone_keeps_first_row_per_key():
    recs = parse_heat_zones(FIXTURE_CSV)
    index = index_by_zone(recs)
    assert set(index) == {"tallinn-kesklinn", "lasnamae-katlamaja",
                          "nomme-muu"}
    assert index["tallinn-kesklinn"]["tariff_eur_mwh"] == 123.45
    doubled = index_by_zone(recs + [dict(recs[0], tariff_eur_mwh=1.0)])
    assert doubled["tallinn-kesklinn"]["tariff_eur_mwh"] == 123.45


def test_cache_freshness_is_pure_and_ttlstated(tmp_path):
    assert HEAT_TTL_S == 30 * 86400  # monthly pull per docs/p4_heat.md
    missing = os.path.join(str(tmp_path), "heat-x.csv")
    assert cache_is_fresh(missing) is False
    p = tmp_path / "heat-x.csv"
    p.write_text("zone_key\n1\n", encoding="utf-8")
    assert cache_is_fresh(str(p), ttl_s=HEAT_TTL_S) is True
    aged = 31 * 86400.0
    assert cache_is_fresh(str(p), ttl_s=HEAT_TTL_S,
                          now=os.path.getmtime(str(p)) + aged) is False


# ---------------------------------------------------------------------------
# NULL contracts: missing slice is always NULL with Estonian markers.
# ---------------------------------------------------------------------------

def test_both_dims_null_without_zone_and_name_checks():
    for fn in ALL_FNS:
        v, reason = fn(None)
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_missing_zone_points_at_ku_and_konkurentsiamet():
    _, reason = dim_heating_tariff(None)
    assert "KÜ" in reason and "Konkurentsiamet" in reason
    _, reason = dim_roof_bonus(None)
    assert "EI OLE" in reason and "KÜ" in reason


def test_both_dims_accept_missing_listing_side():
    for fn in ALL_FNS:
        for zone in (KEHTIV_ZONE, PENDING_ZONE, {}):
            v, reason = fn(zone)  # listing=None must never crash
            assert isinstance(reason, str) and reason, fn.__name__
            assert v is None or isinstance(v, int)


def test_non_dict_input_is_null_not_crash():
    for fn in ALL_FNS:
        v, reason = fn("utilitas")  # type: ignore[arg-type]
        assert v is None, fn.__name__
        assert "EI OLE" in reason, fn.__name__


def test_joined_but_empty_record_is_null_not_scored():
    v, reason = dim_heating_tariff({"zone_key": "X"})
    assert v is None
    assert "tühi" in reason and "EI OLE" in reason


# ---------------------------------------------------------------------------
# Demo P4-008 bands (predictability, never cheapness).
# ---------------------------------------------------------------------------

def test_tariff_known_zone_scores_predictability_capped():
    v, reason = dim_heating_tariff(KEHTIV_ZONE)
    assert v == 60
    assert "utilitas" in reason and "123.45" in reason
    assert "registriandmed" in reason and "mitte hinnang" in reason
    assert "ülempiir 60" in reason
    assert "KÜ aruannet" in reason


def test_operator_known_tariff_pending_scores_weak_signal():
    v, reason = dim_heating_tariff(PENDING_ZONE)
    assert v == 45
    assert "adven" in reason
    assert "kooskõlastamisel" in reason
    assert "ülempiir 45" in reason


def test_tariff_without_kehtiv_status_stays_weak():
    zone = dict(KEHTIV_ZONE, tariff_status="kooskõlastamisel")
    v, reason = dim_heating_tariff(zone)
    assert v == 45 and "ülempiir 45" in reason


def test_never_zero_never_hundred():
    for zone in (KEHTIV_ZONE, PENDING_ZONE, {"zone_key": "X"}):
        v, _ = dim_heating_tariff(zone)
        assert v != 0 and v != 100


# ---------------------------------------------------------------------------
# Coverage P4-036 bands (bonus slice only, upside capped).
# ---------------------------------------------------------------------------

def test_bonus_applicable_scores_upside_kicker():
    v, reason = dim_roof_bonus(KEHTIV_ZONE)
    assert v == 65
    assert "boonus" in reason
    assert "registriandmed" in reason and "mitte hinnang" in reason
    assert "ülempiir 65" in reason
    assert "päikese/masti/reklaami" in reason and "liitmata" in reason


def test_bonus_absent_or_unknown_is_null_with_unjoined_legs():
    for zone in (PENDING_ZONE, {"zone_key": "X"}):
        v, reason = dim_roof_bonus(zone)
        assert v is None, zone["zone_key"]
        assert "EI OLE" in reason
        assert "LiDAR" in reason and "EHR" in reason


def test_roof_bonus_never_hundred():
    v, _ = dim_roof_bonus(KEHTIV_ZONE)
    assert v != 100


# ---------------------------------------------------------------------------
# Registry + aggregator.
# ---------------------------------------------------------------------------

def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_HEAT_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_HEAT_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_HEAT_DIMS}) == 2
    out = score_p4_heat(KEHTIV_ZONE)
    assert out == {"heating_tariff": 60, "roof_bonus": 65}
    out = score_p4_heat(PENDING_ZONE)
    assert out == {"heating_tariff": 45, "roof_bonus": None}
    assert score_p4_heat(None) == {"heating_tariff": None,
                                   "roof_bonus": None}
    assert heat.P4_HEAT_DIMS is P4_HEAT_DIMS
