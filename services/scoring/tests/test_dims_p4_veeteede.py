"""P4 Veeteede icebreaking dim (issue #311, single-param demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_veeteede.md) means the single scorer is a documented NULL, so
the tests pin the None contract, the Estonian honesty markers
(hinnang + EI OLE + concrete buyer-side checks), the probe-evidence
markers (veeteedeamet.ee 301 forwarder + Transpordiamet topic page with
month-parenthetical PDF käskkirjad + Teabevärav JS-shell catalogue),
the split-slice cousin pointers, and the registry/aggregator coverage.
"""

import inspect

import dims_p4_veeteede as veeteede
from dims_p4_veeteede import (
    P4_VEETEEDE_DIMS,
    dim_jaamurde_calendar,
    score_p4_veeteede,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [
    dim_jaamurde_calendar,
]

EXPECTED_KEYS = [
    "jaamurde_calendar",
]

EXPECTED_PNUMS = [
    "P4-055",
]


def test_single_dim_always_none_for_every_input():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, _ = fn(origin, pois)
            assert v is None, fn.__name__


def test_reason_carries_honesty_markers_and_concrete_checks():
    _, reason = dim_jaamurde_calendar(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason
    # The buyer-side checks: listen on the Tallinn Bay edge in ice
    # season plus the harbour-schedule cross-check.
    assert "kohapeal" in reason
    assert "Tallinna" in reason
    assert "jäähooajal" in reason
    assert "ts.ee" in reason


def test_reason_names_probe_evidence():
    _, reason = dim_jaamurde_calendar(TALLINN, POIS)
    # Dated-negative facts from the 2026-09-13 probes (evidence in
    # docs/p4_veeteede.md): the old host is a forwarder, the topic
    # page carries month-grain PDF directives, and the national
    # catalogue has no server-rendered icebreaking dataset.
    assert "veeteedeamet.ee" in reason
    assert "Transpordiamet" in reason
    assert "PDF-käskkirjad" in reason
    assert "CSV/API" in reason
    assert "Teabevärava" in reason
    assert "baltice.org" in reason
    # The honest future shape is stated, not scored: calendar dim.
    assert "masinkalendrit" in reason


def test_reason_names_scored_cousins_never_rescores():
    _, reason = dim_jaamurde_calendar(TALLINN, POIS)
    # Split-slice contract: the Sadam + EANS + Männiku + Elron + komun
    # legs of the SAME param stay where they live — this NULL must
    # name them.
    assert "dims_p4_sadam" in reason
    assert "dim_sadam_timetable" in reason
    assert "dims_p4_eans" in reason
    assert "dim_harbour_air_calendar" in reason
    assert "dims_p4_kvagi" in reason
    assert "dim_manniku_weekend_calendar" in reason
    assert "dims_p4_elron" in reason
    assert "dim_elron_night_maintenance" in reason
    assert "dims_p4_komun" in reason
    assert "dim_schedulable_noise_calendar" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(veeteede)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator_cover_single_param():
    assert [k for k, _, _ in P4_VEETEEDE_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_VEETEEDE_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_VEETEEDE_DIMS}) == 1
    assert veeteede.P4_VEETEEDE_DIMS is P4_VEETEEDE_DIMS
    out = score_p4_veeteede(TALLINN, POIS)
    assert out == {"jaamurde_calendar": None}
    assert score_p4_veeteede(None, None) == {"jaamurde_calendar": None}
