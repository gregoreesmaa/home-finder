"""Tests for the outage observation log + reliability build (issue #780).

Hermetic: no network anywhere (live pulls are operator/pole only).
Pins log-append (success appends, failure/corrupt appends nothing),
retention pruning, aggregation windowing + metric, and build CLI.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_outage import (  # noqa: E402
    EXPECTED_PULLS_PER_DAY,
    RELIABILITY_WINDOW_DAYS,
    RETAIN_DAYS,
    append_observation,
    build_reliability,
    build_sidecar,
    decode_application_data,
    main,
    observation_from_sidecar,
    prune_observations,
    read_observations,
)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)

FIXTURE_BODY = json.dumps(json.dumps({
    "scopes": {"p": {
        "areas": [
            {"cid": 7639, "fc": 1, "fcc": 12, "id": 454883598,
             "label": "Tallinn", "pc": 0, "pcc": 0,
             "uc": 27, "ucc": 3169},
            {"cid": 7638, "fc": 0, "fcc": 0, "id": 454746528,
             "label": "Harju maakond", "pc": 2, "pcc": 40,
             "uc": 96, "ucc": 5766},
            {"cid": 1, "fc": 5, "fcc": 99, "id": 1,
             "label": "Tartu", "pc": 0, "pcc": 0,
             "uc": 0, "ucc": 0},
        ],
        "dynareas": [],
        "outages": [{"t": "f"}, {"t": "u"}],
    }},
}))


def _obs(ts, tallinn_fc=0, tallinn_fcc=0, tallinn_pc=0, tallinn_pcc=0,
         tallinn_uc=0, tallinn_ucc=0):
    return {
        "ts": ts.isoformat(),
        "areas": {"Tallinn": {
            "fc": tallinn_fc, "fcc": tallinn_fcc, "pc": tallinn_pc,
            "pcc": tallinn_pcc, "uc": tallinn_uc, "ucc": tallinn_ucc,
        }},
        "tallies": {"u": 1},
    }


def test_observation_keeps_city_rollup_only():
    decoded = decode_application_data(FIXTURE_BODY)
    assert decoded is not None
    sidecar = build_sidecar(decoded, now=NOW)
    obs = observation_from_sidecar(sidecar)
    assert obs is not None
    assert obs["ts"] == NOW.isoformat()
    # City rollup first: Tallinn + Harju logged, Tartu (99-area grain) not.
    assert sorted(obs["areas"]) == ["Harju maakond", "Tallinn"]
    assert obs["areas"]["Tallinn"] == {
        "fc": 1, "fcc": 12, "pc": 0, "pcc": 0, "uc": 27, "ucc": 3169}
    assert obs["tallies"] == {"f": 1, "u": 1}


def test_observation_refuses_labelless_sidecar():
    assert observation_from_sidecar({"pulled_at": NOW.isoformat(),
                                     "areas": [{"fc": 1}]}) is None
    assert observation_from_sidecar({"areas": []}) is None
    assert observation_from_sidecar(None) is None


def test_append_and_read_roundtrip(tmp_path):
    log = str(tmp_path / "observations.jsonl")
    append_observation(log, _obs(NOW, tallinn_fc=1))
    append_observation(log, _obs(NOW, tallinn_uc=3))
    recs = read_observations(log)
    assert len(recs) == 2
    assert recs[0]["areas"]["Tallinn"]["fc"] == 1


def test_read_skips_corrupt_lines(tmp_path):
    log = str(tmp_path / "observations.jsonl")
    with open(log, "w", encoding="utf-8") as fh:
        fh.write("{not json\n")
        fh.write(json.dumps(_obs(NOW)) + "\n")
        fh.write(json.dumps({"no": "ts"}) + "\n")
    # Corrupt lines are gaps, never data.
    assert len(read_observations(log)) == 1
    assert read_observations(str(tmp_path / "missing.jsonl")) == []


def test_prune_keeps_retention_window(tmp_path):
    log = str(tmp_path / "observations.jsonl")
    with open(log, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(_obs(NOW - timedelta(days=RETAIN_DAYS + 1))) + "\n")
        fh.write("{corrupt\n")
        fh.write(json.dumps(_obs(NOW)) + "\n")
    kept = prune_observations(log, now=NOW)
    assert kept == 1
    assert len(read_observations(log)) == 1
    assert prune_observations(str(tmp_path / "missing.jsonl"), now=NOW) == 0


def test_reliability_aggregates_window_metric():
    obs = [
        _obs(NOW - timedelta(hours=1), tallinn_fc=1, tallinn_fcc=12),
        _obs(NOW - timedelta(hours=2), tallinn_pc=1, tallinn_pcc=40,
             tallinn_uc=2, tallinn_ucc=100),
        _obs(NOW - timedelta(hours=3)),
        # Outside the 28-day window: excluded, never aggregated.
        _obs(NOW - timedelta(days=RELIABILITY_WINDOW_DAYS + 1),
             tallinn_fc=9, tallinn_fcc=900),
    ]
    table = build_reliability(obs, now=NOW)
    assert table["window_days"] == RELIABILITY_WINDOW_DAYS == 28
    assert table["expected_pulls_per_day"] == EXPECTED_PULLS_PER_DAY == 288
    assert table["n_obs_total"] == 3
    assert "SAIDI" in table["metric"]  # metric documented, never SAIDI-claim
    tallinn = table["areas"]["Tallinn"]
    assert tallinn["n_obs"] == 3
    assert tallinn["fault_obs"] == 1
    assert tallinn["planned_obs"] == 1
    assert tallinn["upcoming_obs"] == 1
    assert tallinn["fault_customers"] == 12
    assert tallinn["planned_customers"] == 40
    assert tallinn["coverage"] == round(3 / (28 * 288), 4)


def test_reliability_missing_counters_stay_unknown():
    rec = _obs(NOW)
    rec["areas"]["Tallinn"]["fc"] = None
    rec["areas"]["Tallinn"]["fcc"] = None
    table = build_reliability([rec], now=NOW)
    # None counters never zero-fill into calm classes...
    assert table["areas"]["Tallinn"]["fault_obs"] == 0
    # ...but a fully-zero row still reads clean-adjacent (no fault).
    assert table["areas"]["Tallinn"]["planned_obs"] == 0


def test_reliability_empty_log_serves_empty_table():
    table = build_reliability([], now=NOW)
    assert table["n_obs_total"] == 0
    assert table["areas"] == {}


def test_build_reliability_cli(tmp_path):
    log = str(tmp_path / "observations.jsonl")
    out = str(tmp_path / "reliability.json")
    append_observation(log, _obs(NOW, tallinn_fc=1, tallinn_fcc=5))
    rc = main(["--build-reliability", "--log", log, "--out", out])
    assert rc == 0
    with open(out, encoding="utf-8") as fh:
        table = json.load(fh)
    assert table["areas"]["Tallinn"]["fault_obs"] == 1
    assert table["areas"]["Tallinn"]["fault_customers"] == 5
