"""Group 19 on-site inspection dims, batch D (issue #211): hermetic tests.

No network: every scorer is an unconditional NULL, so the tests pin
the NULL contract for every input shape plus the registry surface.
Each dim must name its concrete on-site check (toolkit item or
expert) and carry the EI OLE anti-fake-precision guard.
"""

import dims_group19d as g19d
from dims_group19d import (
    GROUP19D_DIMS,
    dim_appliance_cutout,
    dim_bath_ventilation,
    dim_chimney_draft,
    dim_closet_depth,
    dim_deck_dryrot,
    dim_downspout_term,
    dim_driveway_material,
    dim_exterior_outlets,
    dim_fan_boxes,
    dim_fireplace_separation,
    dim_galv_pipe,
    dim_hosebib_pressure,
    dim_kitchen_exhaust,
    dim_motion_lighting,
    dim_paint_finish,
    dim_patio_slope,
    dim_pet_urine,
    dim_pocket_door,
    dim_posttension_slab,
    dim_radiator_footprint,
    dim_rooflines,
    dim_skylight_leaks,
    dim_smart_lock,
    dim_soffit_fascia,
    dim_sprayfoam_hurdle,
    dim_stair_geometry,
    dim_stair_headroom,
    dim_subfloor_squeak,
    dim_sunken_living,
    dim_ungrounded_outlets,
    dim_vehicle_clearance,
    dim_water_heater_place,
    dim_window_treatment,
    score_group19d,
)

TALLINN = (59.4372, 24.7536)


def _poi(kind, dlat, dlon=0.0):
    return {"kind": kind, "lat": TALLINN[0] + dlat, "lon": TALLINN[1] + dlon}


POIS = [
    _poi("building", 0.001),
    _poi("road", 0.004),
]

ALL_FNS = [fn for _, _, fn in GROUP19D_DIMS]

# (dim fn, keyword proving the reason names the concrete on-site check).
DIM_CHECKS = [
    (dim_smart_lock, "mõõtes"),
    (dim_motion_lighting, "pimedas"),
    (dim_posttension_slab, "EHR"),
    (dim_rooflines, "katuse"),
    (dim_stair_geometry, "mõõdulindiga"),
    (dim_pocket_door, "liigutades"),
    (dim_sunken_living, "ehitusloa"),
    (dim_skylight_leaks, "tihendite"),
    (dim_radiator_footprint, "laser-mõõtja"),
    (dim_sprayfoam_hurdle, "inseneri"),
    (dim_ungrounded_outlets, "GFCI"),
    (dim_soffit_fascia, "redelilt"),
    (dim_vehicle_clearance, "proovisõidul"),
    (dim_appliance_cutout, "mõõdulindi"),
    (dim_closet_depth, "sügavus"),
    (dim_stair_headroom, "läbikäigukõrgus"),
    (dim_kitchen_exhaust, "kanali"),
    (dim_window_treatment, "seinamaterjali"),
    (dim_subfloor_squeak, "kõndides"),
    (dim_fan_boxes, "elektriku"),
    (dim_bath_ventilation, "niiskusmõõtja"),
    (dim_paint_finish, "päevavalguses"),
    (dim_downspout_term, "vihma"),
    (dim_exterior_outlets, "ümber käies"),
    (dim_driveway_material, "praod"),
    (dim_water_heater_place, "tehnoruumi"),
    (dim_patio_slope, "vesiloodiga"),
    (dim_hosebib_pressure, "kraani avades"),
    (dim_pet_urine, "Protimeter"),
    (dim_chimney_draft, "korstnapühkija"),
    (dim_deck_dryrot, "tõstes"),
    (dim_galv_pipe, "surveproovil"),
    (dim_fireplace_separation, "ehitusekspertiisi"),
]


def test_all_33_dims_always_none_with_inspector_check():
    assert len(ALL_FNS) == 33
    for fn in ALL_FNS:
        for origin, pois in [(TALLINN, POIS), (TALLINN, []), (None, None),
                             (None, POIS), (TALLINN, None)]:
            v, reason = fn(origin, pois)
            assert v is None
            assert "EI OLE" in reason
            assert "ära feigi" in reason


def test_each_dim_names_its_concrete_onsite_check():
    assert len(DIM_CHECKS) == 33
    checked = set()
    for fn, keyword in DIM_CHECKS:
        _, reason = fn(TALLINN, POIS)
        assert keyword in reason, fn.__name__
        checked.add(fn)
    assert checked == set(ALL_FNS)


def test_reasons_never_claim_measurement_or_guarantee():
    for fn in ALL_FNS:
        _, reason = fn(TALLINN, POIS)
        lowered = reason.lower()
        assert "mõõdetud" not in lowered, fn.__name__
        assert "garanteeritud" not in lowered, fn.__name__


def test_registry_covers_exactly_the_33_batch_params():
    assert [(key, pid) for key, pid, _ in GROUP19D_DIMS] == [
        ("smart_lock", "p417"),
        ("motion_lighting", "p418"),
        ("posttension_slab", "p431"),
        ("rooflines", "p432"),
        ("stair_geometry", "p433"),
        ("pocket_door", "p434"),
        ("sunken_living", "p435"),
        ("skylight_leaks", "p436"),
        ("radiator_footprint", "p437"),
        ("sprayfoam_hurdle", "p438"),
        ("ungrounded_outlets", "p439"),
        ("soffit_fascia", "p440"),
        ("vehicle_clearance", "p451"),
        ("appliance_cutout", "p452"),
        ("closet_depth", "p453"),
        ("stair_headroom", "p454"),
        ("kitchen_exhaust", "p455"),
        ("window_treatment", "p456"),
        ("subfloor_squeak", "p457"),
        ("fan_boxes", "p458"),
        ("bath_ventilation", "p459"),
        ("paint_finish", "p460"),
        ("downspout_term", "p472"),
        ("exterior_outlets", "p473"),
        ("driveway_material", "p474"),
        ("water_heater_place", "p475"),
        ("patio_slope", "p477"),
        ("hosebib_pressure", "p478"),
        ("pet_urine", "p492"),
        ("chimney_draft", "p494"),
        ("deck_dryrot", "p496"),
        ("galv_pipe", "p497"),
        ("fireplace_separation", "p498"),
    ]
    for key, pid, fn in GROUP19D_DIMS:
        assert fn.__name__ == "dim_" + key
    assert g19d.GROUP19D_DIMS is GROUP19D_DIMS


def test_score_group19d_returns_all_nulls():
    out = score_group19d(TALLINN, POIS)
    assert set(out) == {key for key, _, _ in GROUP19D_DIMS}
    assert all(v is None for v in out.values())
    assert all(v is None for v in score_group19d(None, None).values())
