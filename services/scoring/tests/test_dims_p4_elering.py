"""P4 Elering dims (issues #265 demo + #345 coverage): hermetic tests.

No network: fetch_elering_system is never called here (its contract —
single polite GET, file cache, TTL, transport errors raise — is
covered via the pure cache_is_fresh helper plus a cache-hit fetch
test that performs no GET). Parsing runs on fixtures mirroring the
real 2026-09-13 /api/system/with-plan envelope shape (incl. null
solar/losses); every dim is tested through the (origin, pois,
elering-snapshot) shape: joined snapshot -> still NULL with
traceable national context, missing snapshot -> NULL naming the
gap. NULL stays NULL with Estonian honesty markers.
"""

import json
import os
import time

import dims_p4_elering as elering
from dims_p4_elering import (
    ELERING_DIMS,
    ELERING_SYSTEM_URL,
    ELERING_TTL_DAYS,
    cache_is_fresh,
    dim_feed_in_rules,
    dim_grid_backup,
    dim_system_adequacy,
    fetch_elering_system,
    parse_elering_system,
    score_p4_elering,
    summarize_elering_system,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

#: Real-shape envelope (field names + nulls as observed 2026-09-13;
#: values trimmed to three points).
REAL_SHAPE_ENVELOPE = {
    "success": True,
    "data": {
        "real": [
            {"timestamp": 1789246800, "production": 555.12,
             "consumption": 755.05, "losses": None, "frequency": 50.0,
             "system_balance": -199.92, "ac_balance": 796.11,
             "production_renewable": 263.45,
             "solar_energy_production": None},
            {"timestamp": 1789247700, "production": 545.65,
             "consumption": 751.78, "losses": None, "frequency": 50.0,
             "system_balance": -206.13, "ac_balance": 789.80,
             "production_renewable": 251.22,
             "solar_energy_production": None},
            {"timestamp": 1789248600, "production": 522.75,
             "consumption": 729.71, "losses": None, "frequency": 50.0,
             "system_balance": 12.5, "ac_balance": 780.0,
             "production_renewable": 200.0,
             "solar_energy_production": 34.2},
        ],
        "plan": [],
    },
}
REAL_SHAPE_TEXT = json.dumps(REAL_SHAPE_ENVELOPE)

ALL_FNS = [dim_system_adequacy, dim_feed_in_rules, dim_grid_backup]

EXPECTED_KEYS = ["system_adequacy", "feed_in_rules", "grid_backup"]
EXPECTED_PNUMS = ["P4-009", "P4-036", "P4-046"]


def _snapshot():
    return summarize_elering_system(
        parse_elering_system(REAL_SHAPE_TEXT))


# ---------------------------------------------------------------------------
# Ingestion contract: URL/TTL constants + cache freshness (no network).
# ---------------------------------------------------------------------------

def test_source_identity_and_monthly_ttl():
    assert ELERING_SYSTEM_URL == \
        "https://dashboard.elering.ee/api/system/with-plan"
    assert ELERING_TTL_DAYS == 30  # parameters4.md P4-009 "TTL: monthly"
    assert elering.USER_AGENT.startswith("home-finder")


def test_cache_is_fresh_missing_stale_and_fresh(tmp_path):
    missing = os.path.join(str(tmp_path), "nope.json")
    assert cache_is_fresh(missing) is False
    stale = os.path.join(str(tmp_path), "stale.json")
    with open(stale, "w", encoding="utf-8") as f:
        f.write("x")
    old = time.time() - (ELERING_TTL_DAYS + 1) * 86400.0
    os.utime(stale, (old, old))
    assert cache_is_fresh(stale) is False
    fresh = os.path.join(str(tmp_path), "fresh.json")
    with open(fresh, "w", encoding="utf-8") as f:
        f.write("x")
    assert cache_is_fresh(fresh) is True


def test_fetch_returns_fresh_cache_without_network(tmp_path):
    cache_dir = str(tmp_path)
    with open(os.path.join(cache_dir, "elering-system.json"), "w",
              encoding="utf-8") as f:
        f.write(REAL_SHAPE_TEXT)
    # Fresh cache -> returns text with no GET performed.
    assert fetch_elering_system(cache_dir) == REAL_SHAPE_TEXT


# ---------------------------------------------------------------------------
# Parsing: real-shape envelope, nulls, envelopes that are never data.
# ---------------------------------------------------------------------------

def test_parse_real_shape_fields_and_null_solar_stays_none():
    pts = parse_elering_system(REAL_SHAPE_TEXT)
    assert len(pts) == 3
    first = pts[0]
    assert first["timestamp"] == 1789246800
    assert first["production_mw"] == 555.12
    assert first["consumption_mw"] == 755.05
    assert first["system_balance_mw"] == -199.92
    assert first["frequency_hz"] == 50.0
    assert first["renewable_mw"] == 263.45
    # Observed nulls stay None — never blessed as 0.0.
    assert first["solar_mw"] is None
    assert pts[2]["solar_mw"] == 34.2
    assert set(first) == set(elering.ELERING_POINT_FIELDS)


def test_parse_skips_timestamp_less_rows_and_non_rows():
    payload = json.dumps({"success": True, "data": {"real": [
        {"production": 1.0},
        {"timestamp": None, "production": 2.0},
        "not-a-row",
        {"timestamp": 9, "system_balance": -1.5},
    ]}})
    pts = parse_elering_system(payload)
    assert len(pts) == 1
    assert pts[0]["timestamp"] == 9
    assert pts[0]["production_mw"] is None
    assert pts[0]["system_balance_mw"] == -1.5


def test_parse_error_envelopes_yield_empty_never_data():
    assert parse_elering_system('{"success": false}') == []
    assert parse_elering_system('{"success": true}') == []
    assert parse_elering_system('{"success": true, "data": {}}') == []
    assert parse_elering_system('{"success": true, "data": {"real": {}}}') \
        == []
    assert parse_elering_system("not json at all {{{") == []
    assert parse_elering_system("[1, 2]") == []


def test_summarize_math_and_all_null_solar_stays_none():
    snap = _snapshot()
    assert snap is not None
    assert snap["points"] == 3
    assert snap["start_ts"] == 1789246800
    assert snap["end_ts"] == 1789248600
    assert abs(snap["avg_balance_mw"]
               - ((-199.92 - 206.13 + 12.5) / 3)) < 1e-9
    assert abs(snap["deficit_share"] - (2 / 3)) < 1e-9
    assert snap["avg_solar_mw"] == 34.2  # only the valued point counts
    assert snap["freq_ok_share"] == 1.0
    assert set(snap) == set(elering.ELERING_SNAPSHOT_FIELDS)


def test_summarize_all_null_measures_and_empty():
    pts = parse_elering_system(json.dumps(
        {"success": True, "data": {"real": [
            {"timestamp": 1}, {"timestamp": 2}]}}))
    snap = summarize_elering_system(pts)
    assert snap is not None
    assert snap["points"] == 2
    assert snap["avg_balance_mw"] is None
    assert snap["deficit_share"] is None
    assert snap["avg_solar_mw"] is None  # never 0.0
    assert snap["freq_ok_share"] is None
    assert summarize_elering_system([]) is None


# ---------------------------------------------------------------------------
# Dims: always NULL (national != address), reasons carry markers.
# ---------------------------------------------------------------------------

def test_all_three_dims_always_none_for_every_input():
    snap = _snapshot()
    for fn in ALL_FNS:
        for origin, pois, snap_arg in [
                (TALLINN, POIS, snap), (TALLINN, [], snap),
                (None, None, snap), (None, POIS, None),
                (TALLINN, None, None), (TALLINN, POIS, None),
                (None, None, None)]:
            v, _ = fn(origin, pois, snap_arg)
            assert v is None, fn.__name__


def test_all_reasons_carry_honesty_markers_and_buyer_side_pointer():
    snap = _snapshot()
    for fn in ALL_FNS:
        for snap_arg in (snap, None):
            _, reason = fn(TALLINN, POIS, snap_arg)
            assert "hinnang" in reason, fn.__name__
            assert "EI OLE" in reason, fn.__name__
            assert "ära feigi" in reason, fn.__name__
            assert "mõõdetud" not in reason \
                and "garanteeritud" not in reason


def test_system_adequacy_echoes_snapshot_and_names_feeder_gap():
    snap = _snapshot()
    _, with_snap = dim_system_adequacy(TALLINN, POIS, snap)
    assert "Elering Live" in with_snap
    assert "bilanss" in with_snap
    assert "SÜSTEEMI" in with_snap
    assert "SAIDI" in with_snap
    assert "rikkekaardilt" in with_snap and "netikaardilt" in with_snap
    _, without_snap = dim_system_adequacy(TALLINN, POIS, None)
    assert "hetktõmmis puudub" in without_snap
    assert "EI OLE" in without_snap


def test_feed_in_rules_names_human_only_rules_and_building_checks():
    _, reason = dim_feed_in_rules(TALLINN, POIS, _snapshot())
    assert "inimloetavad" in reason
    assert "EHR" in reason and "liitumiskaardilt" in reason
    assert "upside" in reason
    _, bare = dim_feed_in_rules(TALLINN, POIS, None)
    assert "EI OLE" in bare


def test_grid_backup_names_unpublished_condition_and_redundancy():
    _, reason = dim_grid_backup(TALLINN, POIS, _snapshot())
    assert "kus avaldatud" in reason
    assert "Elektrilevi pool" in reason
    assert "kamin" in reason and "linnavesi" in reason
    assert "KÜ-lt" in reason


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in ELERING_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in ELERING_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in ELERING_DIMS}) == 3
    snap = _snapshot()
    out = score_p4_elering(TALLINN, POIS, snap)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_elering(None, None, None) == \
        {k: None for k in EXPECTED_KEYS}
    assert score_p4_elering(TALLINN, POIS) == \
        {k: None for k in EXPECTED_KEYS}
    assert elering.ELERING_DIMS is ELERING_DIMS
