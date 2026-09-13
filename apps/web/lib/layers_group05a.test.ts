// Group 5 plans-A layer tests (issue #161): p42 ehitus proxy +
// p44 korterstock proxy ship; p45/p47/p74 are documented no-map
// (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G05A_CAL,
  G05A_RASTER_FILE,
  G05A_VERDICTS,
  GROUP05A_ALL_PARAMS,
  GROUP05A_BONUS,
  GROUP05A_DECAY,
  GROUP05A_HOOK,
  GROUP05A_LAYER_IDS,
  GROUP05A_LAYERS,
  GROUP05A_NO_MAP_PARAMS,
  GROUP05A_PARAM_IDS,
  GROUP05A_TAGS,
  bonusSpecForGroup05A,
  group05aAreaScore,
  group05aMatchesContract,
  isGroup05ALayerId,
} from "./layers_group05a";

describe("group05a registry", () => {
  it("ships exactly two layers (p42 + p44); no-map params stay out", () => {
    expect(GROUP05A_LAYER_IDS).toEqual(["ehitus", "korterstock"]);
    expect(GROUP05A_LAYERS.map((l) => l.id)).toEqual(["ehitus", "korterstock"]);
    expect(GROUP05A_PARAM_IDS).toEqual({ ehitus: 42, korterstock: 44 });
    expect([...GROUP05A_ALL_PARAMS]).toEqual([42, 44, 45, 47, 74]);
    // p45/p47/p74 must never gain a layer silently: the shipped
    // param set is exactly p42 + p44.
    const shipped = new Set(GROUP05A_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([42, 44]);
    expect([...GROUP05A_NO_MAP_PARAMS]).toEqual([45, 47, 74]);
  });

  it("labels both layers honestly (hinnang, never measured)", () => {
    for (const def of GROUP05A_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP05A_LAYERS[0].source).toContain("PLANK");
    expect(GROUP05A_LAYERS[1].source).toContain("üüriregister");
  });

  it("documents the PBF-extract source tags (construction + apartments)", () => {
    expect(GROUP05A_TAGS.ehitus).toContain("construction");
    expect(GROUP05A_TAGS.ehitus).toContain("landuse");
    expect(GROUP05A_TAGS.korterstock).toContain("apartments");
    expect(GROUP05A_TAGS.korterstock).toContain("building");
    // korterstock never re-skins p386 rentbleed: no student tags.
    expect(GROUP05A_TAGS.korterstock).not.toContain("dormitory");
    expect(GROUP05A_TAGS.korterstock).not.toContain("university");
    expect(GROUP05A_TAGS.korterstock).not.toContain("college");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G05A_CAL.ehitus.half).toBe(1);
    expect(G05A_CAL.ehitus.sigma).toBe(0.3);
    expect(G05A_CAL.korterstock.half).toBe(15);
    expect(G05A_CAL.korterstock.sigma).toBe(0.3);
    expect(GROUP05A_DECAY.ehitus).toBe(0.3);
    expect(GROUP05A_DECAY.korterstock).toBe(0.3);
    expect(GROUP05A_BONUS.ehitus).toEqual({ kind: "area", half: 1 });
    expect(GROUP05A_BONUS.korterstock).toEqual({ kind: "area", half: 15 });
    expect(bonusSpecForGroup05A("ehitus")).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup05A("korterstock")).toEqual({ kind: "area", half: 15 });
    expect(bonusSpecForGroup05A("parks")).toBeUndefined();
    expect(isGroup05ALayerId("ehitus")).toBe(true);
    expect(isGroup05ALayerId("korterstock")).toBe(true);
    expect(isGroup05ALayerId("parks")).toBe(false);
    expect(G05A_RASTER_FILE.ehitus).toBe("ehitus-walk-raster.json");
    expect(G05A_RASTER_FILE.korterstock).toBe("korterstock-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP05A_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G05A_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [42, "proxy"],
      [44, "proxy"],
      [45, "no-map"],
      [47, "no-map"],
      [74, "no-map"],
    ]);
    expect(GROUP05A_HOOK).toContain("G05A-HOOK (#161)");
  });
});

describe("group05a math", () => {
  it("saturates area counts: 0 -> 0, half -> 50, far above half -> ~100", () => {
    expect(group05aAreaScore(0, 1)).toBe(0);
    expect(group05aAreaScore(1, 1)).toBe(50);
    expect(group05aAreaScore(15, 15)).toBe(50);
    expect(group05aAreaScore(1e9, 15)).toBeGreaterThan(99.9);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group05aMatchesContract("ehitus", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group05aMatchesContract("ehitus", { half: 15, sigma: 0.3 })).toBe(false);
    expect(group05aMatchesContract("ehitus", { half: 1, sigma: 0.5 })).toBe(false);
    expect(group05aMatchesContract("korterstock", { half: 15, sigma: 0.3 })).toBe(true);
    expect(group05aMatchesContract("korterstock", { half: 1, sigma: 0.3 })).toBe(false);
    expect(group05aMatchesContract("ehitus", null)).toBe(false);
  });
});
