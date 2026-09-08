"""Regression: ranking contract shared with the TS frontend (packages/shared)."""

from fastapi.testclient import TestClient

from app import combined_score, deal_norm, app

client = TestClient(app)


def test_deal_norm_bounds():
    assert deal_norm(-15) == 0.0
    assert deal_norm(25) == 1.0
    assert deal_norm(-999) == 0.0
    assert deal_norm(999) == 1.0
    assert abs(deal_norm(5) - 0.5) < 1e-9


def test_combined_formula_matches_frontend():
    # liv 80, discount +5 (norm 0.5) -> round(100*(0.48+0.20)) = 68
    assert combined_score(80, 5) == 68


def test_listings_sort_modes_have_distinct_winners():
    by_combined = client.get("/listings?sort=combined").json()["items"]
    by_liv = client.get("/listings?sort=livability").json()["items"]
    by_deal = client.get("/listings?sort=deal").json()["items"]
    assert [l["id"] for l in by_liv][0] == "parnu-rannarajoon"
    assert [l["id"] for l in by_deal][0] == "tartu-karlova"
    assert [l["id"] for l in by_combined][0] == "tallinn-kalamaja"
    assert by_liv[0]["score_livability"] > by_liv[1]["score_livability"]
    assert by_deal[0]["discount_pct"] > by_deal[1]["discount_pct"]
    assert by_combined[0]["score_combined"] > by_combined[1]["score_combined"]


def test_area_scores_levels():
    feats = client.get("/area-scores").json()["features"]
    levels = {f["properties"]["h3"]: f["properties"]["level"] for f in feats}
    assert levels == {
        "mock-tallinn": "good",
        "mock-tartu": "mid",
        "mock-parnu": "bad",
    }
