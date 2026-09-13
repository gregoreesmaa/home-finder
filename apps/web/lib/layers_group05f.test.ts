// Group 5 plans-F layer tests (issue #166): p485 upcycle proxy ships;
// p389 is a documented no-map (no layer, scorer dim only).
import { describe, expect, it } from "vitest";
import {
  G05F_CAL,
  G05F_RASTER_FILE,
  G05F_VERDICTS,
  GROUP05F_ALL_PARAMS,
  GROUP05F_HOOK,
  GROUP05F_BONUS,
  GROUP05F_DECAY,
  GROUP05F_LAYER_IDS,
  GROUP05F_LAYERS,
  GROUP05F_NO_MAP_PARAMS,
  GROUP05F_PARAM_IDS,
  GROUP05F_TAGS,
  bonusSpecForGroup05F,
  group05fAreaScore,
  group05fMatchesContract,
  isGroup05FLayerId,
} from "./layers_group05f";

describe("group05f registry", () => {
  it("ships exactly one layer (p485); the designation param stays out", () => {
    expect(GROUP05F_LAYER_IDS).toEqual(["upcycle"]);
    expect(GROUP05F_LAYERS.map((l) => l.id)).toEqual(["upcycle"]);
    expect(GROUP05F_PARAM_IDS).toEqual({ upcycle: 485 });
    expect([...GROUP05F_ALL_PARAMS]).toEqual([389, 485]);
    // p389 must never gain a layer silently: the shipped
    // param set is exactly p485.
    const shipped = new Set(GROUP05F_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([485]);
    expect([...GROUP05F_NO_MAP_PARAMS]).toEqual([389]);
  });

  it("labels the layer honestly (hinnang, never a rezoning ruling)", () => {
    for (const def of GROUP05F_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("KOV");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP05F_LAYERS[0].source).toContain("punkrid");
  });

  it("documents the PBF-extract source tags (lifecycle keys, way-mapped stock)", () => {
    expect(GROUP05F_TAGS.upcycle).toContain("abandoned");
    expect(GROUP05F_TAGS.upcycle).toContain("disused");
    // Rezoning stock, not nuisance: no industrial/brownfield/quarry
    // (industprox G07 + brownsoil G07B + p408 lowspec stay un-skinned).
    expect(GROUP05F_TAGS.upcycle).not.toContain("industrial");
    expect(GROUP05F_TAGS.upcycle).not.toContain("brownfield");
    expect(GROUP05F_TAGS.upcycle).not.toContain("quarry");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G05F_CAL.upcycle.half).toBe(2);
    expect(G05F_CAL.upcycle.sigma).toBe(0.3);
    expect(GROUP05F_DECAY.upcycle).toBe(0.3);
    expect(GROUP05F_BONUS.upcycle).toEqual({ kind: "area", half: 2 });
    expect(bonusSpecForGroup05F("upcycle")).toEqual({ kind: "area", half: 2 });
    expect(bonusSpecForGroup05F("parks")).toBeUndefined();
    expect(isGroup05FLayerId("upcycle")).toBe(true);
    expect(isGroup05FLayerId("parks")).toBe(false);
    expect(G05F_RASTER_FILE.upcycle).toBe("upcycle-walk-raster.json");
  });

  it("serves fallback demo points (near + far)", () => {
    for (const def of GROUP05F_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G05F_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [389, "no-map"],
      [485, "proxy"],
    ]);
    expect(GROUP05F_HOOK).toContain("G05F-HOOK (#166)");
  });
});

describe("group05f math", () => {
  it("saturates stock counts like buildout (two buildings read 50)", () => {
    expect(group05fAreaScore(0, 2)).toBe(0);
    expect(group05fAreaScore(2, 2)).toBe(50);
    expect(group05fAreaScore(6, 2)).toBe(75);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group05fMatchesContract("upcycle", { half: 2, sigma: 0.3 })).toBe(true);
    expect(group05fMatchesContract("upcycle", { half: 1, sigma: 0.3 })).toBe(false);
    expect(group05fMatchesContract("upcycle", { half: 2, sigma: 0.5 })).toBe(false);
    expect(group05fMatchesContract("upcycle", null)).toBe(false);
  });
});
