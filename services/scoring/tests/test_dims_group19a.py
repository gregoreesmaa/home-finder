"""Group 19 on-site-inspection-A dims (issue #208): hermetic tests.

No network: every scorer is input-independent NULL by design (Tier-4
on-site forensic facts), so tests assert None + Estonian
inspector-check reasons across varied inputs, plus registry and
aggregator coverage. No Overpass fragment / POI kinds exist here —
there is deliberately nothing to fetch.
"""

import dims_group19a as g19a
from dims_group19a import GROUP19A_DIMS, score_group19a

TALLINN = (59.4372, 24.7536)

POIS = [{"kind": "anything", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]

EXPECTED_KEYS = [
    "renovation_budget", "structural_integrity", "hvac_systems",
    "ev_charging_readiness", "plumbing_pipe_materials",
    "electrical_service_capacity", "water_pressure_heating",
    "ceiling_height_volume", "interior_acoustic_insulation",
    "ventilation_air_exchange", "basement_usability",
    "hurricane_readiness", "severe_winter_resilience",
    "seismic_retrofitting", "storm_shelter", "off_grid_capabilities",
    "moving_truck_access", "foundation_type", "insulation_materials",
    "interior_door_quality", "floor_joist_engineering",
    "cabinet_construction", "window_frame_materials", "roofing_lifespan",
    "exterior_cladding", "smart_home_lockin", "whole_home_purification",
    "physical_security", "problematic_plumbing", "synthetic_stucco",
    "chimney_flue", "retaining_wall", "hidden_splices", "mold_history",
]

EXPECTED_PNUMS = [
    "p10", "p31", "p38", "p55", "p57", "p58", "p59", "p91", "p95",
    "p96", "p97", "p111", "p114", "p115", "p116", "p120", "p150",
    "p171", "p172", "p173", "p174", "p175", "p176", "p177", "p178",
    "p179", "p197", "p199", "p203", "p205", "p206", "p207", "p208",
    "p209",
]


def test_every_dim_is_none_for_every_input_with_honest_reason():
    assert len(GROUP19A_DIMS) == 34
    for key, pnum, fn in GROUP19A_DIMS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []),
                             (None, None), (None, POIS)]:
            v, reason = fn(origin, pois)
            assert v is None, (key, origin, pois)
            assert "EI OLE" in reason, key
            assert "hinnang" in reason, key
            assert "feigi" in reason, key


def test_reasons_name_the_concrete_check_per_cluster():
    by_key = {key: fn for key, _, fn in GROUP19A_DIMS}
    assert "pakku" in by_key["renovation_budget"](TALLINN, POIS)[1]
    assert "EVS 932" in by_key["structural_integrity"](TALLINN, POIS)[1]
    assert "elektriku" in by_key["ev_charging_readiness"](TALLINN, POIS)[1]
    assert "torumehe" in by_key["plumbing_pipe_materials"](TALLINN, POIS)[1]
    assert "kraani" in by_key["water_pressure_heating"](TALLINN, POIS)[1]
    assert "laseri" in by_key["ceiling_height_volume"](TALLINN, POIS)[1]
    assert "Protimeter" in by_key["basement_usability"](TALLINN, POIS)[1]
    # Streets are mapped but the courtyard fact is not (judgment call).
    assert "tänavakaart" in by_key["moving_truck_access"](TALLINN, POIS)[1]
    assert "kaamerauuring" in by_key["chimney_flue"](TALLINN, POIS)[1]
    assert "EHR" in by_key["hidden_splices"](TALLINN, POIS)[1]
    assert "Protimeter" in by_key["mold_history"](TALLINN, POIS)[1]


def test_no_snapshot_fetch_surface_exists():
    # Zero honest area signal => no Overpass fragment, no POI kinds.
    assert not hasattr(g19a, "GROUP19A_OVERPASS_FRAGMENT")
    assert not hasattr(g19a, "GROUP19A_POI_KIND")
    assert not hasattr(g19a, "kinds_from_tags")


def test_registry_and_aggregator_cover_all_34():
    assert [k for k, _, _ in GROUP19A_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in GROUP19A_DIMS] == EXPECTED_PNUMS
    out = score_group19a(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_group19a(None, None) == {k: None for k in EXPECTED_KEYS}
    assert g19a.GROUP19A_DIMS is GROUP19A_DIMS
