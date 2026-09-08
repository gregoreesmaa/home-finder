"""Regression: kv.ee adapter parses search HTML offline (no network)."""

import os

from adapters.kv_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "kv_search.html")


def test_parse_kv_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "kv-1234567"
    assert rows[0]["source"] == "kv.ee"
    assert rows[0]["source_url"].startswith("https://kv.ee/")
    assert rows[0]["price"] == 285000
    assert "Kotzebue" in rows[0]["address"]
    assert rows[1]["price"] == 149000


def test_parse_empty_html_yields_no_rows():
    assert parse_search_html("<html><body>no results</body></html>") == []
