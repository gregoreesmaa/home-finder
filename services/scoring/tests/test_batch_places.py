"""Tests for scripts/build/batch_places.py (issue #630).

Hermetic: urlopen is stubbed, env key is faked per-test — no network,
no real key material anywhere. Pins the hard refusal without a key,
the fixture harvest path, TTL short-circuit, and quota enforcement.
"""

import io
import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_places import main  # noqa: E402

FIXTURE = {"places": [
    {"id": "p1",
     "displayName": {"text": "Kohvik Bar"},
     "rating": 4.6, "userRatingCount": 42,
     "priceLevel": "PRICE_LEVEL_INEXPENSIVE",
     "location": {"latitude": 59.437, "longitude": 24.753}},
    {"id": "p2",
     "displayName": {"text": "Unrated Stall"},
     "location": {"latitude": 59.438, "longitude": 24.754}},
]}


class _Resp:
    status = 200

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stub_urlopen_factory(monkeypatch, calls, body=None, status=200):
    payload = json.dumps(body if body is not None else FIXTURE).encode()

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
    monkeypatch.delenv("GOOGLE_PLACES_API_KEY", raising=False)


def test_refuses_without_key(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--lat", "59.437", "--lon", "24.753",
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "GOOGLE_PLACES_API_KEY" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_fixture_harvest_writes_cache_and_spends_quota(tmp_path, monkeypatch,
                                                       capsys):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--lat", "59.437", "--lon", "24.753",
               "--cache-dir", str(tmp_path)])
    assert rc == 0
    assert len(calls) == 1
    cached = list((tmp_path).glob("places_59*.json"))
    assert len(cached) == 1
    quota = json.loads((tmp_path / "places_quota.json").read_text())
    assert quota["used"] == 1
    assert "GOOGLE_PLACES_API_KEY" not in capsys.readouterr().out


def test_fresh_cache_skips_request(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    args = ["--lat", "59.437", "--lon", "24.753",
            "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    assert main(args) == 0
    assert len(calls) == 1  # second run served from TTL cache


def test_exhausted_quota_refuses_without_request(tmp_path, monkeypatch,
                                                 capsys):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "test-key-not-real")
    (tmp_path / "places_quota.json").write_text(json.dumps(
        {"window_start": time.time(), "used": 500}))
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--lat", "59.437", "--lon", "24.753",
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "quota" in capsys.readouterr().err.lower()


def test_key_never_echoed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "sk-test-secret-abc123")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    assert main(["--lat", "59.437", "--lon", "24.753",
                 "--cache-dir", str(tmp_path)]) == 0
    out = capsys.readouterr()
    assert "sk-test-secret-abc123" not in out.out
    assert "sk-test-secret-abc123" not in out.err
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert "sk-test-secret-abc123" not in path.read_text()
