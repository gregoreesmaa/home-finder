"""Hermetic unit tests for Group 7 env-health dims (issue #140).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group07.py -q
"""

import dims_group07 as G
from dims_group07 import (
    dim_allergens,
    dim_industrial,
    dim_odor,
    dim_pests,
    dim_radon,
    kinds_from_tags,
    score_group07,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_industrial, dim_odor):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None


def test_industrial_bands():
    assert dim_industrial(TALLINN, [poi("industrial", 100)])[0] == 30
    assert dim_industrial(TALLINN, [poi("industrial", 400)])[0] == 55
    assert dim_industrial(TALLINN, [poi("industrial", 900)])[0] == 75
    # Empty POI list: no mapped industry within the fetch window -> clean.
    assert dim_industrial(TALLINN, [])[0] == 85


def test_odor_bands():
    assert dim_odor(TALLINN, [poi("odor", 100)])[0] == 30
    assert dim_odor(TALLINN, [poi("odor", 400)])[0] == 55
    assert dim_odor(TALLINN, [poi("odor", 900)])[0] == 75
    assert dim_odor(TALLINN, [])[0] == 90


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "industrial"}) == "industrial"
    assert kinds_from_tags({"landuse": "landfill"}) == "odor"
    assert kinds_from_tags({"man_made": "wastewater_plant"}) == "odor"
    assert kinds_from_tags({"landuse": "quarry"}) is None
    assert kinds_from_tags({"man_made": "works"}) is None
    assert kinds_from_tags({"amenity": "school"}) is None


def test_no_map_dims_always_none():
    # p66/p67/p137: NULL whatever the input — never a faked number.
    for fn in (dim_radon, dim_pests, dim_allergens):
        for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                             (TALLINN, [poi("industrial", 50), poi("odor", 50)])):
            score, reason = fn(origin, pois)
            assert score is None
            assert "hinnangut pole" in reason


def test_honesty_labels():
    # Load-bearing: proxies, never measured units. Every reason —
    # including the None paths — says proksi or explains the absence;
    # none mentions AQI/OU/Bq/pollen counts.
    fns = (dim_industrial, dim_odor, dim_radon, dim_pests, dim_allergens)
    for fn in fns:
        for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                             (TALLINN, [poi("industrial", 120), poi("odor", 400)])):
            _, reason = fn(origin, pois)
            low = reason.lower()
            assert "proksi" in low or "hinnangut pole" in low, (fn.__name__, reason)
            for unit in ("AQI", "OU/m", "Bq/m", "grains"):
                assert unit not in reason, (fn.__name__, reason)


def test_score_group07_registry():
    dims, reasons = score_group07(TALLINN, [poi("industrial", 500)])
    assert set(dims) == {"industrial", "odor", "radon", "pests", "allergens"}
    assert set(G.GROUP07_PARAM_IDS.values()) == {61, 62, 66, 67, 137}
    # Only the two proxies score; the three no-map dims stay NULL (no reasons).
    assert dims["radon"] is None and dims["pests"] is None and dims["allergens"] is None
    assert len(reasons) == 2
    dims_none, reasons_none = score_group07(None, None)
    assert all(v is None for v in dims_none.values())
    assert reasons_none == []


def test_scores_within_bounds():
    # Sweep distances: every non-None score stays absolute 0..100.
    for d in (0, 10, 49, 50, 51, 300, 1000, 5000):
        pois = [poi("industrial", d), poi("odor", d)]
        dims, _ = score_group07(TALLINN, pois)
        for v in dims.values():
            assert v is None or 0 <= v <= 100
