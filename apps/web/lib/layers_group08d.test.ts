// Group 8 flood/climate-D layer tests (issue #170): p447 vernalpool
// ships; p377/p378/p429 are documented no-map (no layer, scorer dims
// only).
import { describe, expect, it } from "vitest";
import {
  G08D_CAL,
  G08D_DECAY_KM,
  G08D_HOOK,
  G08D_LAYER_IDS,
  G08D_LAYERS,
  G08D_NO_MAP_PARAMS,
  G08D_PARAM_IDS,
  G08D_RASTER_FILE,
  G08D_VERDICTS,
  G08D_ALL_PARAMS,
  G08D_TAGS,
  g08dBonusSpecFor,
  g08dCleanFromHalf,
  g08dCleanlinessAt,
  g08dMatchesContract,
  isG08DLayerId,
} from "./layers_group08d";

describe("group08d registry", () => {
  it("ships exactly one layer (p447); no-map params stay out", () => {
    expect(G08D_LAYER_IDS).toEqual(["vernalpool"]);
    expect(G08D_LAYERS.map((l) => l.id)).toEqual(["vernalpool"]);
    expect(G08D_PARAM_IDS).toEqual({ vernalpool: [447] });
    expect([...G08D_ALL_PARAMS]).toEqual([377, 378, 429, 447]);
    // p377/p378/p429 must never gain a layer silently: the shipped
    // param set is exactly p447.
    const shipped = new Set(G08D_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([447]);
    expect([...G08D_NO_MAP_PARAMS]).toEqual([377, 378, 429]);
  });

  it("labels the layer honestly (hinnang, never measured)", () => {
    for (const def of G08D_LAYERS) {
      for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
        expect(s).toContain("hinnang");
      }
      expect(def.source).toContain("PROKSI");
      expect(def.source).toContain("2026-09-12");
    }
    // Never a flood zone, return period, or water-table claim.
    expect(G08D_LAYERS[0].source).not.toContain("üleujutustsoon");
    expect(G08D_LAYERS[0].source).toContain("intermittent");
  });

  it("documents the PBF-extract source tags (ephemeral ponds only)", () => {
    expect(G08D_TAGS.vernalpool).toContain("pond|basin");
    expect(G08D_TAGS.vernalpool).toContain("intermittent");
    // Flow features and all-wetland stay p50 drainage's: no rivers,
    // no bare wetland predicate.
    expect(G08D_TAGS.vernalpool).not.toContain("waterway");
    expect(G08D_TAGS.vernalpool).not.toContain('"wetland"');
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G08D_CAL.vernalpool.halfM).toBe(300);
    expect(G08D_CAL.vernalpool.sigma).toBe(0.3);
    expect(G08D_DECAY_KM.vernalpool).toBe(0.3);
    expect(g08dBonusSpecFor("vernalpool")).toEqual({ kind: "quiet", halfM: 300 });
    expect(isG08DLayerId("vernalpool")).toBe(true);
    expect(isG08DLayerId("parks")).toBe(false);
    expect(G08D_RASTER_FILE.vernalpool).toBe("vernalpool-walk-raster.json");
  });

  it("serves fallback demo points (near + far)", () => {
    for (const def of G08D_LAYERS) {
      expect(def.fallbackPoints.length).toBeGreaterThanOrEqual(2);
    }
  });

  it("pins the per-param verdicts + hook marker", () => {
    expect(G08D_VERDICTS.map((v) => [v.param, v.kind])).toEqual([
      [377, "no-map"],
      [378, "no-map"],
      [429, "no-map"],
      [447, "proxy"],
    ]);
    expect(G08D_HOOK).toContain("G08D-HOOK (#170)");
  });
});

describe("group08d math", () => {
  it("reads 0 on the pond, 50 at halfM, ~100 when far", () => {
    expect(g08dCleanFromHalf(0, 300)).toBe(0);
    expect(g08dCleanFromHalf(300, 300)).toBe(50);
    expect(g08dCleanFromHalf(Infinity, 300)).toBe(100);
    expect(g08dCleanFromHalf(1e9, 300)).toBeGreaterThan(99.9);
  });

  it("scores nearest-pond distance (300 m south reads 50)", () => {
    const pts = [{ lat: 59.4425, lon: 24.7972 }];
    expect(g08dCleanlinessAt("vernalpool", 59.4425, 24.7972, pts)).toBe(0);
    // 300 m south of the source reads 100*300/600 = 50.
    const q = g08dCleanlinessAt("vernalpool", 59.4425 - 300 / 110570, 24.7972, pts);
    expect(q).toBe(50);
    expect(g08dCleanlinessAt("vernalpool", 59.4425, 24.7972, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(g08dMatchesContract({ half: 300, sigma: 0.3 }, "vernalpool")).toBe(true);
    expect(g08dMatchesContract({ half: 500, sigma: 0.3 }, "vernalpool")).toBe(false);
    expect(g08dMatchesContract({ half: 300, sigma: 0.5 }, "vernalpool")).toBe(false);
    expect(g08dMatchesContract(null, "vernalpool")).toBe(false);
  });
});
