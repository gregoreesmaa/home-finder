"""P4 notar.ee dims (issue #253 demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_notar.md) means the scorer is a documented NULL, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side check), the split-slice cousin pointers,
and the registry/aggregator coverage.
"""

import dims_p4_notar as notar
from dims_p4_notar import (
    P4_NOTAR_DIMS,
    dim_notar_closing_guidance,
    score_p4_notar,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "cafe", "lat": 59.4382, "lon": 24.7536}]


def test_dim_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_notar_closing_guidance(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_concrete_check():
    _, reason = dim_notar_closing_guidance(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_reason_names_guidance_gap_and_buyer_check():
    _, reason = dim_notar_closing_guidance(TALLINN, POIS)
    # The demo leg: notar.ee Kinnisvaratehingud guidance prose (human
    # text, no machine feed) — buyer reads the guidance, computes the
    # fee, pulls the extract, and books the notary meanwhile.
    assert "Kinnisvaratehingud" in reason
    assert "notar.ee" in reason
    assert "tasu" in reason
    assert "e-Kinnistusraamatu" in reason
    assert "broneeri notari" in reason


def test_reason_names_scored_p4_004_cousins_never_rescored():
    _, reason = dim_notar_closing_guidance(TALLINN, POIS)
    # Split-slice contract: the KKIS/kataster, taitur, AT and EMTA
    # P4-004 legs stay scored where they live — this NULL names them.
    assert "dims_p4_maa_kataster" in reason
    assert "dim_kinnistus_syva" in reason
    assert "dims_p4_taitur" in reason
    assert "dims_p4_ata" in reason
    assert "dim_kinnistus_checkpoint" in reason
    assert "dims_p4_emta" in reason
    assert "dim_kinnistus_debt" in reason
    assert "dims_group16a" in reason
    assert "dim_closing_costs" in reason


def test_module_adds_no_network_calls():
    import pathlib
    import re
    src = pathlib.Path(notar.__file__).read_text(encoding="utf-8")
    assert re.search(r"^\s*(import|from)\s+\S*(urllib|socket|requests|httplib|http\.client)",
                     src, flags=re.M) is None
    assert "urlopen" not in src
    assert re.search(r"^[A-Z_]*OVERPASS[A-Z_]*\s*=", src, flags=re.M) is None
    assert re.search(r"^def fetch_\w+", src, flags=re.M) is None


def test_registry_and_aggregator_cover_the_dim():
    assert [k for k, _, _ in P4_NOTAR_DIMS] == ["notar_closing_guidance"]
    assert [p for _, p, _ in P4_NOTAR_DIMS] == ["P4-004"]
    assert len({fn for _, _, fn in P4_NOTAR_DIMS}) == 1
    out = score_p4_notar(TALLINN, POIS)
    assert out == {"notar_closing_guidance": None}
    assert score_p4_notar(None, None) == {"notar_closing_guidance": None}
    assert notar.P4_NOTAR_DIMS is P4_NOTAR_DIMS
