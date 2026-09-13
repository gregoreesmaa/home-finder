"""Group 19 on-site-inspection-C dims (issue #210): hermetic tests.

No network: every scorer is input-independent NULL by design (Tier-4
on-site forensic facts), so tests assert None + Estonian
inspector-check reasons across varied inputs, plus registry and
aggregator coverage. No Overpass fragment / POI kinds exist here —
there is deliberately nothing to fetch.
"""

import dims_group19c as g19c
from dims_group19c import GROUP19C_DIMS, score_group19c

TALLINN = (59.4372, 24.7536)

POIS = [{"kind": "anything", "lat": TALLINN[0] + 0.001, "lon": TALLINN[1]}]

EXPECTED_KEYS = [
    "microbial_musty_scent", "natural_ventilation_draft",
    "makeup_air_unit", "ductwork_zoning", "attic_ventilation",
    "condensate_routing", "shutoff_valve_access", "combustion_backdraft",
    "sump_pump_backup", "expansion_valve", "vapor_barrier",
    "sewer_backflow", "grocery_unloading", "emergency_egress",
    "stroller_navigation", "furniture_clearance", "knob_tube_wiring",
    "coal_chute_oil_tank", "hurricane_straps", "generator_fuel",
    "water_storage_tanks", "smoke_air_scrubbing", "tornado_wind_load",
    "lawn_equipment_access", "sprinkler_winterizing",
    "pool_equipment_noise", "snow_storage", "hose_bib_placement",
    "allergen_circulation", "black_mold_vulnerability",
    "perimeter_breach", "safe_room_potential", "driveway_choke",
]

EXPECTED_PNUMS = [
    "p309", "p310", "p321", "p322", "p323", "p324", "p325", "p326",
    "p327", "p328", "p329", "p330", "p341", "p344", "p345", "p348",
    "p357", "p358", "p373", "p374", "p375", "p376", "p379", "p391",
    "p392", "p393", "p396", "p399", "p406", "p407", "p414", "p415",
    "p416",
]


def test_every_dim_is_none_for_every_input_with_honest_reason():
    assert len(GROUP19C_DIMS) == 33
    for key, pnum, fn in GROUP19C_DIMS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []),
                             (None, None), (None, POIS)]:
            v, reason = fn(origin, pois)
            assert v is None, (key, origin, pois)
            assert "EI OLE" in reason, key
            assert "hinnang" in reason, key
            assert "feigi" in reason, key


def test_reasons_name_the_concrete_check_per_cluster():
    by_key = {key: fn for key, _, fn in GROUP19C_DIMS}
    assert "Protimeter" in by_key["microbial_musty_scent"](TALLINN, POIS)[1]
    assert "suitsupliiats" in by_key["natural_ventilation_draft"](TALLINN, POIS)[1]
    assert "CO-mõõtja" in by_key["combustion_backdraft"](TALLINN, POIS)[1]
    assert "mõõdulindiga" in by_key["emergency_egress"](TALLINN, POIS)[1]
    assert "laseriga" in by_key["furniture_clearance"](TALLINN, POIS)[1]
    # Building age is mapped but proves nothing about live wiring.
    assert "vanus" in by_key["knob_tube_wiring"](TALLINN, POIS)[1]
    assert "EHR" in by_key["coal_chute_oil_tank"](TALLINN, POIS)[1]
    # Traffic-noise simulation cannot hear the pool pump (judgment call).
    assert "simulatsioon" in by_key["pool_equipment_noise"](TALLINN, POIS)[1]
    assert "Protimeter" in by_key["black_mold_vulnerability"](TALLINN, POIS)[1]
    # The public road graph is mapped but the courtyard fact is not.
    assert "teekaart" in by_key["driveway_choke"](TALLINN, POIS)[1]
    assert "teekaart" in by_key["grocery_unloading"](TALLINN, POIS)[1]


def test_no_snapshot_fetch_surface_exists():
    # Zero honest area signal => no Overpass fragment, no POI kinds.
    assert not hasattr(g19c, "GROUP19C_OVERPASS_FRAGMENT")
    assert not hasattr(g19c, "GROUP19C_POI_KIND")
    assert not hasattr(g19c, "kinds_from_tags")


def test_registry_and_aggregator_cover_all_33():
    assert [k for k, _, _ in GROUP19C_DIMS] == EXPECTED_KEYS
    assert [p for _, p, _ in GROUP19C_DIMS] == EXPECTED_PNUMS
    out = score_group19c(TALLINN, POIS)
    assert out == {k: None for k in EXPECTED_KEYS}
    assert score_group19c(None, None) == {k: None for k in EXPECTED_KEYS}
    assert g19c.GROUP19C_DIMS is GROUP19C_DIMS
