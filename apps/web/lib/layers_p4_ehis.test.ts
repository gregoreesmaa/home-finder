import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor } from "./layers";
import {
  EHIS_EDGES_M,
  EHIS_LAYER_IDS,
  EHIS_RADIUS_M,
  ehisBandAt,
  isEhisLayerId,
} from "./layers_p4_ehis";

describe("ehis registry", () => {
  it("registers school/kindergarten/hobby slices with parameters4 labels", () => {
    expect([...EHIS_LAYER_IDS].sort()).toEqual([
      "ehis_hobby",
      "ehis_kindergarten",
      "ehis_school",
    ]);
    for (const id of EHIS_LAYER_IDS) {
      expect(isEhisLayerId(id)).toBe(true);
      expect(LAYERS.find((l) => l.id === id)?.paramIds).toEqual([]);
    }
    expect(LAYERS.find((l) => l.id === "ehis_school")?.paramLabel).toBe("P4-011");
  });

  it("band table matches the scorer PROX_BANDS (byte parity)", () => {
    expect(EHIS_RADIUS_M).toBe(2000);
    expect(EHIS_EDGES_M).toEqual([
      [500, 80],
      [1000, 65],
      [2000, 50],
    ]);
  });

  it("bonus spec reuses the dbands distance kernel (no new spec kind)", () => {
    expect(bonusSpecFor("ehis_school")).toEqual({
      kind: "dbands",
      radiusM: 2000,
      edges: [
        [500, 80],
        [1000, 65],
        [2000, 50],
      ],
    });
  });

  it("maps distance to band, NULL beyond the outer edge", () => {
    expect(ehisBandAt(100)).toBe(80);
    expect(ehisBandAt(500)).toBe(80);
    expect(ehisBandAt(501)).toBe(65);
    expect(ehisBandAt(1500)).toBe(50);
    expect(ehisBandAt(2000)).toBe(50);
    expect(ehisBandAt(2001)).toBeNull();
  });
});
