"""Regression: 1partner.ee adapter parses search HTML offline (no network)."""

import os

import adapters.one_partner_ee as one_partner
from adapters import adapter_contract_check
from adapters.one_partner_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "one_partner_search.html")


def test_parse_one_partner_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2  # the priceless blog teaser is skipped
    assert rows[0]["id"] == "1partner-660101"
    assert rows[0]["source"] == "1partner.ee"
    assert rows[0]["source_url"].startswith("https://www.1partner.ee/")
    assert rows[0]["price"] == 289000
    assert "Kotzebue" in rows[0]["address"]
    assert rows[0]["rooms"] == 3
    assert rows[0]["area_m2"] == 71.0
    assert rows[1]["price"] == 155000


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
    monkeypatch.setattr(one_partner, "fetch_html", lambda *a, **k: html)
    assert "660101" in one_partner.fetch_search_html()
    rows = one_partner.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "1partner-660101"


def test_fetch_sends_no_query_params_per_robots(monkeypatch):
    seen = {}

    def spy(url, params=None, **kwargs):
        seen["url"] = url
        seen["params"] = params
        return "<html></html>"

    monkeypatch.setattr(one_partner, "fetch_html", spy)
    one_partner.fetch_search_html(query="tallinn")
    assert seen["params"] == {}
    assert "?" not in seen["url"]


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(one_partner, "fetch_html", counting_fetch)
    first = one_partner.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(one_partner, "fetch_html", boom)
    second = one_partner.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1


def test_adapter_satisfies_contract():
    assert adapter_contract_check(one_partner) == []
    assert one_partner.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in one_partner.HEADERS["User-Agent"]
