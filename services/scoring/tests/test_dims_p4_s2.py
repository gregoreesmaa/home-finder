"""P4 Sentinel-2 demo dim (issue #305): hermetic tests.

No network: the single scorer is a keyed-pixel-bulk NULL (2026-09-13
dated-negative verdict, see dims_p4_s2 docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the Sentinel-2-leg naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_s2 as s2
from dims_p4_s2 import (
    P4_S2_DIMS,
    dim_rohemuutus_s2,
    score_p4_s2,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_rohemuutus_s2]

EXPECTED_KEYS = ["rohemuutus_s2"]

EXPECTED_PNUMS = ["P4-030"]


def test_single_dim_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "aerofoto", "raielube", "kohapeal")), \
            fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(s2)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_sentinel_slice_names_keyed_gap_and_cousin_leg():
    _, reason = dim_rohemuutus_s2(TALLINN, POIS)
    assert "Sentinel-2" in reason
    assert "S3" in reason and "registreeritud kontot" in reason
    assert "STAC" in reason and "NDVI-mõõt" in reason
    assert "2026-09-13" in reason
    assert "dims_p4_eelis" in reason
    assert "dim_rohemuutus_eelis" in reason


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_S2_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_S2_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_S2_DIMS}) == 1
    out = score_p4_s2(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_s2(None, None) == {k: None for k in EXPECTED_KEYS}
    assert s2.P4_S2_DIMS is P4_S2_DIMS
