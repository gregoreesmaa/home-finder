// Group 3 cadastre-C verdict tests (issue #153): p254/p256/p258/p273/p277
// are ALL documented no-map (OTA PR #131 precedent) with scorer dims in
// services/scoring/dims_group03c.py. Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP03C_ALL_PARAMS,
  GROUP03C_CONSIDERED_TAGS,
  GROUP03C_EVIDENCE,
  GROUP03C_HOOK,
  GROUP03C_NO_MAP,
  GROUP03C_SHIPPED_PARAMS,
} from "./layers_group03c";

describe("group03c verdict registry", () => {
  it("owns exactly the five G3-C params and ships zero layers", () => {
    expect([...GROUP03C_ALL_PARAMS]).toEqual([254, 256, 258, 273, 277]);
    expect([...GROUP03C_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP03C_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      254, 256, 258, 273, 277,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(Object.fromEntries(GROUP03C_NO_MAP.map((v) => [v.param, v.dim]))).toEqual({
      254: "dim_wetland_proximity",
      256: "dim_springs",
      258: "dim_soil_ph",
      273: "dim_unregistered_easements",
      277: "dim_riparian_constraints",
    });
    for (const v of GROUP03C_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, never measured)", () => {
    const reasons = GROUP03C_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("hinnang");
    expect(reasons).toContain("EI OLE");
    expect(reasons).not.toMatch(/mõõdetud .* on|garanteeritud/i);
  });

  it("locks the snapshot evidence counts (drift guard)", () => {
    // Springs/wells are sparse (dozens county-wide: no Tallinn gradient).
    expect(GROUP03C_EVIDENCE.springsTagged).toBe(43);
    expect(GROUP03C_EVIDENCE.springsPoints).toBe(35);
    expect(GROUP03C_EVIDENCE.wellsTagged).toBe(30);
    expect(GROUP03C_EVIDENCE.wellsPoints).toBe(28);
    // Wetlands are dense (already feed p50 drainage + wildcorr).
    expect(GROUP03C_EVIDENCE.wetlandsTagged).toBe(1264);
    expect(GROUP03C_EVIDENCE.wetlandsPoly).toBe(667);
    expect(GROUP03C_EVIDENCE.wetlandsLine).toBe(637);
    // Reserves/protected areas exist but carry no per-wetland status.
    expect(GROUP03C_EVIDENCE.reservesLeisureTagged).toBe(137);
    expect(GROUP03C_EVIDENCE.reservesLeisurePoly).toBe(32);
    expect(GROUP03C_EVIDENCE.protectedAreaTagged).toBe(167);
    expect(GROUP03C_EVIDENCE.protectedAreaPoly).toBe(51);
    // derived-soil.geojson is junk: features exist, soil attrs zero.
    expect(GROUP03C_EVIDENCE.soilFileFeatures).toBe(53);
    expect(GROUP03C_EVIDENCE.soilFileSoilAttrs).toBe(0);
  });

  it("documents evaluated tags for proxy params, absence for NULL dims", () => {
    expect(GROUP03C_CONSIDERED_TAGS[254]).toContain("wetland");
    expect(GROUP03C_CONSIDERED_TAGS[254]).toContain("protected_area");
    expect(GROUP03C_CONSIDERED_TAGS[256]).toContain("spring");
    expect(GROUP03C_CONSIDERED_TAGS[277]).toContain("waterway");
    expect(GROUP03C_CONSIDERED_TAGS[277]).toContain("coastline");
    expect(GROUP03C_CONSIDERED_TAGS[258]).toContain("pole");
    expect(GROUP03C_CONSIDERED_TAGS[273]).toContain("kaardistamatu");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP03C_HOOK).toContain("G03C-HOOK");
    expect(GROUP03C_HOOK).toContain("no shared-file wiring");
  });
});
