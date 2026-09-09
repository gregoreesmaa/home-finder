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
    assert rows[0]["image_url"] == "https://img-kv.ee/image/object/4/0699/141030699.jpg"
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


def test_id_from_project_style_urls():
    assert kv_ee._id_from_url("https://www.kv.ee/muua-korter-hinnat-3896526") == "kv-3896526"
    assert kv_ee._id_from_url("https://www.kv.ee/a-b-1234567.html") == "kv-1234567"
    # date slugs and articles must not become ids
    assert kv_ee._id_from_url("https://www.kv.ee/19-08-2026-kliendipaev") is None
    assert kv_ee._id_from_url("https://www.kv.ee/kinnisvaraturu-ulevaade") is None
    assert kv_ee._id_from_url("") is None


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


def test_category_urls_paginate_by_start():
    assert kv_ee.build_search_url("", "/korterid-muuk", 0).endswith("/korterid-muuk?start=0")
    assert kv_ee.build_search_url("", "/majad-muuk", 2).endswith("/majad-muuk?start=100")


def test_scrape_walks_both_categories_page_by_page(monkeypatch):
    """#67 paginates, #69 covers houses: 2 cats x page_limit fetches."""
    html = _fixture_html()
    seen = []
    monkeypatch.setattr(kv_ee, "_fetch_url", lambda u: seen.append(u) or html)
    rows = kv_ee.scrape("", page_limit=2, delay_s=0)
    assert seen == [
        "https://www.kv.ee/korterid-muuk?start=0",
        "https://www.kv.ee/korterid-muuk?start=50",
        "https://www.kv.ee/majad-muuk?start=0",
        "https://www.kv.ee/majad-muuk?start=50",
    ]
    assert len(rows) == 8  # 2 fixture rows x 4 page fetches
    assert {r["id"] for r in rows} == {"kv-3905636", "kv-3879789"}


def test_scrape_query_mode_keeps_legacy_single_search(monkeypatch):
    html = _fixture_html()
    monkeypatch.setattr(kv_ee, "fetch_html", lambda *a, **k: html)
    rows = kv_ee.scrape("haiba", delay_s=0)
    assert [r["id"] for r in rows] == ["kv-3905636", "kv-3879789"]


def test_fetch_and_scrape_use_mocked_http(monkeypatch):
    html = _fixture_html()
    monkeypatch.setattr(kv_ee, "fetch_html", lambda *a, **k: html)
    assert "3905636" in kv_ee.fetch_search_html()
    rows = kv_ee.scrape(delay_s=0)
    assert len(rows) == 4  # 2 fixture rows x apartments + houses (#69)
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


def test_fetch_retries_chrome_until_results_arrive(monkeypatch):
    html = _fixture_html()
    challenge = "<html><head><title>Just a moment...</title></head></html>"

    def blocked(*args, **kwargs):
        raise httpx.HTTPStatusError("403", request=None, response=None)  # type: ignore[arg-type]

    attempts = iter([challenge, html])
    monkeypatch.setattr(kv_ee, "fetch_html", blocked)
    monkeypatch.setattr(kv_ee, "fetch_html_via_chrome", lambda url: next(attempts))
    rows = kv_ee.scrape("haiba")
    assert [r["id"] for r in rows] == ["kv-3905636", "kv-3879789"]


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
    first = kv_ee.scrape(cache_dir=str(tmp_path), delay_s=0)
    assert len(first) == 4 and len(calls) == 2  # apartments + houses pages

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(kv_ee, "fetch_html", boom)
    second = kv_ee.scrape(cache_dir=str(tmp_path), delay_s=0)
    assert second == first and len(calls) == 2
