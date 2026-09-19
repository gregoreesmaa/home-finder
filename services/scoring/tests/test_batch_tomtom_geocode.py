"""Tests for scripts/build/batch_tomtom_geocode.py (issue #675).

Hermetic: urlopen is stubbed, env key is faked per-test - no network,
no real key material anywhere. Pins the hard refusal without a key on
BOTH paths (--repair and --report), the address-hash cache (ZERO
re-calls for known addresses - urlopen call counts), response
max-age backdating fetched_at (ToS 11.4), --report with a key making
zero requests, the before/after coord-less counts, and quota
enforcement. Unresolvable
addresses are kept (NULL, logged), never dropped. The one keyed probe
at the end is explicitly flagged: skipped without TOMTOM_API_KEY,
single polite call, writes to /tmp only, never runs in CI.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
                                "..", "scripts", "build"))

from batch_tomtom_geocode import main  # noqa: E402

FIXTURE_GEOCODE = {"results": [
    {"position": {"lat": 59.437, "lon": 24.753},
     "address": {"streetName": "Tartu mnt 25", "municipality": "Tallinn"},
     "score": 12.5},
]}

LISTINGS = {"listings": [
    {"id": "L1", "address": "Tartu mnt 25, Tallinn",
     "lat": None, "lon": None},
    {"id": "L2", "address": "Tartu mnt 25, Tallinn",  # same address
     "lat": None, "lon": None},
    {"id": "L3", "address": "Tundmatu tänav 999, Tallinn",
     "lat": None, "lon": None},
    {"id": "L4", "address": "Narva mnt 1, Tallinn",
     "lat": 59.442, "lon": 24.785},  # already geocoded
]}


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


def _stub_urlopen_factory(monkeypatch, calls, bodies=None, status=200,
                         headers=None):
    bodies = bodies if bodies is not None else [FIXTURE_GEOCODE]

    class _R(_Resp):
        pass
    _R.status = status
    if headers is not None:
        _R.headers = _Headers(headers)
    state = {"n": 0}

    def _fake(req, timeout=30):
        calls.append(getattr(req, "full_url", "?"))
        idx = min(state["n"], len(bodies) - 1)
        state["n"] += 1
        body = bodies[idx]
        if body == "EMPTY":
            payload = json.dumps({"results": []}).encode()
        else:
            payload = json.dumps(body).encode()
        return _R(payload)

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake)


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv("TOMTOM_API_KEY", raising=False)


def _write_listings(tmp_path):
    p = tmp_path / "listings.json"
    p.write_text(json.dumps(LISTINGS), encoding="utf-8")
    return str(p)


def test_refuses_without_key_repair(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--repair", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "TOMTOM_API_KEY" in capsys.readouterr().err
    assert [p for p in tmp_path.iterdir() if p.name != "listings.json"] == []


def test_refuses_without_key_report(tmp_path, no_key, capsys, monkeypatch):
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--report", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []
    assert "TOMTOM_API_KEY" in capsys.readouterr().err
    assert [p for p in tmp_path.iterdir() if p.name != "listings.json"] == []


def test_repair_before_after_counts_and_zero_recalls(tmp_path, monkeypatch,
                                                     capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    # L1 resolves; L3 is unresolvable (EMPTY); L2 shares L1's address.
    _stub_urlopen_factory(monkeypatch, calls,
                          bodies=[FIXTURE_GEOCODE, "EMPTY"])
    out_file = str(tmp_path / "repaired.json")
    rc = main(["--repair", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path), "--out-file", out_file])
    assert rc == 0
    # ZERO re-calls: L1 + L3 cost one call each; L2 hits L1's hash.
    assert len(calls) == 2
    counts = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert counts == {"coord_less_before": 3, "repaired": 2,
                      "coord_less_after": 1}
    repaired = json.loads(open(out_file, encoding="utf-8").read())
    by_id = {r["id"]: r for r in repaired["listings"]}
    assert by_id["L1"]["lat"] == 59.437  # repaired via cache hash
    assert by_id["L2"]["lat"] == 59.437  # same hash, zero re-calls
    assert by_id["L3"]["lat"] is None  # unresolvable: kept, NULL
    assert by_id["L4"]["lat"] == 59.442  # untouched
    assert "test-key-not-real" not in open(out_file).read()


def test_second_run_costs_zero_calls_for_resolved(tmp_path, monkeypatch,
                                                     capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls,
                          bodies=[FIXTURE_GEOCODE, "EMPTY", "EMPTY"])
    args = ["--repair", "--listings-file", _write_listings(tmp_path),
            "--cache-dir", str(tmp_path)]
    assert main(args) == 0
    assert len(calls) == 2
    capsys.readouterr()
    assert main(args) == 0
    # Resolved addresses: zero re-calls (hash hits). Only the
    # unresolvable L3 re-costs (EMPTY is never cached by design - it
    # may resolve later).
    assert len(calls) == 3


def test_unresolvable_logged_and_kept(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls, bodies=["EMPTY"])
    rc = main(["--repair", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 0
    err = capsys.readouterr().err
    assert "Tundmatu" in err or "L3" in err  # QA surface, kept listing
    assert "test-key-not-real" not in err


def test_quota_cap_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    (tmp_path / "tomtom_geocode_quota.json").write_text(
        json.dumps({"window_start": __import__("time").time(),
                    "used": 100}), encoding="utf-8")
    rc = main(["--repair", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 2
    assert calls == []


def test_max_age_backdates_fetched_at(tmp_path, monkeypatch):
    """I1: a response max-age below TTL caps the effective TTL.

    Stubbed max-age=3600 (< 30 d TTL): the stored fetched_at is
    backdated by (TTL - max-age), so the entry expires ~3600 s after
    the fetch instead of being over-retained for 30 d (ToS 11.4).
    """
    import time

    import dims_tomtom_geocode as d
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls,
                          bodies=[FIXTURE_GEOCODE, "EMPTY"],
                          headers={"Cache-Control": "max-age=3600"})
    before = time.time()
    rc = main(["--repair", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 0
    cache = json.loads((tmp_path / "tomtom_geocode_cache.json")
                       .read_text(encoding="utf-8"))
    assert len(cache) == 1  # L3 EMPTY never cached; L2 hash-hits L1
    entry = next(iter(cache.values()))
    assert entry["lat"] == 59.437
    expected = before - (d.GEOCODE_TTL_S - 3600)
    assert abs(entry["fetched_at"] - expected) < 120


def test_report_with_key_makes_zero_requests(tmp_path, monkeypatch, capsys):
    """M8: --report with a key costs nothing - no requests, no quota."""
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls)
    rc = main(["--report", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 0
    assert calls == []
    assert not (tmp_path / "tomtom_geocode_quota.json").exists()
    counts = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert counts == {"coord_less_before": 3, "repaired": 0,
                      "coord_less_after": 3}


def test_transport_error_never_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("TOMTOM_API_KEY", "test-key-not-real")
    calls: list = []
    _stub_urlopen_factory(monkeypatch, calls, status=429)
    rc = main(["--repair", "--listings-file", _write_listings(tmp_path),
               "--cache-dir", str(tmp_path)])
    assert rc == 0  # repair completes; nothing resolved, all kept NULL
    assert not (tmp_path / "tomtom_geocode_cache.json").exists()


@pytest.mark.skipif(not os.environ.get("TOMTOM_API_KEY"),
                    reason="keyed probe: needs TOMTOM_API_KEY in env; "
                           "single polite geocode call to /tmp only, "
                           "never runs in CI")
def test_keyed_probe_single_address(tmp_path):
    """Live Structured Geocode probe for one address (operator key)."""
    import urllib.request
    key = os.environ["TOMTOM_API_KEY"]
    url = ("https://api.tomtom.com/search/2/structuredGeocode/.json"
           "?key=" + key + "&countryCode=EE&streetName=Tartu%20mnt%2025"
           "&municipality=Tallinn&limit=1")
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=30) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
    dest = tmp_path / "probe_geocode.json"
    dest.write_text(json.dumps(data), encoding="utf-8")
    assert dest.stat().st_size > 0
