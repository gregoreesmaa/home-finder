import { describe, expect, it } from "vitest";
import { LAYERS, bonusSpecFor } from "./layers";
import {
  SPORT_EDGES_M,
  SPORT_LAYER_IDS,
  SPORT_RADIUS_M,
  isSportLayerId,
  sportBandAt,
} from "./layers_p4_sport";

describe("sport registry", () => {
  it("registers pool/hall/field slices with parameters4 labels", () => {
    expect([...SPORT_LAYER_IDS].sort()).toEqual(["sport_field", "sport_hall", "sport_pool"]);
    for (const id of SPORT_LAYER_IDS) {
      expect(isSportLayerId(id)).toBe(true);
      expect(LAYERS.find((l) => l.id === id)?.paramIds).toEqual([]);
    }
    expect(LAYERS.find((l) => l.id === "sport_hall")?.paramLabel).toBe("P4-048");
  });

  it("band table matches the scorer PROX_BANDS (byte parity)", () => {
    expect(SPORT_RADIUS_M).toBe(2000);
    expect(SPORT_EDGES_M).toEqual([
      [500, 80],
      [1000, 65],
      [2000, 50],
    ]);
  });

  it("bonus spec is nearest-venue distance bands", () => {
    expect(bonusSpecFor("sport_hall")).toEqual({
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
    expect(sportBandAt(100)).toBe(80);
    expect(sportBandAt(500)).toBe(80);
    expect(sportBandAt(501)).toBe(65);
    expect(sportBandAt(1500)).toBe(50);
    expect(sportBandAt(2000)).toBe(50);
    expect(sportBandAt(2001)).toBeNull();
  });
});
