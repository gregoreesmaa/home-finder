"""Hermetic tests for dims_group02.py (issue #136).

No network, no snapshot, no EHR: pure listing-attribute inputs only. Run:
  python3 -m pytest services/scoring/tests/test_dims_group02.py -q
"""

import dims_group02 as G
from dims_group02 import (
    dim_accessibility,
    dim_energy,
    dim_permits,
    score_group02,
)


def test_none_only_when_missing_or_unknown():
    # Missing inputs stay None (Flag NULL, never fake).
    assert dim_energy(None)[0] is None
    assert dim_energy("")[0] is None
    assert dim_permits(None)[0] is None
    assert dim_accessibility(None, None)[0] is None
    assert dim_accessibility(None, False)[0] is None
    assert dim_accessibility("korrus", None)[0] is None
    assert dim_accessibility(0, False)[0] is None
    # Unknown codes stay None -- never mapped to a neighbour band.
    assert dim_energy("A+")[0] is None
    assert dim_energy("B!")[0] is None
    assert dim_permits("renovation")[0] is None
    # Floor known above ground but lift unknown: cannot score access.
    assert dim_accessibility(3, None)[0] is None


def test_reasons_are_estonian_and_name_the_source():
    _, r = dim_energy("B")
    assert "Energiaklass B" in r and "mitte hinnang" in r
    assert dim_energy(None)[1] == "Energiaklass puudub"
    _, r = dim_permits("clean")
    assert "korras" in r.lower() or "Load korras" in r
    assert dim_permits(None)[1] == "Loaajaloo info puudub"
    _, r = dim_accessibility(1, None)
    assert "1. korrus" in r
    assert dim_accessibility(None, None)[1] == "Korruse/lifti info puudub"
    # Unknown codes echo back (reviewable) instead of guessing.
    assert "A+" in dim_energy("A+")[1]
    assert "renovation" in dim_permits("renovation")[1]


def test_energy_bands_monotonic_a_to_g():
    scores = [dim_energy(c)[0] for c in "ABCDEFG"]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 100  # A
    assert scores == [100, 90, 78, 62, 45, 28, 12]
    # Case-insensitive, whitespace-tolerant.
    assert dim_energy("  c ")[0] == 78
    assert G.ENERGY_BANDS["A"] == 100


def test_permits_clean_top_unpermitted_bottom():
    assert dim_permits("clean")[0] == 100
    assert dim_permits("flagged")[0] == 20
    assert dim_permits("unpermitted_work")[0] == 0
    assert "kontrolli" in dim_permits("flagged")[1]
    # Case-insensitive.
    assert dim_permits("Clean")[0] == 100


def test_accessibility_lift_and_ground_top_walkup_decays():
    assert dim_accessibility(1, None)[0] == 100  # ground, lift unknown
    assert dim_accessibility(1, False)[0] == 100  # ground needs no lift
    assert dim_accessibility(5, True)[0] == 100  # lift serves all floors
    assert dim_accessibility(None, True)[0] == 100  # lift building
    assert dim_accessibility(2, False)[0] == 80
    assert dim_accessibility(3, False)[0] == 60
    assert dim_accessibility(4, False)[0] == 40
    assert dim_accessibility(5, False)[0] == 25
    assert dim_accessibility(9, False)[0] == 25
    assert "ilma liftita" in dim_accessibility(3, False)[1]


def test_registry_and_aggregate():
    assert [k for k, _, _ in G.GROUP02_DIMS] == [
        "accessibility", "energy", "permits"]
    assert [p for _, p, _ in G.GROUP02_DIMS] == ["p30", "p35", "p48"]
    assert set(G.GROUP02_NO_DIM) == {"p21", "p33"}
    full = {"floor": 3, "has_lift": False,
            "energy_class": "C", "permit_status": "clean"}
    assert score_group02(full) == {
        "accessibility": 60, "energy": 78, "permits": 100}
    assert score_group02(None) == {
        "accessibility": None, "energy": None, "permits": None}
    assert score_group02({}) == {
        "accessibility": None, "energy": None, "permits": None}
    assert set(score_group02(None)) == {k for k, _, _ in G.GROUP02_DIMS}
