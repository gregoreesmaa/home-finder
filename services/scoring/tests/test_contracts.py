"""Contract C2: /listings + /area-scores match contracts/*.json (pytest side)."""

import json
import os

import jsonschema
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)
ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")


def _schema(name):
    with open(os.path.join(ROOT, "contracts", name), encoding="utf-8") as f:
        return json.load(f)


LISTINGS_SCHEMA = _schema("listings.json")
CELLS_SCHEMA = _schema("area-scores.json")


def test_listings_matches_shared_contract():
    body = client.get("/listings?sort=combined").json()
    jsonschema.validate(body, LISTINGS_SCHEMA)
    assert body["items"], "contract is vacuous without items"


def test_cells_match_shared_contract():
    body = client.get("/area-scores").json()
    jsonschema.validate(body, CELLS_SCHEMA)
    body2 = client.get("/heatmap-cells", params={"bbox": "20,57,29,60"}).json()
    jsonschema.validate(
        {k: v for k, v in body2.items() if k != "query"}, CELLS_SCHEMA
    )


def test_contract_rejects_shape_drift():
    bad = {"items": [{"id": "x"}], "sort": "combined", "live": False}
    try:
        jsonschema.validate(bad, LISTINGS_SCHEMA)
    except jsonschema.ValidationError:
        return
    raise AssertionError("schema must reject listings missing required keys")
