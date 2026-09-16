import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor } from "./layers";
import {
  MEDRE_EDGES_M,
  MEDRE_LAYER_IDS,
  MEDRE_RADIUS_M,
  isMedreLayerId,
  medreBandAt,
} from "./layers_p4_medre";

describe("medre registry", () => {
  it("registers gp/clinic slices with parameters4 labels", () => {
    expect([...MEDRE_LAYER_IDS].sort()).toEqual(["medre_clinic", "medre_gp"]);
    for (const id of MEDRE_LAYER_IDS) {
      expect(isMedreLayerId(id)).toBe(true);
      expect(LAYERS.find((l) => l.id === id)?.paramIds).toEqual([]);
    }
    expect(LAYERS.find((l) => l.id === "medre_gp")?.paramLabel).toBe("P4-011");
  });

  it("band table matches the scorer PROX_BANDS (byte parity)", () => {
    expect(MEDRE_RADIUS_M).toBe(2000);
    expect(MEDRE_EDGES_M).toEqual([
      [500, 80],
      [1000, 65],
      [2000, 50],
    ]);
  });

  it("bonus spec reuses the dbands distance kernel (no new spec kind)", () => {
    expect(bonusSpecFor("medre_gp")).toEqual({
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
    expect(medreBandAt(100)).toBe(80);
    expect(medreBandAt(500)).toBe(80);
    expect(medreBandAt(501)).toBe(65);
    expect(medreBandAt(1500)).toBe(50);
    expect(medreBandAt(2000)).toBe(50);
    expect(medreBandAt(2001)).toBeNull();
  });

  it("ships empty fallback by honesty (no joined points exist yet)", async () => {
    const m = await import("./layers_p4_medre");
    for (const def of m.MEDRE_LAYERS) {
      expect(def.fallbackPoints).toEqual([]);
    }
  });
});
