// Group 18 rest-C verdict tests (issue #197): p132 window views is a
// documented no-map (OTA PR #131 precedent) with a scorer dim in
// services/scoring/dims_group18restc.py. Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP18C_ALL_PARAMS,
  GROUP18C_CONSIDERED_TAGS,
  GROUP18C_EVIDENCE,
  GROUP18C_HOOK,
  GROUP18C_NO_MAP,
  GROUP18C_SHIPPED_PARAMS,
} from "./layers_group18restc";

describe("group18c verdict registry", () => {
  it("owns exactly p132 and ships zero layers", () => {
    expect([...GROUP18C_ALL_PARAMS]).toEqual([132]);
    expect([...GROUP18C_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP18C_NO_MAP.map((v) => v.param)).toEqual([132]);
  });

  it("points the verdict at its scorer dim", () => {
    expect(Object.fromEntries(GROUP18C_NO_MAP.map((v) => [v.param, v.dim]))).toEqual({
      132: "dim_windowviews",
    });
    for (const v of GROUP18C_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / ära feigi, never measured)", () => {
    const reasons = GROUP18C_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("hinnang");
    expect(reasons).toContain("ära feigi");
    expect(reasons).not.toMatch(/mõõdetud|garanteeritud/i);
  });

  it("names the already-consumed signals (no silent duplication)", () => {
    const reasons = GROUP18C_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("daylight");
    expect(reasons).toContain("dayopen");
    expect(reasons).toContain("viewshed");
    expect(GROUP18C_NO_MAP[0].nearestMap).toContain("shoredist");
  });

  it("locks the snapshot evidence counts (drift guard)", () => {
    expect(GROUP18C_EVIDENCE.windowTags).toBe(1);
    expect(GROUP18C_EVIDENCE.levelsTagged).toBe(33311);
    expect(GROUP18C_EVIDENCE.tallLevels4).toBe(7853);
    expect(GROUP18C_EVIDENCE.buildingCentroids).toBe(252140);
  });

  it("documents evaluated tags for p132", () => {
    expect(GROUP18C_CONSIDERED_TAGS[132]).toContain("window");
    expect(GROUP18C_CONSIDERED_TAGS[132]).toContain("building:levels");
    expect(GROUP18C_CONSIDERED_TAGS[132]).toContain("dayopen");
    expect(GROUP18C_CONSIDERED_TAGS[132]).toContain("daylight");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP18C_HOOK).toContain("G18C-HOOK");
    expect(GROUP18C_HOOK).toContain("no shared-file wiring");
  });
});
