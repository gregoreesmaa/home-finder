"""Regression: domus.ee adapter parses search HTML offline (no network).

Fixture is a REAL live-markup excerpt (2026-09-08): 2 verbatim cards from
the hub https://domus.ee/objektid/ — a Tartu rental flat (monthly rent,
rooms present) and Muhu land (no rooms cell).
"""

import os

import adapters.domus_ee as domus
from adapters import adapter_contract_check
from adapters.domus_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "domus_search.html")


def test_parse_domus_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "domus-73894235018904380"
    assert rows[0]["source"] == "domus.ee"
    assert rows[0]["source_url"].startswith("https://domus.ee/objektid/")
    assert rows[0]["price"] == 475  # "475 €/kuus" monthly-rent card
    assert "Nõlvaku" in rows[0]["address"]
    assert rows[0]["rooms"] == 2
    assert rows[0]["area_m2"] == 43.2
    assert rows[1]["id"] == "domus-233977266401842900"
    assert rows[1]["price"] == 35000
    assert rows[1]["rooms"] is None  # land card has no rooms cell
    assert rows[1]["area_m2"] == 20000.0


def test_search_url_is_objektid_hub():
    # /kinnisvara 301s to a 2015 blog post — the hub is /objektid/.
    assert domus.SEARCH_URL == "https://domus.ee/objektid/"


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
    assert adapter_contract_check(domus) == []
    assert domus.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in domus.HEADERS["User-Agent"]


def test_fetch_and_scrape_use_mocked_http(monkeypatch):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    monkeypatch.setattr(domus, "fetch_html", lambda *a, **k: html)
    assert "73894235018904380" in domus.fetch_search_html()
    rows = domus.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "domus-73894235018904380"


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(domus, "fetch_html", counting_fetch)
    first = domus.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(domus, "fetch_html", boom)
    second = domus.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1
