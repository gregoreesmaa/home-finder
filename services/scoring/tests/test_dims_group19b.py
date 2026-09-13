"""Group 19 on-site inspection dims, batch B (issue #209): hermetic tests.

No network: every scorer is an unconditional NULL, so the tests pin
the NULL contract for every input shape plus the registry surface.
"""

import dims_group19b as g19b
from dims_group19b import (
    GROUP19B_DIMS,
    dim_acoustic_resonance,
    dim_adaptive_reuse,
    dim_allergen_arch,
    dim_automated_shading,
    dim_automation_lockin,
    dim_backup_cisterns,
    dim_battery_backup,
    dim_biometric_security,
    dim_cantilever_stress,
    dim_ceiling_joists,
    dim_colorblind_finishes,
    dim_countertop_height,
    dim_echo_reverb,
    dim_ev_scale,
    dim_exposed_steel,
    dim_floor_slope,
    dim_flatroof_drainage,
    dim_glazing_costs,
    dim_hardwired_network,
    dim_home_gym,
    dim_radiant_repair,
    dim_register_whistle,
    dim_salvaged_material,
    dim_sewer_intrusion,
    dim_smart_cybersecurity,
    dim_smart_irrigation,
    dim_staircase_ergonomics,
    dim_thermal_bridge,
    dim_threshold_flushness,
    dim_vaulted_ceiling,
    dim_visual_alarm,
    dim_water_hammer,
    dim_window_wells,
    dim_wiring_conduit,
    score_group19b,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


POIS = [
    _poi("charging_station", 0.001),
    _poi("pipeline", 0.004),
    _poi("building", 0.0007),
]

ALL_FNS = [fn for _, _, fn in GROUP19B_DIMS]

EXPECTED_KEYS = [
    "sewer_intrusion", "smart_cybersecurity", "battery_backup",
    "hardwired_network", "smart_irrigation", "staircase_ergonomics",
    "countertop_height", "ceiling_joists", "threshold_flushness",
    "visual_alarm", "allergen_arch", "colorblind_finishes",
    "wiring_conduit", "biometric_security", "ev_scale",
    "automated_shading", "automation_lockin", "backup_cisterns",
    "home_gym", "flatroof_drainage", "cantilever_stress",
    "radiant_repair", "window_wells", "glazing_costs", "exposed_steel",
    "vaulted_ceiling", "adaptive_reuse", "salvaged_material",
    "thermal_bridge", "acoustic_resonance", "echo_reverb",
    "water_hammer", "register_whistle", "floor_slope",
]

EXPECTED_PIDS = [
    "p210", "p212", "p217", "p218", "p219", "p232", "p233", "p235",
    "p236", "p237", "p238", "p240", "p261", "p263", "p264", "p266",
    "p267", "p269", "p284", "p291", "p292", "p293", "p294", "p295",
    "p296", "p297", "p298", "p299", "p302", "p303", "p304", "p306",
    "p307", "p308",
]


def test_all_dims_always_none_with_inspector_check():
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, reason = fn(origin, pois)
            assert v is None
            assert "EI OLE" in reason
            assert "hinnang" in reason
            assert "teadmata" in reason


def test_all_dims_imported_and_registered():
    assert len(ALL_FNS) == 34
    assert [key for key, _, _ in GROUP19B_DIMS] == EXPECTED_KEYS
    assert [pid for _, pid, _ in GROUP19B_DIMS] == EXPECTED_PIDS
    for fn in ALL_FNS:
        assert callable(fn)


def test_sewer_intrusion_names_camera_and_rejects_pipeline_proxy():
    _, reason = dim_sewer_intrusion(TALLINN, POIS)
    assert "kaamera" in reason
    assert "pipeline" in reason
    assert "EI OLE" in reason


def test_ev_scale_names_panel_and_rejects_charger_proxy():
    _, reason = dim_ev_scale(TALLINN, POIS)
    assert "kilb" in reason
    assert "341" in reason
    assert "kW-hinnangut" in reason


def test_meter_dims_name_their_meters():
    assert "laseriga" in dim_staircase_ergonomics(TALLINN, POIS)[1]
    assert "termokaameraga" in dim_thermal_bridge(TALLINN, POIS)[1]
    assert "nivelliir" in dim_floor_slope(TALLINN, POIS)[1]
    assert "nivelliir" in dim_threshold_flushness(TALLINN, POIS)[1]


def test_listening_dims_name_listening():
    for fn in (dim_acoustic_resonance, dim_echo_reverb,
               dim_water_hammer, dim_register_whistle):
        assert "kuula" in fn(TALLINN, POIS)[1]


def test_document_dims_name_their_checks():
    assert "kaetud" in dim_radiant_repair(TALLINN, POIS)[1]
    assert "kaetud" in dim_sewer_intrusion(TALLINN, POIS)[1]
    assert "EHR" in dim_adaptive_reuse(TALLINN, POIS)[1]
    assert "pakkumine" in dim_glazing_costs(TALLINN, POIS)[1]
    assert "arveid" in dim_vaulted_ceiling(TALLINN, POIS)[1]


def test_engineer_dims_name_the_engineer():
    for fn in (dim_ceiling_joists, dim_home_gym, dim_cantilever_stress):
        _, reason = fn(TALLINN, POIS)
        assert "inseneri" in reason


def test_buyer_eye_params_do_not_send_an_engineer():
    _, colorblind = dim_colorblind_finishes(TALLINN, POIS)
    assert "ostja enda silmade" in colorblind
    assert "inseneri" not in colorblind
    _, counter = dim_countertop_height(TALLINN, POIS)
    assert "mõõda kohapeal" in counter


def test_reasons_never_claim_measured_or_guaranteed():
    for fn in ALL_FNS:
        lowered = fn(TALLINN, POIS)[1].lower()
        assert "mõõdetud" not in lowered
        assert "garanteeritud" not in lowered


def test_score_group19b_returns_all_nulls():
    out = score_group19b(TALLINN, POIS)
    assert out == {key: None for key in EXPECTED_KEYS}
    assert score_group19b(None, None) == {key: None for key in EXPECTED_KEYS}
    assert g19b.GROUP19B_DIMS is GROUP19B_DIMS


def test_spot_checks_cover_remaining_dims():
    assert "auditit" in dim_smart_cybersecurity(TALLINN, POIS)[1]
    assert "nimesilte" in dim_battery_backup(TALLINN, POIS)[1]
    assert "kaabliteid" in dim_hardwired_network(TALLINN, POIS)[1]
    assert "kontrollerit" in dim_smart_irrigation(TALLINN, POIS)[1]
    assert "kilpi" in dim_visual_alarm(TALLINN, POIS)[1]
    assert "ventilatsiooni" in dim_allergen_arch(TALLINN, POIS)[1]
    assert "kilbi" in dim_wiring_conduit(TALLINN, POIS)[1]
    assert "ühilduvust" in dim_biometric_security(TALLINN, POIS)[1]
    assert "juhtmestikku" in dim_automated_shading(TALLINN, POIS)[1]
    assert "protokolle" in dim_automation_lockin(TALLINN, POIS)[1]
    assert "pumpa" in dim_backup_cisterns(TALLINN, POIS)[1]
    assert "katuse" in dim_flatroof_drainage(TALLINN, POIS)[1]
    assert "kaevude" in dim_window_wells(TALLINN, POIS)[1]
    assert "korrosiooni" in dim_exposed_steel(TALLINN, POIS)[1]
    assert "visuaalselt" in dim_salvaged_material(TALLINN, POIS)[1]
