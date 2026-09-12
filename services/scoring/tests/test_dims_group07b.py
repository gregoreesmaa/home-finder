"""Hermetic unit tests for Group 7B env-health dims (issue #141).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group07b.py -q
"""

import dims_group07b as G
from dims_group07b import (
    dim_agriland,
    dim_brownsoil,
    dim_hazmat,
    dim_invasive,
    dim_oiltank,
    kinds_from_tags,
    score_group07b,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_brownsoil, dim_oiltank, dim_agriland):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None


def test_brownsoil_bands():
    assert dim_brownsoil(TALLINN, [poi("brownsoil", 100)])[0] == 30
    assert dim_brownsoil(TALLINN, [poi("brownsoil", 400)])[0] == 55
    assert dim_brownsoil(TALLINN, [poi("brownsoil", 900)])[0] == 75
    # Empty POI list: no mapped brownfield within the fetch window -> clean.
    assert dim_brownsoil(TALLINN, [])[0] == 85


def test_oiltank_bands():
    assert dim_oiltank(TALLINN, [poi("oiltank", 100)])[0] == 30
    assert dim_oiltank(TALLINN, [poi("oiltank", 400)])[0] == 55
    assert dim_oiltank(TALLINN, [poi("oiltank", 900)])[0] == 75
    assert dim_oiltank(TALLINN, [])[0] == 85


def test_agriland_bands():
    assert dim_agriland(TALLINN, [poi("agriland", 100)])[0] == 30
    assert dim_agriland(TALLINN, [poi("agriland", 400)])[0] == 55
    assert dim_agriland(TALLINN, [poi("agriland", 900)])[0] == 75
    assert dim_agriland(TALLINN, [])[0] == 90


def test_kinds_from_tags():
    assert kinds_from_tags({"landuse": "brownfield"}) == "brownsoil"
    assert kinds_from_tags({"man_made": "storage_tank"}) == "oiltank"
    assert kinds_from_tags({"landuse": "farmland"}) == "agriland"
    assert kinds_from_tags({"landuse": "farmyard"}) == "agriland"
    assert kinds_from_tags({"landuse": "meadow"}) is None
    assert kinds_from_tags({"landuse": "industrial"}) is None
    assert kinds_from_tags({"man_made": "works"}) is None
    assert kinds_from_tags({"amenity": "school"}) is None


def test_no_map_dims_always_none():
    # p204/p252: NULL whatever the input — never a faked number.
    for fn in (dim_hazmat, dim_invasive):
        for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                             (TALLINN, [poi("brownsoil", 50), poi("oiltank", 50)])):
            score, reason = fn(origin, pois)
            assert score is None
            assert "hinnangut pole" in reason


def test_honesty_labels():
    # Load-bearing: proxies, never measured units. Every reason —
    # including the None paths — says proksi or explains the absence;
    # none mentions mg/kg, tank counts, spray doses or Seveso classes.
    fns = (dim_brownsoil, dim_oiltank, dim_agriland, dim_hazmat, dim_invasive)
    for fn in fns:
        for origin, pois in ((None, None), (TALLINN, None), (TALLINN, []),
                             (TALLINN, [poi("brownsoil", 120), poi("agriland", 400)])):
            _, reason = fn(origin, pois)
            low = reason.lower()
            assert "proksi" in low or "hinnangut pole" in low, (fn.__name__, reason)
            for unit in ("mg/kg", "AQI", "OU/m", "Bq/m", "Seveso"):
                assert unit not in reason, (fn.__name__, reason)


def test_score_group07b_registry():
    dims, reasons = score_group07b(TALLINN, [poi("brownsoil", 500)])
    assert set(dims) == {"brownsoil", "oiltank", "agriland", "hazmat", "invasive"}
    assert set(G.GROUP07B_PARAM_IDS.values()) == {189, 202, 204, 227, 252}
    # Only the three proxies score; the two no-map dims stay NULL (no reasons).
    assert dims["hazmat"] is None and dims["invasive"] is None
    assert len(reasons) == 3
    dims_none, reasons_none = score_group07b(None, None)
    assert all(v is None for v in dims_none.values())
    assert reasons_none == []


def test_scores_within_bounds():
    # Sweep distances: every non-None score stays absolute 0..100.
    for d in (0, 10, 49, 50, 51, 300, 1000, 5000):
        pois = [poi("brownsoil", d), poi("oiltank", d), poi("agriland", d)]
        dims, _ = score_group07b(TALLINN, pois)
        for v in dims.values():
            assert v is None or 0 <= v <= 100
