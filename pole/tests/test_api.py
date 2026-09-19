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


def _client(tmp_path, missing=()):
    built = tmp_path / "built"
    (built / "fixit").mkdir(parents=True)
    if "fixit" not in missing:
        (built / "fixit" / "fixit-points.json").write_text(
            json.dumps(FIXTURE), encoding="utf-8")
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
                     "datex-srti", "datex-weather",
                     "delay", "fixit", "medre", "mobile", "poi"]


def test_dataset_serves_bytes_and_freshness(tmp_path):
    c = _client(tmp_path)
    r = c.get("/v1/fixit")
    assert r.status_code == 200
    assert r.json() == FIXTURE
    assert "X-Pole-Built-At" in r.headers


def test_missing_build_is_honest_503(tmp_path):
    c = _client(tmp_path, missing=("fixit",))
    assert c.get("/v1/fixit").status_code == 503


def test_unknown_dataset_is_404(tmp_path):
    c = _client(tmp_path)
    assert c.get("/v1/nope").status_code == 404
