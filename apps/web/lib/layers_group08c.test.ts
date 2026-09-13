// Group 8 flood/climate-C layer tests (issue #169): p334 surgeroad
// proxy + p336 slidebuf proxy ship; p371/p372 are documented no-map
// (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G08C_CAL,
  GROUP08C_ALL_PARAMS,
  GROUP08C_BONUS,
  GROUP08C_DECAY,
  GROUP08C_HOOK,
  G08C_RASTER_FILE,
  G08C_VERDICTS,
  GROUP08C_LAYER_IDS,
  GROUP08C_LAYERS,
  GROUP08C_NO_MAP_PARAMS,
  GROUP08C_PARAM_IDS,
  GROUP08C_TAGS,
  bonusSpecForGroup08C,
  group08cMatchesContract,
  group08cQuietFromHalf,
  group08cQuietnessAt,
  isGroup08CLayerId,
} from "./layers_group08c";

describe("group08c registry", () => {
  it("ships exactly two layers (p334 + p336); no-map params stay out", () => {
    expect(GROUP08C_LAYER_IDS).toEqual(["surgeroad", "slidebuf"]);
    expect(GROUP08C_LAYERS.map((l) => l.id)).toEqual(["surgeroad", "slidebuf"]);
    expect(GROUP08C_PARAM_IDS).toEqual({ surgeroad: 334, slidebuf: 336 });
    expect([...GROUP08C_ALL_PARAMS]).toEqual([334, 336, 371, 372]);
    // p371/p372 must never gain a layer silently: the shipped
    // param set is exactly p334 + p336.
    const shipped = new Set(GROUP08C_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([334, 336]);
    expect([...GROUP08C_NO_MAP_PARAMS]).toEqual([371, 372]);
  });

  it("labels both layers honestly (hinnang, never measured)", () => {
    for (const def of GROUP08C_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP08C_LAYERS[0].source).toContain("üleujutuskaart");
    expect(GROUP08C_LAYERS[1].source).toContain("varingurisk");
  });

  it("documents the PBF-extract source tags (roads + cliffs)", () => {
    expect(GROUP08C_TAGS.surgeroad).toContain("highway");
    expect(GROUP08C_TAGS.surgeroad).toContain("coastline");
    // Surge source is carriageways: no footways, tracks or paths.
    expect(GROUP08C_TAGS.surgeroad).not.toContain("footway");
    expect(GROUP08C_TAGS.surgeroad).not.toContain("flood_prone");
    expect(GROUP08C_TAGS.slidebuf).toContain("cliff");
    expect(GROUP08C_TAGS.slidebuf).toContain("earth_bank");
    // Slide stays distinct from p50 drainage: no rivers, no wetlands.
    expect(GROUP08C_TAGS.slidebuf).not.toContain("waterway");
    expect(GROUP08C_TAGS.slidebuf).not.toContain("wetland");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G08C_CAL.surgeroad.halfM).toBe(150);
    expect(G08C_CAL.surgeroad.sigma).toBe(0.3);
    expect(G08C_CAL.slidebuf.halfM).toBe(100);
    expect(G08C_CAL.slidebuf.sigma).toBe(0.3);
    expect(GROUP08C_DECAY.surgeroad).toBe(0.3);
    expect(GROUP08C_DECAY.slidebuf).toBe(0.3);
    expect(GROUP08C_BONUS.surgeroad).toEqual({ kind: "quiet", halfM: 150 });
    expect(GROUP08C_BONUS.slidebuf).toEqual({ kind: "quiet", halfM: 100 });
    expect(bonusSpecForGroup08C("surgeroad")).toEqual({ kind: "quiet", halfM: 150 });
    expect(bonusSpecForGroup08C("slidebuf")).toEqual({ kind: "quiet", halfM: 100 });
    expect(bonusSpecForGroup08C("parks")).toBeUndefined();
    expect(isGroup08CLayerId("surgeroad")).toBe(true);
    expect(isGroup08CLayerId("slidebuf")).toBe(true);
    expect(isGroup08CLayerId("parks")).toBe(false);
    expect(G08C_RASTER_FILE.surgeroad).toBe("surgeroad-walk-raster.json");
    expect(G08C_RASTER_FILE.slidebuf).toBe("slidebuf-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP08C_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G08C_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [334, "proxy"],
      [336, "proxy"],
      [371, "no-map"],
      [372, "no-map"],
    ]);
    expect(GROUP08C_HOOK).toContain("G08C-HOOK (#169)");
  });
});

describe("group08c math", () => {
  it("reads 0 at the source, 50 at halfM, ~100 when far", () => {
    expect(group08cQuietFromHalf(0, 150)).toBe(0);
    expect(group08cQuietFromHalf(150, 150)).toBe(50);
    expect(group08cQuietFromHalf(Infinity, 150)).toBe(100);
    expect(group08cQuietFromHalf(1e9, 100)).toBeGreaterThan(99.9);
  });

  it("scores nearest-source distance per layer halfM", () => {
    const pts = [{ lat: 59.46048, lon: 24.81723 }];
    expect(group08cQuietnessAt("surgeroad", 59.46048, 24.81723, pts)).toBe(0);
    // 150 m north of the source reads 100*150/300 = 50 (surge band edge).
    const q = group08cQuietnessAt("surgeroad", 59.46048 + 150 / 110570, 24.81723, pts);
    expect(q).toBe(50);
    // Same geometry under the slidebuf halfM (100) reads 100*150/250 = 60.
    const s = group08cQuietnessAt("slidebuf", 59.46048 + 150 / 110570, 24.81723, pts);
    expect(s).toBe(60);
    expect(group08cQuietnessAt("slidebuf", 59.46048, 24.81723, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group08cMatchesContract("surgeroad", { half: 150, sigma: 0.3 })).toBe(true);
    expect(group08cMatchesContract("surgeroad", { half: 100, sigma: 0.3 })).toBe(false);
    expect(group08cMatchesContract("surgeroad", { half: 150, sigma: 0.5 })).toBe(false);
    expect(group08cMatchesContract("slidebuf", { half: 100, sigma: 0.3 })).toBe(true);
    expect(group08cMatchesContract("slidebuf", { half: 150, sigma: 0.3 })).toBe(false);
    expect(group08cMatchesContract("slidebuf", null)).toBe(false);
  });
});
