"""P4 ETAK measured legs (issue #552): hermetic tests, fixtures only."""

import dims_p4_etak as etak
from dims_p4_etak import (
    P4_ETAK_DIMS,
    P4_ETAK_PARAM_IDS,
    dim_ground_exposure,
    dim_relief_objects,
    dim_water_drainage,
    dim_wetland_dampness,
    score_p4_etak,
)

TALLINN = (59.4372, 24.7536)


def _join(klass="mets", vintage="2024", veetüüp=None, laius_m=None,
          kaugus_m=None, truup=False, hydro_vintage="2024"):
    join = {"maakate": {"klass": klass, "vintage": vintage}}
    if veetüüp is not None or kaugus_m is not None:
        join["hydro"] = {"veetüüp": veetüüp, "laius_m": laius_m,
                         "kaugus_m": kaugus_m, "truup": truup,
                         "vintage": hydro_vintage}
    return join


def test_wetland_classes_score():
    for klass, want in (("madalsoo", 40), ("õõtsik", 40),
                        ("raba", 50), ("soovik", 50)):
        v, reason = dim_wetland_dampness(TALLINN, _join(klass=klass))
        assert v == want, klass
        assert klass in reason
        assert "2024" in reason  # vintage rides along, never mixed silently
        assert "hinnang" in reason


def test_wetland_nonwetland_and_missing_are_null():
    v, reason = dim_wetland_dampness(TALLINN, _join(klass="mets"))
    assert v is None
    assert "ei ole kuivuse tõend" in reason
    v2, reason2 = dim_wetland_dampness(TALLINN, _join(klass=None))
    assert v2 is None
    assert "EI OLE" in reason2
    v3, reason3 = dim_wetland_dampness(TALLINN, None)
    assert v3 is None
    assert "EI OLE" in reason3


def test_water_wide_flow_and_near():
    v, reason = dim_water_drainage(
        TALLINN, _join(veetüüp="vooluvesi", laius_m=15.0, kaugus_m=60.0))
    assert v == 45
    assert "15m" in reason
    v2, _ = dim_water_drainage(
        TALLINN, _join(veetüüp="seisuvesi", laius_m=30.0, kaugus_m=90.0))
    assert v2 == 55
    v3, reason3 = dim_water_drainage(
        TALLINN, _join(veetüüp="vooluvesi", laius_m=15.0, kaugus_m=60.0,
                       truup=True))
    assert v3 == 45
    assert "truubiga" in reason3


def test_water_outside_band_is_null_never_dry():
    v, reason = dim_water_drainage(
        TALLINN, _join(veetüüp="vooluvesi", laius_m=15.0, kaugus_m=150.0))
    assert v is None
    assert "100m" in reason
    assert "ei ole kuivuse tõend" in reason
    v2, reason2 = dim_water_drainage(TALLINN, _join(klass="mets"))
    assert v2 is None
    assert "EI OLE" in reason2


def test_ground_classes_confirm():
    for klass, want in (("eraõued", 55), ("tootmisõued", 55),
                        ("tühermaa", 50), ("haljasala", 70)):
        v, reason = dim_ground_exposure(TALLINN, _join(klass=klass))
        assert v == want, klass
        assert "ETAK-klass" in reason
    v, reason = dim_ground_exposure(TALLINN, _join(klass="põld"))
    assert v is None
    assert "EI OLE" in reason


def test_pinnamood_leg_licence_gated():
    for join in (None, _join(), {"pinnamood": {"lähedus_m": 5}}):
        v, reason = dim_relief_objects(TALLINN, join)
        assert v is None
        assert "EI OLE" in reason
        assert "litsents" in reason


def test_licence_table():
    assert etak.LICENCE_BY_THEME["maakate"] == "CC-BY-4.0"
    assert etak.LICENCE_BY_THEME["hudrograafia"] == "CC-BY-4.0"
    assert etak.LICENCE_BY_THEME["pinnamood"] == "UNVERIFIED"
    assert "Maa- ja Ruumiamet" in etak.ATTRIBUTION


def test_registry_and_rollup():
    assert set(P4_ETAK_DIMS) == {"wetland_dampness", "water_drainage",
                                 "ground_exposure", "relief_objects"}
    assert set(P4_ETAK_PARAM_IDS) == set(P4_ETAK_DIMS)
    assert all(pid == 552 for pid in P4_ETAK_PARAM_IDS.values())
    assert etak.P4_ETAK_DIMS is P4_ETAK_DIMS
    join = _join(klass="madalsoo", veetüüp="vooluvesi", laius_m=12.0,
                 kaugus_m=50.0)
    dims, reasons = score_p4_etak(TALLINN, join)
    assert dims == {"wetland_dampness": 40, "water_drainage": 45,
                    "ground_exposure": None, "relief_objects": None}
    assert len(reasons) == 2  # NULL dims contribute no reasons
    dims_none, reasons_none = score_p4_etak(TALLINN, None)
    assert all(v is None for v in dims_none.values())
    assert reasons_none == []
