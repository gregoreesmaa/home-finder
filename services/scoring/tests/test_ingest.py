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


@pytest.fixture(autouse=True)
def _no_live_geodata(monkeypatch):
    """Keep enrich()/run() offline: geodata resolves to None (-> honest 50).

    Tests that exercise real dimension math inject `resolver=` explicitly
    or cover livability.py directly.
    """
    monkeypatch.setattr(
        ingest.livability, "resolve", lambda address, cache_dir=None: None
    )


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
    # Pool holds only the genuine sale (6000/m2): s1 scores ~0, while the
    # 10/m2 row gets discount 0 with a check-yourself caution, never a
    # fantasy steal.
    assert by_id["s1"]["discount_pct"] == 0.0
    assert by_id["weird"]["discount_pct"] == 0.0
    assert "kontrolli" in by_id["weird"]["reasons"][0]


def test_county_colloquial_maa_forms():
    assert (
        ingest.county_for("Tiiru tee 6, Kallavere küla, Jõelähtme vald, Harjumaa")
        == "Harju maakond"
    )


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
        ],
        # offline: no geodata -> honest neutral fallback with explicit reason
        resolver=lambda address: None,
    )
    by_id = {r["id"]: r for r in rows}
    # median 6000 EUR/m2 -> a is 50% below (steal), b is 50% above
    assert by_id["a"]["price_per_m2"] == 4000
    assert by_id["a"]["discount_pct"] == pytest.approx(33.3, abs=0.1)
    assert by_id["b"]["discount_pct"] == pytest.approx(-33.3, abs=0.1)
    # Harju safety tier (55) applies with no geodata; geo dims stay null.
    assert by_id["a"]["score_livability"] == 55
    assert by_id["a"]["reasons"] == [
        "Harjumaal üle keskmise kuritegevus (riiklikud ülevaated)"
    ]
    assert by_id["a"]["county"] == "Harju maakond"


def test_score_stashes_geocode_coords_on_rows():
    geo = {"lat": 59.4372, "lon": 24.7536, "pois": []}
    (r,) = ingest.enrich(
        [row(id="a", address="A 1, Tallinn", price=200000, area_m2=50.0)],
        resolver=lambda address: geo,
    )
    assert r["lat"] == 59.4372
    assert r["lon"] == 24.7536


def test_build_cells_averages_livability_per_grid():
    cells = ingest.build_cells(
        [
            {"lon": 24.76, "lat": 59.44, "score_livability": 80},
            {"lon": 24.78, "lat": 59.45, "score_livability": 90},
            {"lon": 26.72, "lat": 58.37, "score_livability": 50},
            {"lon": None, "lat": 59.44, "score_livability": 80},
        ]
    )
    assert len(cells) == 2
    tallinn = next(c for c in cells if c["lon"] < 25.0)
    assert tallinn["score_goodness"] == 85
    assert tallinn["level"] == "good"
    assert tallinn["count"] == 2


def test_upsert_cells_writes_sql_per_cell():
    conn = FakeConn()
    n = ingest.upsert_cells(
        conn,
        [{"h3": "cell-1:2", "score_goodness": 70, "level": "good",
          "lon": 25.0, "lat": 58.75, "count": 3}],
    )
    assert n == 1
    sql, params = conn.cur.calls[0]
    assert "INSERT INTO area_scores" in sql
    assert params["h3"] == "cell-1:2"
    assert params["level"] == "good"
    assert conn.committed


def test_enrich_scores_livability_with_injected_geo():
    geo = {"lat": 59.4372, "lon": 24.7536, "pois": [
        {"kind": "school", "lat": 59.4380, "lon": 24.7550},
        {"kind": "bus_stop", "lat": 59.4375, "lon": 24.7540},
        {"kind": "park", "lat": 59.4400, "lon": 24.7600},
        {"kind": "supermarket", "lat": 59.4360, "lon": 24.7520},
    ]}
    (r,) = ingest.enrich(
        [row(id="a", address="A 1, Tallinn", price=200000, area_m2=50.0)],
        resolver=lambda address: geo,
    )
    assert r["score_livability"] != ingest.NEUTRAL_LIVABILITY
    assert len(r["reasons"]) >= 4
    assert not any("arvutamata" in reason for reason in r["reasons"])


def test_enrich_missing_area_gives_no_discount():
    (r,) = ingest.enrich([row(area_m2=None)])
    assert r["price_per_m2"] is None
    assert r["discount_pct"] == 0.0


def test_upsert_writes_one_row_per_record():
    conn = FakeConn()
    n = ingest.upsert(conn, ingest.enrich([row(), row(id="x-2", price=60000)]))
    assert n == 2
    schema_calls = conn.cur.calls[:2]
    assert "ADD COLUMN IF NOT EXISTS image_url" in schema_calls[0][0]
    assert "ADD COLUMN IF NOT EXISTS dims" in schema_calls[1][0]
    upserts = conn.cur.calls[2:]
    assert len(upserts) == 2
    assert conn.committed
    sql, params = upserts[0]
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert params["id"] == "x-1"
    assert params["county"] == "Ida-Viru maakond"
    assert params["image_url"] is None


def test_upsert_carries_image_url():
    conn = FakeConn()
    n = ingest.upsert(conn, ingest.enrich([row(image_url="https://img.test/1.jpg")]))
    assert n == 1
    _sql, params = conn.cur.calls[-1]
    assert params["image_url"] == "https://img.test/1.jpg"


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


def test_disabled_portals_carry_reasons_and_stay_skipped(monkeypatch):
    """C4: the cron never retries blocked portals; reasons stay published."""
    disabled = [(m, n) for m, e, n in ingest.PORTALS if not e]
    assert disabled, "expected some disabled portals"
    for modname, note in disabled:
        assert note.strip(), "%s disabled without a reason" % modname
    # skip mechanics (offline): disabled entries are never fetched
    monkeypatch.setattr(
        ingest, "PORTALS", [(m, False, n) for m, n in disabled]
    )
    monkeypatch.setattr(ingest, "connect", lambda: None)
    report = ingest.run()
    for modname, note in disabled:
        assert report[modname]["status"] == "skipped"
        assert report[modname]["reason"] == note
        assert report[modname]["count"] == 0


def test_sources_exposes_disabled_reasons(monkeypatch):
    monkeypatch.setattr(scoring_app, "_db_rows", lambda sql, params=(): [])
    by_source = {s["source"]: s for s in client.get("/sources").json()["sources"]}
    for modname, enabled, note in ingest.PORTALS:
        if enabled:
            continue
        mod = __import__(modname, fromlist=["SOURCE"])
        entry = by_source[mod.SOURCE]
        assert entry["enabled"] is False
        assert entry["note"] == note


def test_run_without_db_reports_not_stored(monkeypatch):
    monkeypatch.setattr(ingest, "PORTALS", [])
    monkeypatch.setattr(ingest, "connect", lambda: None)
    assert ingest.run()["_total"] == {
        "fetched": 0,
        "unique": 0,
        "skipped_no_price": 0,
        "stored": 0,
        "cells": 0,
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
    assert by_source["kv.ee"]["enabled"] is True
    assert "Chrome" in by_source["kv.ee"]["note"]


def test_run_uses_cache_dir_env_when_no_flag(monkeypatch, tmp_path):
    """#78: container cron sets HF_CACHE_DIR; explicit arg still wins."""
    seen = {}

    class Probe:
        SOURCE = "probe.ee"

        @staticmethod
        def scrape(*a, **k):
            seen["cache_dir"] = k.get("cache_dir", a[2] if len(a) > 2 else None)
            return []

    monkeypatch.setattr(ingest, "PORTALS", [("adapters.probe_ee", True, "")])
    monkeypatch.setitem(sys.modules, "adapters.probe_ee", Probe)
    monkeypatch.setattr(ingest, "connect", lambda: None)
    monkeypatch.setenv(ingest.CACHE_DIR_ENV_VAR, str(tmp_path))

    ingest.run()
    assert seen["cache_dir"] == str(tmp_path)

    ingest.run("/explicit")
    assert seen["cache_dir"] == "/explicit"


def test_run_page_limit_env_and_explicit_win(monkeypatch):
    """#67: HF_PAGE_LIMIT flows to adapters; explicit arg still wins."""
    seen = {}

    class Probe:
        SOURCE = "probe.ee"

        @staticmethod
        def scrape(*a, **k):
            seen["page_limit"] = a[1] if len(a) > 1 else None
            return []

    monkeypatch.setattr(ingest, "PORTALS", [("adapters.probe_ee", True, "")])
    monkeypatch.setitem(sys.modules, "adapters.probe_ee", Probe)
    monkeypatch.setattr(ingest, "connect", lambda: None)
    monkeypatch.delenv(ingest.PAGE_LIMIT_ENV_VAR, raising=False)

    ingest.run()
    assert seen["page_limit"] == ingest.DEFAULT_PAGE_LIMIT

    monkeypatch.setenv(ingest.PAGE_LIMIT_ENV_VAR, "3")
    ingest.run()
    assert seen["page_limit"] == 3

    ingest.run(page_limit=1)
    assert seen["page_limit"] == 1
