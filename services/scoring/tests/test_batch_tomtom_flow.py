"""Tests for scripts/build/batch_tomtom_flow.py (issue #671).

Hermetic: urlopen is stubbed, env key is faked per-test - no network,
no real key material anywhere. Pins the hard refusal without a key on
BOTH paths (--pull and --build), the fixture harvest path, TTL
short-circuit, and quota enforcement. The one keyed probe at the end
is explicitly flagged: skipped without TOMTOM_API_KEY, single polite
call, writes to /tmp only, never runs in CI.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_tomtom_flow import build_table, main  # noqa: E402

FIXTURE_FLOW = {"flowSegmentData": {
    "currentSpeed": 28, "freeFlowSpeed": 50,
    "currentTravelTime": 120, "freeFlowTravelTime": 70,
    "roadClosure": False}}


def fixture_cells():
    return [{"probe_id": "tartu-mnt", "band": "morning",
             "current": 28, "freeflow": 50},
            {"probe_id": "parnu-mnt", "band": "morning",
             "current": 48, "freeflow": 50},
            {"probe_id": "broken", "band": "morning",
             "current": None, "freeflow": None}]


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
    payload = json.dumps(body if body is not None else FIXTURE_FLOW).encode()

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
    rc = main(["--pull", "--band", "morning",
               "--cache-dir", str(tmp_path)])
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
    table = build_table(fixture_cells())
    assert table["counts"]["total"] == len(fixture_cells())
    assert table["counts"]["measured"] == 2
    assert table["counts"]["unmeasured"] == 1
    bands = {r["probe_id"]: r["speed_band"] for r in table["rows"]}
    assert bands["tartu-mnt"] == "slow"
    assert bands["parnu-mnt"] == "free"


def test_fixture_pull_then_build(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--pull", "--band", "morning",
               "--cache-dir", str(tmp_path)])
    assert rc == 0
    # 10 default probes x 1 band = 10 keyed calls.
    assert len(calls) == 10
    cached = list(tmp_path.glob("tomtom_flow_*_morning.json"))
    assert len(cached) == 10
    for p in cached:
        assert "test-key-not-real" not in p.read_text(encoding="utf-8")
    quota = json.loads((tmp_path / "tomtom_flow_quota.json").read_text())
    assert quota["used"] == 10
    out = capsys.readouterr()
    assert "test-key-not-real" not in out.out
    assert "test-key-not-real" not in out.err


def test_build_with_calibration(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    assert main(["--pull", "--band", "morning",
                 "--cache-dir", str(tmp_path)]) == 0
    delay = tmp_path / "delay.json"
    delay.write_text(json.dumps({"factors": {"tartu-mnt": 1.8}}),
                     encoding="utf-8")
    rc = main(["--build", "--band", "morning", "--delay-file", str(delay),
               "--cache-dir", str(tmp_path)])
    assert rc == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["counts"]["measured"] == 10
    assert out["calibration"]["disagree"] == 1  # flow slow vs delay jammed


def test_fresh_cache_skips_request(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    args = ["--pull", "--band", "morning", "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    n_first = len(calls)
    assert main(args) == 0
    assert len(calls) == n_first


def test_quota_cap_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    (tmp_path / "tomtom_flow_quota.json").write_text(
        json.dumps({"window_start": __import__("time").time(),
                    "used": 80}), encoding="utf-8")
    rc = main(["--pull", "--band", "morning",
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []


def test_transport_error_never_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls, status=429)
    rc = main(["--pull", "--band", "morning",
               "--cache-dir", str(tmp_path)])
    assert rc == 1
    assert list(tmp_path.glob("tomtom_flow_*_morning.json")) == []


@pytest.mark.skipif(not os.environ.get("TOMTOM_API_KEY"),
                    reason="keyed probe: needs TOMTOM_API_KEY in env; "
                           "single polite flow-segment call to /tmp only, "
                           "never runs in CI")
def test_keyed_probe_single_segment(tmp_path):
    """Live flow-segment probe for one arterial point (operator key)."""
    import urllib.request
    key = os.environ["TOMTOM_API_KEY"]
    url = ("https://api.tomtom.com/traffic/services/4/flowSegmentData"
           "/absolute/10/json?point=59.428,24.78&key=" + key)
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
    dest = tmp_path / "probe_flow.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    assert dest.stat().st_size > 0
