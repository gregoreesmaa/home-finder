"""Regression: live ingestion (adapters -> enrich -> PostGIS) + DB-first API.

All network/DB access is faked; these prove the shaping logic:
county mapping, batch-median discount math, upsert call shape,
run() reporting, and /listings mock fallback vs live rows.
"""

import sys

import pytest
from fastapi.testclient import TestClient

import app as scoring_app
import ingest


class FakeCursor:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))


class FakeConn:
    def __init__(self):
        self.cur = FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self):
        return self.cur

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def row(**kw):
    base = {
        "id": "x-1",
        "source": "pindi.ee",
        "source_url": "https://example.test/1",
        "address": "Rakvere tn 87, Narva",
        "price": 47500,
        "rooms": 2,
        "area_m2": 50.0,
    }
    base.update(kw)
    return base


def test_county_for_known_and_unknown_cities():
    assert ingest.county_for("Kotzebue 12, Tallinn") == "Harju maakond"
    assert ingest.county_for("Tähe 45, Tartu") == "Tartu maakond"
    assert ingest.county_for("Mere pst 7, Pärnu") == "Pärnu maakond"
    assert ingest.county_for("Rakvere tn 87, Narva") == "Ida-Viru maakond"
    assert ingest.county_for("Somewhere New") == "Eesti"
    assert ingest.county_for("") == "Eesti"


def test_county_for_full_hierarchy_addresses():
    # Live addresses carry street, village, parish AND county.
    assert (
        ingest.county_for("Nõlvaku tn 17, Annelinn, Tartu linn, Tartu maakond")
        == "Tartu maakond"
    )
    assert (
        ingest.county_for("Kadaka, Nurme küla, Muhu vald, Saare maakond")
        == "Saare maakond"
    )
    assert (
        ingest.county_for("Raemetsa, Reiu küla, Pärnu linn, Pärnu maakond")
        == "Pärnu maakond"
    )


def test_deal_type_from_url_markers():
    rent = "https://domus.ee/objektid/1-uurile-anda-korter-2-tuba-tartu-linn/"
    assert ingest.deal_type(rent, "adapters.domus_ee") == "rent"
    land = "https://domus.ee/objektid/2-muua-maa-muhu-vald-nurme-kula/"
    assert ingest.deal_type(land, "adapters.domus_ee") == "land"
    sale = "https://domus.ee/objektid/3-muua-korter-1-tuba-parnu-linn/"
    assert ingest.deal_type(sale, "adapters.domus_ee") == "sale"
    # Sale-hub default when unmarked; domus (mixed hub) stays unknown.
    remax = "https://www.remax.ee/objekt/tartu/karlova/korter/80518936/"
    assert ingest.deal_type(remax, "adapters.remax_ee") == "sale"
    assert ingest.deal_type("https://domus.ee/objektid/9-x/", "adapters.domus_ee") == "unknown"


def test_sale_floor_keeps_mislabeled_rows_out_of_median():
    rows = ingest.enrich(
        [
            row(
                id="s1",
                address="A 1, Tallinn",
                price=300000,
                area_m2=50.0,
                source_url="https://x.test/muua-a",
            ),
            row(
                id="weird",
                address="B 2, Tallinn",
                price=500,
                area_m2=50.0,
                source_url="https://x.test/muua-b",
            ),
        ],
        "adapters.remax_ee",
    )
    by_id = {r["id"]: r for r in rows}
    # Pool holds only the genuine sale (6000/m2): s1 scores ~0, the 10/m2
    # row is still scored against it instead of corrupting the median.
    assert by_id["s1"]["discount_pct"] == 0.0
    assert by_id["weird"]["discount_pct"] == pytest.approx(99.8, abs=0.1)


def test_enrich_excludes_rent_and_land_from_medians():
    rows = ingest.enrich(
        [
            row(
                id="s1",
                address="A 1, Tallinn",
                price=200000,
                area_m2=50.0,
                source_url="https://x.test/muua-korter-a",
            ),
            row(
                id="s2",
                address="B 2, Tallinn",
                price=400000,
                area_m2=50.0,
                source_url="https://x.test/muua-korter-b",
            ),
            row(
                id="r1",
                address="C 3, Tallinn",
                price=475,
                area_m2=43.2,
                source_url="https://domus.ee/objektid/1-uurile-anda-korter-tallinn/",
            ),
        ],
        "adapters.domus_ee",
    )
    by_id = {r["id"]: r for r in rows}
    # Median over the two sales (6000/m2); the 11 EUR/m2 rent must not move it.
    assert by_id["s1"]["discount_pct"] == pytest.approx(33.3, abs=0.1)
    assert by_id["s2"]["discount_pct"] == pytest.approx(-33.3, abs=0.1)
    assert by_id["r1"]["deal_type"] == "rent"
    assert by_id["r1"]["discount_pct"] == 0.0
    assert "Üürikuulutus" in by_id["r1"]["reasons"][0]


def test_enrich_discount_against_county_median():
    rows = ingest.enrich(
        [
            row(id="a", address="A 1, Tallinn", price=200000, area_m2=50.0),
            row(id="b", address="B 2, Tallinn", price=400000, area_m2=50.0),
        ]
    )
    by_id = {r["id"]: r for r in rows}
    # median 6000 EUR/m2 -> a is 50% below (steal), b is 50% above
    assert by_id["a"]["price_per_m2"] == 4000
    assert by_id["a"]["discount_pct"] == pytest.approx(33.3, abs=0.1)
    assert by_id["b"]["discount_pct"] == pytest.approx(-33.3, abs=0.1)
    assert by_id["a"]["score_livability"] == ingest.NEUTRAL_LIVABILITY
    assert by_id["a"]["county"] == "Harju maakond"


def test_enrich_missing_area_gives_no_discount():
    (r,) = ingest.enrich([row(area_m2=None)])
    assert r["price_per_m2"] is None
    assert r["discount_pct"] == 0.0


def test_upsert_writes_one_row_per_record():
    conn = FakeConn()
    n = ingest.upsert(conn, ingest.enrich([row(), row(id="x-2", price=60000)]))
    assert n == 2
    assert len(conn.cur.calls) == 2
    assert conn.committed
    sql, params = conn.cur.calls[0]
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert params["id"] == "x-1"
    assert params["county"] == "Ida-Viru maakond"


def test_run_reports_per_source_and_skips_priceless(monkeypatch):
    monkeypatch.setattr(
        ingest,
        "PORTALS",
        [
            ("adapters.good_ee", True, ""),
            ("adapters.bad_ee", True, ""),
            ("adapters.blocked_ee", False, "HTTP 403 bot protection"),
        ],
    )

    class Good:
        SOURCE = "good.ee"

        @staticmethod
        def scrape(*a, **k):
            return [
                row(id="g-1", source="good.ee"),
                row(id="g-2", source="good.ee", price=None),
            ]

    class Bad:
        SOURCE = "bad.ee"

        @staticmethod
        def scrape(*a, **k):
            raise RuntimeError("boom")

    monkeypatch.setitem(sys.modules, "adapters.good_ee", Good)
    monkeypatch.setitem(sys.modules, "adapters.bad_ee", Bad)

    conn = FakeConn()
    monkeypatch.setattr(ingest, "connect", lambda: conn)

    report = ingest.run()
    assert report["adapters.good_ee"] == {"status": "ok", "count": 2}
    assert report["adapters.bad_ee"]["status"] == "error"
    assert report["adapters.blocked_ee"]["status"] == "skipped"
    assert report["_total"]["fetched"] == 2
    assert report["_total"]["skipped_no_price"] == 1
    assert report["_total"]["stored"] == 1
    assert conn.closed


def test_run_without_db_reports_not_stored(monkeypatch):
    monkeypatch.setattr(ingest, "PORTALS", [])
    monkeypatch.setattr(ingest, "connect", lambda: None)
    assert ingest.run()["_total"] == {
        "fetched": 0,
        "unique": 0,
        "skipped_no_price": 0,
        "stored": 0,
        "db": False,
    }


client = TestClient(scoring_app.app)


def test_listings_falls_back_to_mocks_without_db(monkeypatch):
    monkeypatch.setattr(scoring_app, "get_db_listings", lambda: None)
    r = client.get("/listings?sort=combined")
    assert r.status_code == 200
    body = r.json()
    assert body["live"] is False
    assert len(body["items"]) == 3
    assert all(item["is_live"] is False for item in body["items"])


def test_listings_serves_db_rows_when_present(monkeypatch):
    live = [
        {
            "id": "pindi-1",
            "source": "pindi.ee",
            "source_url": "https://example.test/1",
            "address": "Rakvere tn 87, Narva",
            "county": "Ida-Viru maakond",
            "price": 47500,
            "price_per_m2": 950,
            "rooms": 2,
            "area_m2": 50.0,
            "score_livability": 50,
            "discount_pct": 12.5,
            "reasons": ["Elamiskvaliteet arvutamata (automaatimport)"],
        }
    ]
    monkeypatch.setattr(scoring_app, "get_db_listings", lambda: live)
    r = client.get("/listings?sort=deal")
    assert r.status_code == 200
    body = r.json()
    assert body["live"] is True
    (item,) = body["items"]
    assert item["is_live"] is True
    assert item["source"] == "pindi.ee"
    assert item["score_combined"] == scoring_app.combined_score(50, 12.5)


def test_sources_reports_counts_and_blocks(monkeypatch):
    monkeypatch.setattr(
        scoring_app,
        "_db_rows",
        lambda sql, params=(): [{"source": "pindi.ee", "n": 4}],
    )
    r = client.get("/sources")
    assert r.status_code == 200
    by_source = {s["source"]: s for s in r.json()["sources"]}
    assert by_source["pindi.ee"]["count"] == 4
    assert by_source["pindi.ee"]["enabled"] is True
    assert by_source["kv.ee"]["enabled"] is False
    assert "403" in by_source["kv.ee"]["note"]
