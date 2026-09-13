// Group 1 listing-portal verdict tests, batch A (issue #202):
// p1/p5/p22/p23/p24/p25/p26/p27/p28/p32/p36/p37/p39/p92/p93/p94/
// p99/p109/p110/p119 are ALL documented no-map (OTA PR #131 precedent)
// with NULL scorer dims in services/scoring/dims_group01a.py.
// Hermetic: no network, no snapshot.
import { describe, expect, it } from "vitest";
import {
  GROUP01A_ALL_PARAMS,
  GROUP01A_CONSIDERED_TAGS,
  GROUP01A_EVIDENCE,
  GROUP01A_HOOK,
  GROUP01A_NO_MAP,
  GROUP01A_SHIPPED_PARAMS,
} from "./layers_group01a";

const OWNED = [
  1, 5, 22, 23, 24, 25, 26, 27, 28, 32, 36, 37, 39, 92, 93, 94, 99, 109,
  110, 119,
] as const;

describe("group01a verdict registry", () => {
  it("owns exactly the twenty G1-A params and ships zero layers", () => {
    expect([...GROUP01A_ALL_PARAMS]).toEqual([...OWNED]);
    expect([...GROUP01A_SHIPPED_PARAMS]).toEqual([]);
    // Every owned param has exactly one documented verdict.
    expect(GROUP01A_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([
      ...OWNED,
    ]);
  });

  it("points every verdict at its scorer dim", () => {
    expect(Object.fromEntries(GROUP01A_NO_MAP.map((v) => [v.param, v.dim]))).toEqual({
      1: "dim_purchase_price",
      5: "dim_utility_costs",
      22: "dim_bedrooms",
      23: "dim_bathrooms",
      24: "dim_floor_plan_flow",
      25: "dim_kitchen",
      26: "dim_workspace",
      27: "dim_storage",
      28: "dim_parking",
      32: "dim_move_in_readiness",
      36: "dim_finishes",
      37: "dim_outdoor_living",
      39: "dim_smart_home",
      92: "dim_primary_suite",
      93: "dim_laundry",
      94: "dim_mudroom",
      99: "dim_flex_space",
      109: "dim_gear_storage",
      110: "dim_outdoor_kitchen",
      119: "dim_backup_heating",
    });
    for (const v of GROUP01A_NO_MAP) {
      expect(v.reason.length).toBeGreaterThan(40);
      expect(v.nearestMap.length).toBeGreaterThan(0);
    }
  });

  it("states honesty in Estonian (hinnang / EI OLE on every NULL verdict)", () => {
    for (const v of GROUP01A_NO_MAP) {
      expect(v.reason).toContain("hinnang");
      expect(v.reason).toContain("EI OLE");
    }
    const reasons = GROUP01A_NO_MAP.map((v) => v.reason).join(" ");
    expect(reasons).not.toContain("mõõdetud");
    expect(reasons).not.toMatch(/garanteeritud/i);
  });

  it("locks the structural evidence counts (drift guard)", () => {
    expect(GROUP01A_EVIDENCE.groupTotal).toBe(40);
    expect(GROUP01A_EVIDENCE.batchOwns).toBe(20);
    // Per-listing facts have no snapshot area signal by construction.
    expect(GROUP01A_EVIDENCE.snapshotSignals).toBe(0);
  });

  it("documents the rejected proxy for parking, absence for the rest", () => {
    expect(GROUP01A_CONSIDERED_TAGS[28]).toContain("tagasi lükatud");
    for (const p of OWNED) {
      expect(GROUP01A_CONSIDERED_TAGS[p]).toContain("puudub");
    }
  });

  it("marks the no-wiring hook contract", () => {
    expect(GROUP01A_HOOK).toContain("G01A-HOOK");
    expect(GROUP01A_HOOK).toContain("no shared-file wiring");
  });
});
