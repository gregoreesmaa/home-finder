"""P4 sadam demo + coverage dims (issues #298, #368): hermetic tests.

No network: all four scorers are unpublished-feed NULLs (2026-09-13
dated-negative verdict, see dims_p4_sadam docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE +
buyer-side check pointer), the per-param missing-input naming, and the
registry/aggregator coverage. The module itself makes no network calls
(pinned by source inspection).
"""

import inspect

import dims_p4_sadam as sadam
from dims_p4_sadam import (
    P4_SADAM_DIMS,
    dim_sadam_cruise_calendar,
    dim_sadam_noise_notices,
    dim_sadam_odour_sector,
    dim_sadam_timetable,
    score_p4_sadam,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_sadam_cruise_calendar, dim_sadam_noise_notices,
           dim_sadam_odour_sector, dim_sadam_timetable]

EXPECTED_KEYS = ["sadam_cruise_calendar", "sadam_noise_notices",
                 "sadam_odour_sector", "sadam_timetable"]

EXPECTED_PNUMS = ["P4-033", "P4-023", "P4-053", "P4-055"]


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
        assert "pole" in reason, fn.__name__
        assert any(marker in reason for marker in (
            "ts.ee", "kohapeal", "dims_p4_", "EANS", "Ilmateenistuse",
            "Kaitseväe", "keskkonnaamet.ee", "uudised")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(sadam)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_demo_param_names_timetable_cruise_and_kesk_leg():
    _, reason = dim_sadam_cruise_calendar(TALLINN, POIS)
    assert "kruiisigraafiku" in reason
    assert "/laevad-sadamas/" in reason
    assert "/kruiisid/" in reason
    assert "dims_p4_kesk" in reason


def test_noise_slice_names_trans_kaur_and_ehr_cousins():
    _, reason = dim_sadam_noise_notices(TALLINN, POIS)
    assert "laeva/helikopteri" in reason
    assert "dims_p4_trans" in reason
    assert "dims_p4_kaur" in reason
    assert "dims_p4_ehr" in reason


def test_odour_slice_names_sector_shape_and_rose_cousins():
    _, reason = dim_sadam_odour_sector(TALLINN, POIS)
    assert "sektor + kalender" in reason
    assert "Harku tuuleroosi" in reason
    assert "dims_p4_ilm" in reason
    assert "dims_p4_kaur" in reason
    assert "dims_p4_eelis" in reason
    assert "dims_p4_komun" in reason


def test_timetable_slice_names_foghorns_and_elron_komun_legs():
    _, reason = dim_sadam_timetable(TALLINN, POIS)
    assert "udusireenide/jäämurdjate" in reason
    assert "dims_p4_elron" in reason
    assert "dims_p4_komun" in reason


def test_registry_and_aggregator_cover_all_four():
    assert [k for k, _, _ in P4_SADAM_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_SADAM_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_SADAM_DIMS}) == 4
    out = score_p4_sadam(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_sadam(None, None) == {k: None for k in EXPECTED_KEYS}
    assert sadam.P4_SADAM_DIMS is P4_SADAM_DIMS
