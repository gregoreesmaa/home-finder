"""Group 11 leftover-A companion dims (issue #134): hermetic binding tests.

No network: the canonical dims run on fixture POIs; this module's own
surface (registry, verdicts, layer-keyed entry point) is asserted as
data. The scorer math itself is covered by test_dims_group11.py and
test_dims_group11b.py -- this file only pins the reuse binding so a
canonical-dim rename breaks loudly here instead of silently unmapping
a shipped layer.
"""

from dims_group11 import (
    dim_forage,
    dim_medical_special,
    dim_rec_special,
    dim_school_bus,
)
from dims_group11b import dim_worship
from dims_group11c import G11C_LAYER_DIMS, G11C_VERDICTS, score_group11c

TALLINN = (59.4372, 24.7536)

# One nearby POI per kind the five dims consume.
POIS = [
    {"kind": "school", "lat": 59.4380, "lon": 24.7550},
    {"kind": "bus_stop", "lat": 59.4375, "lon": 24.7540},
    {"kind": "rec_special", "lat": 59.4385, "lon": 24.7560},
    {"kind": "hospital", "lat": 59.4390, "lon": 24.7570},
    {"kind": "worship", "lat": 59.4379, "lon": 24.7532},
    {"kind": "forest", "lat": 59.4364, "lon": 24.7489},
]


def test_registry_binds_params_to_canonical_dims():
    assert G11C_LAYER_DIMS == {
        "schoolbus": (88, "Koolibussiühendus (hinnang)", dim_school_bus),
        "recspecial": (101, "Erisport ja vaba aeg", dim_rec_special),
        "medspecial": (124, "Eriarstiabi", dim_medical_special),
        "worship": (169, "Pühakojad", dim_worship),
        "forage": (190, "Korjealad (seen/mari)", dim_forage),
    }


def test_verdicts_proxy_only_for_unmapped_bus_routes():
    assert G11C_VERDICTS == {88: "proxy", 101: "real", 124: "real", 169: "real", 190: "real"}
    assert set(G11C_VERDICTS) == {param for param, _, _ in G11C_LAYER_DIMS.values()}


def test_score_group11c_scores_all_layers_near_fixtures():
    scores = score_group11c(TALLINN, POIS)
    assert set(scores) == {"schoolbus", "recspecial", "medspecial", "worship", "forage"}
    for layer, score in scores.items():
        assert score is not None, layer
        assert 60 <= score <= 100, (layer, score)


def test_score_group11c_absent_kinds_use_documented_fallbacks():
    scores = score_group11c(TALLINN, [])
    assert scores == {
        "schoolbus": 15,
        "recspecial": 25,
        "medspecial": 25,
        "worship": 20,
        "forage": 20,
    }


def test_score_group11c_missing_inputs_stay_null():
    assert score_group11c(None, POIS) == {
        "schoolbus": None,
        "recspecial": None,
        "medspecial": None,
        "worship": None,
        "forage": None,
    }
    assert score_group11c(TALLINN, None) == {
        "schoolbus": None,
        "recspecial": None,
        "medspecial": None,
        "worship": None,
        "forage": None,
    }


def test_proxy_reason_never_claims_a_route():
    _, reason = dim_school_bus(TALLINN, POIS)
    assert "hinnang" in reason
    assert "liin" not in reason
