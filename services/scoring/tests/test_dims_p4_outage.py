"""P4 live-outage dims (issue #729): hermetic tests.

No network: the harvester pull is never called here (its contract —
single polite GET, 5-min TTL, transport errors raise, 429 stops — is
covered via the pure parse_outage_snapshot freshness pin plus a
validation test that raises before any I/O in batch_outage). Fixture
rows repeat the live SHAPE with the observed 2026-09-19 Tallinn/Harju
counters (facts, tiny); synthetic rows pin the fault/planned/stale
edges no live row covers.
"""

from datetime import datetime, timedelta, timezone

import dims_p4_outage as outage
from dims_p4_outage import (
    OUTAGE_TTL_S,
    OUTAGE_T_FAULT,
    OUTAGE_T_PLAN,
    OUTAGE_T_UPCOMING,
    coerce_area,
    dim_outage_now,
    parse_outage_snapshot,
    pick_city_row,
    score_p4_outage,
)

TALLINN = (59.4372, 24.7536)
NOW = datetime(2026, 9, 19, 15, 30, tzinfo=timezone.utc)

#: Observed live shape 2026-09-19 (GetApplicationData, facts).
LIVE_TALLINN = {"cid": 7639, "fc": 0, "fcc": 0, "id": 454883598,
                "label": "Tallinn", "pc": 0, "pcc": 0,
                "uc": 27, "ucc": 3169}
LIVE_HARJU = {"cid": 7638, "fc": 0, "fcc": 0, "id": 454746528,
              "label": "Harju maakond", "pc": 0, "pcc": 0,
              "uc": 96, "ucc": 5766}


def _snap(rows, at=NOW):
    return {"pulled_at": at.isoformat(), "areas": rows}


def test_field_vocabulary_pinned_from_app_js():
    assert (OUTAGE_T_PLAN, OUTAGE_T_FAULT, OUTAGE_T_UPCOMING) == ("p", "f", "u")
    assert OUTAGE_TTL_S == 300


def test_coerce_area_keeps_counters_and_skips_labelless():
    area = coerce_area(LIVE_TALLINN)
    assert area["label"] == "Tallinn"
    assert (area["fc"], area["fcc"], area["uc"], area["ucc"]) == (0, 0, 27, 3169)
    assert coerce_area({"fc": 1}) is None
    assert coerce_area(None) is None


def test_parse_snapshot_enforces_5min_ttl():
    fresh = parse_outage_snapshot(_snap([LIVE_TALLINN]), now=NOW)
    assert fresh is not None
    assert fresh["areas"]["Tallinn"]["ucc"] == 3169
    stale = parse_outage_snapshot(
        _snap([LIVE_TALLINN], at=NOW - timedelta(seconds=301)), now=NOW)
    assert stale is None
    assert parse_outage_snapshot({"areas": []}, now=NOW) is None
    assert parse_outage_snapshot(None, now=NOW) is None


def test_city_row_prefers_tallinn_then_harju():
    snap = {"areas": {"Harju maakond": coerce_area(LIVE_HARJU),
                      "Tallinn": coerce_area(LIVE_TALLINN)}}
    assert pick_city_row(snap)["label"] == "Tallinn"
    assert pick_city_row({"areas": {"Harju maakond": coerce_area(LIVE_HARJU)}}
                         )["label"] == "Harju maakond"
    assert pick_city_row({"areas": {}}) is None


def test_live_tallinn_row_scores_upcoming_only_70():
    snap = {"areas": {"Tallinn": coerce_area(LIVE_TALLINN)}}
    score, reason = dim_outage_now(TALLINN, snap)
    assert score == 70
    assert "27" in reason and "3169" in reason
    assert "hetkeseis" in reason


def test_active_fault_scores_30_and_planned_55():
    fault = dict(LIVE_TALLINN, fc=2, fcc=410)
    score, reason = dim_outage_now(
        TALLINN, {"areas": {"Tallinn": coerce_area(fault)}})
    assert score == 30
    assert "rikkeline" in reason
    planned = dict(LIVE_TALLINN, uc=0, ucc=0, pc=1, pcc=55)
    score, reason = dim_outage_now(
        TALLINN, {"areas": {"Tallinn": coerce_area(planned)}})
    assert score == 55
    assert "plaaniline" in reason


def test_clean_row_scores_capped_80_and_gaps_stay_null():
    clean = dict(LIVE_TALLINN, uc=0, ucc=0)
    score, reason = dim_outage_now(
        TALLINN, {"areas": {"Tallinn": coerce_area(clean)}})
    assert score == 80
    assert "EI OLE" not in reason
    assert dim_outage_now(None, {"areas": {}})[0] is None
    assert "EI OLE" in dim_outage_now(TALLINN, None)[1]
    assert "EI OLE" in dim_outage_now(TALLINN, {"areas": {}})[1]
    thin = dict(LIVE_TALLINN, uc=0, ucc=0, fc=None)
    assert dim_outage_now(
        TALLINN, {"areas": {"Tallinn": coerce_area(thin)}})[0] is None


def test_score_entry_point_keys():
    snap = {"areas": {"Tallinn": coerce_area(LIVE_TALLINN)}}
    assert score_p4_outage(TALLINN, snap) == {"outage_now": 70}
    assert score_p4_outage(TALLINN, None) == {"outage_now": None}
    assert outage.P4_OUTAGE_DIMS[0][:2] == ("outage_now", "P4-009")
