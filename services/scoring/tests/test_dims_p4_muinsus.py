"""P4 muinsus demo + coverage dims (issues #324, #380): hermetic tests.

No network: both scorers are down-registry NULLs (2026-09-13
dated-negative verdict, see dims_p4_muinsus docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the per-param missing-input naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_muinsus as muinsus
from dims_p4_muinsus import (
    P4_MUINSUS_DIMS,
    dim_glimpse_corridor,
    dim_permit_heritage,
    score_p4_muinsus,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_permit_heritage, dim_glimpse_corridor]

EXPECTED_KEYS = ["permit_heritage", "glimpse_corridor"]

EXPECTED_PNUMS = ["P4-005", "P4-041"]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_all_reasons_carry_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "pole" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "kohapeal", "dims_p4_", "dims_group06", "Muinsuskaitseamet",
            "register.muinas.ee", "vaatekohtade")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(muinsus)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_demo_param_names_dead_host_down_register_and_ehr_group06_legs():
    _, reason = dim_permit_heritage(TALLINN, POIS)
    assert "register.muinsuskaitseamet.ee" in reason
    assert "NXDOMAIN" in reason
    assert "register.muinas.ee" in reason
    assert "520" in reason
    assert "dims_p4_ehr" in reason
    assert "dims_group06" in reason


def test_corridor_slice_names_corridor_gap_and_ehr_lidar_legs():
    _, reason = dim_glimpse_corridor(TALLINN, POIS)
    assert "vaatekoridor" in reason
    assert "520" in reason
    assert "vaatekohtade" in reason
    assert "dims_p4_ehr" in reason
    assert "LiDAR" in reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_MUINSUS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_MUINSUS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_MUINSUS_DIMS}) == 2
    out = score_p4_muinsus(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_muinsus(None, None) == {k: None for k in EXPECTED_KEYS}
    assert muinsus.P4_MUINSUS_DIMS is P4_MUINSUS_DIMS
