"""Regression: pindi.ee adapter parses live offers HTML offline (no network)."""

import os

import adapters.pindi_ee as pindi
from adapters import adapter_contract_check
from adapters.pindi_ee import parse_search_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "pindi_search.html")


def test_parse_pindi_search_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        rows = parse_search_html(f.read())
    assert len(rows) == 2
    assert rows[0]["id"] == "pindi-17102"
    assert rows[0]["source"] == "pindi.ee"
    assert rows[0]["source_url"].startswith("https://www.pindi.ee/kinnisvarapakkumised/")
    assert rows[0]["price"] == 47500
    assert "Rakvere tn 87" in rows[0]["address"]
    assert rows[0]["rooms"] == 3
    assert rows[0]["area_m2"] == 61.5
    assert rows[1]["id"] == "pindi-18636"
    assert rows[1]["price"] == 94000
    assert "Metsapargi tn 8" in rows[1]["address"]


def test_parse_empty_html_yields_no_rows():
    assert parse_search_html("<html><body>no results</body></html>") == []


def test_client_side_template_card_is_skipped():
    template = (
        '<div class="offer"><a href="{{url}}?offset={{offset}}/" class="offer-link">'
        '<div class="offer-name">{{title}}</div>'
        '<div class="offer-price-amount">{{transactions.transaction.price._}} €</div>'
        '<div class="js-offer-price-favorite" item-id="{{originalId}}"></div>'
        "</a></div>"
    )
    assert parse_search_html(template) == []


def test_decimal_rent_price_truncates_to_whole_euros():
    card = (
        '<div class="offer">'
        '<a href="https://www.pindi.ee/kinnisvarapakkumised/rent-office/?offset=3" class="offer-link">'
        '<div class="offer-name">Harju maakond, Tallinn</div>'
        '<div class="offer-price-amount">2 011.1 €</div>'
        '<div class="js-offer-price-favorite" item-id="18628"></div>'
        "</a></div>"
    )
    rows = parse_search_html(card)
    assert len(rows) == 1
    assert rows[0]["price"] == 2011


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
    monkeypatch.setattr(pindi, "fetch_html", lambda *a, **k: html)
    assert "17102" in pindi.fetch_search_html()
    rows = pindi.scrape()
    assert len(rows) == 2
    assert rows[0]["id"] == "pindi-17102"


def test_scrape_serves_second_call_from_cache(monkeypatch, tmp_path):
    with open(FIXTURE, encoding="utf-8") as f:
        html = f.read()
    calls = []

    def counting_fetch(*args, **kwargs):
        calls.append(1)
        return html

    monkeypatch.setattr(pindi, "fetch_html", counting_fetch)
    first = pindi.scrape(cache_dir=str(tmp_path))
    assert len(first) == 2 and len(calls) == 1

    def boom(*args, **kwargs):
        raise AssertionError("network must not be hit on warm cache")

    monkeypatch.setattr(pindi, "fetch_html", boom)
    second = pindi.scrape(cache_dir=str(tmp_path))
    assert second == first and len(calls) == 1


def test_adapter_satisfies_contract():
    assert adapter_contract_check(pindi) == []
    assert pindi.SEARCH_URL == "https://www.pindi.ee/kinnisvara-pakkumised/"
    assert pindi.ROBOTS_URL.endswith("/robots.txt")
    assert "home-finder" in pindi.HEADERS["User-Agent"]
