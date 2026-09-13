// Group 19 on-site-inspection-A verdict tests (issue #208): p10/p31/p38/
// p55/p57/p58/p59/p91/p95/p96/p97/p111/p114/p115/p116/p120/p150/p171/
// p172/p173/p174/p175/p176/p177/p178/p179/p197/p199/p203/p205/p206/p207/
// p208/p209 are ALL documented no-map (OTA PR #131 precedent) with
// scorer dims in services/scoring/dims_group19a.py.
// Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP19A_ALL_PARAMS,
  GROUP19A_CONSIDERED_TAGS,
  GROUP19A_HOOK,
  GROUP19A_NO_MAP,
  GROUP19A_SHIPPED_PARAMS,
} from "./layers_group19a";

const OWNED = [
  10, 31, 38, 55, 57, 58, 59, 91, 95, 96, 97, 111, 114, 115, 116, 120,
  150, 171, 172, 173, 174, 175, 176, 177, 178, 179, 197, 199, 203, 205,
  206, 207, 208, 209,
];

const DIM_BY_PARAM: Record<number, string> = {
  10: "dim_renovation_budget",
  31: "dim_structural_integrity",
  38: "dim_hvac_systems",
  55: "dim_ev_charging_readiness",
  57: "dim_plumbing_pipe_materials",
  58: "dim_electrical_service_capacity",
  59: "dim_water_pressure_heating",
  91: "dim_ceiling_height_volume",
  95: "dim_interior_acoustic_insulation",
  96: "dim_ventilation_air_exchange",
  97: "dim_basement_usability",
  111: "dim_hurricane_readiness",
  114: "dim_severe_winter_resilience",
  115: "dim_seismic_retrofitting",
  116: "dim_storm_shelter",
  120: "dim_off_grid_capabilities",
  150: "dim_moving_truck_access",
  171: "dim_foundation_type",
  172: "dim_insulation_materials",
  173: "dim_interior_door_quality",
  174: "dim_floor_joist_engineering",
  175: "dim_cabinet_construction",
  176: "dim_window_frame_materials",
  177: "dim_roofing_lifespan",
  178: "dim_exterior_cladding",
  179: "dim_smart_home_lockin",
  197: "dim_whole_home_purification",
  199: "dim_physical_security",
  203: "dim_problematic_plumbing",
  205: "dim_synthetic_stucco",
  206: "dim_chimney_flue",
  207: "dim_retaining_wall",
  208: "dim_hidden_splices",
  209: "dim_mold_history",
};

describe("group19a verdict registry", () => {
  it("owns exactly the 34 G19-A params and ships zero layers", () => {
    expect([...GROUP19A_ALL_PARAMS]).toEqual(OWNED);
    expect([...GROUP19A_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP19A_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual(
      OWNED,
    );
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP19A_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual(DIM_BY_PARAM);
    for (const v of GROUP19A_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (EI OLE hinnangut, never a faked score)", () => {
    for (const v of GROUP19A_NO_MAP) {
      expect(v.reason).toContain("EI OLE");
      expect(v.reason).toContain("hinnang");
    }
    const reasons = GROUP19A_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toMatch(/garanteeritud|kindel skoor/i);
  });

  it("admits no shipped map proxy for any param", () => {
    for (const v of GROUP19A_NO_MAP) {
      expect(v.nearestMap).toContain("pole");
    }
  });

  it("documents the absent source for every param (no OSM tags to map)", () => {
    for (const p of OWNED) {
      expect(GROUP19A_CONSIDERED_TAGS[p as keyof typeof GROUP19A_CONSIDERED_TAGS]).toContain(
        "pole",
      );
    }
    // Shell tags never see the forensic interior — spot-check the framing.
    expect(GROUP19A_CONSIDERED_TAGS[57]).toContain("torustiku");
    expect(GROUP19A_CONSIDERED_TAGS[206]).toContain("kaamerauuring");
    expect(GROUP19A_CONSIDERED_TAGS[208]).toContain("EHR");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP19A_HOOK).toContain("G19A-HOOK");
    expect(GROUP19A_HOOK).toContain("no shared-file wiring");
  });
});
