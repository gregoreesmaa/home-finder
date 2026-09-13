// Group 3 cadastre-A layer tests (issue #151): p50 drainage proxy ships,
// p29/p68/p71/p75 are documented no-map (no layer, scorer dims only).
import { describe, expect, it } from "vitest";
import {
  G03_CAL,
  G03_RASTER_FILE,
  GROUP03_ALL_PARAMS,
  GROUP03_BONUS,
  GROUP03_DECAY,
  GROUP03_LAYER_IDS,
  GROUP03_LAYERS,
  GROUP03_PARAM_IDS,
  GROUP03_TAGS,
  bonusSpecForGroup03,
  group03MatchesContract,
  group03QuietFromHalf,
  group03QuietnessAt,
  isGroup03LayerId,
} from "./layers_group03";

describe("group03 registry", () => {
  it("ships exactly one layer (p50); no-map params stay out", () => {
    expect(GROUP03_LAYER_IDS).toEqual(["drainage"]);
    expect(GROUP03_LAYERS.map((l) => l.id)).toEqual(["drainage"]);
    expect(GROUP03_PARAM_IDS).toEqual({ drainage: 50 });
    expect([...GROUP03_ALL_PARAMS]).toEqual([29, 50, 68, 71, 75]);
    // p29/p68/p71/p75 must never gain a layer silently: the shipped
    // param set is exactly p50.
    const shipped = new Set(GROUP03_LAYERS.flatMap((l) => l.paramIds));
    expect([...shipped]).toEqual([50]);
  });

  it("labels the proxy honestly (hinnang/proksi, never measured)", () => {
    const def = GROUP03_LAYERS[0];
    for (const s of [def.title, def.goodLabel, def.badLabel, def.source]) {
      expect(s).toContain("hinnang");
    }
    expect(def.title).toContain("drenaažiproksi");
    expect(def.source).toContain("EI OLE");
    expect(def.source).toContain("2026-09-12");
  });

  it("documents the PBF-extract source tags (sea + inland + flow)", () => {
    const q = GROUP03_TAGS.drainage;
    for (const t of ["coastline", "natural", "water", "wetland", "waterway"]) {
      expect(q).toContain(t);
    }
  });

  it("locks calibration (drift guard mirrors the Python builder)", () => {
    expect(G03_CAL.drainage.halfM).toBe(300);
    expect(G03_CAL.drainage.sigma).toBe(0.3);
    expect(GROUP03_DECAY.drainage).toBe(0.3);
    expect(GROUP03_BONUS.drainage).toEqual({ kind: "quiet", halfM: 300 });
    expect(bonusSpecForGroup03("drainage")).toEqual({ kind: "quiet", halfM: 300 });
    expect(bonusSpecForGroup03("parks")).toBeUndefined();
    expect(isGroup03LayerId("drainage")).toBe(true);
    expect(isGroup03LayerId("parks")).toBe(false);
    expect(G03_RASTER_FILE.drainage).toBe("drainage-walk-raster.json");
  });

  it("serves fallback demo points (wet-adjacent + dry)", () => {
    expect(GROUP03_LAYERS[0].fallbackPoints.length).toBeGreaterThanOrEqual(2);
  });
});

describe("group03 quiet math", () => {
  it("reads 0 on the water, 50 at halfM, ~100 when dry", () => {
    expect(group03QuietFromHalf(0, 300)).toBe(0);
    expect(group03QuietFromHalf(300, 300)).toBe(50);
    expect(group03QuietFromHalf(Infinity, 300)).toBe(100);
    expect(group03QuietFromHalf(1e9, 300)).toBeGreaterThan(99.9);
  });

  it("scores nearest-water distance (Balti probe: 159 m -> 35)", () => {
    const pts = [{ lat: 59.4405, lon: 24.7369 }];
    expect(group03QuietnessAt(59.4405, 24.7369, pts)).toBe(0);
    // 159 m north of the source reads 100*159/459 = 35.
    const q = group03QuietnessAt(59.4405 + 159 / 110570, 24.7369, pts);
    expect(q).toBe(35);
    expect(group03QuietnessAt(59.4405, 24.7369, [])).toBeNull();
  });

  it("matches the wire contract only on locked calibration", () => {
    expect(group03MatchesContract({ half: 300, sigma: 0.3 })).toBe(true);
    expect(group03MatchesContract({ half: 500, sigma: 0.3 })).toBe(false);
    expect(group03MatchesContract({ half: 300, sigma: 0.5 })).toBe(false);
    expect(group03MatchesContract(null)).toBe(false);
  });
});
