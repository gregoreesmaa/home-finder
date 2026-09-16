"""P4 komun demo + coverage dims (issues #290, #363): hermetic tests.

No network: all eighteen scorers are unpublished-feed NULLs
(2026-09-13 dated-negative verdict + 2026-09-16 lumekaart re-dig,
see dims_p4_komun docstring), so the tests pin the None contract,
the Estonian honesty markers (hinnang + EI OLE + buyer-side check
pointer), the per-param missing-input naming, the re-dig endpoint
evidence (areas-only layer vs gated class folder), and the
registry/aggregator coverage. The module itself makes no network
calls (pinned by source inspection).
"""

import inspect
import json
import os

import dims_p4_komun as komun
from dims_p4_komun import (
    P4_KOMUN_DIMS,
    dim_farm_odour_cells,
    dim_fixit_responsiveness,
    dim_geology_uvk_crosscheck,
    dim_heatpump_hum,
    dim_icefall_duty_warnings,
    dim_ku_loan_support,
    dim_odour_complaint_cells,
    dim_odour_rose_sectors,
    dim_quarry_blast_season,
    dim_renovation_grant_queue,
    dim_rat_icefall_hex,
    dim_schedulable_noise_calendar,
    dim_small_horrors_calendar,
    dim_snow_maintenance_class,
    dim_stormwater_notices,
    dim_tree_felling_flag,
    dim_uvk_development_plan,
    dim_woodburning_zones,
    score_p4_komun,
)

TALLINN = (59.4372, 24.7536)
POIS = [{"kind": "station", "lat": 59.4382, "lon": 24.7536}]

ALL_FNS = [dim_snow_maintenance_class, dim_ku_loan_support,
           dim_renovation_grant_queue, dim_geology_uvk_crosscheck,
           dim_uvk_development_plan, dim_farm_odour_cells,
           dim_fixit_responsiveness, dim_tree_felling_flag,
           dim_odour_complaint_cells, dim_small_horrors_calendar,
           dim_odour_rose_sectors, dim_quarry_blast_season,
           dim_schedulable_noise_calendar, dim_heatpump_hum,
           dim_icefall_duty_warnings, dim_woodburning_zones,
           dim_stormwater_notices, dim_rat_icefall_hex]

EXPECTED_KEYS = ["snow_maintenance_class", "ku_loan_support",
                 "renovation_grant_queue", "geology_uvk_crosscheck",
                 "uvk_development_plan", "farm_odour_cells",
                 "fixit_responsiveness", "tree_felling_flag",
                 "odour_complaint_cells", "small_horrors_calendar",
                 "odour_rose_sectors", "quarry_blast_season",
                 "schedulable_noise_calendar", "heatpump_hum",
                 "icefall_duty_warnings", "woodburning_zones",
                 "stormwater_notices", "rat_icefall_hex"]

EXPECTED_PNUMS = ["P4-018", "P4-007", "P4-010", "P4-016", "P4-017",
                  "P4-024", "P4-026", "P4-030", "P4-042", "P4-047",
                  "P4-053", "P4-054", "P4-055", "P4-057", "P4-058",
                  "P4-059", "P4-060", "P4-062"]


def test_all_eighteen_dims_always_none_for_every_input():
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
            "tallinn.ee", "lumekaart", "kohapeal", "14410",
            "annateada", "dims_p4_", "EHR", "EIS", "Maa-amet",
            "Päästeamet", "Sadam", "EANS", "KÜ", "Ilmateenistus",
            "linnaosa", "Tark Tee")), fn.__name__
        assert "ära feigi" in reason, fn.__name__
        assert "mõõdetud" not in reason and "garanteeritud" not in reason


def test_module_adds_no_network_calls():
    src = inspect.getsource(komun)
    assert "urlopen" not in src
    assert "httpx" not in src
    assert "requests.get" not in src
    assert "urllib" not in src


def test_demo_param_names_snow_page_viewer_and_sibling_legs():
    _, reason = dim_snow_maintenance_class(TALLINN, POIS)
    assert "talihooldusklass" in reason
    assert "lumekaart" in reason
    assert "tallinn.ee/et/lumi" in reason
    assert "dims_p4_tlt" in reason
    assert "dims_p4_osm" in reason


def test_uvk_plan_slice_names_tvesi_complement_not_duplicate():
    _, reason = dim_uvk_development_plan(TALLINN, POIS)
    assert "liitumispiirkond" in reason
    assert "dims_p4_tvesi" in reason
    assert "iseteenindusest" in reason


def test_stormwater_slice_names_tvesi_fee_table_and_eis_queue():
    _, reason = dim_stormwater_notices(TALLINN, POIS)
    assert "dims_p4_tvesi" in reason
    assert "EIS" in reason


def test_schedulable_noise_slice_names_harbour_air_and_elron_legs():
    _, reason = dim_schedulable_noise_calendar(TALLINN, POIS)
    assert "Sadama laevagraafikut" in reason
    assert "EANS" in reason
    assert "dims_p4_elron" in reason


def test_fixit_slice_names_human_channels_not_a_table():
    _, reason = dim_fixit_responsiveness(TALLINN, POIS)
    assert "14410" in reason
    assert "annateada.ee" in reason


def test_rat_hex_slice_never_names_addresses():
    _, reason = dim_rat_icefall_hex(TALLINN, POIS)
    assert "kunagi mitte aadressid" in reason
    assert "kohapealsel vaatlusel" in reason


def test_geology_slice_names_subsurface_sibling():
    _, reason = dim_geology_uvk_crosscheck(TALLINN, POIS)
    assert "dims_p4_maa_subsurface" in reason


def test_redig_endpoint_evidence_pinned_in_docstring():
    src = inspect.getsource(komun)
    assert "Teehoolduspiirkonnad_veebikaart" in src
    assert "Token Required" in src
    assert "Pirita_hooldus" in src
    assert "config.json" in src
    assert "#536" in src
    assert "dims_p4_trans" in src


def test_snow_reason_names_areas_layer_and_gated_folder():
    _, reason = dim_snow_maintenance_class(TALLINN, POIS)
    assert "Teehoolduspiirkonnad" in reason
    assert "klassiväljadeta" in reason
    assert "võtit" in reason


def test_areas_fixture_has_no_class_attribute():
    path = os.path.join(os.path.dirname(__file__), "fixtures",
                        "komun_teehooldus_layer.json")
    with open(path, encoding="utf-8") as fh:
        inv = json.load(fh)
    assert inv["service"] == (
        "veebikaart/Teehoolduspiirkonnad_veebikaart/MapServer")
    assert inv["class_attributes"] == []
    hay = " ".join(inv["fields"]).lower()
    assert "klass" not in hay and "tase" not in hay and "level" not in hay
    assert "nimetus" in inv["fields"] and "markused" in inv["fields"]
    v, _ = dim_snow_maintenance_class(TALLINN, POIS)
    assert v is None


def test_registry_and_aggregator_cover_all_eighteen():
    assert [k for k, _, _ in P4_KOMUN_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in P4_KOMUN_DIMS] == EXPECTED_PNUMS
    assert len({fn for _, _, fn in P4_KOMUN_DIMS}) == 18
    out = score_p4_komun(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_p4_komun(None, None) == {k: None for k in EXPECTED_KEYS}
    assert komun.P4_KOMUN_DIMS is P4_KOMUN_DIMS
