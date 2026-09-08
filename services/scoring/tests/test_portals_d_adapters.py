"""Regression: portals-D adapters (oberhaus/arcovara/lvm/remax) parse offline.

Covers GitHub issues #16-#19. Fully offline: fixtures are small real-markup
excerpts (not scraped dumps); network paths use monkeypatched fetch_html.
Shared files (test_portal_stubs.py, test_adapters_base.py) are left
untouched so sibling portal batches merge cleanly. The remax fixture pair
(remax_search.html + remax_search.json) holds the same 2 REAL listings from
the hub's JSON endpoint in both rendered-card and raw-JSON form.
"""

import importlib
import json
import os

import pytest
from adapters import adapter_contract_check

PORTALS = {
    # module -> (SOURCE, id prefix, fixture, first-row expectations)
    "adapters.oberhaus_ee": (
        "oberhaus.ee", "oberhaus-551201", "oberhaus_search.html",
        {"address": "Pärnu mnt 88", "price": 345000, "rooms": 3, "area_m2": 74.5,
         "second_price": 189000},
    ),
    "adapters.arcovara_ee": (
        "arcovara.ee", "arcovara-770301", "arcovara_search.html",
        {"address": "Kadaka tee 56", "price": 259000, "rooms": 4, "area_m2": 81.0,
         "second_price": 320000},
    ),
    "adapters.lvm_ee": (
        "lvm.ee", "lvm-660401", "lvm_search.html",
        {"address": "Viru väljak 6", "price": 410000, "rooms": 3, "area_m2": 88.0,
         "second_price": 175000},
    ),
    "adapters.remax_ee": (
        "remax.ee", "remax-80443837", "remax_search.html",
        # REAL live values (Telliskivi/Õle 29/2, Tallinn). rooms is None:
        # the live `rooms` field carries ad copy, never a count.
        {"address": "Telliskivi", "price": 199000, "rooms": None, "area_m2": 72.8,
         "second_price": 106650},
    ),
}


def _fixture(modname):
    _source, _first_id, fname, _exp = PORTALS[modname]
    path = os.path.join(os.path.dirname(__file__), "fixtures", fname)
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("modname", list(PORTALS))
def test_adapter_contract_clean(modname):
    mod = importlib.import_module(modname)
    source, _first_id, _fname, _exp = PORTALS[modname]
    assert adapter_contract_check(mod) == []
    assert mod.SOURCE == source
    assert mod.BASE_URL.startswith("https://")
    assert mod.SEARCH_URL.startswith("https://")
    assert mod.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in mod.HEADERS["User-Agent"]
    assert all(mod.SELECTORS[k] for k in ("card", "url", "price"))


@pytest.mark.parametrize("modname", list(PORTALS))
def test_parse_fixture_yields_two_canonical_rows(modname):
    mod = importlib.import_module(modname)
    source, first_id, _fname, exp = PORTALS[modname]
    rows = mod.parse_search_html(_fixture(modname))
    assert len(rows) == 2
    first, second = rows
    assert first["id"] == first_id
    assert first["source"] == source
    assert first["source_url"].startswith(mod.BASE_URL + "/")
    assert exp["address"] in first["address"]
    assert first["price"] == exp["price"]
    assert first["rooms"] == exp["rooms"]
    assert first["area_m2"] == exp["area_m2"]
    assert second["price"] == exp["second_price"]
    for row in rows:
        for key in ("id", "source", "source_url", "address", "price", "rooms", "area_m2"):
            assert key in row, "missing %s" % key
        assert row["address"].strip()


@pytest.mark.parametrize("modname", list(PORTALS))
def test_parse_empty_html_yields_no_rows(modname):
    mod = importlib.import_module(modname)
    assert mod.parse_search_html("") == []
    assert mod.parse_search_html("<html><body>no results</body></html>") == []


@pytest.mark.parametrize("modname", list(PORTALS))
def test_fetch_and_scrape_use_mocked_http(modname, monkeypatch):
    mod = importlib.import_module(modname)
    _source, first_id, _fname, _exp = PORTALS[modname]
    html = _fixture(modname)
    monkeypatch.setattr(mod, "fetch_html", lambda *a, **k: html)
    assert mod.fetch_search_html()
    rows = mod.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == first_id


def _remax_json_fixture():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "remax_search.json")
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_remax_search_url_is_muugiobjektid_hub():
    mod = importlib.import_module("adapters.remax_ee")
    assert mod.SEARCH_URL == "https://www.remax.ee/muugiobjektid/"


def test_remax_json_payload_parses_to_same_rows_as_rendered_cards():
    mod = importlib.import_module("adapters.remax_ee")
    from_json = mod.parse_search_html(_remax_json_fixture())
    from_html = mod.parse_search_html(_fixture("adapters.remax_ee"))
    assert len(from_json) == 2
    assert from_json == from_html
    assert from_json[0]["id"] == "remax-80443837"
    assert from_json[0]["source_url"] == (
        "https://www.remax.ee/objekt/tallinn/pohja-tallinn/korter/80443837/"
    )


def test_remax_ad_copy_rooms_yield_none_not_bogus_numbers():
    # Card 2's live `rooms` value is ad copy ("Super asukoht ..."), not a
    # room count — the numeric-rooms guard must yield None, never digits
    # scraped from prose (other live cards embed figures like "133 000€").
    mod = importlib.import_module("adapters.remax_ee")
    rows = mod.parse_search_html(_remax_json_fixture())
    assert rows[1]["rooms"] is None
    assert "Narva mnt 9a" in rows[1]["address"]
    assert rows[1]["area_m2"] == 23.7


def test_remax_malformed_json_yields_no_rows():
    mod = importlib.import_module("adapters.remax_ee")
    assert mod.parse_search_html("[not json") == []


@pytest.mark.parametrize("modname", list(PORTALS))
def test_scrape_serves_second_call_from_cache(modname, monkeypatch, tmp_path):
    mod = importlib.import_module(modname)
    html = _fixture(modname)
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(mod, "fetch_html", counting_fetch)
    first = mod.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(mod, "fetch_html", boom)
    second = mod.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1
