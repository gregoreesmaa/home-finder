"""P4 insurers demo dim (issue #286): hermetic tests.

No network: the single scorer is a proprietary-tariff NULL (2026-09-13
dated-negative verdict, see dims_p4_insurers docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the insurer-leg naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_insurers as insurers
from dims_p4_insurers import (
    P4_INSURERS_DIMS,
    dim_insurer_tariff,
    score_p4_insurers,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_insurer_tariff]

EXPECTED_KEYS = ["insurer_tariff"]

EXPECTED_PNUMS = ["P4-015"]


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
            "kalkulaatorist", "pakkumine", "omavastutust")), \
            fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(insurers)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_insurer_slice_names_proprietary_gap_and_cousin_legs():
    _, reason = dim_insurer_tariff(TALLINN, POIS)
    assert "tariifitsoon" in reason
    assert "PZU" in reason and "ERGO" in reason and "If" in reason
    assert "2026-09-13" in reason
    assert "kalkulaatorist" in reason
    assert "dim_kindlustatavus_kaur" in reason
    assert "dim_kindlustus_eelis" in reason
    assert "dim_theft_tariff_proxy" in reason
    assert "dim_insurability" in reason


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_INSURERS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_INSURERS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_INSURERS_DIMS}) == 1
    out = score_p4_insurers(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_insurers(None, None) == {k: None for k in EXPECTED_KEYS}
    assert insurers.P4_INSURERS_DIMS is P4_INSURERS_DIMS
