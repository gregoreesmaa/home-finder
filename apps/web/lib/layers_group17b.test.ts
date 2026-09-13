// Group 17 municipal-services-B layer tests (issue #178): p469 lawncare
// proxy ships; p463/p464/p465 are documented no-map (no layer, scorer
// dims only).
import { describe, expect, it } from "vitest";
import {
  G17B_CAL,
  G17B_RASTER_FILE,
  G17B_VERDICTS,
  GROUP17B_HOOK,
  GROUP17B_ALL_PARAMS,
  GROUP17B_BONUS,
  GROUP17B_DECAY,
  GROUP17B_LAYER_IDS,
  GROUP17B_LAYERS,
  GROUP17B_NO_MAP_PARAMS,
  GROUP17B_PARAM_IDS,
  GROUP17B_TAGS,
  bonusSpecForGroup17B,
  group17bAreaScore,
  group17bMatchesContract,
  isGroup17BLayerId,
} from "./layers_group17b";

describe("group17b registry", () => {
  it("ships exactly one layer (p469); no-map params stay out", () => {
    expect(GROUP17B_LAYER_IDS).toEqual(["lawncare"]);
    expect(GROUP17B_LAYERS.map((l) => l.id)).toEqual(["lawncare"]);
    expect(GROUP17B_PARAM_IDS).toEqual({ lawncare: 469 });
    expect([...GROUP17B_ALL_PARAMS]).toEqual([463, 464, 465, 469]);
    // p463/p464/p465 must never gain a layer silently: the shipped
    // param set is exactly p469.
    const shipped = new Set(GROUP17B_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([469]);
    expect([...GROUP17B_NO_MAP_PARAMS]).toEqual([463, 464, 465]);
  });

  it("labels all layers honestly (hinnang, never registry data)", () => {
    for (const def of GROUP17B_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP17B_LAYERS[0].source).toContain("muruala");
    expect(GROUP17B_LAYERS[0].source).toContain("aasa");
    expect(GROUP17B_LAYERS[0].source).toContain("kontrollregister");
  });

  it("documents the PBF-extract source tags (mown grass only, no meadow)", () => {
    expect(GROUP17B_TAGS.lawncare).toContain("grass");
    expect(GROUP17B_TAGS.lawncare).toContain("landuse");
    // Unmown meadows are out by design (a meadow is not a lawn).
    expect(GROUP17B_TAGS.lawncare).not.toContain("meadow");
    // No footway source: footway density already scores as pedinfra.
    expect(GROUP17B_TAGS.lawncare).not.toContain("highway");
    expect(GROUP17B_TAGS.lawncare).not.toContain("footway");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G17B_CAL.lawncare.half).toBe(20);
    expect(G17B_CAL.lawncare.sigma).toBe(0.3);
    expect(GROUP17B_DECAY.lawncare).toBe(0.3);
    expect(GROUP17B_BONUS.lawncare).toEqual({ kind: "area", half: 20 });
    expect(bonusSpecForGroup17B("lawncare")).toEqual({ kind: "area", half: 20 });
    expect(bonusSpecForGroup17B("parks")).toBeUndefined();
    expect(isGroup17BLayerId("lawncare")).toBe(true);
    expect(isGroup17BLayerId("parks")).toBe(false);
    expect(G17B_RASTER_FILE.lawncare).toBe("lawncare-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP17B_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G17B_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [463, "no-map"],
      [464, "no-map"],
      [465, "no-map"],
      [469, "proxy"],
    ]);
    expect(GROUP17B_HOOK).toContain("G17B-HOOK (#178)");
  });
});

describe("group17b math", () => {
  it("saturates lawn counts like viewshed/moorage/G17A (half reads 50)", () => {
    expect(group17bAreaScore(0, 20)).toBe(0);
    expect(group17bAreaScore(20, 20)).toBe(50);
    expect(group17bAreaScore(60, 20)).toBe(75);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group17bMatchesContract("lawncare", { half: 20, sigma: 0.3 })).toBe(true);
    expect(group17bMatchesContract("lawncare", { half: 1, sigma: 0.3 })).toBe(false);
    expect(group17bMatchesContract("lawncare", { half: 20, sigma: 0.5 })).toBe(false);
    expect(group17bMatchesContract("lawncare", null)).toBe(false);
  });
});
