"""P4 libs demo + coverage dims (issues #321, #379): hermetic tests.

No network: all three scorers are unpublished-feed NULLs
(2026-09-13 dated-negative verdict, see dims_p4_libs docstring), so
the tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + buyer-side check pointer), the per-param
missing-input naming, and the registry/aggregator coverage. The
module itself makes no network calls (pinned by source inspection).
"""

import inspect

import dims_p4_libs as libs
from dims_p4_libs import (
    P4_LIBS_DIMS,
    dim_civic_use_visits,
    dim_culture_evening_events,
    dim_library_evening_hours,
    score_p4_libs,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "library", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_library_evening_hours, dim_culture_evening_events,
           dim_civic_use_visits]

EXPECTED_KEYS = ["library_evening_hours", "culture_evening_events",
                 "civic_use_visits"]

EXPECTED_PNUMS = ["P4-045", "P4-045", "P4-039"]


def test_all_three_dims_always_none_for_every_input():
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
            "kohapeal", "jaluta", "Kõik lahtiolekuajad",
            "uudiskiri", "küsi", "dims_p4_")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(libs)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_library_slice_names_hours_gap_and_osm_sibling():
    _, reason = dim_library_evening_hours(TALLINN, POIS)
    assert "lahtioleku-tabelit" in reason
    assert "Kõik lahtiolekuajad" in reason
    assert "dims_p4_osm" in reason


def test_culture_slice_names_feed_gap_and_access_siblings():
    _, reason = dim_culture_evening_events(TALLINN, POIS)
    assert "õhtuste sündmuste voogu" in reason
    assert "kultuurikava.ee" in reason
    assert "dims_p4_peatus" in reason
    assert "dims_p4_tlt" in reason
    assert "dims_p4_rel2021" in reason


def test_civic_slice_is_taste_only_and_names_siblings():
    _, reason = dim_civic_use_visits(TALLINN, POIS)
    assert "külastatavuse tabelit" in reason
    assert "maitse" in reason
    assert "proksi" in reason
    assert "parameters4.md" in reason
    assert "dims_p4_osm" in reason
    assert "dims_p4_arireg" in reason


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_LIBS_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_LIBS_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_LIBS_DIMS}) == 3
    out = score_p4_libs(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_libs(None, None) == {k: None for k in EXPECTED_KEYS}
    assert libs.P4_LIBS_DIMS is P4_LIBS_DIMS
