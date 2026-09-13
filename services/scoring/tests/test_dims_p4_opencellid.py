"""P4 OpenCellID mast-density dims (issue #269, single-param demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_opencellid.md) means the single scorer is a documented
NULL, so the tests pin the None contract, the Estonian honesty
markers (hinnang + EI OLE + concrete buyer-side checks), the
key-gate evidence markers, the split-slice cousin pointers, and the
registry/aggregator coverage. No token anywhere: the key-gated
bulk is asserted via the reason's dated 401 wording, never via a
live or stored credential.
"""

import dims_p4_opencellid as ocid
from dims_p4_opencellid import (
    P4_OPENCELLID_DIMS,
    dim_mast_density,
    score_p4_opencellid,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_mast_density,
]

EXPECTED_KEYS = [
    "mast_density",
]

EXPECTED_PNUMS = [
    "P4-009",
]


def test_single_dim_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reason_carries_honesty_markers_and_concrete_checks():
    _, reason = dim_mast_density(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # The buyer-side checks: TTJA address check + operator maps + Ookla.
    assert "netikaardilt" in reason
    assert "levikaart" in reason
    assert "Ookla" in reason


def test_reason_names_key_gate_evidence():
    _, reason = dim_mast_density(TALLINN, POIS)
    # Dated-negative key facts from the 2026-09-13 probes (evidence
    # in docs/p4_opencellid.md): the anonymous Tallinn BBOX count
    # 401s and CSV downloads need an access token.
    assert "401" in reason
    assert "API Key not known" in reason
    assert "token" in reason
    assert "võtmeta" in reason
    # The honest future shape is stated, not scored.
    assert "jäme" in reason
    assert "nõrk-hea laega" in reason


def test_reason_names_scored_cousins_never_rescores():
    _, reason = dim_mast_density(TALLINN, POIS)
    # Split-slice contract: the G10 OSM proxy plus the Elektrilevi
    # and Elering legs of the SAME param stay where they live —
    # this NULL must name them.
    assert "dims_group10c" in reason
    assert "dim_internet" in reason
    assert "dims_p4_elektrilevi" in reason
    assert "dim_power_reliability" in reason
    assert "dims_p4_elering" in reason
    assert "dim_system_adequacy" in reason


def test_registry_and_aggregator_cover_single_param():
    assert [k for k, _, _ in P4_OPENCELLID_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_OPENCELLID_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_OPENCELLID_DIMS}) == 1
    assert ocid.P4_OPENCELLID_DIMS is P4_OPENCELLID_DIMS
    out = score_p4_opencellid(TALLINN, POIS)
    assert out == {"mast_density": None}
    assert score_p4_opencellid(None, None) == {"mast_density": None}
