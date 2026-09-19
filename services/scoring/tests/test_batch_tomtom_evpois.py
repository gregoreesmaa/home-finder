"""Tests for scripts/build/batch_tomtom_evpois.py (issue #673).

Hermetic: urlopen is stubbed, env key is faked per-test - no network,
no real key material anywhere. Pins the hard refusal without a key on
BOTH paths (--pull and --build), the fixture harvest path, TTL
short-circuit, dedupe, and quota enforcement. The one keyed probe at
the end is explicitly flagged: skipped without TOMTOM_API_KEY,
single polite call, writes to /tmp only, never runs in CI.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_tomtom_evpois import build_table, main  # noqa: E402

FIXTURE_SEARCH = {"results": [
    {"id": "ev1",
     "poi": {"name": "Laadija A",
             "chargingInformation": {"connectors": [
                 {"connectorType": "CCS"}, {"connectorType": "Type2"}]}},
     "position": {"lat": 59.437, "lon": 24.753}},
    {"id": "ev2",
     "poi": {"name": "Laadija B"},
     "position": {"lat": 59.438, "lon": 24.754}},
]}


def fixture_cells():
    return [{"poi_id": "ev1", "name": "Laadija A",
             "lat": 59.437, "lon": 24.753,
             "connectors": ["CCS", "Type2"]},
            {"poi_id": "ev2", "name": "Laadija B",
             "lat": 59.438, "lon": 24.754, "connectors": None},
            {"poi_id": "ev3", "name": "Asukohata",
             "lat": None, "lon": None, "connectors": None}]


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
                         else FIXTURE_SEARCH).encode()

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
    assert table["counts"]["geocoded"] == 2
    assert table["counts"]["coord_less"] == 1


def test_fixture_pull_then_build_dedupes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    assert main(["--pull", "--cache-dir", str(tmp_path)]) == 0
    # 6 default tiles = 6 keyed calls (quota window is 20).
    assert len(calls) == 6
    assert "categorySet=7309" in calls[0]
    cached = list(tmp_path.glob("tomtom_ev_*.json"))
    assert len(cached) == 6
    for p in cached:
        assert "test-key-not-real" not in p.read_text(encoding="utf-8")
    capsys.readouterr()  # drain pull output (+ unverified-category warning)
    assert main(["--build", "--cache-dir", str(tmp_path)]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    # Same 2 POIs in every tile fixture -> deduped to 2.
    assert out == {"total": 2, "geocoded": 2, "coord_less": 0}


def test_fresh_cache_skips_request(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    args = ["--pull", "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    assert main(args) == 0
    assert len(calls) == 6


def test_quota_cap_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    (tmp_path / "tomtom_evpois_quota.json").write_text(
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
    assert list(tmp_path.glob("tomtom_ev_*.json")) == []


@pytest.mark.skipif(not os.environ.get("TOMTOM_API_KEY"),
                    reason="keyed probe: needs TOMTOM_API_KEY in env; "
                           "single polite search call to /tmp only, "
                           "never runs in CI")
def test_keyed_probe_single_tile(tmp_path):
    """Live EV-POI probe for one tile (operator key only)."""
    import urllib.request
    key = os.environ["TOMTOM_API_KEY"]
    url = ("https://api.tomtom.com/search/2/nearbySearch/.json"
           "?key=" + key +
           "&lat=59.437&lon=24.7535&radius=4000&categorySet=7309&limit=5")
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
    dest = tmp_path / "probe_ev.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    assert dest.stat().st_size > 0
