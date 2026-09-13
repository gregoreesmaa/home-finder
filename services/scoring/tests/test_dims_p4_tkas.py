"""P4 Tervisekassa dims (issue #272 demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_tkas.md) means the scorer is a documented NULL, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side check), the PowerBI-embed gap pointer,
the split-slice cousin pointers, and the registry/aggregator coverage.
"""

import dims_p4_tkas as tkas
from dims_p4_tkas import (
    P4_TKAS_DIMS,
    dim_gp_list_open,
    score_p4_tkas,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "clinic", "lat": 59.4382, "lon": 24.7536}]


def test_dim_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_gp_list_open(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_concrete_check():
    _, reason = dim_gp_list_open(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_reason_names_powerbi_gap_and_buyer_check():
    _, reason = dim_gp_list_open(TALLINN, POIS)
    # The demo leg: Tervisekassa nimistu open/closed lives in a
    # PowerBI-embedded report with no per-linnaosa bulk — the buyer
    # checks the nimistuotsing, files the switch request, and asks
    # on site meanwhile.
    assert "Tervisekassa" in reason
    assert "nimistu" in reason
    assert "PowerBI" in reason
    assert "nimistuotsing" in reason
    assert "vahetusavaldus" in reason
    assert "kohapeal" in reason


def test_reason_names_scored_p4_011_cousins_never_rescored():
    _, reason = dim_gp_list_open(TALLINN, POIS)
    # Split-slice contract: the EHIS capacity, REL2021 demand, and
    # Haridusamet queue P4-011 legs stay scored where they live —
    # this NULL names them.
    assert "dims_p4_ehis" in reason
    assert "dim_school_pressure" in reason
    assert "school_pressure" in reason
    assert "dims_p4_rel2021" in reason
    assert "dim_kindergarten_pressure_rel" in reason
    assert "kindergarten_pressure_rel" in reason
    assert "dims_p4_haridus" in reason
    assert "dim_kindergarten_queue_gp" in reason
    assert "kindergarten_queue_gp" in reason


def test_module_adds_no_network_calls():
    import pathlib
    import re
    src = pathlib.Path(tkas.__file__).read_text(encoding="utf-8")
    assert re.search(r"^\s*(import|from)\s+\S*(urllib|socket|requests|httplib|http\.client)",
                     src, flags=re.M) is None
    assert "urlopen" not in src
    assert re.search(r"^[A-Z_]*OVERPASS[A-Z_]*\s*=", src, flags=re.M) is None
    assert re.search(r"^def fetch_\w+", src, flags=re.M) is None


def test_registry_and_aggregator_cover_the_dim():
    assert [k for k, _, _ in P4_TKAS_DIMS] == ["gp_list_open"]
    assert [p for _, p, _ in P4_TKAS_DIMS] == ["P4-011"]
    assert len({fn for _, _, fn in P4_TKAS_DIMS}) == 1
    out = score_p4_tkas(TALLINN, POIS)
    assert out == {"gp_list_open": None}
    assert score_p4_tkas(None, None) == {"gp_list_open": None}
    assert tkas.P4_TKAS_DIMS is P4_TKAS_DIMS
