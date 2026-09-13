"""P4 fix-it channels dims (issues #301 demo + #370 coverage): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_fixit.md) means both scorers are documented NULLs, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side check), the split-slice cousin pointers,
and the registry/aggregator coverage.
"""

import dims_p4_fixit as fixit
from dims_p4_fixit import (
    P4_FIXIT_DIMS,
    dim_fixit_channel_responsiveness,
    dim_rat_icefall_channel_flags,
    score_p4_fixit,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_fixit_channel_responsiveness,
    dim_rat_icefall_channel_flags,
]

EXPECTED_KEYS = [
    "fixit_channel_responsiveness",
    "rat_icefall_channel_flags",
]

EXPECTED_PNUMS = [
    "P4-026", "P4-062",
]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_both_reasons_carry_honesty_markers_and_concrete_check():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_p4_026_reason_names_channels_and_scored_cousins():
    _, reason = dim_fixit_channel_responsiveness(TALLINN, POIS)
    # Human intake channels: helpline + report map.
    assert "14410" in reason
    assert "annateada.ee" in reason
    # Split-slice contract: the komun / OSM / arireg legs stay scored
    # where they live — this NULL must name them, not rescore.
    assert "dims_p4_komun" in reason
    assert "dim_fixit_responsiveness" in reason
    assert "dims_p4_osm" in reason
    assert "dim_fixit" in reason
    assert "dims_p4_arireg" in reason
    assert "dim_maintenance_echo" in reason


def test_p4_062_reason_names_join_and_never_addresses():
    _, reason = dim_rat_icefall_channel_flags(TALLINN, POIS)
    # Coverage rides the P4-026 join; hex only, never addresses.
    assert "P4-026" in reason
    assert "kunagi mitte aadressid" in reason
    assert "kohapealsel vaatlusel" in reason
    assert "KÜ" in reason
    # Split-slice contract: paaste / komun / OSM / arireg legs stay
    # scored where they live — named, never re-scored here.
    assert "dims_p4_paaste" in reason
    assert "dims_p4_komun" in reason
    assert "dim_rat_icefall_hex" in reason
    assert "dims_p4_osm" in reason
    assert "dim_rats" in reason
    assert "dims_p4_arireg" in reason
    assert "dim_waste_echo" in reason


def test_rate_vs_flags_shapes_do_not_double_score():
    _, rate_reason = dim_fixit_channel_responsiveness(TALLINN, POIS)
    _, flag_reason = dim_rat_icefall_channel_flags(TALLINN, POIS)
    # Lag rate (P4-026) vs count flags (P4-062): different honest
    # shapes, so the reasons must read differently.
    assert "parandamiskiirus" in rate_reason
    assert "lipud" in flag_reason
    assert rate_reason != flag_reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_FIXIT_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_FIXIT_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_FIXIT_DIMS}) == 2
    out = score_p4_fixit(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_fixit(None, None) == {k: None for k in EXPECTED_KEYS}
    assert fixit.P4_FIXIT_DIMS is P4_FIXIT_DIMS
