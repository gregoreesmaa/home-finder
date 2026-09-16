import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor } from "./layers";
import {
  OHUSEIRE_EDGES_M,
  OHUSEIRE_RADIUS_M,
  isOhuseireLayerId,
  ohuseireBandAt,
} from "./layers_p4_ohuseire";

describe("ohuseire registry", () => {
  it("registers the thin station layer with parameters4 label", () => {
    expect(isOhuseireLayerId("ohuseire")).toBe(true);
    expect(LAYERS.find((l) => l.id === "ohuseire")?.paramIds).toEqual([]);
    expect(LAYERS.find((l) => l.id === "ohuseire")?.paramLabel).toBe("P4-031");
  });

  it("band table is the flat district band (scorer 1-station leg)", () => {
    expect(OHUSEIRE_RADIUS_M).toBe(2000);
    expect(OHUSEIRE_EDGES_M).toEqual([[2000, 60]]);
  });

  it("bonus spec reuses the dbands distance kernel (no new spec kind)", () => {
    expect(bonusSpecFor("ohuseire")).toEqual({
      kind: "dbands",
      radiusM: 2000,
      edges: [[2000, 60]],
    });
  });

  it("maps any in-radius distance to 60, NULL beyond", () => {
    expect(ohuseireBandAt(100)).toBe(60);
    expect(ohuseireBandAt(2000)).toBe(60);
    expect(ohuseireBandAt(2001)).toBeNull();
  });
});
