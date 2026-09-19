"""Tests for scripts/build/batch_tomtom_incidents.py (issue #672).

Hermetic: urlopen is stubbed, env key is faked per-test - no network,
no real key material anywhere. Pins the hard refusal without a key on
BOTH paths (--pull and --build), the fixture harvest path, TTL
short-circuit, freshness labeling, and quota enforcement. The one
keyed probe at the end is explicitly flagged: skipped without
TOMTOM_API_KEY, single polite call, writes to /tmp only, never runs
in CI.
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_tomtom_incidents import build_table, main  # noqa: E402

FIXTURE_INCIDENTS = {"incidents": [
    {"id": "i1",
     "properties": {"iconCategory": 8, "magnitudeOfDelay": 3,
                    "events": ["JAM"], "freeText": "Ummik Tartu mnt"},
     "geometry": {"type": "LineString",
                  "coordinates": [[24.78, 59.428], [24.79, 59.429]]}},
    {"id": "i2",
     "properties": {"iconCategory": 10, "magnitudeOfDelay": 1},
     "geometry": {"type": "LineString",
                  "coordinates": [[24.70, 59.41]]}},
]}


def fixture_cells():
    return [{"incident_id": "i1", "category": 8, "magnitude": 3,
             "description": "Ummik", "points": [(59.428, 24.78)]},
            {"incident_id": "i2", "category": 10, "magnitude": 1,
             "description": None, "points": []}]


class _Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _Resp:
    status = 200
    headers = _Headers()

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stub_urlopen_factory(monkeypatch, calls, body=None, status=200):
    payload = json.dumps(body if body is not None
                         else FIXTURE_INCIDENTS).encode()

    class _R(_Resp):
        pass
    _R.status = status

    def _fake(req, timeout=30):
        calls.append(getattr(req, "full_url", "?"))
        return _R(payload)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake)


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)


def test_refuses_without_key_pull(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "TOMTOM_API_KEY" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_refuses_without_key_build(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--build", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "TOMTOM_API_KEY" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_builds_table_from_fixture(tmp_path):
    table = build_table(fixture_cells(), fetched_at=time.time())
    assert table["counts"]["total"] == len(fixture_cells())
    assert table["counts"]["by_magnitude"] == {"3": 1, "1": 1}


def test_fixture_pull_then_build_labels_fresh(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    assert main(["--pull", "--cache-dir", str(tmp_path)]) == 0
    assert len(calls) == 1  # one bbox poll
    cached = tmp_path / "tomtom_incidents.json"
    assert cached.exists()
    assert "test-key-not-real" not in cached.read_text(encoding="utf-8")
    quota = json.loads(
        (tmp_path / "tomtom_incidents_quota.json").read_text())
    assert quota["used"] == 1
    capsys.readouterr()  # drain pull output
    assert main(["--build", "--cache-dir", str(tmp_path)]) == 0
    out, err = capsys.readouterr().out, capsys.readouterr().err
    assert json.loads(out.strip().splitlines()[-1])["fresh"] is True
    assert "test-key-not-real" not in out + err


def test_fresh_cache_skips_request(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    args = ["--pull", "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    assert main(args) == 0
    assert len(calls) == 1  # fresh cache: no second request


def test_quota_cap_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    (tmp_path / "tomtom_incidents_quota.json").write_text(
        json.dumps({"window_start": time.time(), "used": 2}),
        encoding="utf-8")
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []


def test_transport_error_never_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls, status=429)
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 1
    assert not (tmp_path / "tomtom_incidents.json").exists()


@pytest.mark.skipif(not os.environ.get("TOMTOM_API_KEY"),
                    reason="keyed probe: needs TOMTOM_API_KEY in env; "
                           "single polite bbox call to /tmp only, "
                           "never runs in CI")
def test_keyed_probe_single_bbox(tmp_path):
    """Live incident bbox probe for Tallinn (operator key only)."""
    import urllib.request
    key = os.environ["TOMTOM_API_KEY"]
    url = ("https://api.tomtom.com/traffic/services/5/incidentDetails"
           "?bbox=24.55,59.35,24.95,59.49&timeValidityFilter=present"
           "&key=" + key)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
    dest = tmp_path / "probe_incidents.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    assert dest.stat().st_size > 0
