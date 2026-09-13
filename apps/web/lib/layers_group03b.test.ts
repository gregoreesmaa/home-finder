// Group 3 cadastre-B verdict tests (issue #152): p183/p184/p201/p228/p251
// are ALL documented no-map (OTA PR #131 precedent) with scorer dims in
// services/scoring/dims_group03b.py. Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP03B_ALL_PARAMS,
  GROUP03B_CONSIDERED_TAGS,
  GROUP03B_EVIDENCE,
  GROUP03B_HOOK,
  GROUP03B_NO_MAP,
  GROUP03B_SHIPPED_PARAMS,
} from "./layers_group03b";

describe("group03b verdict registry", () => {
  it("owns exactly the five G3-B params and ships zero layers", () => {
    expect([...GROUP03B_ALL_PARAMS]).toEqual([183, 184, 201, 228, 251]);
    expect([...GROUP03B_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP03B_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      183, 184, 201, 228, 251,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(Object.fromEntries(GROUP03B_NO_MAP.map((v) => [v.param, v.dim]))).toEqual({
      183: "dim_water_table",
      184: "dim_geothermal",
      201: "dim_septic",
      228: "dim_water_rights",
      251: "dim_soil_percolation",
    });
    for (const v of GROUP03B_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, never measured)", () => {
    const reasons = GROUP03B_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("hinnang");
    expect(reasons).toContain("EI OLE");
    expect(reasons).not.toMatch(/mõõdetud veetase on|garanteeritud/i);
  });

  it("locks the snapshot evidence counts (drift guard)", () => {
    expect(GROUP03B_EVIDENCE.wells).toBe(28);
    expect(GROUP03B_EVIDENCE.springs).toBe(35);
    expect(GROUP03B_EVIDENCE.wetlandsPoly).toBe(606);
    expect(GROUP03B_EVIDENCE.wetlandsLine).toBe(548);
    // derived-soil.geojson is junk: features exist, soil attrs zero.
    expect(GROUP03B_EVIDENCE.soilFileFeatures).toBe(53);
    expect(GROUP03B_EVIDENCE.soilFileSoilAttrs).toBe(0);
  });

  it("documents evaluated tags for proxy params, absence for NULL dims", () => {
    expect(GROUP03B_CONSIDERED_TAGS[183]).toContain("water_well");
    expect(GROUP03B_CONSIDERED_TAGS[201]).toContain("wetland");
    expect(GROUP03B_CONSIDERED_TAGS[228]).toContain("waterway");
    expect(GROUP03B_CONSIDERED_TAGS[184]).toContain("pole");
    expect(GROUP03B_CONSIDERED_TAGS[251]).toContain("pole");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP03B_HOOK).toContain("G03B-HOOK");
    expect(GROUP03B_HOOK).toContain("no shared-file wiring");
  });
});
