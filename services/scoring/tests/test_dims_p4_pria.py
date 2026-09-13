"""P4 PRIA field-block dims (issue #299, single-param demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_pria.md) means the single scorer is a documented NULL, so
the tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + concrete buyer-side checks), the probe-evidence
markers (kls.pria.ee interactive map + Teabevärav JS-shell catalogue),
the split-slice cousin pointers, and the registry/aggregator coverage.
"""

import inspect

import dims_p4_pria as pria
from dims_p4_pria import (
    P4_PRIA_DIMS,
    dim_pollupuhver_pria,
    score_p4_pria,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_pollupuhver_pria,
]

EXPECTED_KEYS = [
    "pollupuhver_pria",
]

EXPECTED_PNUMS = [
    "P4-024",
]


def test_single_dim_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reason_carries_honesty_markers_and_concrete_checks():
    _, reason = dim_pollupuhver_pria(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # The buyer-side checks: on-site spray-strip/green-edge/farm-smell
    # watch plus the KÜ/neighbour spray-schedule question.
    assert "kohapealsel vaatlusel" in reason
    assert "pritsimisriba" in reason
    assert "farmilõhna" in reason
    assert "pritsimisgraafikut" in reason


def test_reason_names_probe_evidence():
    _, reason = dim_pollupuhver_pria(TALLINN, POIS)
    # Dated-negative facts from the 2026-09-13 probes (evidence in
    # docs/p4_pria.md): the veebikaart is an interactive last-two-years
    # lookup and the Teabevärav catalogue has no server-rendered bulk.
    assert "kls.pria.ee" in reason
    assert "veebikaart" in reason
    assert "kahel viimasel aastal" in reason
    assert "Teabevärava" in reason
    assert "põllumassiivide hulgitõmmet" in reason
    # The honest future shape is stated, not scored.
    assert "jäme" in reason
    assert "SHP/CSV" in reason


def test_reason_names_scored_cousins_never_rescores():
    _, reason = dim_pollupuhver_pria(TALLINN, POIS)
    # Split-slice contract: the scored KAUR pollen + EELIS habitat legs
    # and the NULL Terviseamet + komun legs of the SAME param stay
    # where they live — this NULL must name them.
    assert "dims_p4_kaur" in reason
    assert "dim_tervis_kaur" in reason
    assert "dims_p4_eelis" in reason
    assert "dim_maaloodus_eelis" in reason
    assert "dims_p4_tervise" in reason
    assert "dim_country_health_nuisances" in reason
    assert "dims_p4_komun" in reason
    assert "dim_farm_odour_cells" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(pria)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator_cover_single_param():
    assert [k for k, _, _ in P4_PRIA_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_PRIA_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_PRIA_DIMS}) == 1
    assert pria.P4_PRIA_DIMS is P4_PRIA_DIMS
    out = score_p4_pria(TALLINN, POIS)
    assert out == {"pollupuhver_pria": None}
    assert score_p4_pria(None, None) == {"pollupuhver_pria": None}
