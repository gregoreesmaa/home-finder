"""Hermetic unit tests for Group 7C environmental-health dims (issue #142).

No network, no snapshot: all POIs are synthetic. Run from repo root:
  python3 -m pytest services/scoring/tests/test_dims_group07c.py -q
"""

import dims_group07c as G
from dims_group07c import (
    dim_dust,
    dim_vector_habitat,
    dim_voc,
    dim_water_hardness,
    dim_water_treatment,
    kinds_from_tags,
    score_group07c,
)

TALLINN = (59.4372, 24.7536)  # city centre reference origin (inside supply box)
RURAL = (59.20, 24.50)  # outside the Tallinn supply box


def poi(kind, metres_north, lon_off=0.0):
    """Synthetic POI `metres_north` metres north of TALLINN."""
    return {"kind": kind, "lat": TALLINN[0] + metres_north / 111320.0,
            "lon": TALLINN[1] + lon_off}


def test_none_when_missing():
    for fn in (dim_vector_habitat, dim_dust):
        assert fn(None, [])[0] is None
        assert fn(TALLINN, None)[0] is None
        assert fn(None, None)[0] is None
    assert dim_water_treatment(None, None)[0] is None
    assert dim_water_treatment(RURAL, [])[0] is None
    assert dim_water_hardness(RURAL, [])[0] is None
    assert dim_voc(TALLINN, [])[0] is None
    assert dim_voc(None, None)[0] is None


def test_vector_habitat_bands():
    assert dim_vector_habitat(TALLINN, [poi("vector_habitat", 50)])[0] == 30
    assert dim_vector_habitat(TALLINN, [poi("vector_habitat", 200)])[0] == 50
    assert dim_vector_habitat(TALLINN, [poi("vector_habitat", 500)])[0] == 70
    assert dim_vector_habitat(TALLINN, [poi("vector_habitat", 1000)])[0] == 85
    # Empty POI list: no mapped habitat within the fetch window -> calm.
    assert dim_vector_habitat(TALLINN, [])[0] == 92


def test_dust_bands_and_pollen_deferral():
    assert dim_dust(TALLINN, [poi("dust_source", 100)])[0] == 35
    assert dim_dust(TALLINN, [poi("dust_source", 300)])[0] == 55
    assert dim_dust(TALLINN, [poi("dust_source", 700)])[0] == 75
    assert dim_dust(TALLINN, [poi("dust_source", 1200)])[0] == 88
    assert dim_dust(TALLINN, [])[0] == 92
    _, reason = dim_dust(TALLINN, [poi("dust_source", 300)])
    assert "p137" in reason  # pollen side belongs to the sibling


def test_water_treatment_knowledge():
    v, reason = dim_water_treatment(TALLINN, [], "central")
    assert v == 85 and "hinnang" in reason
    # Inside the Tallinn box the supply is assumed central (labelled).
    assert dim_water_treatment(TALLINN, [])[0] == 85
    assert dim_water_treatment(TALLINN, [], "well")[0] is None
    assert dim_water_treatment(RURAL, [], "central")[0] == 85


def test_water_hardness_knowledge():
    assert dim_water_hardness(TALLINN, [])[0] == 80
    assert dim_water_hardness(TALLINN, [], "central")[0] == 80
    assert dim_water_hardness(RURAL, [], "well")[0] == 45
    assert dim_water_hardness(RURAL, [])[0] is None


def test_voc_age_logic():
    assert dim_voc(TALLINN, [], 2026)[0] == 50  # brand new: ventilate
    assert dim_voc(TALLINN, [], 2020, 2025)[0] == 50  # fresh renovation
    assert dim_voc(TALLINN, [], 1990)[0] == 85  # settled
    assert dim_voc(TALLINN, [], 2024)[0] == 50  # boundary: age 2
    assert dim_voc(TALLINN, [], 2023)[0] == 85  # boundary: age 3
    _, reason = dim_voc(TALLINN, [], 2026)
    assert "tuuluta" in reason


def test_kinds_from_tags():
    assert kinds_from_tags({"natural": "wood"}) == "vector_habitat"
    assert kinds_from_tags({"natural": "wetland"}) == "vector_habitat"
    assert kinds_from_tags({"landuse": "forest"}) == "vector_habitat"
    assert kinds_from_tags({"landuse": "meadow"}) == "vector_habitat"
    assert kinds_from_tags({"landuse": "quarry"}) == "dust_source"
    assert kinds_from_tags({"landuse": "industrial"}) == "dust_source"
    assert kinds_from_tags({"landuse": "construction"}) == "dust_source"
    assert kinds_from_tags({"highway": "primary"}) == "dust_source"
    assert kinds_from_tags({"highway": "residential"}) is None
    assert kinds_from_tags({"natural": "water"}) is None
    assert kinds_from_tags({}) is None


def test_fragment_is_way_aware():
    frag = G.GROUP07C_OVERPASS_FRAGMENT
    assert "around:" in frag
    assert "way[" in frag and "node[" in frag
    for tag in ("wood", "wetland", "forest", "meadow", "quarry",
                "industrial", "construction", "motorway"):
        assert tag in frag


def test_honesty_strings():
    for _title, fn in G.GROUP07C_DIMS.values():
        v, reason = fn(TALLINN, [])
        assert "hinnang" in reason or "proksi" in reason, (fn.__name__, reason)
        assert "dB" not in reason and "g/m" not in reason, (fn.__name__, reason)


def test_score_group07c_registry():
    dims, reasons = score_group07c(
        TALLINN, [poi("vector_habitat", 500), poi("dust_source", 900)],
        water_source="central", building_year=1990)
    assert set(dims) == {"vector_habitat", "dust", "water_treatment",
                         "voc", "water_hardness"}
    assert set(G.GROUP07C_PARAM_IDS.values()) == {257, 260, 316, 401, 402}
    assert dims["vector_habitat"] == 70
    assert dims["dust"] == 88
    assert dims["water_treatment"] == 85
    assert dims["voc"] == 85
    assert dims["water_hardness"] == 80
    assert len(reasons) == 5
    dims_none, reasons_none = score_group07c(None, None)
    assert all(v is None for v in dims_none.values())
    assert reasons_none == []


def test_scores_within_bounds():
    # Sweep distances: every non-None score stays absolute 0..100.
    for d in (0, 10, 49, 50, 51, 300, 1000, 5000):
        pois = [poi("vector_habitat", d), poi("dust_source", d)]
        dims, _ = score_group07c(TALLINN, pois, water_source="central",
                                 building_year=1990)
        for v in dims.values():
            assert v is not None and 0 <= v <= 100
