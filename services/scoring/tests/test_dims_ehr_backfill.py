"""Hermetic unit tests for the EHR avaandmed backfill module (issue #537).

No network: fetch paths are tested cache-first / stubbed-never-remote.
Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_ehr_backfill.py -q
"""

import os

import pytest

import dims_ehr_backfill as B
from dims_ehr_backfill import (
    av_report_url,
    cache_is_fresh,
    fetch_av_report,
)


def test_interface_list_from_spec():
    # 16 /info/reports keys incl. buildings + energy labels (spec v1.7.1).
    assert len(B.AV_REPORT_KEYS) == 16
    assert "eh_ehitised" in B.AV_REPORT_KEYS
    assert "eh_ehitis_osad" in B.AV_REPORT_KEYS
    assert B.ENERGY_REPORT_KEY == "hoone_energia_margised"
    assert B.ENERGY_REPORT_KEY in B.AV_REPORT_KEYS
    assert B.AV_API_VERSION == "1.7.1"
    # Documented servers kept as provenance (live 404s — dated negative).
    assert set(B.AV_SERVERS) == {"dev", "test", "live"}
    assert B.AV_SERVERS["live"].rstrip("/").endswith("/api/av/v1")
    assert B.SWAGGER_UI_URL == "https://swaggerui.ehr.ee/"


def test_backfill_capability_map():
    # Each capability leg points at a real spec key (no invented keys).
    for _leg, key in B.EHR_BACKFILL_REPORTS.items():
        assert key in B.AV_REPORT_KEYS
    assert B.EHR_BACKFILL_REPORTS["energy_labels"] == B.ENERGY_REPORT_KEY


def test_av_report_url():
    url = av_report_url("http://livekluster.ehr.ee/api/av/v1",
                        "eh_ehitised")
    assert url == ("http://livekluster.ehr.ee/api/av/v1/info/reports/"
                   "eh_ehitised")
    # Trailing slash tolerated; energy key builds too.
    assert av_report_url("https://devkluster.ehr.ee/api/av/v1/",
                         "hoone_energia_margised").endswith(
        "/info/reports/hoone_energia_margised")
    # Empty base: no anonymous route verified — ValueError, never a guess.
    with pytest.raises(ValueError):
        av_report_url("", "eh_ehitised")
    # Unknown key: never invent interface knowledge.
    with pytest.raises(ValueError):
        av_report_url("https://devkluster.ehr.ee/api/av/v1", "ehitised_bulk")


def test_cache_is_fresh(tmp_path):
    import time
    p = str(tmp_path / "x.json")
    assert cache_is_fresh(p) is False  # missing file
    with open(p, "w") as fh:
        fh.write("{}")
    assert cache_is_fresh(p, ttl_days=30) is True
    old = time.time() - 31 * 86400.0
    os.utime(p, (old, old))
    assert cache_is_fresh(p, ttl_days=30) is False


def test_fetch_av_report_cache_first_makes_no_request(tmp_path, monkeypatch):
    cached = tmp_path / "ehr-av-eh_ehitised.json"
    cached.write_text('{"cached": true}', encoding="utf-8")

    def _boom(*a, **k):
        raise AssertionError("no request on a fresh cache hit")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    text = fetch_av_report("eh_ehitised", "http://example.invalid",
                           cache_dir=str(tmp_path))
    assert text == '{"cached": true}'


def test_fetch_av_report_empty_base_raises_without_network(
        tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("empty base must raise before any request")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(ValueError):
        fetch_av_report("eh_ehitised", "", cache_dir=str(tmp_path))
    with pytest.raises(ValueError):
        fetch_av_report("eh_ehitised", None, cache_dir=str(tmp_path))


def test_fetch_av_report_unknown_key_raises_without_network(
        tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("unknown key must raise before any request")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    with pytest.raises(ValueError):
        fetch_av_report("ehitised_bulk", "http://example.invalid",
                        cache_dir=str(tmp_path))


def test_fetch_av_report_errors_never_cached(tmp_path, monkeypatch):
    import urllib.request

    def _fail(*a, **k):
        raise IOError("simulated transport error")

    monkeypatch.setattr(urllib.request, "urlopen", _fail)
    with pytest.raises(IOError):
        fetch_av_report("eh_ehitised", "http://example.invalid",
                        cache_dir=str(tmp_path))
    # Nothing cached from the failed pull (stale cache left untouched —
    # here: no cache file created at all).
    assert list(tmp_path.iterdir()) == []
