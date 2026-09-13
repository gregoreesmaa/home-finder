"""P4 recreation dims (issue #312, single-param demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_recre.md) means both scorers are documented NULLs, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side checks), the probe-evidence markers
(human directories, tunniplaan/pilet pages, hoolduskava-not-queue),
the split-slice sibling pointers (scored legs named, never
re-scored; green NULL agreers named), and the registry/aggregator
coverage. The module itself makes no network calls (pinned by source
inspection).
"""

import inspect

import dims_p4_recre as recre
from dims_p4_recre import (
    P4_RECRE_DIMS,
    dim_recre_allotment_queue,
    dim_recre_facility_15min,
    score_p4_recre,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "sport", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_recre_facility_15min,
    dim_recre_allotment_queue,
]

EXPECTED_KEYS = [
    "recre_facility_15min",
    "recre_allotment_queue",
]

EXPECTED_PNUMS = [
    "P4-048",
    "P4-048",
]


def test_both_dims_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reasons_carry_honesty_markers_and_buyer_side_pointer():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        assert "hinnang" in reason, fn.__name__
        assert "EI OLE" in reason, fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_facility_slice_names_timetable_gap_and_scored_siblings():
    _, reason = dim_recre_facility_15min(TALLINN, POIS)
    # The missing artifact: operator timetables/tables, not the kava join.
    assert "tunniplaani" in reason
    assert "kataloogilehtedel" in reason
    assert "tunniplaan" in reason
    # Buyer-side check: trial ring + timetable verification.
    assert "prooviring" in reason
    # Scored sibling legs stay where they live, never re-scored here.
    assert "dims_p4_peatus" in reason
    assert "dims_p4_tlt" in reason
    assert "dims_group11" in reason
    assert "dim_rec_special" in reason


def test_queue_slice_names_publication_gap_and_agreeing_nulls():
    _, reason = dim_recre_allotment_queue(TALLINN, POIS)
    # Dated-negative probe facts: hoolduskava, not a queue; no table.
    assert "hoolduskava" in reason
    assert "järjekorratabelit" in reason
    assert "Lillepi" in reason
    assert "Pelgu" in reason
    # Buyer-side check: ask the association directly.
    assert "aiandusühistult" in reason
    assert "järjekorra" in reason
    # Agreeing NULL legs (city-register + OSM), never re-scored.
    assert "dims_p4_green" in reason
    assert "dim_allotment_queue" in reason
    assert "dims_p4_osm" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(recre)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator_cover_both_dims():
    assert [k for k, _, _ in P4_RECRE_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_RECRE_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_RECRE_DIMS}) == 2
    assert recre.P4_RECRE_DIMS is P4_RECRE_DIMS
    out = score_p4_recre(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_recre(None, None) == {k: None for k in EXPECTED_KEYS}
