"""P4 CitySens pilot dims (issue #307, single-param demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_citysens.md) means the single scorer is a documented
NULL, so the tests pin the None contract, the Estonian honesty
markers (hinnang + EI OLE + concrete buyer-side checks), the
press-release evidence markers, the split-slice cousin pointers, and
the registry/aggregator coverage. No pilot feed is fetched anywhere:
the dated probes live only in the reason wording and docs.
"""

import inspect

import dims_p4_citysens as citysens
from dims_p4_citysens import (
    P4_CITYSENS_DIMS,
    dim_pilot_microclimate,
    score_p4_citysens,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_pilot_microclimate,
]

EXPECTED_KEYS = [
    "pilot_microclimate",
]

EXPECTED_PNUMS = [
    "P4-031",
]


def test_single_dim_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reason_carries_honesty_markers_and_concrete_checks():
    _, reason = dim_pilot_microclimate(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # The buyer-side checks: DIY sensor map + on-site shade/wind visit.
    assert "sensor.community" in reason
    assert "kohapealse" in reason


def test_reason_names_press_release_evidence():
    _, reason = dim_pilot_microclimate(TALLINN, POIS)
    # Dated-negative facts from the 2026-09-13 probes (evidence
    # in docs/p4_citysens.md): press pages, dead programme URL,
    # no machine links on either pilot page.
    assert "pressiteade" in reason
    assert "Tehnopol" in reason
    assert "Tallinnovation" in reason
    assert "404" in reason
    assert "masinlingi" in reason
    # The honest future shape is stated, not scored.
    assert "jäme" in reason
    assert "nõrk-hea laega" in reason


def test_reason_names_scored_cousins_never_rescores():
    _, reason = dim_pilot_microclimate(TALLINN, POIS)
    # Split-slice contract: the Harku, LiDAR, EHR and OSM legs of
    # the SAME param stay where they live — this NULL must name them.
    assert "dims_p4_ilm" in reason
    assert "dims_p4_maa_lidar" in reason
    assert "dims_p4_ehr" in reason
    assert "dims_p4_osm" in reason
    assert "dim_backyard_weather" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(citysens)
    assert "httpx" not in src
    assert "urlopen" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator_cover_single_param():
    assert [k for k, _, _ in P4_CITYSENS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_CITYSENS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_CITYSENS_DIMS}) == 1
    assert citysens.P4_CITYSENS_DIMS is P4_CITYSENS_DIMS
    out = score_p4_citysens(TALLINN, POIS)
    assert out == {"pilot_microclimate": None}
    assert score_p4_citysens(None, None) == {"pilot_microclimate": None}
