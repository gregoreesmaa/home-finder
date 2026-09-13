// Group 3 cadastre-D layer tests (issue #154): p332 moorage proxy +
// p340 shoredist ship; p331/p337/p339 are documented no-map (no layer,
// scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G03D_CAL,
  GROUP03D_HOOK,
  G03D_RASTER_FILE,
  G03D_VERDICTS,
  GROUP03D_ALL_PARAMS,
  GROUP03D_BONUS,
  GROUP03D_DECAY,
  GROUP03D_LAYER_IDS,
  GROUP03D_LAYERS,
  GROUP03D_NO_MAP_PARAMS,
  GROUP03D_PARAM_IDS,
  GROUP03D_TAGS,
  bonusSpecForGroup03D,
  group03dAreaScore,
  group03dMatchesContract,
  group03dQuietFromHalf,
  group03dQuietnessAt,
  isGroup03DLayerId,
} from "./layers_group03d";

describe("group03d registry", () => {
  it("ships exactly two layers (p332 + p340); no-map params stay out", () => {
    expect(GROUP03D_LAYER_IDS).toEqual(["moorage", "shoredist"]);
    expect(GROUP03D_LAYERS.map((l) => l.id)).toEqual(["moorage", "shoredist"]);
    expect(GROUP03D_PARAM_IDS).toEqual({ moorage: 332, shoredist: 340 });
    expect([...GROUP03D_ALL_PARAMS]).toEqual([331, 332, 337, 339, 340]);
    // p331/p337/p339 must never gain a layer silently: the shipped
    // param set is exactly p332 + p340.
    const shipped = new Set(GROUP03D_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([332, 340]);
    expect([...GROUP03D_NO_MAP_PARAMS]).toEqual([331, 337, 339]);
  });

  it("labels both layers honestly (hinnang, never measured)", () => {
    for (const def of GROUP03D_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP03D_LAYERS[0].source).toContain("lubade register");
    expect(GROUP03D_LAYERS[1].source).toContain("ehituskeeluotsus");
  });

  it("documents the PBF-extract source tags (marina/moorings + shore)", () => {
    expect(GROUP03D_TAGS.moorage).toContain("marina");
    expect(GROUP03D_TAGS.moorage).toContain("seamark:type");
    expect(GROUP03D_TAGS.moorage).not.toContain("mooring=no");
    expect(GROUP03D_TAGS.shoredist).toContain("coastline");
    expect(GROUP03D_TAGS.shoredist).toContain("natural");
    // Shore stays distinct from p50 drainage: no rivers, no wetlands.
    expect(GROUP03D_TAGS.shoredist).not.toContain("waterway");
    expect(GROUP03D_TAGS.shoredist).not.toContain("wetland");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G03D_CAL.moorage.half).toBe(1);
    expect(G03D_CAL.moorage.sigma).toBe(0.3);
    expect(G03D_CAL.shoredist.halfM).toBe(100);
    expect(G03D_CAL.shoredist.sigma).toBe(0.3);
    expect(GROUP03D_DECAY.moorage).toBe(0.3);
    expect(GROUP03D_DECAY.shoredist).toBe(0.3);
    expect(GROUP03D_BONUS.moorage).toEqual({ kind: "area", half: 1 });
    expect(GROUP03D_BONUS.shoredist).toEqual({ kind: "quiet", halfM: 100 });
    expect(bonusSpecForGroup03D("moorage")).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup03D("shoredist")).toEqual({ kind: "quiet", halfM: 100 });
    expect(bonusSpecForGroup03D("parks")).toBeUndefined();
    expect(isGroup03DLayerId("moorage")).toBe(true);
    expect(isGroup03DLayerId("shoredist")).toBe(true);
    expect(isGroup03DLayerId("parks")).toBe(false);
    expect(G03D_RASTER_FILE.moorage).toBe("moorage-walk-raster.json");
    expect(G03D_RASTER_FILE.shoredist).toBe("shoredist-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP03D_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G03D_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [331, "no-map"],
      [332, "proxy"],
      [337, "no-map"],
      [339, "no-map"],
      [340, "real"],
    ]);
    expect(GROUP03D_HOOK).toContain("G03D-HOOK (#154)");
  });
});

describe("group03d math", () => {
  it("reads 0 at the shore, 50 at halfM, ~100 when far inland", () => {
    expect(group03dQuietFromHalf(0, 100)).toBe(0);
    expect(group03dQuietFromHalf(100, 100)).toBe(50);
    expect(group03dQuietFromHalf(Infinity, 100)).toBe(100);
    expect(group03dQuietFromHalf(1e9, 100)).toBeGreaterThan(99.9);
  });

  it("scores nearest-shore distance (Kalamaja probe: ~300 m -> 75)", () => {
    const pts = [{ lat: 59.448, lon: 24.738 }];
    expect(group03dQuietnessAt(59.448, 24.738, pts)).toBe(0);
    // 300 m south of the source reads 100*300/400 = 75.
    const q = group03dQuietnessAt(59.448 - 300 / 110570, 24.738, pts);
    expect(q).toBe(75);
    expect(group03dQuietnessAt(59.448, 24.738, [])).toBeNull();
  });

  it("saturates mooring counts (one marina reads 50 at half 1)", () => {
    expect(group03dAreaScore(0, 1)).toBe(0);
    expect(group03dAreaScore(1, 1)).toBe(50);
    expect(group03dAreaScore(3, 1)).toBe(75);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group03dMatchesContract("shoredist", { half: 100, sigma: 0.3 })).toBe(true);
    expect(group03dMatchesContract("shoredist", { half: 300, sigma: 0.3 })).toBe(false);
    expect(group03dMatchesContract("shoredist", { half: 100, sigma: 0.5 })).toBe(false);
    expect(group03dMatchesContract("moorage", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group03dMatchesContract("moorage", { half: 2, sigma: 0.3 })).toBe(false);
    expect(group03dMatchesContract("moorage", null)).toBe(false);
  });
});
