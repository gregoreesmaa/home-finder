"""Fixture tests for scripts/build/batch_medre_ads.py (issue #660, Step 2).

Hermetic: synthetic ADS index + synthetic register rows only, never
network. The Step-2 adapter joins 378 Harju reception rows (adr_id key)
+ 537 Uldarstiabi clinic rows (address-text key) to coordinates;
unjoined rows stay counted, never invented (paaste #493 precedent).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from batch_medre_ads import fixture_rows_378_537, join_ads


def test_ads_join_counts_on_fixture(tmp_path):
    out = join_ads(fixture_rows_378_537(), str(tmp_path))
    assert out["counts"]["reception"] == 378
    assert out["counts"]["clinic"] == 537
    assert 0.0 <= out["linkage_rate"] <= 1.0


def test_unjoined_stays_counted_never_invented(tmp_path):
    bundle = fixture_rows_378_537()
    out = join_ads(bundle, str(tmp_path))
    total = out["counts"]["reception"] + out["counts"]["clinic"]
    joined = len(out["points"])
    unjoined = out["unjoined"]["reception"] + out["unjoined"]["clinic"]
    # Every input row is either joined or counted-unjoined — none lost,
    # none invented.
    assert joined + unjoined == total
    assert unjoined > 0  # fixture carries unknown keys on purpose
    assert out["linkage_rate"] == joined / total
    for p in out["points"]:
        assert set(p) == {"lat", "lon", "slice"}
        assert p["slice"] in ("gp", "clinic")
        assert 57.0 <= p["lat"] <= 60.0
        assert 21.0 <= p["lon"] <= 28.0


def test_sidecar_shape_matches_loader(tmp_path):
    out = join_ads(fixture_rows_378_537(), str(tmp_path))
    sidecar = os.path.join(str(tmp_path), "medre", "medre-points.json")
    with open(sidecar, encoding="utf-8") as f:
        doc = json.load(f)
    # Shape the existing loader reads (snapshot.ts loadMedrePoints):
    # a points list of lat/lon/slice only.
    assert isinstance(doc["points"], list)
    assert len(doc["points"]) == len(out["points"])
    assert doc["linkage_rate"] == out["linkage_rate"]
    assert doc["counts"]["total"] == len(out["points"])
