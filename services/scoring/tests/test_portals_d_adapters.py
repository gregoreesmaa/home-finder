"""Regression: portals-D adapters (oberhaus/arcovara/lvm/remax) parse offline.

Covers GitHub issues #16-#19. Fully offline: arcovara/lvm fixtures are
small verbatim excerpts (2 real cards each) from saved live search HTML
(not scraped dumps); network paths use monkeypatched fetch_html. Shared
files (test_portal_stubs.py, test_adapters_base.py) are left untouched so
sibling portal batches merge cleanly.
"""

import importlib
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
        "arcovara.ee", "arcovara-353253", "arcovara_search.html",
        {"address": "Eisma küla 24", "price": 122000, "rooms": 3, "area_m2": 77.5,
         "second_price": 650},
    ),
    "adapters.lvm_ee": (
        "lvm.ee", "lvm-80533810", "lvm_search.html",
        {"address": "Papiniidu tänav 54", "price": 520, "rooms": 2, "area_m2": 34.7,
         "second_price": 365000},
    ),
    "adapters.remax_ee": (
        "remax.ee", "remax-440501", "remax_search.html",
        {"address": "Randvere tee 25", "price": 525000, "rooms": 4, "area_m2": 102.0,
         "second_price": 238000},
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


LIVE_SEARCH_URLS = {
    # #17/#18: corrected hubs, verified against the saved live pages.
    "adapters.arcovara_ee": "https://www.arcovara.ee/et/otsi-kinnisvara",
    "adapters.lvm_ee": "https://lvm.ee/objektid/",
}


@pytest.mark.parametrize("modname,expected", list(LIVE_SEARCH_URLS.items()))
def test_search_url_points_at_live_hub(modname, expected):
    mod = importlib.import_module(modname)
    assert mod.SEARCH_URL == expected


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
