// Group 19 on-site inspection-D verdict tests (issue #211):
// p417/p418, p431-p440, p451-p460, p472-p475, p477/p478, p492, p494,
// p496-p498 are ALL documented no-map (OTA PR #131 precedent) with
// scorer dims in services/scoring/dims_group19d.py.
// Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP19D_ALL_PARAMS,
  GROUP19D_HOOK,
  GROUP19D_NO_MAP,
  GROUP19D_SHIPPED_PARAMS,
} from "./layers_group19d";

const EXPECTED_PARAMS = [
  417, 418, 431, 432, 433, 434, 435, 436, 437, 438, 439, 440, 451, 452,
  453, 454, 455, 456, 457, 458, 459, 460, 472, 473, 474, 475, 477, 478,
  492, 494, 496, 497, 498,
];

const EXPECTED_DIMS: Record<number, string> = {
  417: "dim_smart_lock",
  418: "dim_motion_lighting",
  431: "dim_posttension_slab",
  432: "dim_rooflines",
  433: "dim_stair_geometry",
  434: "dim_pocket_door",
  435: "dim_sunken_living",
  436: "dim_skylight_leaks",
  437: "dim_radiator_footprint",
  438: "dim_sprayfoam_hurdle",
  439: "dim_ungrounded_outlets",
  440: "dim_soffit_fascia",
  451: "dim_vehicle_clearance",
  452: "dim_appliance_cutout",
  453: "dim_closet_depth",
  454: "dim_stair_headroom",
  455: "dim_kitchen_exhaust",
  456: "dim_window_treatment",
  457: "dim_subfloor_squeak",
  458: "dim_fan_boxes",
  459: "dim_bath_ventilation",
  460: "dim_paint_finish",
  472: "dim_downspout_term",
  473: "dim_exterior_outlets",
  474: "dim_driveway_material",
  475: "dim_water_heater_place",
  477: "dim_patio_slope",
  478: "dim_hosebib_pressure",
  492: "dim_pet_urine",
  494: "dim_chimney_draft",
  496: "dim_deck_dryrot",
  497: "dim_galv_pipe",
  498: "dim_fireplace_separation",
};

describe("group19d verdict registry", () => {
  it("owns exactly the 33 G19-D params and ships zero layers", () => {
    expect([...GROUP19D_ALL_PARAMS]).toEqual(EXPECTED_PARAMS);
    expect([...GROUP19D_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP19D_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual(
      EXPECTED_PARAMS,
    );
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP19D_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual(EXPECTED_DIMS);
    const dims = new Set(GROUP19D_NO_MAP.map((v) => v.dim));
    // One dim per param: no two verdicts share a scorer.
    expect(dims.size).toBe(GROUP19D_NO_MAP.length);
    for (const v of GROUP19D_NO_MAP) {
      expect(v.dim).toMatch(/^dim_[a-z0-9_]+$/);
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, never measured)", () => {
    const reasons = GROUP19D_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("hinnang");
    expect(reasons).toContain("EI OLE");
    expect(reasons).not.toMatch(/mõõdetud|garanteeritud/i);
    // Every NULL verdict names the on-site check the buyer must do.
    for (const v of GROUP19D_NO_MAP) {
      expect(v.reason).toMatch(/kohapeal|kohapealse|külastus/i);
    }
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP19D_HOOK).toContain("G19D-HOOK");
    expect(GROUP19D_HOOK).toContain("no shared-file wiring");
  });
});
