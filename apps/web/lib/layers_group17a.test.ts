// Group 17 municipal-services-A layer tests (issue #177): p187 compost
// proxy + p311 gritbin proxy + p312 leafdrop proxy ship; p60/p347 are
// documented no-map (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G17A_CAL,
  G17A_RASTER_FILE,
  G17A_VERDICTS,
  GROUP17A_HOOK,
  GROUP17A_ALL_PARAMS,
  GROUP17A_BONUS,
  GROUP17A_DECAY,
  GROUP17A_LAYER_IDS,
  GROUP17A_LAYERS,
  GROUP17A_NO_MAP_PARAMS,
  GROUP17A_PARAM_IDS,
  GROUP17A_TAGS,
  bonusSpecForGroup17A,
  group17aAreaScore,
  group17aMatchesContract,
  isGroup17ALayerId,
} from "./layers_group17a";

describe("group17a registry", () => {
  it("ships exactly three layers (p187 + p311 + p312); no-map params stay out", () => {
    expect(GROUP17A_LAYER_IDS).toEqual(["compost", "gritbin", "leafdrop"]);
    expect(GROUP17A_LAYERS.map((l) => l.id)).toEqual(["compost", "gritbin", "leafdrop"]);
    expect(GROUP17A_PARAM_IDS).toEqual({ compost: 187, gritbin: 311, leafdrop: 312 });
    expect([...GROUP17A_ALL_PARAMS]).toEqual([60, 187, 311, 312, 347]);
    // p60/p347 must never gain a layer silently: the shipped
    // param set is exactly p187 + p311 + p312.
    const shipped = new Set(GROUP17A_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([187, 311, 312]);
    expect([...GROUP17A_NO_MAP_PARAMS]).toEqual([60, 347]);
  });

  it("labels all layers honestly (hinnang, never registry data)", () => {
    for (const def of GROUP17A_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP17A_LAYERS[0].source).toContain("jäätmejaama");
    expect(GROUP17A_LAYERS[1].source).toContain("sahaplaan");
    expect(GROUP17A_LAYERS[1].source).toContain("p446");
    expect(GROUP17A_LAYERS[2].source).toContain("prügikasti");
    expect(GROUP17A_LAYERS[2].source).toContain("veograafik");
  });

  it("documents the PBF-extract source tags (recycling + grit bins + waste)", () => {
    expect(GROUP17A_TAGS.compost).toContain("recycling");
    expect(GROUP17A_TAGS.compost).toContain("green_waste");
    expect(GROUP17A_TAGS.compost).toContain("food_waste");
    expect(GROUP17A_TAGS.gritbin).toContain("grit_bin");
    expect(GROUP17A_TAGS.leafdrop).toContain("recycling");
    expect(GROUP17A_TAGS.leafdrop).toContain("waste_disposal");
    // No road-class source: road class already scores inverted as p446.
    for (const t of Object.values(GROUP17A_TAGS)) {
      expect(t).not.toContain("highway");
    }
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G17A_CAL.compost.half).toBe(1);
    expect(G17A_CAL.compost.sigma).toBe(0.3);
    expect(G17A_CAL.gritbin.half).toBe(1);
    expect(G17A_CAL.gritbin.sigma).toBe(0.3);
    expect(G17A_CAL.leafdrop.half).toBe(1);
    expect(G17A_CAL.leafdrop.sigma).toBe(0.3);
    expect(GROUP17A_DECAY.compost).toBe(0.3);
    expect(GROUP17A_DECAY.gritbin).toBe(0.3);
    expect(GROUP17A_DECAY.leafdrop).toBe(0.3);
    expect(GROUP17A_BONUS.compost).toEqual({ kind: "area", half: 1 });
    expect(GROUP17A_BONUS.gritbin).toEqual({ kind: "area", half: 1 });
    expect(GROUP17A_BONUS.leafdrop).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup17A("compost")).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup17A("leafdrop")).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup17A("parks")).toBeUndefined();
    expect(isGroup17ALayerId("gritbin")).toBe(true);
    expect(isGroup17ALayerId("leafdrop")).toBe(true);
    expect(isGroup17ALayerId("parks")).toBe(false);
    expect(G17A_RASTER_FILE.compost).toBe("compost-walk-raster.json");
    expect(G17A_RASTER_FILE.gritbin).toBe("gritbin-walk-raster.json");
    expect(G17A_RASTER_FILE.leafdrop).toBe("leafdrop-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP17A_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G17A_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [60, "no-map"],
      [187, "proxy"],
      [311, "proxy"],
      [312, "proxy"],
      [347, "no-map"],
    ]);
    expect(GROUP17A_HOOK).toContain("G17A-HOOK (#177)");
  });
});

describe("group17a math", () => {
  it("saturates service counts like viewshed/moorage (one station reads 50)", () => {
    expect(group17aAreaScore(0, 1)).toBe(0);
    expect(group17aAreaScore(1, 1)).toBe(50);
    expect(group17aAreaScore(3, 1)).toBe(75);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group17aMatchesContract("compost", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group17aMatchesContract("compost", { half: 2, sigma: 0.3 })).toBe(false);
    expect(group17aMatchesContract("gritbin", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group17aMatchesContract("gritbin", { half: 1, sigma: 0.5 })).toBe(false);
    expect(group17aMatchesContract("leafdrop", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group17aMatchesContract("leafdrop", { half: 300, sigma: 0.3 })).toBe(false);
    expect(group17aMatchesContract("compost", null)).toBe(false);
  });
});
