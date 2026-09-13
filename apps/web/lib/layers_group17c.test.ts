// Group 17 HOA-C verdict tests (issue #207): p3 HOA fees is a
// documented no-map (OTA PR #131 precedent) with the scorer dim in
// services/scoring/dims_group17c.py. Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP17C_ALL_PARAMS,
  GROUP17C_CONSIDERED_TAGS,
  GROUP17C_EVIDENCE,
  GROUP17C_HOOK,
  GROUP17C_NO_MAP,
  GROUP17C_SHIPPED_PARAMS,
} from "./layers_group17c";

describe("group17c verdict registry", () => {
  it("owns exactly the single G17-C param and ships zero layers", () => {
    expect([...GROUP17C_ALL_PARAMS]).toEqual([3]);
    expect([...GROUP17C_SHIPPED_PARAMS]).toEqual([]);
    // The owned param has exactly one documented verdict.
    expect(GROUP17C_NO_MAP.map((v) => v.param)).toEqual([3]);
  });

  it("points the verdict at its scorer dim", () => {
    expect(
      Object.fromEntries(GROUP17C_NO_MAP.map((v) => [v.param, v.dim])),
    ).toEqual({
      3: "dim_hoa_fees",
    });
    for (const v of GROUP17C_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE, never a faked fee)", () => {
    const reasons = GROUP17C_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).toContain("hinnang");
    expect(reasons).toContain("EI OLE");
    expect(reasons).toContain("Äriregistri");
    expect(reasons).not.toMatch(/keskmine haldustasu on|garanteeritud/i);
  });

  it("locks the snapshot evidence (drift guard: zero fee keys)", () => {
    expect(GROUP17C_EVIDENCE.feeKeysInSnapshot).toBe(0);
  });

  it("documents the evaluated-tag absence (registry source, not OSM)", () => {
    expect(GROUP17C_CONSIDERED_TAGS[3]).toContain("pole");
    expect(GROUP17C_CONSIDERED_TAGS[3]).toContain("Äriregister");
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP17C_HOOK).toContain("G17C-HOOK");
    expect(GROUP17C_HOOK).toContain("no shared-file wiring");
  });
});
