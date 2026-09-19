"""Tests for scripts/build/batch_datex_truckpark.py (issue #686).

Hermetic: urlopen is stubbed, env key is faked per-test - no network,
no real key material anywhere. Pins the hard refusal without a key on
BOTH paths (--pull and --build), the fixture harvest path, TTL
short-circuit, and quota enforcement. The one keyed probe at the end
is explicitly flagged: skipped without DATEX_API_KEY, single polite
GET, writes to /tmp only, never runs in CI.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_datex_truckpark import build_table, main, parse_truckpark  # noqa: E402

FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<d2LogicalModel xmlns="http://datex2.eu/schema/2/2_0">
  <payloadPublication>
    <genericPublication>
      <parkingTablePublicationExtension>
        <parkingTable id="TRUCK_PARKS">
          <parkingRecord id="44444444-5555-4666-8777-888888888888">
            <parkingName>Tallinna ringtee parkla</parkingName>
            <parkingLocation>
              <pointByCoordinates>
                <pointCoordinates>
                  <latitude>59.3800</latitude>
                  <longitude>24.6600</longitude>
                </pointCoordinates>
              </pointByCoordinates>
            </parkingLocation>
            <numberOfSpaces>42</numberOfSpaces>
          </parkingRecord>
        </parkingTable>
      </parkingTablePublicationExtension>
    </genericPublication>
  </payloadPublication>
</d2LogicalModel>
"""


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
    payload = body if body is not None else FIXTURE_XML.encode("utf-8")

    class _R(_Resp):
        pass
    _R.status = status

    def _fake(req, timeout=30):
        calls.append(getattr(req, "full_url", "?"))
        assert req.get_header("X-datex-api-key") == "test-key-not-real"
        return _R(payload)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake)


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("DATEX_API_KEY", raising=False)


def _write_fixture(tmp_path):
    p = tmp_path / "fixture.xml"
    p.write_text(FIXTURE_XML, encoding="utf-8")
    return str(p)


def test_refuses_without_key_pull(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "DATEX_API_KEY" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_refuses_without_key_build(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--build", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "DATEX_API_KEY" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_parses_fixture_site(tmp_path):
    rows = parse_truckpark(_write_fixture(tmp_path))
    assert len(rows) == 1
    assert rows[0]["lat"] == pytest.approx(59.3800)
    assert rows[0]["spaces"] == 42
    table = build_table(rows)
    assert table["counts"] == {"sites": 1, "located": 1, "spaces": 42}


def test_fixture_pull_then_build(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATEX_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 0
    assert len(calls) == 1
    cached = list(tmp_path.glob("datex_truckpark.xml"))
    assert cached
    for p in cached:
        assert "test-key-not-real" not in p.read_text(encoding="utf-8")
    quota = json.loads(
        (tmp_path / "datex_truckpark_quota.json").read_text())
    assert quota["used"] == len(calls)
    out = capsys.readouterr()
    assert "test-key-not-real" not in out.out
    assert "test-key-not-real" not in out.err
    rc = main(["--build", "--cache-dir", str(tmp_path)])
    assert rc == 0
    assert '"sites": 1' in capsys.readouterr().out


def test_fresh_cache_skips_request(tmp_path, monkeypatch):
    monkeypatch.setenv("DATEX_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    args = ["--pull", "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    n_first = len(calls)
    assert main(args) == 0
    assert len(calls) == n_first  # fresh cache: no new requests


def test_quota_cap_refuses(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DATEX_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    (tmp_path / "datex_truckpark_quota.json").write_text(
        json.dumps({"window_start": __import__("time").time(),
                    "used": 4}), encoding="utf-8")
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []


def test_transport_error_never_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("DATEX_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls, status=429)
    rc = main(["--pull", "--cache-dir", str(tmp_path)])
    assert rc == 1
    assert list(tmp_path.glob("datex_truckpark.xml")) == []


@pytest.mark.skipif(not os.environ.get("DATEX_API_KEY"),
                    reason="keyed probe: needs DATEX_API_KEY in env; "
                           "single polite GET to /tmp only, "
                           "never runs in CI")
def test_keyed_probe_single_feed(tmp_path):
    """Live GET of the truckParking feed (operator key only)."""
    import urllib.request
    key = os.environ["DATEX_API_KEY"]
    base = (os.environ.get("DATEX_BASE_URL")
            or "https://tarktee.transpordiamet.ee").rstrip("/")
    req = urllib.request.Request(
        base + "/api/v1/datex/truckParking", method="GET",
        headers={"X-DATEX-API-KEY": key,
                 "Accept": "application/xml"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        body = resp.read()
    assert len(body) > 64
    dest = tmp_path / "probe_truckpark.xml"
    dest.write_bytes(body)
    assert dest.stat().st_size > 0


def test_build_stdout_is_pure_table_json(tmp_path, monkeypatch, capsys):
    """Stdout contract (#776): the pole wrapper redirects stdout into
    built/datex-truckpark/table.json and the web route parses rows+counts,
    so --build stdout must be exactly one JSON doc (the full table)
    and the human ok: status must ride stderr."""
    monkeypatch.setenv("DATEX_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    assert main(["--pull", "--cache-dir", str(tmp_path)]) == 0
    pull_out = capsys.readouterr()
    assert "ok:" in pull_out.err
    assert "ok:" not in pull_out.out
    assert main(["--build", "--cache-dir", str(tmp_path)]) == 0
    build_out = capsys.readouterr()
    table = json.loads(build_out.out)
    assert isinstance(table["rows"], list)
    assert isinstance(table["counts"], dict)
