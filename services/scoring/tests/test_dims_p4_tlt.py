"""P4 TLT dims (issues #277 demo + #351 coverage): hermetic tests.

No network: all nine scorers are unpublished-feed NULLs (2026-09-13
dated-negative verdict, see dims_p4_tlt docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the per-param missing-input naming, and
the registry/aggregator coverage. The module itself makes no network
calls (pinned by source inspection).
"""

import inspect

import dims_p4_tlt as tlt
from dims_p4_tlt import (
    P4_TLT_DIMS,
    dim_tlt_bus_cut,
    dim_tlt_commute_offset,
    dim_tlt_delight_access,
    dim_tlt_evening_access,
    dim_tlt_evening_ridership,
    dim_tlt_guest_arrival,
    dim_tlt_night_network,
    dim_tlt_school_routes,
    dim_tlt_winter_ops,
    score_p4_tlt,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "stop", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_tlt_bus_cut, dim_tlt_school_routes, dim_tlt_winter_ops,
           dim_tlt_night_network, dim_tlt_evening_ridership,
           dim_tlt_commute_offset, dim_tlt_evening_access,
           dim_tlt_delight_access, dim_tlt_guest_arrival]

EXPECTED_KEYS = ["tlt_bus_cut", "tlt_school_routes", "tlt_winter_ops",
                 "tlt_night_network", "tlt_evening_ridership",
                 "tlt_commute_offset", "tlt_evening_access",
                 "tlt_delight_access", "tlt_guest_arrival"]
EXPECTED_PNUMS = ["P4-061", "P4-012", "P4-018", "P4-027", "P4-032",
                  "P4-037", "P4-045", "P4-048", "P4-049"]


def test_all_nine_dims_always_none_for_every_input():
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
        assert any(marker in reason for marker in (
            "tlt.ee", "transport.tallinn.ee", "reisplaneerijast",
            "reisplaneerijaga", "kohapeal", "EMTA", "OSM")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(tlt)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_demo_param_names_line_change_notices_and_fringe_check():
    _, reason = dim_tlt_bus_cut(TALLINN, POIS)
    assert "liinimuudatuste" in reason
    assert "teadeteajaloos" in reason or "teadeteajalugu" in reason


def test_winter_slice_names_autumn_timetable_gap():
    _, reason = dim_tlt_winter_ops(TALLINN, POIS)
    assert "sügis-talvised" in reason or "talvist" in reason
    assert "talihoolduse" in reason


def test_night_slice_names_planner_and_food_coverage_check():
    _, reason = dim_tlt_night_network(TALLINN, POIS)
    assert "ööbusside" in reason or "öövõrgu" in reason
    assert "Wolt" in reason


def test_ridership_slice_is_usage_not_safety():
    _, reason = dim_tlt_evening_ridership(TALLINN, POIS)
    assert "kasutus-mitte-turvalisus" in reason
    assert "PPA" in reason


def test_commute_slice_names_emta_calculator():
    _, reason = dim_tlt_commute_offset(TALLINN, POIS)
    assert "EMTA" in reason
    assert "reisplaneerija" in reason


def test_guest_slice_names_saturday_19_probe():
    _, reason = dim_tlt_guest_arrival(TALLINN, POIS)
    assert "19:00" in reason
    assert "Bolti" in reason


def test_registry_and_aggregator_cover_all_nine():
    assert [k for k, _, _ in P4_TLT_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_TLT_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_TLT_DIMS}) == 9
    out = score_p4_tlt(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_tlt(None, None) == {k: None for k in EXPECTED_KEYS}
    assert tlt.P4_TLT_DIMS is P4_TLT_DIMS
