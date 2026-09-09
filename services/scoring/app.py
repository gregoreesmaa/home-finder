"""Scoring API (FastAPI). Canonical ranking contract, mirrored in TS.

discount_pct: % below predicted market price (POSITIVE = steal / good deal).
GET /listings?sort=combined|livability|deal  -> best-to-worst sorted items.
GET /area-scores -> H3 hex goodness as GeoJSON (mock until PostGIS is wired).
POST /score -> score one listing (livability + deal -> combined).
GET /heatmap-cells?bbox=minlon,minlat,maxlon,maxlat -> cell aggregates as GeoJSON.
GET /heatmap-tiles/{z}/{x}/{y} -> JSON cell aggregate for one slippy-map tile
    (v1 JSON stepping stone to binary MVT via PostGIS ST_AsMVT).

PostGIS path: when DATABASE_URL is set and psycopg is installed, cell reads
try `area_scores` first and fall back to the in-memory mock on any failure,
so tests/CI (no DB) stay green and prod reads the real table.
"""

import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

app = FastAPI(title="home-finder scoring")

# The Next.js web UI reads this API cross-origin from the browser; without
# these headers every fetch is CORS-blocked (the page then silently falls
# back to bundled mock data). Local loopback on any port: production web
# (:3000), dev server (:3100 in tests), future tooling.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


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
    db_rows = get_db_listings()
    live = db_rows is not None and len(db_rows) > 0
    items: List[dict] = []
    for l in db_rows if live else MOCK_LISTINGS:
        item = dict(l)
        item["score_combined"] = combined_score(
            item.get("score_livability") or 0, item.get("discount_pct") or 0
        )
        item["is_live"] = live
        items.append(item)
    items.sort(key=sort_key(sort), reverse=True)
    return {"items": items, "sort": sort, "live": live}


_LISTINGS_SQL = (
    "SELECT id, source, source_url, address, county, price, price_per_m2,"
    " rooms, area_m2, lat, lon, score_livability, discount_pct, reasons,"
    " image_url"
    " FROM listings"
)


def _num(v):
    """Coerce DB numerics (psycopg returns Decimal) to int/float/None."""
    if v is None:
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def get_db_listings() -> Optional[List[dict]]:
    """Live rows from PostGIS, or None when unavailable/empty (mock fallback)."""
    rows = _db_rows(_LISTINGS_SQL)
    if not rows:
        return None
    out = []
    for r in rows:
        reasons = r.get("reasons")
        if isinstance(reasons, str):
            try:
                reasons = json.loads(reasons)
            except ValueError:
                reasons = []
        out.append(
            {
                "id": str(r["id"]),
                "source": r.get("source"),
                "source_url": r.get("source_url"),
                "address": r.get("address", ""),
                "county": r.get("county", "Eesti"),
                "price": _num(r.get("price")),
                "price_per_m2": _num(r.get("price_per_m2")),
                "rooms": _num(r.get("rooms")),
                "area_m2": _num(r.get("area_m2")),
                "lat": _num(r.get("lat")),
                "lon": _num(r.get("lon")),
                "score_livability": _num(r.get("score_livability")),
                "discount_pct": _num(r.get("discount_pct")),
                "reasons": list(reasons or []),
                "image_url": r.get("image_url"),
            }
        )
    return out or None


@app.get("/sources")
def sources():
    """Per-portal integration status: live DB counts + honest block reasons."""
    import importlib

    from ingest import PORTALS

    counts: Dict[str, int] = {}
    rows = _db_rows("SELECT source, count(*) AS n FROM listings GROUP BY source")
    if rows:
        counts = {str(r["source"]): int(r["n"]) for r in rows}
    out: List[Dict[str, Any]] = []
    for modname, enabled, note in PORTALS:
        try:
            source = importlib.import_module(modname).SOURCE
        except Exception:
            source = modname
        out.append(
            {
                "source": source,
                "enabled": enabled,
                "note": note,
                "count": counts.get(source, 0),
            }
        )
    return {"sources": out}


def heat_level(score: int) -> str:
    if score >= 70:
        return "good"
    if score >= 40:
        return "mid"
    return "bad"


# ---- PostGIS-backed cell reads (graceful mock fallback) ----

_CELLS_SQL = (
    "SELECT h3, score_goodness, level,"
    " ST_X(ST_Centroid(geom)) AS lon, ST_Y(ST_Centroid(geom)) AS lat"
    " FROM area_scores"
)
_CELLS_BBOX_SQL = _CELLS_SQL + " WHERE geom && ST_MakeEnvelope(%s,%s,%s,%s,4326)"


def _db_rows(sql: str, params: tuple = ()):
    """Return DB rows or None when no DB is configured/reachable."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    try:
        import psycopg  # type: ignore
    except ImportError:
        return None
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:  # type: ignore[attr-defined]
            with conn.cursor() as cur:
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:
        return None


def get_cells(bounds: Optional[tuple] = None) -> Tuple[List[dict], bool]:
    """(Cell aggregates, live).

    live is True only when PostGIS area_scores actually yielded cells; any
    mock fallback returns live=False so the UI can badge demo data honestly.
    """
    rows = None
    if bounds is not None:
        rows = _db_rows(_CELLS_BBOX_SQL, bounds)
    else:
        rows = _db_rows(_CELLS_SQL)
    if rows:
        cells = []
        for r in rows:
            try:
                cells.append(
                    {
                        "h3": str(r["h3"]),
                        "score_goodness": int(r["score_goodness"]),
                        "lon": float(r["lon"]),
                        "lat": float(r["lat"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        if cells:
            return cells, True
    if bounds is None:
        return list(MOCK_HEXES), False
    minlon, minlat, maxlon, maxlat = bounds
    return [
        h
        for h in MOCK_HEXES
        if minlon <= h["lon"] <= maxlon and minlat <= h["lat"] <= maxlat
    ], False


def cells_to_geojson(cells: List[dict], live: bool = False) -> dict:
    features = []
    for h in cells:
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
    fc: dict = {"type": "FeatureCollection", "features": features}
    fc["live"] = live
    return fc


@app.get("/area-scores")
def area_scores():
    cells, live = get_cells()
    return cells_to_geojson(cells, live)


# ---- POST /score ----


class ScoreRequest(BaseModel):
    score_livability: float = Field(..., ge=0, le=100)
    discount_pct: Optional[float] = None
    price: Optional[float] = Field(None, gt=0)
    predicted_price: Optional[float] = Field(None, gt=0)

    @model_validator(mode="after")
    def _need_discount_or_price_pair(self):
        if self.discount_pct is None and (
            self.price is None or self.predicted_price is None
        ):
            raise ValueError("provide discount_pct or both price and predicted_price")
        return self


@app.post("/score")
def score(req: ScoreRequest):
    discount = req.discount_pct
    if discount is None:
        discount = (req.predicted_price - req.price) / req.predicted_price * 100.0
    dn = deal_norm(discount)
    combined = combined_score(req.score_livability, discount)
    return {
        "score_livability": req.score_livability,
        "discount_pct": round(float(discount), 2),
        "deal_norm": dn,
        "score_combined": combined,
        "level": heat_level(combined),
    }


# ---- GET /heatmap-cells + GET /heatmap-tiles ----


def parse_bbox(bbox: str) -> tuple:
    try:
        parts = [float(p) for p in bbox.split(",")]
    except ValueError:
        raise HTTPException(
            status_code=422, detail="bbox must be minlon,minlat,maxlon,maxlat numbers"
        )
    if len(parts) != 4:
        raise HTTPException(
            status_code=422, detail="bbox must be minlon,minlat,maxlon,maxlat"
        )
    minlon, minlat, maxlon, maxlat = parts
    if not (-180 <= minlon <= 180 and -180 <= maxlon <= 180):
        raise HTTPException(status_code=422, detail="bbox lon out of [-180,180]")
    if not (-90 <= minlat <= 90 and -90 <= maxlat <= 90):
        raise HTTPException(status_code=422, detail="bbox lat out of [-90,90]")
    if not (minlon < maxlon and minlat < maxlat):
        raise HTTPException(status_code=422, detail="bbox min must be < max")
    return (minlon, minlat, maxlon, maxlat)


@app.get("/heatmap-cells")
def heatmap_cells(bbox: Optional[str] = None):
    bounds = parse_bbox(bbox) if bbox is not None else None
    cells, live = get_cells(bounds)
    fc = cells_to_geojson(cells, live)
    fc["query"] = {"bbox": list(bounds) if bounds else None}
    return fc


def tile_bounds(z: int, x: int, y: int) -> tuple:
    n = 2**z
    minlon = x / n * 360.0 - 180.0
    maxlon = (x + 1) / n * 360.0 - 180.0

    def _lat(yy: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))

    maxlat = _lat(y)
    minlat = _lat(y + 1)
    return (minlon, minlat, maxlon, maxlat)


@app.get("/heatmap-tiles/{z}/{x}/{y}")
def heatmap_tile(z: int, x: int, y: int):
    if not (0 <= z <= 19):
        raise HTTPException(status_code=422, detail="z must be 0..19")
    n = 2**z
    if not (0 <= x < n and 0 <= y < n):
        raise HTTPException(status_code=422, detail="x/y out of range for z")
    bounds = tile_bounds(z, x, y)
    cells, live = get_cells(bounds)
    minlon, minlat, maxlon, maxlat = bounds
    return {
        "z": z,
        "x": x,
        "y": y,
        "bounds": {
            "minlon": minlon,
            "minlat": minlat,
            "maxlon": maxlon,
            "maxlat": maxlat,
        },
        "count": len(cells),
        "live": live,
        "cells": [
            {
                "h3": c["h3"],
                "score_goodness": c["score_goodness"],
                "level": heat_level(c["score_goodness"]),
                "lon": c["lon"],
                "lat": c["lat"],
            }
            for c in cells
        ],
    }
