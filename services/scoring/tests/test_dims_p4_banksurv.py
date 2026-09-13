"""P4 banksurv demo dim (issue #323): hermetic tests.

No network: the single scorer is a proprietary-survey NULL (2026-09-13
dated-negative verdict, see dims_p4_banksurv docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the bank-leg naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_banksurv as banksurv
from dims_p4_banksurv import (
    P4_BANKSURV_DIMS,
    dim_bargaining_margin_banksurv,
    score_p4_banksurv,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_bargaining_margin_banksurv]

EXPECTED_KEYS = ["bargaining_margin_banksurv"]

EXPECTED_PNUMS = ["P4-038"]


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
            "maaklerilt", "publikatsioon", "võrdlustehingutega")), \
            fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(banksurv)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_bank_slice_names_proprietary_gap_and_cousin_legs():
    _, reason = dim_bargaining_margin_banksurv(TALLINN, POIS)
    assert "tagatis" in reason
    assert "Swedbank" in reason and "SEB" in reason and "Luminor" in reason
    assert "2026-09-13" in reason
    assert "maaklerilt" in reason
    assert "dim_bargaining_margin" in reason
    assert "dim_bargaining_margin_stat" in reason
    assert "dims_p4_maa_tehingud" in reason
    assert "dims_p4_stat" in reason
    assert "dims_p4_own_store" in reason


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_BANKSURV_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_BANKSURV_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_BANKSURV_DIMS}) == 1
    out = score_p4_banksurv(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_banksurv(None, None) == {k: None for k in EXPECTED_KEYS}
    assert banksurv.P4_BANKSURV_DIMS is P4_BANKSURV_DIMS
