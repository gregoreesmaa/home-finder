"""Tests for scripts/build/batch_tomtom_isochrones.py (issue #670).

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

from batch_tomtom_isochrones import build_table, main  # noqa: E402

FIXTURE_SHED = {"reachableRange": {
    "center": {"latitude": 59.437, "longitude": 24.753},
    "boundary": [
        {"latitude": 59.40, "longitude": 24.70},
        {"latitude": 59.40, "longitude": 24.80},
        {"latitude": 59.47, "longitude": 24.80},
        {"latitude": 59.47, "longitude": 24.70},
    ]}}


def fixture_cells():
    return [{"hub": "city-center", "budget_s": 1800, "band": "rush",
             "ring": [(59.40, 24.70), (59.40, 24.80), (59.47, 24.80)]},
            {"hub": "port", "budget_s": 900, "band": "offpeak", "ring": []}]


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
    payload = json.dumps(body if body is not None else FIXTURE_SHED).encode()

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
    table = build_table(fixture_cells())
    assert table["counts"]["total"] == len(fixture_cells())
    assert table["counts"]["measured"] == 1
    assert table["counts"]["unmeasured"] == 1


def test_fixture_pull_then_build(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 0
    # 5 hubs x 2 budgets x 2 bands = 20 keyed calls = full window.
    assert len(calls) == 20
    cached = list(tmp_path.glob("tomtom_shed_*.json"))
    assert len(cached) == 20
    for p in cached:
        assert "test-key-not-real" not in p.read_text(encoding="utf-8")
    quota = json.loads((tmp_path / "tomtom_sheds_quota.json").read_text())
    assert quota["used"] == 20
    out = capsys.readouterr()
    assert "test-key-not-real" not in out.out
    assert "test-key-not-real" not in out.err


def test_fresh_cache_skips_request(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    args = ["--pull", "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    n_first = len(calls)
    assert main(args) == 0
    assert len(calls) == n_first  # fresh cache: no new requests


def test_quota_cap_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    (tmp_path / "tomtom_sheds_quota.json").write_text(
        json.dumps({"window_start": __import__("time").time(),
                    "used": 20}), encoding="utf-8")
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []


def test_transport_error_never_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls, status=429)
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 1
    assert list(tmp_path.glob("tomtom_shed_*.json")) == []


@pytest.mark.skipif(not os.environ.get("TOMTOM_API_KEY"),
                    reason="keyed probe: needs TOMTOM_API_KEY in env; "
                           "single polite reachable-range call to /tmp "
                           "only, never runs in CI")
def test_keyed_probe_single_shed(tmp_path):
    """Live reachable-range probe for one hub (operator key only)."""
    import urllib.request
    key = os.environ["TOMTOM_API_KEY"]
    url = ("https://api.tomtom.com/routing/1/calculateReachableRange"
           "/59.437,24.7535/json?key=" + key +
           "&timeBudgetInSec=900&traffic=true")
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
    dest = tmp_path / "probe_shed.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    assert dest.stat().st_size > 0
