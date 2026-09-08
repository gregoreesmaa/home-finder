"""Scoring API stub (FastAPI). Canonical ranking contract, mirrored in TS.

discount_pct: % below predicted market price (POSITIVE = steal / good deal).
GET /listings?sort=combined|livability|deal  -> best-to-worst sorted items.
GET /area-scores -> H3 hex goodness as GeoJSON (mock until PostGIS is wired).
"""

from typing import List, Optional

from fastapi import FastAPI, Query

app = FastAPI(title="home-finder scoring")


def deal_norm(discount_pct: float) -> float:
    return min(1.0, max(0.0, (discount_pct + 15.0) / 40.0))


def combined_score(livability: float, discount_pct: float) -> int:
    return round(100 * (0.6 * (livability / 100.0) + 0.4 * deal_norm(discount_pct)))


MOCK_LISTINGS = [
    {
        "id": "tallinn-kalamaja",
        "address": "Kotzebue 12, Tallinn",
        "county": "Harju maakond",
        "price": 285000,
        "price_per_m2": 4200,
        "rooms": 3,
        "area_m2": 68,
        "score_livability": 88,
        "discount_pct": 10,
        "reasons": ["Harju keskmisest -5%", "12 min kesklinna"],
    },
    {
        "id": "tartu-karlova",
        "address": "Tähe 45, Tartu",
        "county": "Tartu maakond",
        "price": 149000,
        "price_per_m2": 2600,
        "rooms": 2,
        "area_m2": 57,
        "score_livability": 64,
        "discount_pct": 18,
        "reasons": ["Turuennustusest -18% alla", "8 min ülikooli"],
    },
    {
        "id": "parnu-rannarajoon",
        "address": "Mere pst 7, Pärnu",
        "county": "Pärnu maakond",
        "price": 198000,
        "price_per_m2": 3100,
        "rooms": 3,
        "area_m2": 64,
        "score_livability": 95,
        "discount_pct": -9,
        "reasons": ["Parim koolide ligipääs", "5 min randa"],
    },
]

MOCK_HEXES = [
    {"h3": "mock-tallinn", "score_goodness": 85, "lon": 24.75, "lat": 59.43},
    {"h3": "mock-tartu", "score_goodness": 62, "lon": 26.72, "lat": 58.37},
    {"h3": "mock-parnu", "score_goodness": 30, "lon": 24.50, "lat": 58.38},
]


def sort_key(sort: str):
    if sort == "livability":
        return lambda l: l["score_livability"]
    if sort == "deal":
        return lambda l: l["discount_pct"]
    return lambda l: l["score_combined"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/listings")
def listings(sort: str = Query("combined", pattern="^(combined|livability|deal)$")):
    items: List[dict] = []
    for l in MOCK_LISTINGS:
        item = dict(l)
        item["score_combined"] = combined_score(l["score_livability"], l["discount_pct"])
        items.append(item)
    items.sort(key=sort_key(sort), reverse=True)
    return {"items": items, "sort": sort}


def heat_level(score: int) -> str:
    if score >= 70:
        return "good"
    if score >= 40:
        return "mid"
    return "bad"


@app.get("/area-scores")
def area_scores():
    features = []
    for h in MOCK_HEXES:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "h3": h["h3"],
                    "score_goodness": h["score_goodness"],
                    "level": heat_level(h["score_goodness"]),
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [h["lon"], h["lat"]],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}
