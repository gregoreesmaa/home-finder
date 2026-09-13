"""P4 comapps dims (issues #302 demo + #371 coverage): hermetic tests.

No network: both scorers are closed-feed NULLs, so the tests pin the
None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), and the registry/aggregator coverage.
"""

import dims_p4_comapps as comapps
from dims_p4_comapps import (
    P4_COMAPPS_DIMS,
    dim_grocery_ride,
    dim_taxi_guest,
    score_p4_comapps,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_grocery_ride, dim_taxi_guest]

EXPECTED_KEYS = ["grocery_ride", "taxi_guest"]
EXPECTED_PNUMS = ["P4-027", "P4-049"]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_both_reasons_carry_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "oma aadressil", "tellimusäpp", "taksotellimus",
            "KÜ", "külalise", "kohapeal")), fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_grocery_ride_names_closed_feeds_and_evening_probe():
    _, reason = dim_grocery_ride(TALLINN, POIS)
    assert "Wolt" in reason and "Bolt" in reason
    assert "Barbora" in reason
    assert "kell 22" in reason
    assert "ära feigi" in reason


def test_taxi_guest_names_onsite_test_and_ku_check():
    _, reason = dim_taxi_guest(TALLINN, POIS)
    assert "külalisparkimine" in reason
    assert "KÜ" in reason
    assert "kaardikiht puudub" in reason


def test_registry_and_aggregator_cover_both():
    assert [k for k, _, _ in P4_COMAPPS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_COMAPPS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_COMAPPS_DIMS}) == 2
    out = score_p4_comapps(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_comapps(None, None) == {k: None for k in EXPECTED_KEYS}
    assert comapps.P4_COMAPPS_DIMS is P4_COMAPPS_DIMS
