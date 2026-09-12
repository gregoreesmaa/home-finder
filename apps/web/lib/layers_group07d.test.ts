import { describe, expect, it } from "vitest";
import {
  G07D_CAL,
  G07D_DECAY_KM,
  G07D_LAYERS,
  G07D_NO_MAP,
  G07D_NO_METRO,
  G07D_PARAM_IDS,
  G07D_RASTER_FILE,
  G07D_TAGS,
  g07dBonusSpecFor,
  g07dCleanFromHalf,
  g07dCleanlinessAt,
  g07dHavKm,
  g07dMatchesContract,
  g07dRadiusKmFor,
  isG07DLayerId,
  type G07DLayerId,
} from "./layers_group07d";

const IDS: G07DLayerId[] = ["agrifield", "wildcorr"];

describe("group07d layer registry", () => {
  it("covers exactly the two mappable assigned params", () => {
    expect(G07D_LAYERS.map((l) => l.id).sort()).toEqual([...IDS].sort());
    expect(G07D_LAYERS.flatMap((l) => l.paramIds).sort((a, b) => a - b)).toEqual([409, 450]);
    expect(G07D_PARAM_IDS.agrifield).toEqual([409]);
    expect(G07D_PARAM_IDS.wildcorr).toEqual([450]);
  });

  it("documents the three no-map verdicts (harvest/lead/aesthetic)", () => {
    expect(G07D_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([448, 471, 499]);
    for (const v of G07D_NO_MAP) expect(v.reason.length).toBeGreaterThan(10);
  });

  it("labels every layer honestly: proksi+hinnang everywhere, units nowhere", () => {
    for (const l of G07D_LAYERS) {
      for (const s of [l.title, l.goodLabel, l.badLabel, l.source]) {
        expect(s.toLowerCase()).toContain("proksi");
        expect(s.toLowerCase()).toContain("hinnang");
        expect(s).not.toMatch(/mg\/kg|AQI|OU\/m|Bq\/m|doos|Seveso|koridori id/);
      }
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
    }
  });

  it("wildcorr never claims a corridor registry", () => {
    const w = G07D_LAYERS.find((l) => l.id === "wildcorr");
    expect(w?.source).toContain("mitte rändekoridoride register");
  });

  it("has finite Estonian fallback points (source + clean witnesses)", () => {
    for (const l of G07D_LAYERS) {
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat) && Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(57);
        expect(p.lat).toBeLessThan(60);
      }
    }
  });

  it("documents source tags per layer (no live fetch)", () => {
    expect(G07D_TAGS.agrifield).toContain("farmland");
    expect(G07D_TAGS.agrifield).toContain("meadow");
    expect(G07D_TAGS.agrifield).toContain("greenhouse_horticulture");
    expect(G07D_TAGS.wildcorr).toContain("wood");
    expect(G07D_TAGS.wildcorr).toContain("wetland");
    expect(G07D_TAGS.wildcorr).toContain("nature_reserve");
  });

  it("ships no metro masters by documented decision", () => {
    expect(G07D_NO_METRO).toBe(true);
    for (const id of IDS) {
      expect(G07D_RASTER_FILE[id]).toBe(`${id}-walk-raster.json`);
    }
  });

  it("keeps decay radii positive with matching radius helper", () => {
    for (const id of IDS) {
      expect(G07D_DECAY_KM[id]).toBeGreaterThan(0);
      expect(g07dRadiusKmFor(id)).toBe(G07D_DECAY_KM[id]);
    }
  });

  it("guards the hook and emits quiet specs at the locked halves", () => {
    expect(isG07DLayerId("agrifield")).toBe(true);
    expect(isG07DLayerId("wildcorr")).toBe(true);
    expect(isG07DLayerId("parks")).toBe(false);
    expect(isG07DLayerId("pets")).toBe(false);
    expect(g07dBonusSpecFor("agrifield")).toEqual({ kind: "quiet", halfM: 800 });
    expect(g07dBonusSpecFor("wildcorr")).toEqual({ kind: "quiet", halfM: 500 });
  });
});

describe("group07d math mirrors the Python builder", () => {
  it("uses the 57.29/110.57 equirectangular scale", () => {
    expect(g07dHavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(g07dHavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("cleanliness is 0 on the source, 50 at half, 100 at infinity", () => {
    expect(g07dCleanFromHalf(0, 500)).toBe(0);
    expect(g07dCleanFromHalf(500, 500)).toBe(50);
    expect(g07dCleanFromHalf(Infinity, 500)).toBe(100);
  });

  it("distance fallback: meadow is red, far is green, empty is null", () => {
    const pts = [{ lat: 59.4407, lon: 24.8041 }]; // Lasnamäe-fringe meadow
    expect(g07dCleanlinessAt("agrifield", 59.4407, 24.8041, pts)).toBe(0);
    expect(g07dCleanlinessAt("agrifield", 59.4407, 24.8041, [])).toBeNull();
    const far = g07dCleanlinessAt("agrifield", 59.4374, 24.7454, pts);
    expect(far).not.toBeNull();
    expect(far as number).toBeGreaterThan(60);
  });

  it("wildcorr fallback halves at 500 m (parcel scale)", () => {
    const pts = [{ lat: 59.4364, lon: 24.7489 }]; // central grove
    expect(g07dCleanlinessAt("wildcorr", 59.4364, 24.7489, pts)).toBe(0);
    expect(g07dCleanlinessAt("wildcorr", 59.4364, 24.7489, [])).toBeNull();
  });

  it("bonus specs match the locked calibration", () => {
    expect(G07D_CAL.agrifield.halfM).toBe(800);
    expect(G07D_CAL.agrifield.sigma).toBe(0.8);
    expect(G07D_CAL.wildcorr.halfM).toBe(500);
    expect(G07D_CAL.wildcorr.sigma).toBe(0.5);
  });

  it("contract matcher accepts matching docs, rejects drift", () => {
    expect(g07dMatchesContract({ half: 800, sigma: 0.8 }, "agrifield")).toBe(true);
    expect(g07dMatchesContract({ half: 500, sigma: 0.8 }, "agrifield")).toBe(false);
    expect(g07dMatchesContract({ half: 500, sigma: 0.5 }, "wildcorr")).toBe(true);
    expect(g07dMatchesContract({ half: 500, sigma: 0.8 }, "wildcorr")).toBe(false);
    expect(g07dMatchesContract(null, "wildcorr")).toBe(false);
  });
});
