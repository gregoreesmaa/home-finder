"""Integration: fixtures -> adapters -> ingest -> PostGIS -> API (issue C1).

Runs only when DATABASE_URL points at a reachable PostGIS (local compose
stack or the CI service container); otherwise skipped. Test rows use
`t-` prefixed ids and are deleted afterwards, so real data is untouched.
"""

import os

import pytest

psycopg = pytest.importorskip("psycopg")

import ingest
from adapters import kv_ee

URL = os.environ.get("DATABASE_URL")


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS listings (
  id TEXT PRIMARY KEY, source TEXT NOT NULL, source_url TEXT NOT NULL,
  address TEXT NOT NULL, county TEXT NOT NULL, price INTEGER NOT NULL,
  price_per_m2 INTEGER, rooms NUMERIC, area_m2 NUMERIC,
  lat DOUBLE PRECISION, lon DOUBLE PRECISION,
  score_livability INTEGER, discount_pct NUMERIC,
  reasons JSONB DEFAULT '[]', scraped_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS area_scores (
  h3 TEXT PRIMARY KEY, score_goodness INTEGER NOT NULL,
  level TEXT NOT NULL, geom GEOMETRY(Polygon, 4326)
);
"""


def _db():
    if not URL:
        pytest.skip("DATABASE_URL not set")
    try:
        conn = psycopg.connect(URL, connect_timeout=5)
    except Exception:
        pytest.skip("PostGIS unreachable")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SCHEMA_SQL)
    conn.autocommit = False
    return conn


@pytest.fixture()
def conn():
    c = _db()
    yield c
    with c.cursor() as cur:
        cur.execute("DELETE FROM listings WHERE id LIKE 't-%'")
        cur.execute("DELETE FROM area_scores WHERE h3 LIKE 't-%'")
    c.commit()
    c.close()


def test_adapter_ingest_db_api_roundtrip(conn, monkeypatch):
    monkeypatch.setattr(ingest, "connect", lambda: conn)
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "kv_search.html")
    with open(fixture, encoding="utf-8") as f:
        rows = kv_ee.parse_search_html(f.read())
    assert len(rows) == 2
    for r in rows:
        r["id"] = "t-" + r["id"]
    geo = {"lat": 59.4372, "lon": 24.7536, "pois": []}
    enriched = ingest.enrich(rows, "adapters.kv_ee", resolver=lambda a: geo)
    priced = [r for r in enriched if r.get("price")]
    assert ingest.upsert(conn, priced) == 2
    cells = ingest.build_cells(priced)
    assert cells, "geocoded rows must bin into cells"
    for c in cells:  # isolate test cells from prod cell-% keys on cleanup
        c["h3"] = "t-" + c["h3"]
    assert ingest.upsert_cells(conn, cells) >= 1

    import app as scoring_app

    monkeypatch.setenv("DATABASE_URL", URL)
    db_rows = scoring_app.get_db_listings()
    ids = {r["id"] for r in db_rows}
    assert "t-kv-3905636" in ids
    trow = next(r for r in db_rows if r["id"] == "t-kv-3905636")
    assert trow["price"] == 45000
    assert trow["reasons"], "reasons must survive the round trip"
    live_cells, live = scoring_app.get_cells()
    assert live is True
    assert live_cells, "seeded cells must read back live"
