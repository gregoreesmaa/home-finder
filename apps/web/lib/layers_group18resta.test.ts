// Group 18 rest-A layer tests (issue #172): p34 dayopen proxy +
// p305 glassglare proxy ship; p100/p231/p287 are documented no-map
// (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G18A_CAL,
  G18A_RASTER_FILE,
  G18A_VERDICTS,
  GROUP18ARESTA_ALL_PARAMS,
  GROUP18A_HOOK,
  GROUP18ARESTA_BONUS,
  GROUP18ARESTA_DECAY,
  GROUP18ARESTA_LAYER_IDS,
  GROUP18ARESTA_LAYERS,
  GROUP18ARESTA_NO_MAP_PARAMS,
  GROUP18ARESTA_PARAM_IDS,
  GROUP18ARESTA_TAGS,
  bonusSpecForGroup18ARestA,
  group18aMatchesContract,
  group18aQuietFromHalf,
  group18aQuietnessAt,
  isGroup18ARestALayerId,
} from "./layers_group18resta";

describe("group18resta registry", () => {
  it("ships exactly two layers (p34 + p305); no-map params stay out", () => {
    expect(GROUP18ARESTA_LAYER_IDS).toEqual(["dayopen", "glassglare"]);
    expect(GROUP18ARESTA_LAYERS.map((l) => l.id)).toEqual(["dayopen", "glassglare"]);
    expect(GROUP18ARESTA_PARAM_IDS).toEqual({ dayopen: 34, glassglare: 305 });
    expect([...GROUP18ARESTA_ALL_PARAMS]).toEqual([34, 100, 231, 287, 305]);
    // p100/p231/p287 must never gain a layer silently: the shipped
    // param set is exactly p34 + p305.
    const shipped = new Set(GROUP18ARESTA_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([34, 305]);
    expect([...GROUP18ARESTA_NO_MAP_PARAMS]).toEqual([100, 231, 287]);
  });

  it("labels all layers honestly (hinnang, never measured data)", () => {
    for (const def of GROUP18ARESTA_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP18ARESTA_LAYERS[0].source).toContain("päikesetunnid");
    expect(GROUP18ARESTA_LAYERS[1].source).toContain("luksid");
  });

  it("documents the PBF-extract source tags (tall masses + glass facades)", () => {
    expect(GROUP18ARESTA_TAGS.dayopen).toContain("building");
    expect(GROUP18ARESTA_TAGS.dayopen).toContain("building:levels");
    // Daylight obstruction is mass, not glazing: no material query.
    expect(GROUP18ARESTA_TAGS.dayopen).not.toContain("material");
    expect(GROUP18ARESTA_TAGS.glassglare).toContain("building:material");
    expect(GROUP18ARESTA_TAGS.glassglare).toContain("glass");
    expect(GROUP18ARESTA_TAGS.glassglare).toContain("mirror");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G18A_CAL.dayopen.halfM).toBe(150);
    expect(G18A_CAL.dayopen.sigma).toBe(0.3);
    expect(G18A_CAL.glassglare.halfM).toBe(200);
    expect(G18A_CAL.glassglare.sigma).toBe(0.3);
    expect(GROUP18ARESTA_DECAY.dayopen).toBe(0.3);
    expect(GROUP18ARESTA_DECAY.glassglare).toBe(0.3);
    expect(GROUP18ARESTA_BONUS.dayopen).toEqual({ kind: "quiet", halfM: 150 });
    expect(GROUP18ARESTA_BONUS.glassglare).toEqual({ kind: "quiet", halfM: 200 });
    expect(bonusSpecForGroup18ARestA("dayopen")).toEqual({ kind: "quiet", halfM: 150 });
    expect(bonusSpecForGroup18ARestA("glassglare")).toEqual({ kind: "quiet", halfM: 200 });
    expect(bonusSpecForGroup18ARestA("parks")).toBeUndefined();
    expect(isGroup18ARestALayerId("dayopen")).toBe(true);
    expect(isGroup18ARestALayerId("glassglare")).toBe(true);
    expect(isGroup18ARestALayerId("parks")).toBe(false);
    expect(G18A_RASTER_FILE.dayopen).toBe("dayopen-walk-raster.json");
    expect(G18A_RASTER_FILE.glassglare).toBe("glassglare-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP18ARESTA_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G18A_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [34, "proxy"],
      [100, "no-map"],
      [231, "no-map"],
      [287, "no-map"],
      [305, "proxy"],
    ]);
    expect(GROUP18A_HOOK).toContain("G18A-HOOK (#172)");
  });
});

describe("group18resta math", () => {
  it("reads 0 on the source, 50 at halfM, ~100 when far", () => {
    expect(group18aQuietFromHalf(0, 150)).toBe(0);
    expect(group18aQuietFromHalf(150, 150)).toBe(50);
    expect(group18aQuietFromHalf(200, 200)).toBe(50);
    expect(group18aQuietFromHalf(Infinity, 150)).toBe(100);
    expect(group18aQuietFromHalf(1e9, 200)).toBeGreaterThan(99.9);
  });

  it("scores nearest-source distance (Lasnamäe probe: ~150 m -> 50)", () => {
    const pts = [{ lat: 59.44, lon: 24.82 }];
    expect(group18aQuietnessAt("dayopen", 59.44, 24.82, pts)).toBe(0);
    // 150 m from the source reads 100*150/300 = 50.
    const q = group18aQuietnessAt("dayopen", 59.44 - 150 / 110570, 24.82, pts);
    expect(q).toBe(50);
    // Same geometry, glare half: 100*150/350 = 42.86 -> 43.
    expect(group18aQuietnessAt("glassglare", 59.44 - 150 / 110570, 24.82, pts)).toBe(43);
    expect(group18aQuietnessAt("dayopen", 59.44, 24.82, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group18aMatchesContract("dayopen", { half: 150, sigma: 0.3 })).toBe(true);
    expect(group18aMatchesContract("dayopen", { half: 300, sigma: 0.3 })).toBe(false);
    expect(group18aMatchesContract("glassglare", { half: 200, sigma: 0.3 })).toBe(true);
    expect(group18aMatchesContract("glassglare", { half: 200, sigma: 0.5 })).toBe(false);
    expect(group18aMatchesContract("dayopen", null)).toBe(false);
  });
});
