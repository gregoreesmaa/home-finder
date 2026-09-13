"""P4 green demo + coverage dims (issues #300, #369): hermetic tests.

No network: all five scorers are unpublished-feed NULLs
(2026-09-13 dated-negative verdict, see dims_p4_green docstring), so
the tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + buyer-side check pointer), the per-param
missing-input naming, and the registry/aggregator coverage. The
module itself makes no network calls (pinned by source inspection).
"""

import inspect

import dims_p4_green as green
from dims_p4_green import (
    P4_GREEN_DIMS,
    dim_allotment_queue,
    dim_bench_view_3min,
    dim_blossom_chorus_cells,
    dim_courtyard_green_deficit,
    dim_delight_green_15min,
    score_p4_green,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "park", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_bench_view_3min, dim_delight_green_15min,
           dim_allotment_queue, dim_blossom_chorus_cells,
           dim_courtyard_green_deficit]

EXPECTED_KEYS = ["bench_view_3min", "delight_green_15min",
                 "allotment_queue", "blossom_chorus_cells",
                 "courtyard_green_deficit"]

EXPECTED_PNUMS = ["P4-048", "P4-048", "P4-048", "P4-042", "P4-056"]


def test_all_five_dims_always_none_for_every_input():
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
            "kohapeal", "jaluta", "kaardilt", "aiandusühistult",
            "KÜ", "dims_p4_", "Kadriorg", "Hirvepark", "Pirita",
            "Lillepi", "Pelgu")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(green)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_bench_slice_names_register_gap_and_ehr_sibling():
    _, reason = dim_bench_view_3min(TALLINN, POIS)
    assert "pinkide/vaatekohtade registrit" in reason
    assert "Kadrioru" in reason
    assert "dims_p4_ehr" in reason


def test_delight_slice_names_kava_gap_and_access_siblings():
    _, reason = dim_delight_green_15min(TALLINN, POIS)
    assert "rohealade-kava" in reason
    assert "dims_p4_peatus" in reason
    assert "dims_p4_tlt" in reason


def test_allotment_slice_names_queue_gap_and_osm_agreement():
    _, reason = dim_allotment_queue(TALLINN, POIS)
    assert "järjekorratabelit" in reason
    assert "Lillepi" in reason
    assert "dims_p4_osm" in reason


def test_blossom_slice_forbids_doorway_precision_and_names_siblings():
    _, reason = dim_blossom_chorus_cells(TALLINN, POIS)
    assert "ukse-" in reason
    assert "parameters4.md" in reason
    assert "dims_p4_osm" in reason
    assert "dims_p4_paaste" in reason
    assert "dims_p4_komun" in reason


def test_courtyard_slice_names_lidar_and_ilm_siblings_not_duplicate():
    _, reason = dim_courtyard_green_deficit(TALLINN, POIS)
    assert "haljastusinventari" in reason
    assert "dims_p4_maa_lidar" in reason
    assert "dims_p4_ilm" in reason
    assert "kohapeal" in reason


def test_registry_and_aggregator_cover_all_five():
    assert [k for k, _, _ in P4_GREEN_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_GREEN_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_GREEN_DIMS}) == 5
    out = score_p4_green(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_green(None, None) == {k: None for k in EXPECTED_KEYS}
    assert green.P4_GREEN_DIMS is P4_GREEN_DIMS
