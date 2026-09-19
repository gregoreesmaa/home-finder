"""Tests for scripts/build/batch_tomtom_matrix.py (issue #669).

Hermetic: urlopen is stubbed, env key is faked per-test - no network,
no real key material anywhere. Pins the hard refusal without a key on
BOTH paths (--pull and --build), the fixture harvest path, TTL
short-circuit, and quota enforcement. The one keyed probe at the end
is explicitly flagged: skipped without TOMTOM_API_KEY, single polite
call, writes to /tmp only, never runs in CI.
"""

import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_tomtom_matrix import build_table, main  # noqa: E402

FIXTURE_AREAS = {"areas": [
    {"area_id": "a1", "lat": 59.437, "lon": 24.753},
    {"area_id": "a2", "lat": 59.438, "lon": 24.754},
]}

FIXTURE_MATRIX = {"results": [
    {"originIndex": 0,
     "summary": {"travelTimeInSeconds": 1500, "trafficDelayInSeconds": 300}},
    {"originIndex": 1,
     "summary": {"travelTimeInSeconds": 900, "trafficDelayInSeconds": 60}},
]}


def fixture_cells():
    return [{"area_id": "a1", "hub": "city-center",
             "rush_s": 1500, "offpeak_s": 1200},
            {"area_id": "a2", "hub": "city-center",
             "rush_s": 900, "offpeak_s": 840}]


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
    payload = json.dumps(body if body is not None else FIXTURE_MATRIX).encode()

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


def _write_areas(tmp_path):
    p = tmp_path / "areas.json"
    p.write_text(json.dumps(FIXTURE_AREAS), encoding="utf-8")
    return str(p)


def test_refuses_without_key_pull(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--pull", "--areas-file", _write_areas(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "TOMTOM_API_KEY" in capsys.readouterr().err
    assert [p for p in tmp_path.iterdir() if p.name != "areas.json"] == []


def test_refuses_without_key_build(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--build", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "TOMTOM_API_KEY" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_builds_table_from_fixture(tmp_path):
    table = build_table(fixture_cells())
    assert table["counts"]["total"] == len(fixture_cells())
    assert table["counts"]["measured"] == 2
    first = table["rows"][0]
    assert first["delay_s"] == 300
    assert first["band"] == "ok"


def test_fixture_pull_then_build(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--pull", "--areas-file", _write_areas(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 0
    # 5 hubs x 2 bands = 10 keyed calls = the full quota window.
    assert len(calls) == 10
    cached = list(tmp_path.glob("tomtom_matrix_*.json"))
    assert cached
    for p in cached:
        assert "test-key-not-real" not in p.read_text(encoding="utf-8")
    quota = json.loads((tmp_path / "tomtom_matrix_quota.json").read_text())
    assert quota["used"] == len(calls)
    out = capsys.readouterr()
    assert "test-key-not-real" not in out.out
    assert "test-key-not-real" not in out.err


def test_fresh_cache_skips_request(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    args = ["--pull", "--areas-file", _write_areas(tmp_path),
            "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    n_first = len(calls)
    assert main(args) == 0
    assert len(calls) == n_first  # fresh cache: no new requests


def test_quota_cap_refuses(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    (tmp_path / "tomtom_matrix_quota.json").write_text(
        json.dumps({"window_start": __import__("time").time(),
                    "used": 10}), encoding="utf-8")
    rc = main(["--pull", "--areas-file", _write_areas(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []


def test_transport_error_never_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls, status=429)
    rc = main(["--pull", "--areas-file", _write_areas(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 1
    assert list(tmp_path.glob("tomtom_matrix_*.json")) == []


@pytest.mark.skipif(not os.environ.get("TOMTOM_API_KEY"),
                    reason="keyed probe: needs TOMTOM_API_KEY in env; "
                           "single polite 1x1 call to /tmp only, "
                           "never runs in CI")
def test_keyed_probe_single_cell(tmp_path):
    """Live 1-origin x 1-hub matrix probe (operator key only)."""
    import urllib.request
    key = os.environ["TOMTOM_API_KEY"]
    body = json.dumps({
        "origins": [{"point": {"latitude": 59.437, "longitude": 24.753}}],
        "destinations": [{"point": {"latitude": 59.4215,
                                    "longitude": 24.7996}}],
        "options": {"traffic": True, "travelMode": "car"},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tomtom.com/routing/matrix/2?key=" + key, data=body,
        method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
    dest = tmp_path / "probe_matrix.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    assert dest.stat().st_size > 0
