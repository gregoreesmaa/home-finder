// Group 5 plans-C layer tests (issue #163): p223 commbleed proxy +
// p224 windsolar proxy + p225 viewshed proxy ship; p221/p222 are
// documented no-map (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G05C_CAL,
  G05C_RASTER_FILE,
  G05C_VERDICTS,
  GROUP05C_ALL_PARAMS,
  GROUP05C_HOOK,
  GROUP05C_BONUS,
  GROUP05C_DECAY,
  GROUP05C_LAYER_IDS,
  GROUP05C_LAYERS,
  GROUP05C_NO_MAP_PARAMS,
  GROUP05C_PARAM_IDS,
  GROUP05C_TAGS,
  bonusSpecForGroup05C,
  group05cAreaScore,
  group05cMatchesContract,
  group05cQuietFromHalf,
  group05cQuietnessAt,
  isGroup05CLayerId,
} from "./layers_group05c";

describe("group05c registry", () => {
  it("ships exactly three layers (p223 + p224 + p225); no-map params stay out", () => {
    expect(GROUP05C_LAYER_IDS).toEqual(["commbleed", "windsolar", "viewshed"]);
    expect(GROUP05C_LAYERS.map((l) => l.id)).toEqual(["commbleed", "windsolar", "viewshed"]);
    expect(GROUP05C_PARAM_IDS).toEqual({ commbleed: 223, windsolar: 224, viewshed: 225 });
    expect([...GROUP05C_ALL_PARAMS]).toEqual([221, 222, 223, 224, 225]);
    // p221/p222 must never gain a layer silently: the shipped
    // param set is exactly p223 + p224 + p225.
    const shipped = new Set(GROUP05C_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([223, 224, 225]);
    expect([...GROUP05C_NO_MAP_PARAMS]).toEqual([221, 222]);
  });

  it("labels all layers honestly (hinnang, never registry data)", () => {
    for (const def of GROUP05C_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("EI OLE");
      expect(def.source).toContain("2026-09-12");
    }
    expect(GROUP05C_LAYERS[0].source).toContain("KOV");
    expect(GROUP05C_LAYERS[1].source).toContain("katusepaneeli");
    expect(GROUP05C_LAYERS[1].source).toContain("Eleringi");
    expect(GROUP05C_LAYERS[2].source).toContain("kõrguspiirangute");
  });

  it("documents the PBF-extract source tags (zones + farms + viewpoints)", () => {
    expect(GROUP05C_TAGS.commbleed).toContain("commercial");
    expect(GROUP05C_TAGS.commbleed).toContain("retail");
    expect(GROUP05C_TAGS.commbleed).toContain("mall");
    // Bleed pressure, not errands: no plain supermarkets (grocery's own).
    expect(GROUP05C_TAGS.commbleed).not.toContain("supermarket");
    expect(GROUP05C_TAGS.windsolar).toContain("generator");
    expect(GROUP05C_TAGS.windsolar).toContain("wind");
    expect(GROUP05C_TAGS.windsolar).toContain("solar");
    expect(GROUP05C_TAGS.viewshed).toContain("viewpoint");
    expect(GROUP05C_TAGS.viewshed).toContain("tourism");
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G05C_CAL.commbleed.halfM).toBe(300);
    expect(G05C_CAL.commbleed.sigma).toBe(0.3);
    expect(G05C_CAL.windsolar.halfM).toBe(800);
    expect(G05C_CAL.windsolar.sigma).toBe(0.3);
    expect(G05C_CAL.viewshed.half).toBe(1);
    expect(G05C_CAL.viewshed.sigma).toBe(0.3);
    expect(GROUP05C_DECAY.commbleed).toBe(0.3);
    expect(GROUP05C_DECAY.windsolar).toBe(0.3);
    expect(GROUP05C_DECAY.viewshed).toBe(0.3);
    expect(GROUP05C_BONUS.commbleed).toEqual({ kind: "quiet", halfM: 300 });
    expect(GROUP05C_BONUS.windsolar).toEqual({ kind: "quiet", halfM: 800 });
    expect(GROUP05C_BONUS.viewshed).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup05C("commbleed")).toEqual({ kind: "quiet", halfM: 300 });
    expect(bonusSpecForGroup05C("viewshed")).toEqual({ kind: "area", half: 1 });
    expect(bonusSpecForGroup05C("parks")).toBeUndefined();
    expect(isGroup05CLayerId("windsolar")).toBe(true);
    expect(isGroup05CLayerId("viewshed")).toBe(true);
    expect(isGroup05CLayerId("parks")).toBe(false);
    expect(G05C_RASTER_FILE.commbleed).toBe("commbleed-walk-raster.json");
    expect(G05C_RASTER_FILE.windsolar).toBe("windsolar-walk-raster.json");
    expect(G05C_RASTER_FILE.viewshed).toBe("viewshed-walk-raster.json");
  });

  it("serves fallback demo points (near + far per layer)", () => {
    for (const def of GROUP05C_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G05C_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [221, "no-map"],
      [222, "no-map"],
      [223, "proxy"],
      [224, "proxy"],
      [225, "proxy"],
    ]);
    expect(GROUP05C_HOOK).toContain("G05C-HOOK (#163)");
  });
});

describe("group05c math", () => {
  it("reads 0 on the source, 50 at halfM, ~100 when far", () => {
    expect(group05cQuietFromHalf(0, 300)).toBe(0);
    expect(group05cQuietFromHalf(300, 300)).toBe(50);
    expect(group05cQuietFromHalf(800, 800)).toBe(50);
    expect(group05cQuietFromHalf(Infinity, 300)).toBe(100);
    expect(group05cQuietFromHalf(1e9, 800)).toBeGreaterThan(99.9);
  });

  it("scores nearest-source distance (Ülemiste probe: ~150 m -> 33)", () => {
    const pts = [{ lat: 59.4229, lon: 24.7956 }];
    expect(group05cQuietnessAt("commbleed", 59.4229, 24.7956, pts)).toBe(0);
    // 150 m from the source reads 100*150/450 = 33.33 -> 33.
    const q = group05cQuietnessAt("commbleed", 59.4229 - 150 / 110570, 24.7956, pts);
    expect(q).toBe(33);
    // Same geometry, wind/solar half: 100*150/950 = 15.79 -> 16.
    expect(group05cQuietnessAt("windsolar", 59.4229 - 150 / 110570, 24.7956, pts)).toBe(16);
    expect(group05cQuietnessAt("commbleed", 59.4229, 24.7956, [])).toBeNull();
  });

  it("saturates viewpoint counts like moorage (one viewpoint reads 50)", () => {
    expect(group05cAreaScore(0, 1)).toBe(0);
    expect(group05cAreaScore(1, 1)).toBe(50);
    expect(group05cAreaScore(3, 1)).toBe(75);
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group05cMatchesContract("commbleed", { half: 300, sigma: 0.3 })).toBe(true);
    expect(group05cMatchesContract("commbleed", { half: 100, sigma: 0.3 })).toBe(false);
    expect(group05cMatchesContract("windsolar", { half: 800, sigma: 0.3 })).toBe(true);
    expect(group05cMatchesContract("windsolar", { half: 800, sigma: 0.5 })).toBe(false);
    expect(group05cMatchesContract("viewshed", { half: 1, sigma: 0.3 })).toBe(true);
    expect(group05cMatchesContract("viewshed", { half: 2, sigma: 0.3 })).toBe(false);
    expect(group05cMatchesContract("commbleed", null)).toBe(false);
  });
});
