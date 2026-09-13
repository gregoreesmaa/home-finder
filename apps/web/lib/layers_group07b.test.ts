import { describe, expect, it } from "vitest";
import {
  G07B_CAL,
  G07B_DECAY_KM,
  G07B_LAYERS,
  G07B_NO_MAP,
  G07B_NO_METRO,
  G07B_PARAM_IDS,
  G07B_RASTER_FILE,
  G07B_TAGS,
  g07bBonusSpecFor,
  g07bCleanFromHalf,
  g07bCleanlinessAt,
  g07bHavKm,
  g07bMatchesContract,
  g07bRadiusKmFor,
  isG07BLayerId,
  type G07BLayerId,
} from "./layers_group07b";

const IDS: G07BLayerId[] = ["brownsoil", "oiltank", "agriland"];

describe("group07b layer registry", () => {
  it("covers exactly the three mappable assigned params", () => {
    expect(G07B_LAYERS.map((l) => l.id).sort()).toEqual([...IDS].sort());
    expect(G07B_LAYERS.flatMap((l) => l.paramIds).sort((a, b) => a - b)).toEqual([189, 202, 227]);
    expect(G07B_PARAM_IDS.brownsoil).toEqual([189]);
    expect(G07B_PARAM_IDS.oiltank).toEqual([202]);
    expect(G07B_PARAM_IDS.agriland).toEqual([227]);
  });

  it("documents the two no-map verdicts (hazmat/invasive)", () => {
    expect(G07B_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([204, 252]);
    for (const v of G07B_NO_MAP) expect(v.reason.length).toBeGreaterThan(10);
  });

  it("labels every layer honestly: proksi+hinnang everywhere, units nowhere", () => {
    for (const l of G07B_LAYERS) {
      for (const s of [l.title, l.goodLabel, l.badLabel, l.source]) {
        expect(s.toLowerCase()).toContain("proksi");
        expect(s.toLowerCase()).toContain("hinnang");
        expect(s).not.toMatch(/mg\/kg|AQI|OU\/m|Bq\/m|liitrit|doos/);
      }
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
    }
  });

  it("has finite Estonian fallback points (source + clean witnesses)", () => {
    for (const l of G07B_LAYERS) {
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat) && Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(57);
        expect(p.lat).toBeLessThan(60);
      }
    }
  });

  it("documents source tags per layer (no live fetch)", () => {
    expect(G07B_TAGS.brownsoil).toContain("brownfield");
    expect(G07B_TAGS.oiltank).toContain("storage_tank");
    expect(G07B_TAGS.agriland).toContain("farmland");
    expect(G07B_TAGS.agriland).toContain("farmyard");
  });

  it("ships no metro masters by documented decision", () => {
    expect(G07B_NO_METRO).toBe(true);
    for (const id of IDS) {
      expect(G07B_RASTER_FILE[id]).toBe(`${id}-walk-raster.json`);
    }
  });

  it("keeps decay radii positive with matching radius helper", () => {
    for (const id of IDS) {
      expect(G07B_DECAY_KM[id]).toBeGreaterThan(0);
      expect(g07bRadiusKmFor(id)).toBe(G07B_DECAY_KM[id]);
    }
  });

  it("guards the hook and emits quiet specs at the locked halves", () => {
    expect(isG07BLayerId("brownsoil")).toBe(true);
    expect(isG07BLayerId("oiltank")).toBe(true);
    expect(isG07BLayerId("agriland")).toBe(true);
    expect(isG07BLayerId("parks")).toBe(false);
    expect(isG07BLayerId("pets")).toBe(false);
    expect(g07bBonusSpecFor("brownsoil")).toEqual({ kind: "quiet", halfM: 500 });
    expect(g07bBonusSpecFor("oiltank")).toEqual({ kind: "quiet", halfM: 500 });
    expect(g07bBonusSpecFor("agriland")).toEqual({ kind: "quiet", halfM: 800 });
  });
});

describe("group07b math mirrors the Python builder", () => {
  it("uses the 57.29/110.57 equirectangular scale", () => {
    expect(g07bHavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(g07bHavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("cleanliness is 0 on the source, 50 at half, 100 at infinity", () => {
    expect(g07bCleanFromHalf(0, 500)).toBe(0);
    expect(g07bCleanFromHalf(500, 500)).toBe(50);
    expect(g07bCleanFromHalf(Infinity, 500)).toBe(100);
  });

  it("distance fallback: depot is red, far is green, empty is null", () => {
    const pts = [{ lat: 59.4983, lon: 24.937 }]; // Muuga fuel depot
    expect(g07bCleanlinessAt("oiltank", 59.4983, 24.937, pts)).toBe(0);
    expect(g07bCleanlinessAt("oiltank", 59.4983, 24.937, [])).toBeNull();
    const far = g07bCleanlinessAt("oiltank", 59.2, 24.5, pts);
    expect(far).not.toBeNull();
    expect(far as number).toBeGreaterThan(90);
  });

  it("agriland fallback halves at 800 m (spray-drift scale)", () => {
    const pts = [{ lat: 59.44, lon: 24.9261 }]; // Lasnamäe-fringe field
    expect(g07bCleanlinessAt("agriland", 59.44, 24.9261, pts)).toBe(0);
    expect(g07bCleanlinessAt("agriland", 59.44, 24.9261, [])).toBeNull();
  });

  it("bonus specs match the locked calibration", () => {
    expect(G07B_CAL.brownsoil.halfM).toBe(500);
    expect(G07B_CAL.oiltank.sigma).toBe(0.5);
    expect(G07B_CAL.agriland.halfM).toBe(800);
    expect(G07B_CAL.agriland.sigma).toBe(0.8);
  });

  it("contract matcher accepts matching docs, rejects drift", () => {
    expect(g07bMatchesContract({ half: 500, sigma: 0.5 }, "brownsoil")).toBe(true);
    expect(g07bMatchesContract({ half: 501, sigma: 0.5 }, "brownsoil")).toBe(false);
    expect(g07bMatchesContract({ half: 500, sigma: 0.3 }, "oiltank")).toBe(false);
    expect(g07bMatchesContract({ half: 500, sigma: 0.5 }, "oiltank")).toBe(true);
    expect(g07bMatchesContract({ half: 800, sigma: 0.8 }, "agriland")).toBe(true);
    expect(g07bMatchesContract({ half: 500, sigma: 0.8 }, "agriland")).toBe(false);
    expect(g07bMatchesContract(null, "agriland")).toBe(false);
  });
});
