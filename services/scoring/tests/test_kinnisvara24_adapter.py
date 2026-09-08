"""Regression: kinnisvara24.ee adapter parses search HTML offline (no network)."""

import os

import adapters.kinnisvara24_ee as k24
from adapters import adapter_contract_check
from adapters.kinnisvara24_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "kinnisvara24_search.html")


def test_contract_clean():
    assert adapter_contract_check(k24) == []
    assert k24.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in k24.HEADERS["User-Agent"]
    assert k24.SELECTORS["card"]


def test_parse_kinnisvara24_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "kinnisvara24-445566"
    assert rows[0]["source"] == "kinnisvara24.ee"
    assert rows[0]["source_url"].startswith("https://kinnisvara24.ee/")
    assert rows[0]["price"] == 259000
    assert "Kotzebue" in rows[0]["address"]
    assert rows[0]["rooms"] == 3
    assert rows[0]["area_m2"] == 64.0
    assert rows[1]["price"] == 189000


def test_parse_empty_html_yields_no_rows():
    assert parse_search_html("<html><body>no results</body></html>") == []


def test_records_match_canonical_shape():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    for row in rows:
        for key in ("id", "source", "source_url", "address", "price", "rooms", "area_m2"):
            assert key in row, "missing %s" % key
        assert row["address"].strip()


def test_fetch_and_scrape_use_mocked_http(monkeypatch):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    monkeypatch.setattr(k24, "fetch_html", lambda *a, **k: html)
    assert "445566" in k24.fetch_search_html()
    rows = k24.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "kinnisvara24-445566"


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(k24, "fetch_html", counting_fetch)
    first = k24.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(k24, "fetch_html", boom)
    second = k24.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1
