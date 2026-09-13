"""P4 Elron dims (issues #284 demo + #358 coverage): hermetic tests.

No network: all four scorers are unpublished-feed NULLs (2026-09-13
dated-negative verdict, see dims_p4_elron docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the per-param missing-input naming, and
the registry/aggregator coverage. The module itself makes no network
calls (pinned by source inspection).
"""

import inspect

import dims_p4_elron as elron
from dims_p4_elron import (
    P4_ELRON_DIMS,
    dim_elron_construction_calendar,
    dim_elron_evening_ridership,
    dim_elron_night_maintenance,
    dim_elron_schedule_changes,
    score_p4_elron,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_elron_construction_calendar, dim_elron_evening_ridership,
           dim_elron_night_maintenance, dim_elron_schedule_changes]

EXPECTED_KEYS = ["elron_construction_calendar", "elron_evening_ridership",
                 "elron_night_maintenance", "elron_schedule_changes"]
EXPECTED_PNUMS = ["P4-014", "P4-032", "P4-055", "P4-061"]


def test_all_four_dims_always_none_for_every_input():
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
            "elron.ee", "kohapeal", "Peatus.ee", "dims_p4_rb")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(elron)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_demo_param_names_temporary_timetables_and_rb_sibling():
    _, reason = dim_elron_construction_calendar(TALLINN, POIS)
    assert "ajutiste sõiduplaanide" in reason
    assert "PDF" in reason
    assert "dims_p4_rb" in reason


def test_ridership_slice_is_usage_not_safety():
    _, reason = dim_elron_evening_ridership(TALLINN, POIS)
    assert "kasutus-mitte-turvalisus" in reason
    assert "PPA" in reason


def test_maintenance_slice_names_repair_page_and_other_legs():
    _, reason = dim_elron_night_maintenance(TALLINN, POIS)
    assert "raudteeremondid" in reason
    assert "sadama" in reason


def test_schedule_slice_names_fringe_stations_and_peatus_diff():
    _, reason = dim_elron_schedule_changes(TALLINN, POIS)
    assert "Lilleküla" in reason
    assert "Peatus.ee GTFS diffi" in reason


def test_registry_and_aggregator_cover_all_four():
    assert [k for k, _, _ in P4_ELRON_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_ELRON_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_ELRON_DIMS}) == 4
    out = score_p4_elron(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_elron(None, None) == {k: None for k in EXPECTED_KEYS}
    assert elron.P4_ELRON_DIMS is P4_ELRON_DIMS
