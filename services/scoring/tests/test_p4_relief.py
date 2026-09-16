"""P4 DTM relief dims (issue #553): hermetic tests, fixtures only."""

import dims_p4_relief as relief
from dims_p4_relief import (
    P4_RELIEF_DIMS,
    P4_RELIEF_PARAM_IDS,
    build_capabilities_url,
    build_describe_url,
    build_window_url,
    cache_is_fresh,
    classify_character,
    dim_cycling_effort,
    dim_driveway_grade,
    dim_klint_edge,
    dim_lowland_dampness,
    dim_viewpoint,
    p336_agreement,
    score_p4_relief,
)

TALLINN = (59.4372, 24.7536)


def _join(slope_deg=1.0, rel_elev_m=0.0, dist_klint_m=None,
          coverage_id="dtm-1", vintage="2024"):
    return {"slope_deg": slope_deg, "rel_elev_m": rel_elev_m,
            "dist_klint_m": dist_klint_m, "coverage_id": coverage_id,
            "vintage": vintage}


def test_character_overlay_has_no_score():
    assert classify_character(0.5, 0.0) == "tasane"
    assert classify_character(3.0, 0.0) == "laanõlv"
    assert classify_character(7.0, 5.0) == "nõlv"
    assert classify_character(12.0, 5.0) == "järsak"
    assert classify_character(25.0, 25.0) == "klindiserv"
    assert classify_character(1.0, -5.0) == "madalik"
    assert classify_character(1.0, 20.0) == "kõrgendik"
    # Steep but low = järsak, never klindiserv without height.
    assert classify_character(25.0, 0.0) == "järsak"


def test_lowland_flag_flood_avoider_taste():
    v, reason = dim_lowland_dampness(TALLINN, _join(1.0, -5.0))
    assert v == 45
    assert "madalik" in reason
    assert "üleujutus" in reason
    assert "libisemisrisk" in reason  # slope != slide risk, stated
    v2, reason2 = dim_lowland_dampness(TALLINN, _join(1.0, 5.0))
    assert v2 is None
    assert "EI OLE" in reason2


def test_viewpoint_view_seeker_taste():
    v, reason = dim_viewpoint(TALLINN, _join(3.0, 20.0))
    assert v == 65
    assert "vaateotsija" in reason
    assert "näitab vaadet, mitte keeldu" in reason
    assert "hinnamodelleerimisse" in reason  # no view monetisation
    v2, _ = dim_viewpoint(TALLINN, _join(3.0, 5.0))
    assert v2 is None


def test_cycling_cyclist_taste():
    v, _ = dim_cycling_effort(TALLINN, _join(12.0, 5.0))
    assert v == 45
    v2, reason2 = dim_cycling_effort(TALLINN, _join(7.0, 5.0))
    assert v2 == 60
    assert "ratturi" in reason2
    v3, _ = dim_cycling_effort(TALLINN, _join(1.0, 0.0))
    assert v3 is None


def test_klint_edge_buyer_check_never_ban():
    v, reason = dim_klint_edge(TALLINN, _join(25.0, 25.0))
    assert v == 50
    assert "kuju, mitte keeldu" in reason
    assert "libisemisrisk" in reason
    v2, _ = dim_klint_edge(TALLINN, _join(3.0, 2.0, dist_klint_m=100.0))
    assert v2 == 50  # proximity alone triggers the check
    v3, _ = dim_klint_edge(TALLINN, _join(3.0, 2.0, dist_klint_m=500.0))
    assert v3 is None


def test_driveway_grade_graduates_null():
    v, reason = dim_driveway_grade(TALLINN, _join(12.0, 5.0))
    assert v == 50
    assert "Mõõdetud kalle" in reason
    assert "ostja kontrolliks" in reason  # kerbs stay buyer check
    v2, _ = dim_driveway_grade(TALLINN, _join(6.0, 2.0))
    assert v2 == 65
    v3, _ = dim_driveway_grade(TALLINN, _join(1.0, 0.0))
    assert v3 is None


def test_missing_and_partial_join_is_null():
    for join in (None, {}, {"slope_deg": 5.0}, {"rel_elev_m": 3.0}):
        for dim in (dim_lowland_dampness, dim_viewpoint,
                    dim_cycling_effort, dim_klint_edge,
                    dim_driveway_grade):
            v, reason = dim(TALLINN, join)
            assert v is None, (dim, join)
            assert "EI OLE" in reason


def test_p336_cross_check_labels():
    assert p336_agreement(True, 25.0) == "kokkulangevus"
    assert p336_agreement(False, 1.0) == "kokkulangevus"
    assert p336_agreement(True, 1.0) == "lahknevus"
    assert p336_agreement(False, 25.0) == "lahknevus"
    assert p336_agreement(True, None) == "hindamata"


def test_wcs_url_builders_and_service_facts():
    assert build_capabilities_url() == (
        "https://teenus.maaamet.ee/ows/wcs-dtm"
        "?service=WCS&request=GetCapabilities")
    assert build_describe_url("dtm-1").endswith(
        "request=DescribeCoverage&coverageId=dtm-1")
    url = build_window_url("dtm-1", 6591000, 6591200, 543800, 544200)
    # Northings in y, eastings in x (axisLabels y x).
    assert "SUBSET=y(6591000,6591200)" in url
    assert "SUBSET=x(543800,544200)" in url
    assert relief.COVERAGES == ("dtm-25", "dtm-10", "dtm-1")
    assert relief.NATIVE_CRS == "EPSG:3301"
    assert relief.LICENCE == "CC-BY-4.0"
    assert cache_is_fresh("/nonexistent-xyz-relief") is False


def test_registry_and_rollup():
    assert set(P4_RELIEF_DIMS) == {"lowland_dampness", "viewpoint",
                                   "cycling_effort", "klint_edge",
                                   "driveway_grade"}
    assert set(P4_RELIEF_PARAM_IDS) == set(P4_RELIEF_DIMS)
    assert all(pid == 553 for pid in P4_RELIEF_PARAM_IDS.values())
    assert relief.P4_RELIEF_DIMS is P4_RELIEF_DIMS
    dims, reasons = score_p4_relief(TALLINN, _join(25.0, 25.0))
    assert dims["klint_edge"] == 50
    assert dims["viewpoint"] == 65
    assert dims["cycling_effort"] == 45
    assert dims["lowland_dampness"] is None
    assert len(reasons) == 4  # NULL dims contribute no reasons
    dims_none, reasons_none = score_p4_relief(TALLINN, None)
    assert all(v is None for v in dims_none.values())
    assert reasons_none == []
