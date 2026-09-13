// Group 5 plans-B layer tests (issue #162): p106 gardens proxy +
// p146 buildout proxy ship; p107/p186/p188 are documented no-map
// (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G05B_CAL,
  G05B_RASTER_FILE,
  G05B_VERDICTS,
  GROUP05B_ALL_PARAMS,
  GROUP05B_BONUS,
  GROUP05B_DECAY,
  GROUP05B_HOOK,
  GROUP05B_LAYER_IDS,
  GROUP05B_LAYERS,
  GROUP05B_NO_MAP_PARAMS,
  GROUP05B_PARAM_IDS,
  GROUP05B_TAGS,
  bonusSpecForGroup05B,
  group05bAreaScore,
  group05bMatchesContract,
  isGroup05BLayerId,
} from "./layers_group05b";

describe("group05b registry", () => {
  it("ships exactly two layers (p106 + p146); no-map params stay out", () => {
    expect(GROUP05B_LAYER_IDS).toEqual(["gardens", "buildout"]);
    expect(GROUP05B_LAYERS.map((l) => l.id)).toEqual(["gardens", "buildout"]);
    expect(GROUP05B_PARAM_IDS).toEqual({ gardens: 106, buildout: 146 });
    expect([...GROUP05B_ALL_PARAMS]).toEqual([106, 107, 146, 186, 188]);
    // p107/p186/p188 must never gain a layer silently: the shipped
    // param set is exactly p106 + p146.
    const shipped = new Set(GROUP05B_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([106, 146]);
    expect([...GROUP05B_NO_MAP_PARAMS]).toEqual([107, 186, 188]);
  });

  it("labels both layers honestly (hinnang, never measured)", () => {
    for (const def of GROUP05B_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP05B_LAYERS[0].source).toContain("mullauuring");
    expect(GROUP05B_LAYERS[1].source).toContain("sihttihedus");
  });

  it("documents the PBF-extract source tags (gardens + construction)", () => {
    expect(GROUP05B_TAGS.gardens).toContain("leisure");
    expect(GROUP05B_TAGS.gardens).toContain("garden");
    expect(GROUP05B_TAGS.gardens).toContain("allotments");
    expect(GROUP05B_TAGS.buildout).toContain("construction");
    // Gardens exclude private backyards by predicate (see keep_garden):
    // the fragment stays a plain source-tags query like siblings.
    expect(GROUP05B_TAGS.gardens).not.toContain("residential");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G05B_CAL.gardens.half).toBe(1);
    expect(G05B_CAL.gardens.sigma).toBe(0.3);
    expect(G05B_CAL.buildout.half).toBe(2);
    expect(G05B_CAL.buildout.sigma).toBe(0.3);
    expect(GROUP05B_DECAY.gardens).toBe(0.3);
    expect(GROUP05B_DECAY.buildout).toBe(0.3);
    expect(GROUP05B_BONUS.gardens).toEqual({ kind: "area", half: 1 });
    expect(GROUP05B_BONUS.buildout).toEqual({ kind: "area", half: 2 });
    expect(bonusSpecForGroup05B("gardens")).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup05B("buildout")).toEqual({ kind: "area", half: 2 });
    expect(bonusSpecForGroup05B("parks")).toBeUndefined();
    expect(isGroup05BLayerId("gardens")).toBe(true);
    expect(isGroup05BLayerId("buildout")).toBe(true);
    expect(isGroup05BLayerId("parks")).toBe(false);
    expect(G05B_RASTER_FILE.gardens).toBe("gardens-walk-raster.json");
    expect(G05B_RASTER_FILE.buildout).toBe("buildout-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP05B_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G05B_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [106, "proxy"],
      [107, "no-map"],
      [146, "proxy"],
      [186, "no-map"],
      [188, "no-map"],
    ]);
    expect(GROUP05B_HOOK).toContain("G05B-HOOK (#162)");
  });
});

describe("group05b math", () => {
  it("saturates facility counts (one garden reads 50, two sites read 50)", () => {
    expect(group05bAreaScore(0, 1)).toBe(0);
    expect(group05bAreaScore(1, 1)).toBe(50);
    expect(group05bAreaScore(2, 2)).toBe(50);
    expect(group05bAreaScore(1e9, 1)).toBeLessThanOrEqual(100);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group05bMatchesContract("gardens", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group05bMatchesContract("gardens", { half: 2, sigma: 0.3 })).toBe(false);
    expect(group05bMatchesContract("gardens", { half: 1, sigma: 0.5 })).toBe(false);
    expect(group05bMatchesContract("buildout", { half: 2, sigma: 0.3 })).toBe(true);
    expect(group05bMatchesContract("buildout", { half: 1, sigma: 0.3 })).toBe(false);
    expect(group05bMatchesContract("gardens", null)).toBe(false);
  });
});
