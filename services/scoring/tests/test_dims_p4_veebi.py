"""P4 veebi demo + coverage dims (issues #304, #373): hermetic tests.

No network: all four scorers are unpublished-feed NULLs
(2026-09-13 dated-negative verdict, confirmed by the 2026-09-16
§7.7 endpoint dig, see dims_p4_veebi docstring), so the tests pin
the None contract, the Estonian honesty markers (hinnang + EI OLE
+ buyer-side check pointer), the per-param missing-leg naming, the
dig inventory (no lighting/current-ortho/lit-street feed), and the
registry/aggregator coverage. The module itself makes no network
calls (pinned by source inspection).
"""

import inspect

import dims_p4_veebi as veebi
from dims_p4_veebi import (
    P4_VEEBI_DIMS,
    VEEBI_ABSENT_FEEDS,
    VEEBI_ARCGIS,
    VEEBI_BENEFICIARY_SERVICES,
    VEEBI_DIG_DATE,
    VEEBI_ORTO_VINTAGES,
    VEEBI_THEME_SERVICES,
    dim_arrival_lighting,
    dim_december_darkness_veebi,
    dim_lit_street_usage,
    dim_street_ortho_history,
    score_p4_veebi,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "lit_street", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_december_darkness_veebi, dim_street_ortho_history,
           dim_lit_street_usage, dim_arrival_lighting]

EXPECTED_KEYS = ["december_darkness", "street_ortho_history",
                 "lit_street_usage", "arrival_lighting"]

EXPECTED_PNUMS = ["P4-035", "P4-029", "P4-032", "P4-040"]


def test_all_four_dims_always_none_for_every_input():
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
            "kohapeal", "jaluta", "kõnni", "külasta", "detsembri",
            "õhtul", "novembri", "dims_p4_")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(veebi)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_darkness_names_inventory_gap_and_light_siblings():
    _, reason = dim_december_darkness_veebi(TALLINN, POIS)
    assert "inventari/kaarti" in reason
    assert "VIIRS" in reason
    assert "dims_p4_ehr" in reason
    assert "dims_p4_ilm" in reason
    assert "dims_p4_maa_lidar" in reason
    assert "dims_p4_osm" in reason


def test_ortho_history_names_imagery_and_sidewalk_siblings():
    _, reason = dim_street_ortho_history(TALLINN, POIS)
    assert "ajalooliidestust" in reason
    assert "foto kuupäevaga" in reason
    assert "dims_p4_maa_aerial" in reason
    assert "dims_p4_osm" in reason


def test_lit_usage_labels_usage_not_safety_and_names_siblings():
    _, reason = dim_lit_street_usage(TALLINN, POIS)
    assert "mitte turvalisus" in reason
    assert "PPA/Päästeamet" in reason
    assert "dims_p4_osm" in reason
    assert "dims_p4_elron" in reason
    assert "dims_p4_tlt" in reason


def test_arrival_names_light_gap_and_no_safety_claim():
    _, reason = dim_arrival_lighting(TALLINN, POIS)
    assert "200 m" in reason
    assert "23:00" in reason
    assert "ei ole turvaväide" in reason
    assert "Päästeamet/PPA" in reason
    assert "dims_p4_osm" in reason
    assert "dims_p4_maa_aerial" in reason


def test_dig_inventory_records_no_lighting_feed():
    # Second-round dig (2026-09-16) is evidence-complete: the NULL
    # verdict traces to inventoried services, not to a guess.
    assert VEEBI_DIG_DATE == "2026-09-16"
    assert VEEBI_ARCGIS.startswith("https://gis.tallinn.ee/")
    assert len(VEEBI_THEME_SERVICES) == 16
    lowered = " ".join(VEEBI_THEME_SERVICES).lower()
    assert "valgustus" not in lowered and "lamp" not in lowered
    assert "orto" not in lowered
    assert VEEBI_ORTO_VINTAGES == ("ortofoto2003", "ortofoto2005")
    assert len(VEEBI_ABSENT_FEEDS) == 3  # lighting/current-ortho/lit-street
    # Beneficiaries recorded with no separate digs.
    assert "veebikaart/tervishoid_veebikaart" in VEEBI_BENEFICIARY_SERVICES
    assert "veebikaart/sotsiaalteenused" in VEEBI_BENEFICIARY_SERVICES
    assert "Haljastuse_arengukava_muinsuskaitse" in VEEBI_BENEFICIARY_SERVICES
    assert "Linnaosad_asumid" in VEEBI_BENEFICIARY_SERVICES


def test_registry_and_aggregator_cover_all_four():
    assert [k for k, _, _ in P4_VEEBI_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_VEEBI_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_VEEBI_DIMS}) == 4
    out = score_p4_veebi(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_veebi(None, None) == {k: None for k in EXPECTED_KEYS}
    assert veebi.P4_VEEBI_DIMS is P4_VEEBI_DIMS
