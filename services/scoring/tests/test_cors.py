"""Regression: the local web UI must be able to read the API cross-origin.

Without CORS headers the browser blocks GET /listings and /area-scores
from http://localhost:3000 and the page silently falls back to mock data.
"""

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)
WEB_ORIGIN = "http://localhost:3000"


def test_listings_allows_web_origin():
    r = client.get("/listings?sort=combined", headers={"Origin": WEB_ORIGIN})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") in (WEB_ORIGIN, "*")


def test_area_scores_allows_web_origin():
    r = client.get("/area-scores", headers={"Origin": WEB_ORIGIN})
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") in (WEB_ORIGIN, "*")


def test_preflight_allows_web_origin():
    r = client.options(
        "/listings?sort=combined",
        headers={
            "Origin": WEB_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("access-control-allow-origin") in (WEB_ORIGIN, "*")
