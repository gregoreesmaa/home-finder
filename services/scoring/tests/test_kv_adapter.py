"""Regression: kv.ee adapter parses the live search markup offline (no network).

Fixture mirrors the verified live page (2026-09-08): an ItemList JSON-LD
block with one Apartment per hit plus data-object-id DOM anchors. kv.ee
gates scripted HTTP on TLS fingerprint, so fetch falls back to genuine
headless Chrome on HTTP error -- covered below with mocks.
"""

import os

import httpx

import adapters.kv_ee as kv_ee
from adapters.kv_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "kv_search.html")


def _fixture_html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_parse_kv_search_fixture():
    rows = parse_search_html(_fixture_html())
    assert len(rows) == 2
    assert rows[0]["id"] == "kv-3905636"
    assert rows[0]["source"] == "kv.ee"
    assert rows[0]["source_url"].startswith("https://www.kv.ee/")
    assert rows[0]["source_url"].endswith("-3905636.html")
    assert rows[0]["price"] == 45000
    assert rows[0]["rooms"] == 2
    assert rows[0]["area_m2"] == 46.9
    assert "Sireli" in rows[0]["address"]
    assert rows[1]["id"] == "kv-3879789"
    assert rows[1]["price"] == 55000
    assert rows[1]["rooms"] == 4
    assert rows[1]["area_m2"] == 77.9
    assert "Pihlaka" in rows[1]["address"]


def test_parse_empty_html_yields_no_rows():
    assert parse_search_html("<html><body>no results</body></html>") == []


def test_parse_challenge_page_yields_no_rows():
    html = (
        "<html><head><title>KV | Vabandame, meie süsteem tuvastas "
        "võimaliku tõrke teie veebilehitsejas.</title></head>"
        "<body>challenge</body></html>"
    )
    assert parse_search_html(html) == []


def test_parse_dom_fallback_without_jsonld():
    html = (
        '<article class="object-card" data-object-id="555" '
        'data-object-url="/korter-muua-test-555.html">'
        "<h3>Test tn 1, Tallinn</h3>"
        '<div class="price">99 000 €</div></article>'
    )
    (row,) = parse_search_html(html)
    assert row["id"] == "kv-555"
    assert row["price"] == 99000
    assert "Test tn 1" in row["address"]


def test_search_url_uses_sale_route():
    url = kv_ee.build_search_url("haiba")
    assert url.startswith("https://www.kv.ee/et/search")
    assert "deal_type=1" in url
    assert "keyword=haiba" in url


def test_fetch_and_scrape_use_mocked_http(monkeypatch):
    html = _fixture_html()
    monkeypatch.setattr(kv_ee, "fetch_html", lambda *a, **k: html)
    assert "3905636" in kv_ee.fetch_search_html()
    rows = kv_ee.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "kv-3905636"


def test_fetch_falls_back_to_chrome_on_http_block(monkeypatch):
    html = _fixture_html()

    def blocked(*args, **kwargs):
        raise httpx.HTTPStatusError("403", request=None, response=None)  # type: ignore[arg-type]

    calls = []
    monkeypatch.setattr(kv_ee, "fetch_html", blocked)
    monkeypatch.setattr(
        kv_ee, "fetch_html_via_chrome", lambda url: calls.append(url) or html
    )
    rows = kv_ee.scrape("haiba")
    assert [r["id"] for r in rows] == ["kv-3905636", "kv-3879789"]
    assert calls and "keyword=haiba" in calls[0]


def test_records_match_canonical_shape():
    rows = parse_search_html(_fixture_html())
    for row in rows:
        for key in ("id", "source", "source_url", "address", "price"):
            assert key in row, "missing %s" % key
        assert row["address"].strip()
        # detail fields exist (None when the card omits them)
        assert "rooms" in row and "area_m2" in row


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    html = _fixture_html()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(kv_ee, "fetch_html", counting_fetch)
    first = kv_ee.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(kv_ee, "fetch_html", boom)
    second = kv_ee.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1
