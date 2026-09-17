"""P4 harbour live dims (issues #542, #627): hermetic tests.

No network: joined rows are passed in (the harvester + WFS/API pulls
live in scripts/build/batch_harbour.py). Pins the function bands, the
pleasure bands, worst-wins, the NULL-outside contract (never calm or
quiet), the no-season caveat in every reason, and the registry/
aggregator coverage. The module itself makes no network calls (pinned
by source inspection).
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

PIRITA = {"name": "PIRITA SADAM", "function": 2,
          "function_label": "väikesadam (tasulised, <24 m)",
          "dist_m": 494.0}
VANASADAM = {"name": "VANASADAM", "function": 1,
             "function_label": "täisteenus (kõik veesõidukid)",
             "dist_m": 300.0}
CELL_BUSY = {"pleasure": 53, "dist_m": 494.0}
CELL_MILD = {"pleasure": 12, "dist_m": 900.0}

EXPECTED_KEYS = ["harbour_function_zone", "ais_pleasure_density"]
EXPECTED_PNUMS = ["P4-023", "P4-033"]


def test_function_bands_by_function_and_distance():
    s, _ = dim_harbour_function_zone(TALLINN, [VANASADAM])
    assert s == 45  # fn1 within 500 m
    s, _ = dim_harbour_function_zone(
        TALLINN, [{**VANASADAM, "dist_m": 1200.0}])
    assert s == 65  # fn1 within 1500 m
    s, _ = dim_harbour_function_zone(TALLINN, [PIRITA])
    assert s == 70  # fn2 marina within 500 m


def test_function_worst_wins_and_names_port():
    s, reason = dim_harbour_function_zone(TALLINN, [PIRITA, VANASADAM])
    assert s == 45  # working port dominates the marina
    assert "VANASADAM" in reason
    assert "hooajajaotust pole" in reason


def test_function_outside_is_unknown_not_calm():
    s, reason = dim_harbour_function_zone(TALLINN, [])
    assert s is None
    assert "MITTE rahulik" in reason
    s, reason = dim_harbour_function_zone(TALLINN, None)
    assert s is None
    assert "puudub" in reason


def test_pleasure_bands():
    s, _ = dim_ais_pleasure_density(TALLINN, [CELL_BUSY])
    assert s == 70
    s, _ = dim_ais_pleasure_density(TALLINN, [CELL_MILD])
    assert s == 80
    s, _ = dim_ais_pleasure_density(TALLINN, [{"pleasure": 3,
                                              "dist_m": 100.0}])
    assert s == 85


def test_pleasure_outside_is_unknown_not_quiet():
    s, reason = dim_ais_pleasure_density(TALLINN, [])
    assert s is None
    assert "MITTE vaikne" in reason
    assert "rahulik" not in reason  # never claims calm water either


def test_pleasure_far_cell_is_null_despite_busy_count():
    # AIS influence window (1500 m, mirror of the function gate): a busy
    # cell kilometres away must NOT score -- outside is NULL.
    s, reason = dim_ais_pleasure_density(
        TALLINN, [{**CELL_BUSY, "dist_m": 5000.0}])
    assert s is None
    assert "1500" in reason
    assert "MITTE vaikne" in reason


def test_bool_inputs_are_not_distances_or_counts():
    # True == 1 would fake fn1 proximity / a pleasure count of 1.
    s, _ = dim_harbour_function_zone(
        TALLINN, [{**VANASADAM, "dist_m": True}])
    assert s is None
    s, _ = dim_ais_pleasure_density(
        TALLINN, [{"pleasure": True, "dist_m": 100.0}])
    assert s is None
    s, _ = dim_harbour_function_zone(
        TALLINN, [{**VANASADAM, "function": True, "dist_m": 100.0}])
    assert s is None


def test_module_adds_no_network_calls():
    src = inspect.getsource(harbour)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_keys_and_param_numbers():
    assert [k for k, _, _ in P4_HARBOUR_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_HARBOUR_DIMS] == EXPECTED_PNUMS
    assert len({k for k, _, _ in P4_HARBOUR_DIMS}) == 2


def test_aggregator_scores_joined_rows():
    assert score_p4_harbour(TALLINN, [PIRITA], [CELL_BUSY]) == {
        "harbour_function_zone": 70, "ais_pleasure_density": 70}
    assert score_p4_harbour(TALLINN, None, None) == {
        "harbour_function_zone": None, "ais_pleasure_density": None}
    assert score_p4_harbour(None, [PIRITA], [CELL_BUSY]) == {
        "harbour_function_zone": None, "ais_pleasure_density": None}
