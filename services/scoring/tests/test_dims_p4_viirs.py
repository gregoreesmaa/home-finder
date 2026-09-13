"""P4 VIIRS demo dim (issue #325): hermetic tests.

No network: the scorer is a login-walled-source NULL
(2026-09-13 dated-negative verdict, see dims_p4_viirs docstring),
so the tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + buyer-side check pointer), the missing-leg
naming, and the registry/aggregator coverage. The module itself
makes no network calls (pinned by source inspection).
"""

import inspect

import dims_p4_viirs as viirs
from dims_p4_viirs import (
    P4_VIIRS_DIMS,
    dim_viirs_radiance,
    score_p4_viirs,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "street_lamp", "lat": 59.4382, "lon": 24.7536}]


def test_dim_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_viirs_radiance(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    _, reason = dim_viirs_radiance(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "kohapeal" in reason and "detsembri" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(viirs)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_reason_names_login_wall_and_no_faked_number():
    _, reason = dim_viirs_radiance(TALLINN, POIS)
    assert "VIIRS" in reason
    assert "Keycloak" in reason
    assert "302" in reason
    assert "radiantsinumbrit" in reason


def test_reason_names_sibling_slices_without_rescoring():
    _, reason = dim_viirs_radiance(TALLINN, POIS)
    assert "dims_p4_veebi" in reason
    assert "dims_p4_ilm" in reason
    assert "dims_p4_maa_lidar" in reason
    assert "dims_p4_ehr" in reason
    assert "dims_p4_osm" in reason


def test_registry_and_aggregator_cover_the_single_dim():
    assert [k for k, _, _ in P4_VIIRS_DIMS] == ["viirs_radiance"]
    assert [p for _, p, _ in P4_VIIRS_DIMS] == ["P4-035"]
    assert len({fn for _, _, fn in P4_VIIRS_DIMS}) == 1
    out = score_p4_viirs(TALLINN, POIS)
    assert out == {"viirs_radiance": None}
    assert score_p4_viirs(None, None) == {"viirs_radiance": None}
    assert viirs.P4_VIIRS_DIMS is P4_VIIRS_DIMS
