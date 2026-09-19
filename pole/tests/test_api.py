"""Hermetic tests for the harvest-pole read API (issue #676).

The API reads built/*.json from its own directory; tests point BUILT_DIR at
a tmp dir with fixtures, so no network and no Pi are involved.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                ".."))

import api  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

FIXTURE = {"vintage": "2026-09-18", "counts": {"total": 2}, "points": []}

MEDRE_EMPTY = {"vintage": "2026-09-16", "linkage_rate": 0, "points": []}
MEDRE_FULL = {"vintage": "2026-09-16", "linkage_rate": 0.9847,
              "points": [{"lat": 59.43, "lon": 24.75, "slice": "gp"}]}


def _client(tmp_path, missing=(), medre=None):
    built = tmp_path / "built"
    (built / "fixit").mkdir(parents=True)
    if "fixit" not in missing:
        (built / "fixit" / "fixit-points.json").write_text(
            json.dumps(FIXTURE), encoding="utf-8")
    if medre is not None:
        (built / "medre").mkdir(parents=True, exist_ok=True)
        (built / "medre" / "medre-points.json").write_text(
            json.dumps(medre), encoding="utf-8")
    api.BUILT_DIR = str(built)
    return TestClient(api.app)


def test_health_reports_readiness(tmp_path):
    c = _client(tmp_path)
    body = c.get("/health").json()
    assert body["ok"] is True
    assert body["datasets"]["fixit"] is True
    assert body["datasets"]["delay"] is False  # no fixture written


def test_datasets_lists_five(tmp_path):
    c = _client(tmp_path)
    names = sorted(d["name"] for d in c.get("/v1/datasets").json()["datasets"])
    assert names == ["datex-cameras", "datex-counters", "datex-restrictions",
                     "datex-srti", "datex-truckpark", "datex-weather",
                     "delay", "fixit", "medre", "mobile",
                     # OUTAGE-HOOK (#729): live-outage sidecar joins the pole.
                     "outage",
                     # OUTAGE-RELIABILITY-HOOK (#780): observed-reliability
                     # table joins the pole (honest 503 until first build).
                     "outage-reliability", "poi",
                     # SKIS-HOOK (#692): seasonal ski tracks join the pole.
                     "skis",
                     # VIIRS-HOOK (#719): brightness-proxy grid joins the pole.
                     "viirs"]


def test_dataset_serves_bytes_and_freshness(tmp_path):
    c = _client(tmp_path)
    r = c.get("/v1/fixit")
    assert r.status_code == 200
    assert r.json() == FIXTURE
    assert "X-Pole-Built-At" in r.headers


def test_missing_build_is_honest_503(tmp_path):
    c = _client(tmp_path, missing=("fixit",))
    assert c.get("/v1/fixit").status_code == 503


def test_outage_reliability_missing_build_is_honest_503(tmp_path):
    # Issue #780: no reliability table until the first pole build.
    c = _client(tmp_path)
    assert c.get("/health").json()["datasets"]["outage-reliability"] is False
    assert c.get("/v1/outage-reliability").status_code == 503


def test_outage_reliability_serves_table(tmp_path):
    # Issue #780: the built reliability table serves with freshness.
    table = {"built_at": "2026-09-20T12:00:00+00:00", "window_days": 28,
             "metric": "vaadeldud töökindlus", "n_obs_total": 3,
             "areas": {"Tallinn": {"n_obs": 3, "fault_obs": 1}}}
    rel_dir = tmp_path / "built" / "outage"
    rel_dir.mkdir(parents=True)
    (rel_dir / "reliability.json").write_text(
        json.dumps(table), encoding="utf-8")
    c = _client(tmp_path)
    assert c.get("/health").json()["datasets"]["outage-reliability"] is True
    r = c.get("/v1/outage-reliability")
    assert r.status_code == 200
    assert r.json()["window_days"] == 28
    assert "X-Pole-Built-At" in r.headers


def test_unknown_dataset_is_404(tmp_path):
    c = _client(tmp_path)
    assert c.get("/v1/nope").status_code == 404


def test_medre_empty_points_is_honest_503(tmp_path):
    # Issue #765: Step-1 linkage report (points []) must not serve.
    c = _client(tmp_path, medre=MEDRE_EMPTY)
    assert c.get("/health").json()["datasets"]["medre"] is False
    assert c.get("/v1/medre").status_code == 503


def test_medre_joined_points_serve(tmp_path):
    c = _client(tmp_path, medre=MEDRE_FULL)
    assert c.get("/health").json()["datasets"]["medre"] is True
    r = c.get("/v1/medre")
    assert r.status_code == 200
    assert len(r.json()["points"]) == 1


def test_unlisted_empty_points_still_serve(tmp_path):
    # Honest-empty scope guard: fixit points [] keeps serving 200.
    c = _client(tmp_path)
    assert c.get("/v1/fixit").status_code == 200
