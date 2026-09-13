import { describe, expect, it } from "vitest";

import {
  G07C_BONUS,
  G07C_CAL,
  G07C_DECAY_KM,
  G07C_LAYERS,
  G07C_LAYER_IDS,
  G07C_NO_MAP,
  G07C_PARAM_IDS,
  G07C_RASTER_FILE,
  G07C_TAGS,
  g07cBonusSpec,
  g07cHavKm,
  g07cMatchesContract,
  g07cQuietFromHalf,
  g07cScoreAt,
  isG07CLayerId,
} from "./layers_group07c";

describe("G07C registry (issue #142)", () => {
  it("ships exactly the p257 layer", () => {
    expect(G07C_LAYER_IDS).toEqual(["vectorhabitat"]);
    expect(G07C_LAYERS.map((l) => l.id)).toEqual(["vectorhabitat"]);
    expect(G07C_PARAM_IDS.vectorhabitat).toEqual([257]);
    expect(G07C_LAYERS[0].paramIds).toEqual([257]);
  });

  it("labels the proxy honestly (proksi/hinnang, never surveillance claims)", () => {
    const def = G07C_LAYERS[0];
    expect(def.title).toContain("proksi");
    expect(def.title).toContain("hinnang");
    expect(def.badLabel).toContain("MITTE seireandmed");
    expect(def.source).toContain("PROKSI");
    expect(def.goodLabel.length).toBeGreaterThan(0);
    expect(def.fallbackPoints.length).toBeGreaterThan(0);
    for (const p of def.fallbackPoints) {
      expect(Number.isFinite(p.lat)).toBe(true);
      expect(Number.isFinite(p.lon)).toBe(true);
    }
  });

  it("documents every no-map param (260/316/401/402) with a reason", () => {
    expect(Object.keys(G07C_NO_MAP).map(Number).sort()).toEqual([260, 316, 401, 402]);
    for (const reason of Object.values(G07C_NO_MAP)) {
      expect(reason.length).toBeGreaterThan(10);
    }
  });

  it("queries habitat tags offline (nwr/, no live fetch)", () => {
    const q = G07C_TAGS.vectorhabitat;
    expect(q).toContain("nwr[");
    for (const tag of ["wood", "scrub", "heath", "wetland", "forest", "meadow"]) {
      expect(q).toContain(tag);
    }
  });

  it("names raster masters without metro (fake precision refused)", () => {
    expect(G07C_RASTER_FILE.vectorhabitat).toBe("vectorhabitat-walk-raster.json");
  });

  it("locks calibration (TS side of the pytest drift check)", () => {
    expect(G07C_CAL.vectorhabitat).toEqual({ halfM: 300, sigma: 0.3 });
    expect(G07C_DECAY_KM.vectorhabitat).toBe(0.3);
    expect(G07C_BONUS.vectorhabitat).toEqual({ kind: "quiet", halfM: 300 });
    expect(g07cBonusSpec("vectorhabitat")).toEqual({ kind: "quiet", halfM: 300 });
  });

  it("guards the batch id", () => {
    expect(isG07CLayerId("vectorhabitat")).toBe(true);
    expect(isG07CLayerId("parks")).toBe(false);
  });
});

describe("G07C quiet math", () => {
  it("scores 0 on the source, 50 at halfM, ~100 far away", () => {
    expect(g07cQuietFromHalf(0, 300)).toBe(0);
    expect(g07cQuietFromHalf(300, 300)).toBe(50);
    expect(g07cQuietFromHalf(30000, 300)).toBeGreaterThanOrEqual(99);
  });

  it("treats non-finite distance as calm, never as data", () => {
    expect(g07cQuietFromHalf(Infinity, 300)).toBe(100);
  });

  it("uses Tallinn-scale kilometres", () => {
    // 0.01° lon at 59N ≈ 573 m.
    expect(g07cHavKm(24.74, 59.43, 24.75, 59.43)).toBeCloseTo(0.573, 2);
  });

  it("scores null with no points, red at the edge, green far away", () => {
    const pts = [{ lat: 59.3862, lon: 24.6611 }];
    expect(g07cScoreAt("vectorhabitat", 59.43, 24.74, [])).toBeNull();
    expect(g07cScoreAt("vectorhabitat", 59.3862, 24.6611, pts)).toBe(0);
    expect(g07cScoreAt("vectorhabitat", 59.4374, 24.7454, pts)).toBeGreaterThan(80);
  });

  it("matches the raster contract on halfM + sigma only", () => {
    expect(g07cMatchesContract({ half: 300, sigma: 0.3 }, "vectorhabitat")).toBe(true);
    expect(g07cMatchesContract({ half: 500, sigma: 0.3 }, "vectorhabitat")).toBe(false);
    expect(g07cMatchesContract({ half: 300, sigma: 0.5 }, "vectorhabitat")).toBe(false);
    expect(g07cMatchesContract(null, "vectorhabitat")).toBe(false);
  });
});
