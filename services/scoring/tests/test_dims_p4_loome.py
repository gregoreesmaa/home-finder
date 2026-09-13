"""P4 loome dims (issue #322, single-param demo): hermetic tests.

No network: the openness verdict (dated negative 2026-09-13, evidence
in docs/p4_loome.md) means the scorer is a documented NULL, so the
tests pin the None contract, the Estonian honesty markers (hinnang +
EI OLE + concrete buyer-side checks), the taste-match contract
(maitsesobivus, never worth judgement), the probe-evidence markers
(human catalog pages, Teabevarav JS shell, zero file links), the
split-slice sibling pointers (scored legs named, never re-scored;
arireg NULL agreer named), and the registry/aggregator coverage.
The module itself makes no network calls (pinned by source
inspection).
"""

import inspect

import dims_p4_loome as loome
from dims_p4_loome import (
    P4_LOOME_DIMS,
    dim_loome_linnaosa_stats,
    score_p4_loome,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "gallery", "lat": 59.4382, "lon": 24.7536}]


def test_dim_always_none_for_every_input():
    for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                         (None, POIS), (TALLINN, None)]:
        v, _ = dim_loome_linnaosa_stats(origin, pois)
        assert v is None


def test_reason_carries_honesty_markers_and_buyer_side_pointer():
    _, reason = dim_loome_linnaosa_stats(TALLINN, POIS)
    assert "hinnang" in reason
    assert "EI OLE" in reason
    assert "ära feigi" in reason
    assert "ostjaprofiilis" in reason
    assert "jalutuskäik" in reason
    assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_reason_keeps_taste_match_contract_never_worth_judgement():
    _, reason = dim_loome_linnaosa_stats(TALLINN, POIS)
    # P4-044 contract: taste-match wording, never a worth judgement.
    assert "maitsesobivus" in reason
    assert "maitse-hinnang" in reason


def test_reason_names_probe_gap_not_a_guess():
    _, reason = dim_loome_linnaosa_stats(TALLINN, POIS)
    # Dated-negative probe facts: human catalog pages, JS-shell portal.
    assert "inimloetavad kataloogilehed" in reason
    assert "Teabevärav" in reason
    assert "JS-kest" in reason
    assert "masinloetavat linnaosa-tabelit" in reason
    # Buyer-side check: creative-quarter walk, parameters4.md clusters.
    assert "Telliskivi" in reason
    assert "Paavli" in reason
    assert "Noblessneri" in reason


def test_reason_names_sibling_legs_without_rescoring():
    _, reason = dim_loome_linnaosa_stats(TALLINN, POIS)
    # Scored P4-044 legs stay where they live, never re-scored here.
    assert "dims_p4_rel2021" in reason
    assert "dim_herd_occupation_rel" in reason
    assert "dims_p4_osm" in reason
    assert "dim_herd" in reason
    assert "dims_p4_ehis" in reason
    assert "dim_artschool_density" in reason
    assert "dims_p4_maa_tehingud" in reason
    assert "dim_herd_gentrification_front" in reason
    # NULL agreer: arireg address-cluster leg.
    assert "dims_p4_arireg" in reason
    assert "dim_herd_arireg" in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(loome)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_registry_and_aggregator_cover_the_dim():
    assert [k for k, _, _ in P4_LOOME_DIMS] == ["loome_linnaosa_stats"]
    assert [p for _, p, _ in P4_LOOME_DIMS] == ["P4-044"]
    assert len({fn for _, _, fn in P4_LOOME_DIMS}) == 1
    assert loome.P4_LOOME_DIMS is P4_LOOME_DIMS
    out = score_p4_loome(TALLINN, POIS)
    assert out == {"loome_linnaosa_stats": None}
    assert score_p4_loome(None, None) == {"loome_linnaosa_stats": None}
