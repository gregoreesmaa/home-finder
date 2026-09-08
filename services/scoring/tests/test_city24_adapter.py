"""Regression: city24.ee adapter parses the public search JSON API offline.

The /en/for-sale page is a JS shell, so the adapter queries the same JSON
endpoint the site's own frontend uses (no key, no login). Fixture is a
PII-scrubbed 2-item excerpt of a real payload (broker/office/image blobs
removed); no network in tests.
"""

import json
import os

import adapters.city24_ee as city24
from adapters.city24_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "city24_search.json")


def payload():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_parse_city24_json_fixture():
    rows = parse_search_html(payload())
    assert len(rows) == 2
    assert rows[0]["id"] == "city24-2467435"
    assert rows[0]["source"] == "city24.ee"
    assert rows[0]["source_url"] == (
        "https://www.city24.ee/et_EE/kinnisvara-otsing/objekt/2467435"
    )
    assert rows[0]["price"] == 209900
    assert "Kopli tn 61" in rows[0]["address"]
    assert rows[0]["rooms"] == 3
    assert rows[0]["area_m2"] == 69.5
    assert rows[0]["county"] == "Harju maakond"
    assert rows[0]["lat"] is not None and rows[0]["lon"] is not None


def test_parse_garbage_yields_no_rows():
    assert parse_search_html("<html><body>no results</body></html>") == []
    assert parse_search_html("[not json") == []
    assert parse_search_html('{"not": "a list"}') == []


def test_records_match_canonical_shape():
    for row in parse_search_html(payload()):
        for key in ("id", "source", "source_url", "address", "price", "rooms", "area_m2"):
            assert key in row, "missing %s" % key
        assert row["address"].strip()


def test_fetch_queries_both_object_types(monkeypatch):
    seen = []

    def capture(url, params=None, **kwargs):
        seen.append((url, dict(params or {})))
        return "[]"

    monkeypatch.setattr(city24, "fetch_html", capture)
    city24.fetch_search_html()
    assert len(seen) == 2  # apartments + houses, page 1 each
    assert all(u == city24.API_URL for u, _ in seen)
    types = sorted(p["object_types[]"] for _, p in seen)
    assert types == [1, 2]
    assert all("page" in p and p["page"] == 1 for _, p in seen)


def test_scrape_combines_both_pages(monkeypatch):
    def fake_fetch(url, params=None, **kwargs):
        return payload()  # 2 items per object type

    monkeypatch.setattr(city24, "fetch_html", fake_fetch)
    rows = city24.scrape()
    assert len(rows) == 4
    assert {r["id"] for r in rows} == {"city24-2467435", "city24-2366094"}
