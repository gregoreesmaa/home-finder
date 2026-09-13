// Group 19 on-site-inspection-C verdict tests (issue #210): p309/p310/
// p321/p322/p323/p324/p325/p326/p327/p328/p329/p330/p341/p344/p345/
// p348/p357/p358/p373/p374/p375/p376/p379/p391/p392/p393/p396/p399/
// p406/p407/p414/p415/p416 are ALL documented no-map (OTA PR #131
// precedent) with scorer dims in services/scoring/dims_group19c.py.
// Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP19C_ALL_PARAMS,
  GROUP19C_CONSIDERED_TAGS,
  GROUP19C_HOOK,
  GROUP19C_NO_MAP,
  GROUP19C_SHIPPED_PARAMS,
} from "./layers_group19c";

const OWNED = [
  309, 310, 321, 322, 323, 324, 325, 326, 327, 328, 329, 330, 341, 344,
  345, 348, 357, 358, 373, 374, 375, 376, 379, 391, 392, 393, 396, 399,
  406, 407, 414, 415, 416,
];

const DIM_BY_PARAM: Record<number, string> = {
  309: "dim_microbial_musty_scent",
  310: "dim_natural_ventilation_draft",
  321: "dim_makeup_air_unit",
  322: "dim_ductwork_zoning",
  323: "dim_attic_ventilation",
  324: "dim_condensate_routing",
  325: "dim_shutoff_valve_access",
  326: "dim_combustion_backdraft",
  327: "dim_sump_pump_backup",
  328: "dim_expansion_valve",
  329: "dim_vapor_barrier",
  330: "dim_sewer_backflow",
  341: "dim_grocery_unloading",
  344: "dim_emergency_egress",
  345: "dim_stroller_navigation",
  348: "dim_furniture_clearance",
  357: "dim_knob_tube_wiring",
  358: "dim_coal_chute_oil_tank",
  373: "dim_hurricane_straps",
  374: "dim_generator_fuel",
  375: "dim_water_storage_tanks",
  376: "dim_smoke_air_scrubbing",
  379: "dim_tornado_wind_load",
  391: "dim_lawn_equipment_access",
  392: "dim_sprinkler_winterizing",
  393: "dim_pool_equipment_noise",
  396: "dim_snow_storage",
  399: "dim_hose_bib_placement",
  406: "dim_allergen_circulation",
  407: "dim_black_mold_vulnerability",
  414: "dim_perimeter_breach",
  415: "dim_safe_room_potential",
  416: "dim_driveway_choke",
};

describe("group19c verdict registry", () => {
  it("owns exactly the 33 G19-C params and ships zero layers", () => {
    expect([...GROUP19C_ALL_PARAMS]).toEqual(OWNED);
    expect([...GROUP19C_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP19C_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual(
      OWNED,
    );
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP19C_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual(DIM_BY_PARAM);
    for (const v of GROUP19C_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (EI OLE hinnangut, never a faked score)", () => {
    for (const v of GROUP19C_NO_MAP) {
      expect(v.reason).toContain("EI OLE");
      expect(v.reason).toContain("hinnang");
    }
    const reasons = GROUP19C_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toMatch(/garanteeritud|kindel skoor/i);
  });

  it("admits no shipped map proxy for any param", () => {
    for (const v of GROUP19C_NO_MAP) {
      expect(v.nearestMap).toContain("pole");
    }
  });

  it("documents the absent source for every param (no OSM tags to map)", () => {
    for (const p of OWNED) {
      expect(GROUP19C_CONSIDERED_TAGS[p as keyof typeof GROUP19C_CONSIDERED_TAGS]).toContain(
        "pole",
      );
    }
    // Forensic facts need rooms/meters, not shell tags — spot-check.
    expect(GROUP19C_CONSIDERED_TAGS[309]).toContain("nuusutamine");
    expect(GROUP19C_CONSIDERED_TAGS[344]).toContain("mõõdulindi");
    expect(GROUP19C_CONSIDERED_TAGS[358]).toContain("EHR");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP19C_HOOK).toContain("G19C-HOOK");
    expect(GROUP19C_HOOK).toContain("no shared-file wiring");
  });
});
