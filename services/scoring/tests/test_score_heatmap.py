"""Regression: POST /score + heatmap cells/tiles (issue #3)."""

from fastapi.testclient import TestClient

import app as scoring_app
from app import app, combined_score, tile_bounds

client = TestClient(app)


def test_cells_carry_live_flag_from_mock_fallback():
    assert client.get("/area-scores").json()["live"] is False
    assert client.get("/heatmap-cells").json()["live"] is False


def test_cells_report_live_when_db_has_rows(monkeypatch):
    monkeypatch.setattr(
        scoring_app,
        "_db_rows",
        lambda sql, params=(): [
            {"h3": "db-1", "score_goodness": 80, "lon": 24.75, "lat": 59.43}
        ],
    )
    body = client.get("/area-scores").json()
    assert body["live"] is True
    assert body["features"][0]["properties"]["h3"] == "db-1"
    assert client.get("/heatmap-cells").json()["live"] is True


def test_post_score_explicit_discount():
    r = client.post("/score", json={"score_livability": 80, "discount_pct": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score_combined"] == combined_score(80, 5) == 68
    assert abs(body["deal_norm"] - 0.5) < 1e-9
    assert body["discount_pct"] == 5
    assert body["level"] == "mid"


def test_post_score_derives_discount_from_prices():
    # 180k vs predicted 200k -> +10% steal
    r = client.post(
        "/score", json={"score_livability": 88, "price": 180000, "predicted_price": 200000}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discount_pct"] == 10.0
    assert body["score_combined"] == combined_score(88, 10.0)


def test_post_score_overpriced_is_bad_deal():
    r = client.post(
        "/score", json={"score_livability": 95, "price": 220000, "predicted_price": 200000}
    )
    assert r.status_code == 200, r.text
    assert r.json()["discount_pct"] == -10.0


def test_post_score_rejects_missing_discount_and_bad_livability():
    assert client.post("/score", json={"score_livability": 80}).status_code == 422
    assert (
        client.post("/score", json={"score_livability": 120, "discount_pct": 5}).status_code
        == 422
    )
    assert (
        client.post("/score", json={"score_livability": -1, "discount_pct": 5}).status_code
        == 422
    )


def test_heatmap_cells_all_without_bbox():
    body = client.get("/heatmap-cells").json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 3


def test_heatmap_cells_bbox_filters_to_tartu():
    body = client.get("/heatmap-cells", params={"bbox": "26,58,27,59"}).json()
    ids = sorted(f["properties"]["h3"] for f in body["features"])
    assert ids == ["mock-tartu"]
    assert body["features"][0]["properties"]["level"] == "mid"


def test_heatmap_cells_bad_bbox_is_422():
    for bad in ["nope", "1,2,3", "27,59,26,58", "0,0,500,500"]:
        r = client.get("/heatmap-cells", params={"bbox": bad})
        assert r.status_code == 422, bad


def _tile_covering(lon: float, lat: float, z: int):
    import math

    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int(
        (1.0 - math.log(math.tan(lat_r) + 1 / math.cos(lat_r)) / math.pi) / 2.0 * n
    )
    return x, y


def test_heatmap_tile_contains_expected_city():
    z = 6
    x, y = _tile_covering(26.72, 58.37, z)  # Tartu
    r = client.get(f"/heatmap-tiles/{z}/{x}/{y}")
    assert r.status_code == 200, r.text
    body = r.json()
    ids = [c["h3"] for c in body["cells"]]
    assert "mock-tartu" in ids
    assert body["count"] == len(body["cells"])
    assert body["bounds"]["minlon"] < body["bounds"]["maxlon"]
    assert body["bounds"]["minlat"] < body["bounds"]["maxlat"]


def test_heatmap_tile_empty_ocean_has_zero_cells():
    r = client.get("/heatmap-tiles/3/0/0")
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 0


def test_heatmap_tile_rejects_out_of_range():
    assert client.get("/heatmap-tiles/99/0/0").status_code == 422
    assert client.get("/heatmap-tiles/2/99/0").status_code == 422


def test_tile_bounds_math_sane_at_z0():
    minlon, minlat, maxlon, maxlat = tile_bounds(0, 0, 0)
    assert (minlon, maxlon) == (-180.0, 180.0)
    assert minlat < maxlat
