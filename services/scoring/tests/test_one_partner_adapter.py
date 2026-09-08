"""Regression: 1partner.ee adapter parses live /pakkumised HTML offline (no network)."""

import os

import adapters.one_partner_ee as one_partner
from adapters import adapter_contract_check
from adapters.one_partner_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "one_partner_search.html")


def test_parse_one_partner_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "1partner-11920"
    assert rows[0]["source"] == "1partner.ee"
    assert rows[0]["source_url"].startswith("https://www.1partner.ee/pakkumised/")
    assert rows[0]["price"] == 120000
    assert "Vilde tee 65" in rows[0]["address"]
    assert rows[0]["rooms"] == 2
    assert rows[0]["area_m2"] == 47.0
    # second card is a rental: bare room count after the "Tubade arv" label
    assert rows[1]["id"] == "1partner-11919"
    assert rows[1]["price"] == 400
    assert "Heina tn 15" in rows[1]["address"]
    assert rows[1]["rooms"] == 1
    assert rows[1]["area_m2"] == 28.0


def test_parse_empty_html_yields_no_rows():
    assert parse_search_html("<html><body>no results</body></html>") == []


def test_priceless_teaser_is_skipped():
    card = (
        '<div class="catalog-list-item">'
        '<a href="/pakkumised/some-flat-p.12345">'
        '<div class="location">Tallinn</div>'
        "</a></div>"
    )
    assert parse_search_html(card) == []


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
    assert "11920" in one_partner.fetch_search_html()
    rows = one_partner.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "1partner-11920"


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
    assert one_partner.SEARCH_URL == "https://www.1partner.ee/pakkumised"
    assert one_partner.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in one_partner.HEADERS["User-Agent"]
