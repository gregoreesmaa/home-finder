// Group 5 plans-D layer tests (issue #164): p230 strsat proxy ships;
// p226/p244/p275/p280 are documented no-map (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G05D_CAL,
  G05D_RASTER_FILE,
  G05D_VERDICTS,
  GROUP05D_ALL_PARAMS,
  GROUP05D_BONUS,
  GROUP05D_DECAY,
  GROUP05D_HOOK,
  GROUP05D_LAYER_IDS,
  GROUP05D_LAYERS,
  GROUP05D_NO_MAP_PARAMS,
  GROUP05D_PARAM_IDS,
  GROUP05D_TAGS,
  bonusSpecForGroup05D,
  group05dAvoidanceAt,
  group05dAvoidScore,
  group05dMatchesContract,
  isGroup05DAvoidLayer,
  isGroup05DLayerId,
} from "./layers_group05d";

describe("group05d registry", () => {
  it("ships exactly one layer (p230); no-map params stay out", () => {
    expect(GROUP05D_LAYER_IDS).toEqual(["strsat"]);
    expect(GROUP05D_LAYERS.map((l) => l.id)).toEqual(["strsat"]);
    expect(GROUP05D_PARAM_IDS).toEqual({ strsat: 230 });
    expect([...GROUP05D_ALL_PARAMS]).toEqual([226, 230, 244, 275, 280]);
    // p226/p244/p275/p280 must never gain a layer silently: the shipped
    // param set is exactly p230.
    const shipped = new Set(GROUP05D_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([230]);
    expect([...GROUP05D_NO_MAP_PARAMS]).toEqual([226, 244, 275, 280]);
  });

  it("labels the layer honestly (hinnang/proksi, never measured)", () => {
    for (const def of GROUP05D_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP05D_LAYERS[0].source).toContain("PROKSI");
    expect(GROUP05D_LAYERS[0].source).toContain("Airbnb");
  });

  it("documents the PBF-extract source tags (tourist accommodation)", () => {
    expect(GROUP05D_TAGS.strsat).toContain("tourism");
    expect(GROUP05D_TAGS.strsat).toContain("apartment");
    expect(GROUP05D_TAGS.strsat).toContain("guest_house");
    expect(GROUP05D_TAGS.strsat).toContain("hostel");
    expect(GROUP05D_TAGS.strsat).toContain("hotel");
    // STR saturation is guest turnover, not food/drink foot traffic.
    expect(GROUP05D_TAGS.strsat).not.toContain("amenity");
    expect(GROUP05D_TAGS.strsat).not.toContain("shop");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G05D_CAL.strsat.half).toBe(0.35);
    expect(G05D_CAL.strsat.sigma).toBe(0.5);
    expect(GROUP05D_DECAY.strsat).toBe(0.5);
    expect(GROUP05D_BONUS.strsat).toEqual({ kind: "avoid", half: 0.35 });
    expect(bonusSpecForGroup05D("strsat")).toEqual({ kind: "avoid", half: 0.35 });
    expect(bonusSpecForGroup05D("parks")).toBeUndefined();
    expect(isGroup05DLayerId("strsat")).toBe(true);
    expect(isGroup05DLayerId("parks")).toBe(false);
    expect(isGroup05DAvoidLayer("strsat")).toBe(true);
    expect(isGroup05DAvoidLayer("parks")).toBe(false);
    expect(G05D_RASTER_FILE.strsat).toBe("strsat-walk-raster.json");
  });

  it("serves fallback demo points (near + far)", () => {
    for (const def of GROUP05D_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G05D_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [226, "no-map"],
      [230, "proxy"],
      [244, "no-map"],
      [275, "no-map"],
      [280, "no-map"],
    ]);
    expect(GROUP05D_HOOK).toContain("G05D-HOOK (#164)");
  });
});

describe("group05d math", () => {
  it("reads 0 on the beds, 50 at half, ~100 when far", () => {
    expect(group05dAvoidScore(0, 0.35)).toBe(0);
    expect(group05dAvoidScore(0.35, 0.35)).toBe(50);
    expect(group05dAvoidScore(Infinity, 0.35)).toBe(100);
    expect(group05dAvoidScore(1e9, 0.35)).toBeGreaterThan(99.99);
  });

  it("scores inverse nearest-bed distance (150 m -> ~26)", () => {
    const pts = [{ lat: 59.4366, lon: 24.7449 }];
    expect(group05dAvoidanceAt("strsat", 59.4366, 24.7449, pts)).toBe(0);
    // 150 m from the beds: 100*(1-2^(-0.15/0.35)) = 25.6 -> 26.
    const q = group05dAvoidanceAt("strsat", 59.4366 - 150 / 110570, 24.7449, pts);
    expect(q).toBe(26);
    // Nõmme from a Kesklinn bed (~8 km): rounds to 100.
    expect(group05dAvoidanceAt("strsat", 59.36, 24.66, pts)).toBe(100);
    expect(group05dAvoidanceAt("strsat", 59.4366, 24.7449, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group05dMatchesContract("strsat", { half: 0.35, sigma: 0.5 })).toBe(true);
    expect(group05dMatchesContract("strsat", { half: 0.21, sigma: 0.5 })).toBe(false);
    expect(group05dMatchesContract("strsat", { half: 0.35, sigma: 0.3 })).toBe(false);
    expect(group05dMatchesContract("strsat", null)).toBe(false);
  });
});
