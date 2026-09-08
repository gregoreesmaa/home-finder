"""Regression: uusmaa.ee adapter parses live /pakkumised/ HTML offline (no network)."""

import os

import adapters.uusmaa_ee as uusmaa
from adapters import adapter_contract_check
from adapters.uusmaa_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "uusmaa_search.html")


def test_parse_uusmaa_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "uusmaa-29502"
    assert rows[0]["source"] == "uusmaa.ee"
    assert rows[0]["source_url"].startswith("https://uusmaa.ee/pakkumine/29502-")
    assert rows[0]["price"] == 95000
    assert "Riia mnt 71" in rows[0]["address"]
    assert rows[0]["rooms"] == 3
    assert rows[0]["area_m2"] == 62.4
    assert rows[1]["id"] == "uusmaa-29514"
    assert rows[1]["price"] == 229000
    assert "Telliskivi 49" in rows[1]["address"]
    assert rows[1]["area_m2"] == 43.5


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
    monkeypatch.setattr(uusmaa, "fetch_html", lambda *a, **k: html)
    assert "29502" in uusmaa.fetch_search_html()
    rows = uusmaa.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "uusmaa-29502"


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(uusmaa, "fetch_html", counting_fetch)
    first = uusmaa.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(uusmaa, "fetch_html", boom)
    second = uusmaa.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1


def test_adapter_satisfies_contract():
    assert adapter_contract_check(uusmaa) == []
    assert uusmaa.SEARCH_URL == "https://uusmaa.ee/pakkumised/"
    assert uusmaa.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in uusmaa.HEADERS["User-Agent"]
