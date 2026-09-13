"""P4 Maa-aerial dims (issues #246 demo + #330 coverage): hermetic tests.

No network: every fixture is a synthetic in-memory listing/aerial record
(plain dicts — no scraped data). fetch_cached is covered only on its
cache-hit path plus transport-error-raises; freshness/expiry uses
tmp_path. The live probes are manual DoD evidence (pasted in the PR +
docs/p4_maa_aerial.md), not unit runs.
"""

import os
import time
import urllib.error

import dims_p4_maa_aerial as p4
from dims_p4_maa_aerial import (
    P4_MAA_AERIAL_DIMS,
    TTL_DAYS,
    cache_path,
    dim_courtyard_trap,
    dim_glimpse_economics,
    dim_heatpump_hum,
    dim_ice_cliff,
    dim_photo_forensics,
    dim_satellite_change_delta,
    dim_stormwater_subsidy,
    dim_street_block_observer,
    is_fresh,
    parse_wms_layer_names,
    score_p4_maa_aerial,
)

TODAY = "2026-09-13"
ZONES = {"lahkvool": 120.0, "uhisvool": 0.0, "kompensatsioon": 30.0,
         "korge": 400.0}

ALL_FNS = [fn for _, _, fn in P4_MAA_AERIAL_DIMS]
EXPECTED_KEYS = ["photo_forensics", "street_observer", "change_delta",
                 "glimpse", "courtyard_trap", "heatpump_hum",
                 "ice_cliff", "stormwater"]
EXPECTED_PNUMS = ["P4-022", "P4-029", "P4-030", "P4-041", "P4-056",
                  "P4-057", "P4-058", "P4-060"]


def listing(**kw):
    base = {"address": "Tartu mnt 25-12, Tallinn", "floor": 4,
            "exif_daylight_ok": True, "photo_room_count": 3,
            "ehr_room_count": 3}
    base.update(kw)
    return base


def aerial(**kw):
    base = {"ortho_vintage": "2024", "duplicate_hashes": 0,
            "facade_change": False}
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Ingestion helpers: cache path, freshness, polite fetch, caps parsing.
# ---------------------------------------------------------------------------

def test_cache_path_and_freshness_hermetic(tmp_path):
    p = cache_path(str(tmp_path), "caps.xml")
    assert p == os.path.join(str(tmp_path), p4.CACHE_SUBDIR, "caps.xml")
    assert is_fresh(p, 365) is False  # missing file is never fresh
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as fh:
        fh.write("<xml/>")
    assert is_fresh(p, 365) is True
    old = time.time() - 400 * 86400
    os.utime(p, (old, old))
    assert is_fresh(p, 365) is False


def test_ttl_is_annual_bulk():
    assert TTL_DAYS == {"ortho_mosaic": 365, "elevation_wcs": 365,
                        "historical": 365, "stormwater_zones": 365}


def test_fetch_cached_cache_hit_never_touches_network(tmp_path):
    p = cache_path(str(tmp_path), "caps.xml")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as fh:
        fh.write(b"cached")
    # Unreachable URL + fresh cache: must return without raising.
    assert p4.fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                           "caps.xml", 365) == p


def test_fetch_cached_transport_error_raises_and_caches_nothing(
        tmp_path, monkeypatch):
    def _fail(*a, **k):
        raise urllib.error.URLError("unreachable")

    monkeypatch.setattr("urllib.request.urlopen", _fail)
    try:
        p4.fetch_cached("http://127.0.0.1:9/nope", str(tmp_path),
                        "caps.xml", 365)
    except urllib.error.URLError:
        pass
    else:
        raise AssertionError("transport error must raise, never cache")
    assert not os.path.exists(cache_path(str(tmp_path), "caps.xml"))


def test_parse_wms_layer_names_finds_aerial_layers():
    caps = ("<WMS><Name>OGC:WMS</Name><Layer><Name>EESTIFOTO</Name>"
            "<Title>Ortofoto</Title></Layer>"
            "<Layer queryable=\"1\"><Name>nDSM_info</Name>"
            "<Title>Maakatte kõrgusmudeli info</Title></Layer></WMS>")
    names = parse_wms_layer_names(caps)
    assert "EESTIFOTO" in names
    assert "nDSM_info" in names
    assert parse_wms_layer_names("") == []
    assert parse_wms_layer_names(None) == []


def test_scorers_never_touch_network(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("scorer used the network")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    lst, aer = listing(), aerial(mapillary_date="2026-01-15",
                                 facade_ok=True, view_fan="sliver",
                                 enclosure_index=0.2,
                                 heating_changed_heatpump=False,
                                 roof_pitch_steep=False,
                                 dist_cliff_m=5000.0,
                                 stormwater_zone="lahkvool")
    for fn in ALL_FNS:
        if fn is dim_street_block_observer:
            fn(lst, aer, TODAY)
        elif fn is dim_stormwater_subsidy:
            fn(lst, aer, ZONES)
        else:
            fn(lst, aer)
    score_p4_maa_aerial(lst, aer, ZONES, TODAY)


# ---------------------------------------------------------------------------
# P4-022 photo forensics (demo): flag counting + NULL contract.
# ---------------------------------------------------------------------------

def test_p22_null_when_no_leg():
    v, reason = dim_photo_forensics({}, {})
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason


def test_p22_two_flags_scores_30():
    v, reason = dim_photo_forensics(
        listing(exif_daylight_ok=False, photo_room_count=2,
                ehr_room_count=3),
        aerial())
    assert v == 30
    assert "hinnang 30/100" in reason


def test_p22_single_aerial_flag_scores_55():
    v, reason = dim_photo_forensics(
        listing(), aerial(duplicate_hashes=0, facade_change=True))
    assert v == 55
    assert "aerofotolt" in reason


def test_p22_duplicate_hash_scores_flag():
    v, _ = dim_photo_forensics(listing(), aerial(duplicate_hashes=2))
    assert v == 55  # one flag: the relist signal


def test_p22_clean_multi_leg_scores_80():
    v, reason = dim_photo_forensics(listing(), aerial())
    assert v == 80
    assert "relistisignaali EI OLE" in reason


# ---------------------------------------------------------------------------
# P4-029 street observer: bands, staleness cap, NULL contract.
# ---------------------------------------------------------------------------

def test_p29_null_when_no_imagery():
    v, reason = dim_street_block_observer(listing(), {})
    assert v is None
    assert "EI OLE" in reason and "hinnang" in reason


def test_p29_issues_score_40():
    v, reason = dim_street_block_observer(
        listing(), {"mapillary_date": "2026-03-01",
                    "street_issues": ["praht", "vrakk"]})
    assert v == 40
    assert "praht" in reason


def test_p29_bad_facade_without_issue_list_scores_40():
    v, _ = dim_street_block_observer(
        listing(), {"facade_ok": False, "mapillary_date": "2026-03-01"})
    assert v == 40


def test_p29_sidewalk_only_doubt_scores_55():
    v, _ = dim_street_block_observer(
        listing(), {"mapillary_date": "2026-03-01", "facade_ok": True,
                    "sidewalk_ok": False})
    assert v == 55


def test_p29_stale_clean_photo_capped_at_60():
    v, reason = dim_street_block_observer(
        listing(), {"mapillary_date": "2020-01-01", "facade_ok": True},
        TODAY)
    assert v == 60
    assert "lagi" in reason


def test_p29_fresh_clean_scores_75():
    v, _ = dim_street_block_observer(
        listing(), {"mapillary_date": "2026-06-01", "facade_ok": True},
        TODAY)
    assert v == 75


# ---------------------------------------------------------------------------
# P4-030 change delta: dump > change > quiet > NULL.
# ---------------------------------------------------------------------------

def test_p30_null_when_no_leg():
    v, reason = dim_satellite_change_delta(listing(), {})
    assert v is None
    assert "EI OLE" in reason


def test_p30_dump_scores_35():
    v, _ = dim_satellite_change_delta(
        listing(), {"dump_suspected": True, "ndvi_delta": -0.3})
    assert v == 35


def test_p30_ndvi_drop_scores_45():
    v, reason = dim_satellite_change_delta(
        listing(), {"ndvi_delta": -0.22, "construction_nearby": False})
    assert v == 45
    assert "NDVI-langus" in reason


def test_p30_small_ndvi_wobble_is_quiet():
    v, _ = dim_satellite_change_delta(
        listing(), {"ndvi_delta": -0.05, "facade_change": False})
    assert v == 70


def test_p30_quiet_legs_score_70():
    v, _ = dim_satellite_change_delta(
        listing(), {"ndvi_delta": 0.02, "raieluba_nearby": False,
                    "construction_nearby": False})
    assert v == 70


# ---------------------------------------------------------------------------
# P4-041 glimpse: view classes, blockage penalty, fan-missing NULL.
# ---------------------------------------------------------------------------

def test_p41_null_when_fan_missing_even_with_floor():
    v, reason = dim_glimpse_economics(listing(floor=9), {})
    assert v is None
    assert "EI OLE" in reason  # floor alone is a fan input, not a signal


def test_p41_open_sliver_none_classes():
    assert dim_glimpse_economics(listing(), {"view_fan": "open"})[0] == 85
    assert dim_glimpse_economics(listing(), {"view_fan": "sliver"})[0] == 70
    v, reason = dim_glimpse_economics(listing(), {"view_fan": "none"})
    assert v == 50
    assert "maitsesobivus" in reason  # neutral, never a wall penalty


def test_p41_future_blockage_minus_15_floored():
    v, _ = dim_glimpse_economics(
        listing(), {"view_fan": "sliver", "future_blockage": True})
    assert v == 55
    v, _ = dim_glimpse_economics(
        listing(), {"view_fan": "none", "future_blockage": True})
    assert v == 35  # 50 - 15, above the 30 floor


def test_p41_protected_corridor_noted_not_scored():
    v, reason = dim_glimpse_economics(
        listing(), {"view_fan": "open", "protected_view_corridor": True})
    assert v == 85
    assert "vaatekoridor" in reason


# ---------------------------------------------------------------------------
# P4-056 courtyard trap (LiDAR leg ilm names missing): bands + NULL.
# ---------------------------------------------------------------------------

def test_p56_null_when_index_missing():
    v, reason = dim_courtyard_trap(listing(), {})
    assert v is None
    assert "EI OLE" in reason
    assert "P4-ilm" in reason  # wind leg named, not re-scored


def test_p56_bands_and_invalid_index():
    assert dim_courtyard_trap(listing(), {"enclosure_index": 0.85})[0] == 35
    assert dim_courtyard_trap(listing(), {"enclosure_index": 0.7})[0] == 35
    assert dim_courtyard_trap(listing(), {"enclosure_index": 0.5})[0] == 55
    assert dim_courtyard_trap(listing(), {"enclosure_index": 0.1})[0] == 75
    v, _ = dim_courtyard_trap(listing(), {"enclosure_index": 1.5})
    assert v is None  # out-of-range index is not a signal
    v, _ = dim_courtyard_trap(listing(), {"enclosure_index": "suur"})
    assert v is None


def test_p56_green_deficit_noted():
    _, reason = dim_courtyard_trap(
        listing(), {"enclosure_index": 0.8, "courtyard_green": False})
    assert "haljastuse puudujääk" in reason


# ---------------------------------------------------------------------------
# P4-057 heat-pump hum: weak by construction.
# ---------------------------------------------------------------------------

def test_p57_null_when_no_heating_data():
    v, reason = dim_heatpump_hum(listing(), {})
    assert v is None
    assert "EI OLE" in reason and "proksi" in reason


def test_p57_uptake_plus_complaints_scores_40():
    v, _ = dim_heatpump_hum(
        listing(), {"heating_changed_heatpump": True,
                    "hum_complaints": True})
    assert v == 40


def test_p57_uptake_only_never_scores_high():
    v, reason = dim_heatpump_hum(
        listing(), {"heating_changed_heatpump": True})
    assert v == 55
    assert "ei müü vaikust" in reason


def test_p57_no_uptake_with_data_scores_70():
    v, _ = dim_heatpump_hum(
        listing(), {"heating_changed_heatpump": False,
                    "hum_complaints": False})
    assert v == 70


# ---------------------------------------------------------------------------
# P4-058 ice + cliff: dated risks score low, clean-with-data scores 70.
# ---------------------------------------------------------------------------

def test_p58_null_when_no_leg():
    v, reason = dim_ice_cliff(listing(), {})
    assert v is None
    assert "EI OLE" in reason


def test_p58_steep_roof_scores_40():
    v, reason = dim_ice_cliff(
        listing(), {"roof_pitch_steep": True, "roof_type": "viil"})
    assert v == 40
    assert "järsk katus" in reason


def test_p58_warning_date_and_cliff_carried_in_reason():
    v, reason = dim_ice_cliff(
        listing(), {"ice_warning_date": "2026-01-20",
                    "cliff_retreat_nearby": True, "dist_cliff_m": 60.0})
    assert v == 40
    assert "2026-01-20" in reason and "kaljuserv 60 m" in reason


def test_p58_far_cliff_is_not_a_risk():
    v, _ = dim_ice_cliff(
        listing(), {"roof_pitch_steep": False, "dist_cliff_m": 5000.0})
    assert v == 70


# ---------------------------------------------------------------------------
# P4-060 stormwater: zone bands, queue context, NULL contract.
# ---------------------------------------------------------------------------

def test_p60_null_when_table_or_zone_missing():
    v, reason = dim_stormwater_subsidy(listing(), {}, None)
    assert v is None
    assert "EI OLE" in reason
    v, _ = dim_stormwater_subsidy(
        listing(), {"stormwater_zone": "tundmatu"}, ZONES)
    assert v is None


def test_p60_fee_bands():
    assert dim_stormwater_subsidy(
        listing(), {"stormwater_zone": "uhisvool"}, ZONES)[0] == 75
    assert dim_stormwater_subsidy(
        listing(), {"stormwater_zone": "kompensatsioon"}, ZONES)[0] == 65
    assert dim_stormwater_subsidy(
        listing(), {"stormwater_zone": "lahkvool"}, ZONES)[0] == 50
    assert dim_stormwater_subsidy(
        listing(), {"stormwater_zone": "korge"}, ZONES)[0] == 40


def test_p60_queue_position_in_reason_and_bad_fee_null():
    v, reason = dim_stormwater_subsidy(
        listing(), {"stormwater_zone": "lahkvool",
                    "subsidy_queue_pos": 17}, ZONES)
    assert v == 50
    assert "järjekoht 17" in reason
    v, _ = dim_stormwater_subsidy(
        listing(), {"stormwater_zone": "lahkvool"}, {"lahkvool": -5})
    assert v is None


# ---------------------------------------------------------------------------
# Registry + aggregator cover all eight params.
# ---------------------------------------------------------------------------

def test_all_null_reasons_carry_honesty_markers():
    for _, _, fn in P4_MAA_AERIAL_DIMS:
        if fn is dim_street_block_observer:
            v, reason = fn({}, {}, TODAY)
        elif fn is dim_stormwater_subsidy:
            v, reason = fn({}, {}, None)
        else:
            v, reason = fn({}, {})
        assert v is None
        assert "EI OLE" in reason
        assert "hinnang" in reason


def test_registry_and_aggregator_cover_all_eight():
    assert [k for k, _, _ in P4_MAA_AERIAL_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_MAA_AERIAL_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_MAA_AERIAL_DIMS}) == 8
    assert p4.P4_MAA_AERIAL_DIMS is P4_MAA_AERIAL_DIMS
    out = score_p4_maa_aerial({}, {}, None, TODAY)
    assert out == {k: None for k in EXPECTED_KEYS}
    rich = aerial(mapillary_date="2026-06-01", facade_ok=True,
                  ndvi_delta=0.01, facade_change=False,
                  view_fan="sliver", enclosure_index=0.2,
                  heating_changed_heatpump=False,
                  roof_pitch_steep=False, dist_cliff_m=5000.0,
                  stormwater_zone="kompensatsioon")
    out = score_p4_maa_aerial(listing(), rich, ZONES, TODAY)
    assert out == {"photo_forensics": 80, "street_observer": 75,
                   "change_delta": 70, "glimpse": 70,
                   "courtyard_trap": 75, "heatpump_hum": 70,
                   "ice_cliff": 70, "stormwater": 65}
