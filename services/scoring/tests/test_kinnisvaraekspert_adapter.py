"""Regression: kinnisvaraekspert.ee adapter parses the live index offline.

Covers GitHub issue #68. Fixture holds 2 verbatim cards from the saved live
/objektid/ index (2026-09-09): one sale apartment, one rental garage.
Fully offline: network paths use monkeypatched fetch_html.
"""

import os

import adapters.kinnisvaraekspert_ee as ekspert
from adapters import adapter_contract_check

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "kinnisvaraekspert_search.html")


def _fixture_html():
    with open(FIXTURE, encoding="utf-8") as f:
        return f.read()


def test_adapter_contract_clean():
    assert adapter_contract_check(ekspert) == []
    assert ekspert.SOURCE == "kinnisvaraekspert.ee"
    assert ekspert.SEARCH_URL.startswith("https://")


def test_parse_fixture_cards():
    rows = ekspert.parse_search_html(_fixture_html())
    assert len(rows) == 2
    sale, rent = rows
    assert sale["id"] == "ekspert-156286"
    assert sale["source"] == "kinnisvaraekspert.ee"
    assert sale["source_url"] == "https://kinnisvaraekspert.ee/objektid/156286"
    assert sale["price"] == 86000  # &nbsp; thousand separator parsed
    assert sale["rooms"] == 1
    assert sale["area_m2"] == 25.0
    assert sale["address"] == "Oja 118, Pärnu maakond, Pärnu linn"
    assert rent["id"] == "ekspert-156296"
    assert rent["price"] == 750
    assert "Saha-Loo tee 36" in rent["address"]
    assert "Harju maakond" in rent["address"]


def test_parse_empty_html_yields_no_rows():
    assert ekspert.parse_search_html("") == []
    assert ekspert.parse_search_html("<html><body>no results</body></html>") == []


def test_scrape_uses_cached_fetch(monkeypatch):
    html = _fixture_html()
    monkeypatch.setattr(ekspert, "fetch_html", lambda *a, **k: html)
    rows = ekspert.scrape()
    assert [r["id"] for r in rows] == ["ekspert-156286", "ekspert-156296"]


def test_mixed_index_types_as_unknown(monkeypatch):
    """Like domus: marker-free ekspert URLs type as unknown, never as sale."""
    import ingest

    assert ingest.PORTAL_DEFAULT_TYPE["adapters.kinnisvaraekspert_ee"] is None
    assert ingest.deal_type("https://kinnisvaraekspert.ee/objektid/156286",
                            "adapters.kinnisvaraekspert_ee") == "unknown"
