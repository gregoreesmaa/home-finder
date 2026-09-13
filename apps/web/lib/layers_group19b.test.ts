// Group 19 on-site inspection B verdict tests (issue #209):
// p210/p212/p217/p218/p219/p232/p233/p235/p236/p237/p238/p240/p261/
// p263/p264/p266/p267/p269/p284/p291/p292/p293/p294/p295/p296/p297/
// p298/p299/p302/p303/p304/p306/p307/p308 are ALL documented no-map
// (OTA PR #131 precedent) with scorer dims in
// services/scoring/dims_group19b.py. Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP19B_ALL_PARAMS,
  GROUP19B_CONSIDERED_TAGS,
  GROUP19B_EVIDENCE,
  GROUP19B_HOOK,
  GROUP19B_NO_MAP,
  GROUP19B_SHIPPED_PARAMS,
} from "./layers_group19b";

const EXPECTED_PARAMS = [
  210, 212, 217, 218, 219, 232, 233, 235, 236, 237, 238, 240, 261, 263,
  264, 266, 267, 269, 284, 291, 292, 293, 294, 295, 296, 297, 298, 299,
  302, 303, 304, 306, 307, 308,
];

describe("group19b verdict registry", () => {
  it("owns exactly the 34 G19-B params and ships zero layers", () => {
    expect([...GROUP19B_ALL_PARAMS]).toEqual(EXPECTED_PARAMS);
    expect([...GROUP19B_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP19B_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual(
      EXPECTED_PARAMS,
    );
  });

  it("points every verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP19B_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual({
      210: "dim_sewer_intrusion",
      212: "dim_smart_cybersecurity",
      217: "dim_battery_backup",
      218: "dim_hardwired_network",
      219: "dim_smart_irrigation",
      232: "dim_staircase_ergonomics",
      233: "dim_countertop_height",
      235: "dim_ceiling_joists",
      236: "dim_threshold_flushness",
      237: "dim_visual_alarm",
      238: "dim_allergen_arch",
      240: "dim_colorblind_finishes",
      261: "dim_wiring_conduit",
      263: "dim_biometric_security",
      264: "dim_ev_scale",
      266: "dim_automated_shading",
      267: "dim_automation_lockin",
      269: "dim_backup_cisterns",
      284: "dim_home_gym",
      291: "dim_flatroof_drainage",
      292: "dim_cantilever_stress",
      293: "dim_radiant_repair",
      294: "dim_window_wells",
      295: "dim_glazing_costs",
      296: "dim_exposed_steel",
      297: "dim_vaulted_ceiling",
      298: "dim_adaptive_reuse",
      299: "dim_salvaged_material",
      302: "dim_thermal_bridge",
      303: "dim_acoustic_resonance",
      304: "dim_echo_reverb",
      306: "dim_water_hammer",
      307: "dim_register_whistle",
      308: "dim_floor_slope",
    });
    for (const v of GROUP19B_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, never measured)", () => {
    for (const v of GROUP19B_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    const reasons = GROUP19B_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toMatch(/mõõdetud .* on|garanteeritud/i);
  });

  it("names an on-site check per verdict (camera/meter/ears/acts)", () => {
    const reasons = GROUP19B_NO_MAP.map((v) => v.reason).join(" ");
    for (const word of [
      "kaamera",
      "kilb",
      "termokaamer",
      "nivelliir",
      "kuulam",
      "aktid",
      "EHR",
    ]) {
      expect(reasons).toContain(word);
    }
  });

  it("locks the snapshot evidence counts (drift guard)", () => {
    expect(GROUP19B_EVIDENCE.chargingStations).toBe(341);
    expect(GROUP19B_EVIDENCE.pipelineObjects).toBe(4501);
    expect(GROUP19B_EVIDENCE.sewerKeyObjects).toBe(0);
    expect(GROUP19B_EVIDENCE.auditFeeds).toBe(0);
  });

  it("documents evaluated tags for proxy params, absence for NULL dims", () => {
    expect(GROUP19B_CONSIDERED_TAGS[210]).toContain("pipeline");
    expect(GROUP19B_CONSIDERED_TAGS[210]).toContain("0 objekti");
    expect(GROUP19B_CONSIDERED_TAGS[264]).toContain("charging_station");
    expect(GROUP19B_CONSIDERED_TAGS[302]).toContain("puudub");
    expect(GROUP19B_CONSIDERED_TAGS[308]).toContain("nivelliiri");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP19B_HOOK).toContain("G19B-HOOK");
    expect(GROUP19B_HOOK).toContain("no shared-file wiring");
  });
});
