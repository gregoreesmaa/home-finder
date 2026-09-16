"""P4 harbour demo dims (issue #542): hermetic tests.

No network: both scorers are licence/data-gated NULLs (2026-09-16 verdict,
see dims_p4_harbour docstring), so the tests pin the None contract, the
Estonian honesty markers (hinnang + EI OLE + buyer-side check pointer),
the per-leg missing-input naming, and the registry/aggregator coverage.
The module itself makes no network calls (pinned by source inspection).
"""

import inspect

import dims_p4_harbour as harbour
from dims_p4_harbour import (
    P4_HARBOUR_DIMS,
    dim_ais_pleasure_density,
    dim_harbour_function_zone,
    score_p4_harbour,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "port", "lat": 59.4449, "lon": 24.7636}]

ALL_FNS = [dim_harbour_function_zone, dim_ais_pleasure_density]

EXPECTED_KEYS = ["harbour_function_zone", "ais_pleasure_density"]

EXPECTED_PNUMS = ["P4-023", "P4-033"]


def test_both_dims_always_none_for_every_input():
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
            "sadamaregister", "AIS", "ts.ee", "kohapeal", "dims_p4_",
            "INSPIRE")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud skoor" not in reason
        assert "mõõdetud väärtus" not in reason
        assert "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(harbour)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_function_leg_names_licence_gate_and_fixture_mapping():
    _, reason = dim_harbour_function_zone(TALLINN, POIS)
    assert "litsentsi" in reason
    assert "funktsiooni-taksonoomiat" in reason
    assert "dims_p4_trans" in reason
    assert "2026-09-16" in reason


def test_function_leg_pins_outside_is_unknown_not_quiet():
    _, reason = dim_harbour_function_zone(TALLINN, [])
    assert reason.startswith("Sadama funktsiooni-tsooni hinnangut pole")


def test_ais_leg_names_grid_as_is_shape_and_gap_note():
    _, reason = dim_ais_pleasure_density(TALLINN, POIS)
    assert "500 m" in reason
    assert "interpolatsiooni EI OLE" in reason
    assert "AIS-lüngad" in reason


def test_ais_leg_never_claims_calm_outside():
    _, reason = dim_ais_pleasure_density(TALLINN, [])
    assert "pole" in reason
    assert "vaik" not in reason.replace("Väikelaevade", "")


def test_registry_keys_and_param_numbers():
    assert [k for k, _, _ in P4_HARBOUR_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_HARBOUR_DIMS] == EXPECTED_PNUMS
    assert len({k for k, _, _ in P4_HARBOUR_DIMS}) == 2


def test_aggregator_returns_all_none_by_design():
    assert score_p4_harbour(TALLINN, POIS) == {
        "harbour_function_zone": None, "ais_pleasure_density": None}
    assert score_p4_harbour(None, None) == {
        "harbour_function_zone": None, "ais_pleasure_density": None}
