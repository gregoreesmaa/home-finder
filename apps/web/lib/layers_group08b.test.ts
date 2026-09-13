// Group 8 flood/climate-B layer tests (issue #168): p255 windtunnel
// proxy + p333 saltspray proxy ship; p118/p182 are documented no-map
// (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G08B_CAL,
  G08B_RASTER_FILE,
  G08B_VERDICTS,
  GROUP08B_ALL_PARAMS,
  GROUP08B_HOOK,
  GROUP08B_BONUS,
  GROUP08B_DECAY,
  GROUP08B_LAYER_IDS,
  GROUP08B_LAYERS,
  GROUP08B_NO_MAP_PARAMS,
  GROUP08B_PARAM_IDS,
  GROUP08B_TAGS,
  bonusSpecForGroup08B,
  group08bMatchesContract,
  group08bQuietFromHalf,
  group08bQuietnessAt,
  isGroup08BLayerId,
} from "./layers_group08b";

describe("group08b registry", () => {
  it("ships exactly two layers (p255 + p333); no-map params stay out", () => {
    expect(GROUP08B_LAYER_IDS).toEqual(["windtunnel", "saltspray"]);
    expect(GROUP08B_LAYERS.map((l) => l.id)).toEqual(["windtunnel", "saltspray"]);
    expect(GROUP08B_PARAM_IDS).toEqual({ windtunnel: 255, saltspray: 333 });
    expect([...GROUP08B_ALL_PARAMS]).toEqual([118, 182, 255, 333]);
    // p118/p182 must never gain a layer silently: the shipped
    // param set is exactly p255 + p333.
    const shipped = new Set(GROUP08B_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([255, 333]);
    expect([...GROUP08B_NO_MAP_PARAMS]).toEqual([118, 182]);
  });

  it("labels both layers honestly (hinnang, never measured)", () => {
    for (const def of GROUP08B_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP08B_LAYERS[0].source).toContain("ilmajaama");
    expect(GROUP08B_LAYERS[1].source).toContain("korrosioonikiiruse");
  });

  it("documents the PBF-extract source tags (tall buildings + sea)", () => {
    expect(GROUP08B_TAGS.windtunnel).toContain("building:levels");
    expect(GROUP08B_TAGS.saltspray).toContain("coastline");
    expect(GROUP08B_TAGS.saltspray).toContain("natural");
    // Salt stays sea-only: no lakes, rivers, or wetlands (p340's own).
    expect(GROUP08B_TAGS.saltspray).not.toContain("water");
    expect(GROUP08B_TAGS.saltspray).not.toContain("waterway");
    expect(GROUP08B_TAGS.saltspray).not.toContain("wetland");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G08B_CAL.windtunnel.halfM).toBe(200);
    expect(G08B_CAL.windtunnel.sigma).toBe(0.2);
    expect(G08B_CAL.saltspray.halfM).toBe(500);
    expect(G08B_CAL.saltspray.sigma).toBe(0.5);
    expect(GROUP08B_DECAY.windtunnel).toBe(0.2);
    expect(GROUP08B_DECAY.saltspray).toBe(0.5);
    expect(GROUP08B_BONUS.windtunnel).toEqual({ kind: "quiet", halfM: 200 });
    expect(GROUP08B_BONUS.saltspray).toEqual({ kind: "quiet", halfM: 500 });
    expect(bonusSpecForGroup08B("windtunnel")).toEqual({ kind: "quiet", halfM: 200 });
    expect(bonusSpecForGroup08B("saltspray")).toEqual({ kind: "quiet", halfM: 500 });
    expect(bonusSpecForGroup08B("parks")).toBeUndefined();
    expect(isGroup08BLayerId("windtunnel")).toBe(true);
    expect(isGroup08BLayerId("saltspray")).toBe(true);
    expect(isGroup08BLayerId("parks")).toBe(false);
    expect(G08B_RASTER_FILE.windtunnel).toBe("windtunnel-walk-raster.json");
    expect(G08B_RASTER_FILE.saltspray).toBe("saltspray-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP08B_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G08B_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [118, "no-map"],
      [182, "no-map"],
      [255, "proxy"],
      [333, "proxy"],
    ]);
    expect(GROUP08B_HOOK).toContain("G08B-HOOK (#168)");
  });
});

describe("group08b math", () => {
  it("reads 0 on the source, 50 at halfM, ~100 when far", () => {
    expect(group08bQuietFromHalf(0, 200)).toBe(0);
    expect(group08bQuietFromHalf(200, 200)).toBe(50);
    expect(group08bQuietFromHalf(500, 500)).toBe(50);
    expect(group08bQuietFromHalf(Infinity, 200)).toBe(100);
    expect(group08bQuietFromHalf(1e9, 500)).toBeGreaterThan(99.9);
  });

  it("scores nearest-source distance (Õismäe probe: ~150 m -> 43)", () => {
    const pts = [{ lat: 59.412, lon: 24.655 }];
    expect(group08bQuietnessAt("windtunnel", 59.412, 24.655, pts)).toBe(0);
    // 150 m from the source reads 100*150/350 = 42.86 -> 43.
    const q = group08bQuietnessAt("windtunnel", 59.412 - 150 / 110570, 24.655, pts);
    expect(q).toBe(43);
    // Same geometry, salt half: 100*150/650 = 23.08 -> 23.
    expect(group08bQuietnessAt("saltspray", 59.412 - 150 / 110570, 24.655, pts)).toBe(23);
    expect(group08bQuietnessAt("windtunnel", 59.412, 24.655, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group08bMatchesContract("saltspray", { half: 500, sigma: 0.5 })).toBe(true);
    expect(group08bMatchesContract("saltspray", { half: 100, sigma: 0.5 })).toBe(false);
    expect(group08bMatchesContract("saltspray", { half: 500, sigma: 0.2 })).toBe(false);
    expect(group08bMatchesContract("windtunnel", { half: 200, sigma: 0.2 })).toBe(true);
    expect(group08bMatchesContract("windtunnel", { half: 500, sigma: 0.2 })).toBe(false);
    expect(group08bMatchesContract("windtunnel", null)).toBe(false);
  });
});
