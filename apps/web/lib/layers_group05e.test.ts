// Group 5 plans-E layer tests (issue #165): p381 equestrian proxy
// ships; p365/p382/p384/p387 are documented no-map (no layer, scorer
// dims only).
import { describe, expect, it } from "vitest";
import {
  G05E_CAL,
  G05E_RASTER_FILE,
  G05E_VERDICTS,
  GROUP05E_ALL_PARAMS,
  GROUP05E_HOOK,
  GROUP05E_BONUS,
  GROUP05E_DECAY,
  GROUP05E_LAYER_IDS,
  GROUP05E_LAYERS,
  GROUP05E_NO_MAP_PARAMS,
  GROUP05E_PARAM_IDS,
  GROUP05E_TAGS,
  bonusSpecForGroup05E,
  group05eAreaScore,
  group05eMatchesContract,
  isGroup05ELayerId,
} from "./layers_group05e";

describe("group05e registry", () => {
  it("ships exactly one layer (p381); no-map params stay out", () => {
    expect(GROUP05E_LAYER_IDS).toEqual(["equestrian"]);
    expect(GROUP05E_LAYERS.map((l) => l.id)).toEqual(["equestrian"]);
    expect(GROUP05E_PARAM_IDS).toEqual({ equestrian: 381 });
    expect([...GROUP05E_ALL_PARAMS]).toEqual([365, 381, 382, 384, 387]);
    // p365/p382/p384/p387 must never gain a layer silently: the
    // shipped param set is exactly p381.
    const shipped = new Set(GROUP05E_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([381]);
    expect([...GROUP05E_NO_MAP_PARAMS]).toEqual([365, 382, 384, 387]);
  });

  it("labels the layer honestly (hinnang, never registry data)", () => {
    for (const def of GROUP05E_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP05E_LAYERS[0].source).toContain("KOV");
    expect(GROUP05E_LAYERS[0].source).toContain("ratsakogukonna");
  });

  it("documents the PBF-extract source tags (centres + arenas + stables + bridleways)", () => {
    expect(GROUP05E_TAGS.equestrian).toContain("horse_riding");
    expect(GROUP05E_TAGS.equestrian).toContain("equestrian");
    expect(GROUP05E_TAGS.equestrian).toContain("bridleway");
    expect(GROUP05E_TAGS.equestrian).toContain("stable");
    // A plain football pitch is not an arena: leisure=pitch alone
    // must stay out (the sport tag carries the meaning).
    expect(GROUP05E_TAGS.equestrian).not.toContain("pitch");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G05E_CAL.equestrian.half).toBe(1);
    expect(G05E_CAL.equestrian.sigma).toBe(0.3);
    expect(GROUP05E_DECAY.equestrian).toBe(0.3);
    expect(GROUP05E_BONUS.equestrian).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup05E("equestrian")).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup05E("parks")).toBeUndefined();
    expect(isGroup05ELayerId("equestrian")).toBe(true);
    expect(isGroup05ELayerId("parks")).toBe(false);
    expect(G05E_RASTER_FILE.equestrian).toBe("equestrian-walk-raster.json");
  });

  it("serves fallback demo points (near + far)", () => {
    for (const def of GROUP05E_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G05E_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [365, "no-map"],
      [381, "proxy"],
      [382, "no-map"],
      [384, "no-map"],
      [387, "no-map"],
    ]);
    expect(GROUP05E_HOOK).toContain("G05E-HOOK (#165)");
  });
});

describe("group05e math", () => {
  it("saturates facility counts like viewshed/moorage (one facility reads 50)", () => {
    expect(group05eAreaScore(0, 1)).toBe(0);
    expect(group05eAreaScore(1, 1)).toBe(50);
    expect(group05eAreaScore(3, 1)).toBe(75);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group05eMatchesContract("equestrian", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group05eMatchesContract("equestrian", { half: 2, sigma: 0.3 })).toBe(false);
    expect(group05eMatchesContract("equestrian", { half: 1, sigma: 0.5 })).toBe(false);
    expect(group05eMatchesContract("equestrian", null)).toBe(false);
  });
});
