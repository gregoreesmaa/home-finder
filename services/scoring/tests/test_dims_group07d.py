"""Hermetic unit tests for Group 7D env-health dims (issue #143).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group07d.py -q
"""

import dims_group07d as G
from dims_group07d import (
    dim_agrifield,
    dim_harvest,
    dim_leadpipes,
    dim_radonaesth,
    dim_wildcorr,
    kinds_from_tags,
    score_group07d,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_agrifield, dim_wildcorr):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None


def test_agrifield_bands():
    assert dim_agrifield(TALLINN, [poi("agrifield", 100)])[0] == 30
    assert dim_agrifield(TALLINN, [poi("agrifield", 400)])[0] == 55
    assert dim_agrifield(TALLINN, [poi("agrifield", 900)])[0] == 75
    # Empty POI list: no mapped active ag within the fetch window -> clean.
    assert dim_agrifield(TALLINN, [])[0] == 90


def test_wildcorr_bands():
    assert dim_wildcorr(TALLINN, [poi("wildcorr", 100)])[0] == 30
    assert dim_wildcorr(TALLINN, [poi("wildcorr", 400)])[0] == 55
    assert dim_wildcorr(TALLINN, [poi("wildcorr", 900)])[0] == 75
    assert dim_wildcorr(TALLINN, [])[0] == 85


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "farmland"}) == "agrifield"
    assert kinds_from_tags({"landuse": "farmyard"}) == "agrifield"
    assert kinds_from_tags({"landuse": "meadow"}) == "agrifield"
    assert kinds_from_tags({"landuse": "orchard"}) == "agrifield"
    assert kinds_from_tags({"landuse": "greenhouse_horticulture"}) == "agrifield"
    assert kinds_from_tags({"natural": "wood"}) == "wildcorr"
    assert kinds_from_tags({"natural": "wetland"}) == "wildcorr"
    assert kinds_from_tags({"leisure": "nature_reserve"}) == "wildcorr"
    assert kinds_from_tags({"boundary": "nature_reserve"}) == "wildcorr"
    assert kinds_from_tags({"landuse": "forest"}) is None
    assert kinds_from_tags({"landuse": "industrial"}) is None
    assert kinds_from_tags({"natural": "water"}) is None
    assert kinds_from_tags({"amenity": "school"}) is None


def test_no_map_dims_always_none():
    # p448/p471/p499: NULL whatever the input — never a faked number.
    for fn in (dim_harvest, dim_leadpipes, dim_radonaesth):
        for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                             (TALLINN, [poi("agrifield", 50), poi("wildcorr", 50)])):
            score, reason = fn(origin, pois)
            assert score is None
            assert "hinnangut pole" in reason


def test_honesty_labels():
    # Load-bearing: proxies, never measured units. Every reason —
    # including the None paths — says proksi or explains the absence;
    # none mentions spray doses, corridor ids, pipe counts or radon.
    fns = (dim_agrifield, dim_wildcorr, dim_harvest, dim_leadpipes, dim_radonaesth)
    for fn in fns:
        for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                             (TALLINN, [poi("agrifield", 120), poi("wildcorr", 400)])):
            _, reason = fn(origin, pois)
            low = reason.lower()
            assert "proksi" in low or "hinnangut pole" in low, (fn.__name__, reason)
            for unit in ("mg/kg", "AQI", "OU/m", "Bq/m", "Seveso", "koridori id"):
                assert unit not in reason, (fn.__name__, reason)


def test_score_group07d_registry():
    dims, reasons = score_group07d(TALLINN, [poi("agrifield", 500)])
    assert set(dims) == {"agrifield", "wildcorr", "harvest", "leadpipes", "radonaesth"}
    assert set(G.GROUP07D_PARAM_IDS.values()) == {409, 450, 448, 471, 499}
    # Only the two proxies score; the three no-map dims stay NULL (no reasons).
    assert dims["harvest"] is None
    assert dims["leadpipes"] is None
    assert dims["radonaesth"] is None
    assert len(reasons) == 2
    dims_none, reasons_none = score_group07d(None, None)
    assert all(v is None for v in dims_none.values())
    assert reasons_none == []


def test_scores_within_bounds():
    for fn in (dim_agrifield, dim_wildcorr):
        for origin, pois in ((TALLINN, []), (TALLINN, [poi("agrifield", 50)]),
                             (TALLINN, [poi("wildcorr", 1500)])):
            score, _ = fn(origin, pois)
            assert score is not None and 0 <= score <= 100
