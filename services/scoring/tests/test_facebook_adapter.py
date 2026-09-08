"""Regression: facebook adapter is paste-in only (no automated fetching)."""

import os

import pytest

import adapters.facebook as facebook
from adapters import adapter_contract_check
from adapters.facebook import parse_pasted

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "facebook_paste.txt")


def test_parse_pasted_fixture_yields_canonical_record():
    with open(FIXTURE, encoding="utf-8") as f:
        row = parse_pasted(
            f.read(), source_url="https://www.facebook.com/marketplace/item/1234567890123456"
        )
    assert row["source"] == "facebook"
    assert row["source_url"] == "https://www.facebook.com/marketplace/item/1234567890123456"
    assert row["price"] == 285000
    assert "Kotzebue" in row["address"]
    assert row["rooms"] == 3
    assert row["area_m2"] == 68.0
    for key in ("id", "source", "source_url", "address", "price", "rooms", "area_m2"):
        assert key in row, "missing %s" % key
    assert row["id"].startswith("facebook-")


def test_parse_pasted_is_deterministic():
    text = "Kotzebue 12, Tallinn\n285 000 €"
    assert parse_pasted(text) == parse_pasted(text)


def test_parse_pasted_rejects_missing_price():
    with pytest.raises(ValueError):
        parse_pasted("Kotzebue 12, Tallinn\nno price here")


def test_parse_pasted_rejects_empty_text():
    with pytest.raises(ValueError):
        parse_pasted("   \n  ")


def test_no_automated_fetch_by_design():
    with pytest.raises(NotImplementedError):
        facebook.fetch_search_html()
    assert facebook.parse_search_html("<html><body>anything</body></html>") == []


def test_adapter_satisfies_contract():
    assert adapter_contract_check(facebook) == []
    assert facebook.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in facebook.HEADERS["User-Agent"]
