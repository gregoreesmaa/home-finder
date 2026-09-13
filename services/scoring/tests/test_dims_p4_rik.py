"""P4 RIK e-Kinnistusraamat dims (issue #252, single-param demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_rik.md) means the single scorer is a documented NULL, so
the tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + concrete buyer-side check), the paid-flow
evidence markers, the split-slice cousin pointers, and the
registry/aggregator coverage.
"""

import dims_p4_rik as rik
from dims_p4_rik import (
    P4_RIK_DIMS,
    dim_rik_extract,
    score_p4_rik,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_rik_extract,
]

EXPECTED_KEYS = [
    "rik_extract",
]

EXPECTED_PNUMS = [
    "P4-004",
]


def test_single_dim_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reason_carries_honesty_markers_and_concrete_check():
    _, reason = dim_rik_extract(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # The buyer-side check: paid extract + notary checkpoint.
    assert "väljavõte" in reason
    assert "notari" in reason
    assert "notar.ee" in reason


def test_reason_names_paid_flow_evidence():
    _, reason = dim_rik_extract(TALLINN, POIS)
    # Dated-negative money facts from the RIK hinnakiri probe
    # (2026-09-13, evidence in docs/p4_rik.md): per-jagu fees and
    # the contract-walled bulk shape.
    assert "tasuline" in reason
    assert "2 €" in reason
    assert "6 €" in reason
    assert "leping" in reason
    # The honest future shape is stated, not scored.
    assert "nõrk-hea laega" in reason
    assert "keelumärge/hüpoteek" in reason


def test_reason_names_scored_cousins_never_rescores():
    _, reason = dim_rik_extract(TALLINN, POIS)
    # Split-slice contract: the KKIS / AT / EMTA / täitur legs of
    # the SAME param stay scored where they live — this NULL must
    # name them.
    assert "dims_p4_maa_kataster" in reason
    assert "dim_kinnistus_syva" in reason
    assert "dims_p4_ata" in reason
    assert "dims_p4_emta" in reason
    assert "dim_kinnistus_debt" in reason
    assert "dims_p4_taitur" in reason
    assert "dim_kinnistus_checkpoint" in reason


def test_registry_and_aggregator_cover_single_param():
    assert [k for k, _, _ in P4_RIK_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_RIK_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_RIK_DIMS}) == 1
    assert rik.P4_RIK_DIMS is P4_RIK_DIMS
    out = score_p4_rik(TALLINN, POIS)
    assert out == {"rik_extract": None}
    assert score_p4_rik(None, None) == {"rik_extract": None}
