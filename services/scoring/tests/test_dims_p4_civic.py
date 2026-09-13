"""P4 civic dims (issue #320, single-param demo): hermetic tests.

No network: the openness verdict (mixed 2026-09-13, evidence in
docs/p4_civic.md — static ringkond-level XML ZIPs verified but no
precinct-boundary feed; kaasav eelarve + Teeme Ära human-pages
only) means all three scorers are documented NULLs, so the tests
pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side checks), the probe-evidence markers
(ringkond R1–R8 rows without jaoskond rows, CC BY static ZIPs,
human vote/campaign pages), the taste-match guard (never an
ethnic/wealth proxy), the split-slice sibling pointers (scored
legs: none — every existing P4-039 slice is a NULL agreer, named
never re-scored), and the registry/aggregator coverage. The
module itself makes no network calls (pinned by source
inspection).
"""

import inspect

import dims_p4_civic as civic
from dims_p4_civic import (
    P4_CIVIC_DIMS,
    dim_civic_cleanup_action,
    dim_civic_participatory_budget,
    dim_civic_turnout,
    score_p4_civic,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "community", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_civic_turnout,
    dim_civic_participatory_budget,
    dim_civic_cleanup_action,
]

EXPECTED_KEYS = [
    "civic_turnout",
    "civic_participatory_budget",
    "civic_cleanup_action",
]

EXPECTED_PNUMS = [
    "P4-039",
    "P4-039",
    "P4-039",
]


def test_all_three_dims_always_none_for_every_input():
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


def test_turnout_slice_names_ringkonna_gap_and_boundary_gap():
    _, reason = dim_civic_turnout(TALLINN, POIS)
    # Verified probe facts: ringkond rows, no jaoskond rows, static ZIPs.
    assert "R1–R8" in reason
    assert "jaoskonna-ridu pole" in reason
    assert "XML ZIP" in reason
    assert "reaalajas ei uuene" in reason
    assert "jaoskonnapiiride" in reason
    # Taste-match guard: never an ethnic/wealth proxy.
    assert "maitsefilter" in reason
    assert "proksi" in reason
    # Buyer-side check: open-data page + on-foot commons check.
    assert "avaandmete" in reason
    assert "jalutuskäigul" in reason
    # NULL agreers stay where they live, never re-scored here.
    assert "dims_p4_osm" in reason
    assert "dim_civic" in reason
    assert "dims_p4_arireg" in reason
    assert "dim_commons_echo" in reason
    assert "dims_p4_libs" in reason
    assert "dim_civic_use_visits" in reason


def test_budget_slice_names_vote_gap_and_linnaosa_shape():
    _, reason = dim_civic_participatory_budget(TALLINN, POIS)
    # Dated-negative probe facts: human vote pages, no table.
    assert "Kaasav eelarve 2026" in reason
    assert "osalustabelit" in reason
    assert "linnaosa" in reason
    # Buyer-side check: vote + ask the district council.
    assert "hääletusel" in reason
    assert "linnaosakogult" in reason
    # Agreeing NULL legs, never re-scored.
    assert "dims_p4_osm" in reason
    assert "dims_p4_libs" in reason


def test_cleanup_slice_names_register_gap_and_asum_shape():
    _, reason = dim_civic_cleanup_action(TALLINN, POIS)
    # Dated-negative probe facts: campaign front page, no register.
    assert "PANE TALGUD KIRJA" in reason
    assert "osalusregistrit" in reason
    assert "asum" in reason
    # Buyer-side check: register + ask the asum society.
    assert "talgud kirja" in reason
    assert "asumiseltsilt" in reason
    # Agreeing NULL legs, never re-scored.
    assert "dims_p4_osm" in reason
    assert "dims_p4_libs" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(civic)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator_cover_all_three():
    assert [k for k, _, _ in P4_CIVIC_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_CIVIC_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_CIVIC_DIMS}) == 3
    assert civic.P4_CIVIC_DIMS is P4_CIVIC_DIMS
    out = score_p4_civic(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_civic(None, None) == {k: None for k in EXPECTED_KEYS}
