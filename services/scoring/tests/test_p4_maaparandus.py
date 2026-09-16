"""P4 maaparandus dims (issue #551): hermetic tests, fixtures only."""

import dims_p4_maaparandus as maa
from dims_p4_maaparandus import (
    EESVOOL_BAND_M,
    P4_MAAPARANDUS_DIMS,
    P4_MAAPARANDUS_PARAM_IDS,
    build_capabilities_url,
    build_describe_url,
    build_hits_url,
    cache_is_fresh,
    dim_drainage_duty,
    dim_network_wetness,
    score_p4_maaparandus,
)

TALLINN = (59.4372, 24.7536)


def _join(inside_vork=False, ms_kood="1234567890123", inside_kehtetu=False,
          distance_eesvool_m=None):
    return {"inside_vork": inside_vork, "ms_kood": ms_kood,
            "inside_kehtetu": inside_kehtetu,
            "distance_eesvool_m": distance_eesvool_m}


def test_duty_leg_always_null_with_msr_reason():
    v, reason = dim_drainage_duty(TALLINN, _join(inside_vork=True))
    assert v is None
    assert "EI OLE" in reason
    assert "1234567890123" in reason
    assert "MSR" in reason
    # Duty is a legal reading, never asserted from the map.
    assert "kohustus" in reason.lower()
    v2, reason2 = dim_drainage_duty(TALLINN, None)
    assert v2 is None
    assert "EI OLE" in reason2


def test_inside_network_capped_neutral():
    v, reason = dim_network_wetness(TALLINN, _join(inside_vork=True))
    assert v == 55
    assert "1234567890123" in reason
    assert "seisund teadmata" in reason
    assert "MSR" in reason


def test_invalid_system_is_measured_risk():
    v, reason = dim_network_wetness(
        TALLINN, _join(inside_vork=True, inside_kehtetu=True))
    assert v == 40  # kehtetu wins over the neutral inside band
    assert "kehtetus" in reason


def test_near_outflow_dampness_flag():
    v, reason = dim_network_wetness(
        TALLINN, _join(distance_eesvool_m=80.0))
    assert v == 45
    assert "80m" in reason
    assert "ei ole märg krunt" in reason
    v2, _ = dim_network_wetness(TALLINN, _join(distance_eesvool_m=150.0))
    assert v2 is None  # outside the 100 m band


def test_outside_is_null_never_dry():
    v, reason = dim_network_wetness(TALLINN, _join())
    assert v is None
    assert "EI OLE" in reason
    assert "ei ole kuivuse tõend" in reason
    v2, reason2 = dim_network_wetness(TALLINN, None)
    assert v2 is None
    assert "EI OLE" in reason2


def test_band_edge():
    v, _ = dim_network_wetness(
        TALLINN, _join(distance_eesvool_m=EESVOOL_BAND_M))
    assert v == 45
    assert EESVOOL_BAND_M == 100.0


def test_wfs_url_builders():
    assert build_capabilities_url() == (
        "https://gsavalik.envir.ee/geoserver/pta/wfs"
        "?service=WFS&version=2.0.0&request=GetCapabilities")
    assert build_describe_url("pta:msr_vork").endswith(
        "request=DescribeFeatureType&typeNames=pta:msr_vork")
    hits = build_hits_url("pta:msr_vork", (58.9, 23.9, 59.7, 25.4))
    # LAT-LON axis order for EPSG:4326 (the lon-lat order hits zero).
    assert "bbox=58.9,23.9,59.7,25.4,urn:ogc:def:crs:EPSG::4326" in hits
    assert "resultType=hits" in hits
    assert cache_is_fresh("/nonexistent-xyz-maaparandus") is False


def test_licence_gate_documented():
    assert maa.LICENCE == "CC-BY-4.0"
    assert "Kliimaministeerium" in maa.ATTRIBUTION


def test_registry_and_rollup():
    assert set(P4_MAAPARANDUS_DIMS) == {"drainage_duty", "network_wetness"}
    assert P4_MAAPARANDUS_PARAM_IDS == {"drainage_duty": 551,
                                        "network_wetness": 551}
    assert P4_MAAPARANDUS_DIMS["network_wetness"][1] is dim_network_wetness
    assert maa.P4_MAAPARANDUS_DIMS is P4_MAAPARANDUS_DIMS
    dims, reasons = score_p4_maaparandus(TALLINN, _join(inside_vork=True))
    assert dims == {"network_wetness": 55, "drainage_duty": None}
    assert len(reasons) == 1
    dims_none, reasons_none = score_p4_maaparandus(TALLINN, None)
    assert dims_none == {"network_wetness": None, "drainage_duty": None}
    assert reasons_none == []
