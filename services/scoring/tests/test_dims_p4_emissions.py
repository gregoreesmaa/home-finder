"""P4 emissions avoidance dim (issue #533): hermetic tests.

No network: probe evidence lives in docs/p4_emissions.md (checked
2026-09-16; WFS GetCapabilities + DescribeFeatureType + hits + 1 sample
feature, all HTTP 200). The fixture mirrors the real sample feature
("Katlamaja", HEIT0000008, native EPSG:3301 metres); tests pin the
reader, the inverted bands, NULL-beyond (never "clean air"), and the
honesty markers.
"""

import json

import dims_p4_emissions as emissions
from dims_p4_emissions import (
    P4_EMISSIONS_DIMS,
    dim_emission_avoidance,
    parse_production_installations_geojson,
    score_p4_emissions,
)

TALLINN = (59.4372, 24.7536)
POIS = [
    {"kind": "emission_source", "lat": 59.4380, "lon": 24.7545,
     "name": "Katlamaja", "kotkas_id": "HEIT0000008"},
    {"kind": "emission_source", "lat": 59.4440, "lon": 24.7600,
     "name": "Tehas", "kotkas_id": "HEIT0000009"},
]

SAMPLE_GEOJSON = json.dumps({
    "type": "FeatureCollection",
    "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::3301"}},
    "features": [
        {"type": "Feature", "id": "PF.ProductionInstallation.Heiteallikas-HEIT0000008",
         "geometry": {"type": "Point", "coordinates": [616911.00000003, 6538107.99999902]},
         "properties": {
             "name": "Katlamaja",
             "thematicid_thematicidentifier_identifier": "HEIT0000008",
             "thematicid_thematicidentifier_identifierscheme":
                 "KOTKAS infosüsteemi heiteallikate register"}},
        {"type": "Feature", "id": "broken",
         "geometry": {"type": "Point", "coordinates": [None, None]},
         "properties": {"name": "Katkine"}},
    ],
})


def test_parse_sample_feature_projects_and_counts_drops():
    pois, stats = parse_production_installations_geojson(SAMPLE_GEOJSON)
    assert stats == {"rows": 2, "placed": 1, "dropped_no_xy": 1}
    poi = pois[0]
    assert poi["kind"] == "emission_source"
    assert poi["name"] == "Katlamaja"
    assert poi["kotkas_id"] == "HEIT0000008"
    # Native L-EST97 [616911, 6538107]: must land in Estonia, not the sea.
    assert 57.5 < poi["lat"] < 60.0 and 21.5 < poi["lon"] < 28.0


def test_inverted_bands_pinned():
    # ~150 m -> 35 (avoid); second source ~850 m.
    v, reason = dim_emission_avoidance(TALLINN, POIS)
    assert v == 35
    assert "HEIT0000008" in reason
    assert "mitte" in reason and "kokkupuude" in reason
    v, _ = dim_emission_avoidance((59.4312, 24.7476), [  # ~750 m
        {"kind": "emission_source", "lat": 59.4372, "lon": 24.7536,
         "name": "K", "kotkas_id": ""}])
    assert v == 50
    v, _ = dim_emission_avoidance((59.4250, 24.7400), [
        {"kind": "emission_source", "lat": 59.4372, "lon": 24.7536,
         "name": "K", "kotkas_id": ""}])
    assert v == 65


def test_null_beyond_is_never_clean_air():
    v, reason = dim_emission_avoidance((59.0, 24.0), POIS)
    assert v is None
    assert "EI OLE" in reason
    assert "puhta" in reason
    assert "#524" in reason  # station check pointer, not a score


def test_missing_origin_and_missing_pois_are_null_with_ei_ole():
    v, r = dim_emission_avoidance(None, POIS)
    assert v is None and "EI OLE" in r
    v, r = dim_emission_avoidance(
        TALLINN, [{"kind": "cafe", "lat": 59.43, "lon": 24.75}])
    assert v is None and "EI OLE" in r


def test_registry_and_aggregator_cover_the_dim():
    assert [k for k, _, _ in P4_EMISSIONS_DIMS] == ["emission_avoidance"]
    assert [p for _, p, _ in P4_EMISSIONS_DIMS] == ["P4-042"]
    out = score_p4_emissions(TALLINN, POIS)
    assert out == {"emission_avoidance": 35}
    out = score_p4_emissions(None, None)
    assert out == {"emission_avoidance": None}


def test_reasons_never_claim_measured_exposure():
    _, reason = dim_emission_avoidance(TALLINN, POIS)
    assert "garanteeritud" not in reason
    assert "mitte mõõdetud kokkupuude" in reason  # negated, never claimed
    assert "hinnang" in reason
