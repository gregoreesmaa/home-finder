// Group 3 cadastre-E verdict tests (issue #155): p397/p400 are BOTH
// documented no-map (OTA PR #131 precedent) with scorer dims in
// services/scoring/dims_group03e.py. Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP03E_ALL_PARAMS,
  GROUP03E_CONSIDERED_TAGS,
  GROUP03E_EVIDENCE,
  GROUP03E_HOOK,
  GROUP03E_NO_MAP,
  GROUP03E_SHIPPED_PARAMS,
} from "./layers_group03e";

describe("group03e verdict registry", () => {
  it("owns exactly the two G3-E params and ships zero layers", () => {
    expect([...GROUP03E_ALL_PARAMS]).toEqual([397, 400]);
    expect([...GROUP03E_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP03E_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      397, 400,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(Object.fromEntries(GROUP03E_NO_MAP.map((v) => [v.param, v.dim]))).toEqual({
      397: "dim_fence_ownership",
      400: "dim_yard_drainage",
    });
    for (const v of GROUP03E_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / ära feigi, never measured)", () => {
    const reasons = GROUP03E_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("hinnang");
    expect(reasons).toContain("ära feigi");
    expect(reasons).not.toMatch(/mõõdetud|garanteeritud/i);
  });

  it("locks the snapshot evidence counts (drift guard)", () => {
    expect(GROUP03E_EVIDENCE.barriers).toBe(36384);
    expect(GROUP03E_EVIDENCE.fences).toBe(11308);
    // The load-bearing zeros: no ownership signal exists by construction.
    expect(GROUP03E_EVIDENCE.ownershipTags).toBe(0);
    expect(GROUP03E_EVIDENCE.ownerTags).toBe(0);
    expect(GROUP03E_EVIDENCE.operatorTags).toBe(364);
    expect(GROUP03E_EVIDENCE.ditch).toBe(7657);
    expect(GROUP03E_EVIDENCE.drain).toBe(1316);
    expect(GROUP03E_EVIDENCE.ditchDrainTallinn).toBe(2663);
  });

  it("documents evaluated tags for both params", () => {
    expect(GROUP03E_CONSIDERED_TAGS[397]).toContain("barrier");
    expect(GROUP03E_CONSIDERED_TAGS[397]).toContain("ownership");
    expect(GROUP03E_CONSIDERED_TAGS[400]).toContain("ditch");
    expect(GROUP03E_CONSIDERED_TAGS[400]).toContain("p50");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP03E_HOOK).toContain("G03E-HOOK");
    expect(GROUP03E_HOOK).toContain("no shared-file wiring");
  });
});
