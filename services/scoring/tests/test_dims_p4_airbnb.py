"""P4 airbnb demo dim (issue #293): hermetic tests.

No network: the single scorer is an open-licence/no-Tallinn NULL
(2026-09-13 dated-negative verdict, see dims_p4_airbnb docstring), so
the tests pin the None contract, the Estonian honesty markers (hinnang
+ EI OLE + buyer-side check pointer), the Tallinn-gap naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_airbnb as airbnb
from dims_p4_airbnb import (
    P4_AIRBNB_DIMS,
    dim_short_rental_density,
    score_p4_airbnb,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_short_rental_density]

EXPECTED_KEYS = ["short_rental_density"]

EXPECTED_PNUMS = ["P4-003"]


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
            "KÜ", "REL2021", "KV")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(airbnb)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_density_slice_names_tallinn_gap_and_cousin_legs():
    _, reason = dim_short_rental_density(TALLINN, POIS)
    assert "Inside Airbnb" in reason
    assert "Tallinna" in reason
    assert "2026-09-13" in reason
    assert "Riia" in reason
    assert "KÜ" in reason
    assert "REL2021" in reason
    assert "KV" in reason


def test_registry_and_aggregator_cover_single_dim():
    assert [k for k, _, _ in P4_AIRBNB_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_AIRBNB_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_AIRBNB_DIMS}) == 1
    out = score_p4_airbnb(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_airbnb(None, None) == {k: None for k in EXPECTED_KEYS}
    assert airbnb.P4_AIRBNB_DIMS is P4_AIRBNB_DIMS
