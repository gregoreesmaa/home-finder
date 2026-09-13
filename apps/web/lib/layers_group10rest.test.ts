// Group 10 utilities-rest layer tests (issue #171): p215 skyview
// proxy ships; p491 is a documented no-map (no layer, scorer dim only).
import { describe, expect, it } from "vitest";
import {
  G10R_CAL,
  G10R_RASTER_FILE,
  G10R_VERDICTS,
  GROUP10REST_ALL_PARAMS,
  GROUP10REST_BONUS,
  GROUP10REST_DECAY,
  GROUP10REST_HOOK,
  GROUP10REST_LAYER_IDS,
  GROUP10REST_LAYERS,
  GROUP10REST_NO_MAP_PARAMS,
  GROUP10REST_PARAM_IDS,
  GROUP10REST_TAGS,
  bonusSpecForGroup10Rest,
  group10restMatchesContract,
  group10restQuietFromHalf,
  group10restQuietnessAt,
  isGroup10RestLayerId,
} from "./layers_group10rest";

describe("group10rest registry", () => {
  it("ships exactly one layer (p215); the no-map param stays out", () => {
    expect(GROUP10REST_LAYER_IDS).toEqual(["skyview"]);
    expect(GROUP10REST_LAYERS.map((l) => l.id)).toEqual(["skyview"]);
    expect(GROUP10REST_PARAM_IDS).toEqual({ skyview: 215 });
    expect([...GROUP10REST_ALL_PARAMS]).toEqual([215, 491]);
    // p491 must never gain a layer silently: the shipped
    // param set is exactly p215.
    const shipped = new Set(GROUP10REST_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([215]);
    expect([...GROUP10REST_NO_MAP_PARAMS]).toEqual([491]);
  });

  it("labels the layer honestly (hinnang, never measured coverage)", () => {
    for (const def of GROUP10REST_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP10REST_LAYERS[0].source).toContain("TTJA");
    expect(GROUP10REST_LAYERS[0].source).toContain("lõunataevas");
    expect(GROUP10REST_LAYERS[0].badLabel).toContain("Starlink");
  });

  it("documents the PBF-extract source tags (tall buildings + forest)", () => {
    expect(GROUP10REST_TAGS.skyview).toContain("building:levels");
    expect(GROUP10REST_TAGS.skyview).toContain("wood");
    expect(GROUP10REST_TAGS.skyview).toContain("forest");
    // Family houses stay out of the fragment's spirit: the 5-storey
    // cutoff lives in the scorer mapping, like sibling batches.
    expect(GROUP10REST_TAGS.skyview).not.toContain("supermarket");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G10R_CAL.skyview.halfM).toBe(150);
    expect(G10R_CAL.skyview.sigma).toBe(0.3);
    expect(GROUP10REST_DECAY.skyview).toBe(0.3);
    expect(GROUP10REST_BONUS.skyview).toEqual({ kind: "quiet", halfM: 150 });
    expect(bonusSpecForGroup10Rest("skyview")).toEqual({ kind: "quiet", halfM: 150 });
    expect(bonusSpecForGroup10Rest("parks")).toBeUndefined();
    expect(isGroup10RestLayerId("skyview")).toBe(true);
    expect(isGroup10RestLayerId("parks")).toBe(false);
    expect(G10R_RASTER_FILE.skyview).toBe("skyview-walk-raster.json");
  });

  it("serves fallback demo points (obstructed + open, probe-verified)", () => {
    for (const def of GROUP10REST_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G10R_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [215, "proxy"],
      [491, "no-map"],
    ]);
    expect(GROUP10REST_HOOK).toContain("G10R-HOOK (#171)");
  });
});

describe("group10rest math", () => {
  it("reads 0 on the obstruction, 50 at halfM, ~100 when far", () => {
    expect(group10restQuietFromHalf(0, 150)).toBe(0);
    expect(group10restQuietFromHalf(150, 150)).toBe(50);
    expect(group10restQuietFromHalf(Infinity, 150)).toBe(100);
    expect(group10restQuietFromHalf(1e9, 150)).toBeGreaterThan(99.9);
  });

  it("scores nearest-obstruction distance (Lasnamäe probe: ~75 m -> 33)", () => {
    const pts = [{ lat: 59.44, lon: 24.82 }];
    expect(group10restQuietnessAt("skyview", 59.44, 24.82, pts)).toBe(0);
    // 75 m from the obstruction reads 100*75/225 = 33.33 -> 33.
    const q = group10restQuietnessAt("skyview", 59.44 - 75 / 110570, 24.82, pts);
    expect(q).toBe(33);
    expect(group10restQuietnessAt("skyview", 59.44, 24.82, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group10restMatchesContract("skyview", { half: 150, sigma: 0.3 })).toBe(true);
    expect(group10restMatchesContract("skyview", { half: 300, sigma: 0.3 })).toBe(false);
    expect(group10restMatchesContract("skyview", { half: 150, sigma: 0.5 })).toBe(false);
    expect(group10restMatchesContract("skyview", null)).toBe(false);
  });
});
