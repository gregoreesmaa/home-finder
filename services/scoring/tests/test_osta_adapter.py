"""Regression: osta.ee adapter parses search HTML offline (no network)."""

import os

import adapters.osta_ee as osta
from adapters import adapter_contract_check
from adapters.osta_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "osta_search.html")


def test_parse_osta_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "osta-555111"
    assert rows[0]["source"] == "osta.ee"
    assert rows[0]["source_url"].startswith("https://www.osta.ee/")
    # buy-now price wins over the current bid on card 1
    assert rows[0]["price"] == 285000
    assert "Kotzebue" in rows[0]["address"]
    assert rows[0]["rooms"] == 3
    assert rows[0]["area_m2"] == 68.0
    assert rows[1]["price"] == 149000


def test_parse_empty_html_yields_no_rows():
    assert parse_search_html("<html><body>no results</body></html>") == []


def test_records_match_canonical_shape():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    for row in rows:
        for key in ("id", "source", "source_url", "address", "price", "rooms", "area_m2"):
            assert key in row, "missing %s" % key
        assert row["address"].strip()


def test_adapter_satisfies_contract():
    assert adapter_contract_check(osta) == []
    assert osta.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in osta.HEADERS["User-Agent"]


def test_fetch_and_scrape_use_mocked_http(monkeypatch):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    monkeypatch.setattr(osta, "fetch_html", lambda *a, **k: html)
    assert "555111" in osta.fetch_search_html()
    rows = osta.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "osta-555111"


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(osta, "fetch_html", counting_fetch)
    first = osta.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(osta, "fetch_html", boom)
    second = osta.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1
