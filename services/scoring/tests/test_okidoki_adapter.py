"""Regression: okidoki.ee adapter parses search HTML offline (no network).

okidoki is a general classifieds board: the second fixture card is a
non-RE ad, so rooms/area_m2 stay None while the canonical shape holds.
"""

import os

import adapters.okidoki_ee as ok
from adapters import adapter_contract_check
from adapters.okidoki_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "okidoki_search.html")


def test_contract_clean():
    assert adapter_contract_check(ok) == []
    assert ok.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in ok.HEADERS["User-Agent"]
    assert ok.SELECTORS["card"]


def test_parse_okidoki_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "okidoki-556677"
    assert rows[0]["source"] == "okidoki.ee"
    assert rows[0]["source_url"].startswith("https://www.okidoki.ee/")
    assert rows[0]["price"] == 155000
    assert "Kotzebue" in rows[0]["address"]
    assert rows[0]["rooms"] == 2
    assert rows[0]["area_m2"] == 45.0
    # general-classified card: price + title map, detail fields stay None
    assert rows[1]["id"] == "okidoki-889900"
    assert rows[1]["price"] == 250
    assert rows[1]["rooms"] is None
    assert rows[1]["area_m2"] is None


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
    monkeypatch.setattr(ok, "fetch_html", lambda *a, **k: html)
    assert "556677" in ok.fetch_search_html()
    rows = ok.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "okidoki-556677"


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(ok, "fetch_html", counting_fetch)
    first = ok.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(ok, "fetch_html", boom)
    second = ok.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1
