import { describe, expect, it } from "vitest";
import {
  G07_CAL,
  G07_DECAY_KM,
  G07_LAYERS,
  G07_NO_MAP,
  G07_NO_METRO,
  G07_PARAM_IDS,
  G07_RASTER_FILE,
  G07_TAGS,
  g07BonusSpecFor,
  g07CleanFromHalf,
  g07CleanlinessAt,
  g07HavKm,
  g07MatchesContract,
  g07RadiusKmFor,
  isG07LayerId,
  type G07LayerId,
} from "./layers_group07";

const IDS: G07LayerId[] = ["industprox", "odorsrc"];

describe("group07 layer registry", () => {
  it("covers exactly the two mappable assigned params", () => {
    expect(G07_LAYERS.map((l) => l.id).sort()).toEqual([...IDS].sort());
    expect(G07_LAYERS.flatMap((l) => l.paramIds).sort((a, b) => a - b)).toEqual([61, 62]);
    expect(G07_PARAM_IDS.industprox).toEqual([61]);
    expect(G07_PARAM_IDS.odorsrc).toEqual([62]);
  });

  it("documents the three no-map verdicts (radon/pests/allergens)", () => {
    expect(G07_NO_MAP.map((v) => v.param).sort((a, b) => a - b)).toEqual([66, 67, 137]);
    for (const v of G07_NO_MAP) expect(v.reason.length).toBeGreaterThan(10);
  });

  it("labels every layer honestly: proksi+hinnang everywhere, units nowhere", () => {
    for (const l of G07_LAYERS) {
      for (const s of [l.title, l.goodLabel, l.badLabel, l.source]) {
        expect(s.toLowerCase()).toContain("proksi");
        expect(s.toLowerCase()).toContain("hinnang");
        expect(s).not.toMatch(/AQI|OU\/m|Bq\/m|grains/);
      }
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
    }
  });

  it("has finite Estonian fallback points (plant + rural witnesses)", () => {
    for (const l of G07_LAYERS) {
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat) && Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(57);
        expect(p.lat).toBeLessThan(60);
      }
    }
  });

  it("documents source tags per layer (no live fetch)", () => {
    expect(G07_TAGS.industprox).toContain("industrial");
    expect(G07_TAGS.odorsrc).toContain("wastewater_plant");
    expect(G07_TAGS.odorsrc).toContain("landfill");
  });

  it("ships no metro masters by documented decision", () => {
    expect(G07_NO_METRO).toBe(true);
    for (const id of IDS) {
      expect(G07_RASTER_FILE[id]).toBe(`${id}-walk-raster.json`);
    }
  });

  it("keeps decay radii positive with matching radius helper", () => {
    for (const id of IDS) {
      expect(G07_DECAY_KM[id]).toBeGreaterThan(0);
      expect(g07RadiusKmFor(id)).toBe(G07_DECAY_KM[id]);
    }
  });

  it("guards the hook and emits quiet specs at the locked halves", () => {
    expect(isG07LayerId("industprox")).toBe(true);
    expect(isG07LayerId("odorsrc")).toBe(true);
    expect(isG07LayerId("parks")).toBe(false);
    expect(g07BonusSpecFor("industprox")).toEqual({ kind: "quiet", halfM: 500 });
    expect(g07BonusSpecFor("odorsrc")).toEqual({ kind: "quiet", halfM: 500 });
  });
});

describe("group07 math mirrors the Python builder", () => {
  it("uses the 57.29/110.57 equirectangular scale", () => {
    expect(g07HavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(g07HavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("cleanliness is 0 on the source, 50 at half, 100 at infinity", () => {
    expect(g07CleanFromHalf(0, 500)).toBe(0);
    expect(g07CleanFromHalf(500, 500)).toBe(50);
    expect(g07CleanFromHalf(Infinity, 500)).toBe(100);
  });

  it("distance fallback: plant is red, far is green, empty is null", () => {
    const pts = [{ lat: 59.466, lon: 24.698 }]; // Paljassaare plant
    expect(g07CleanlinessAt("odorsrc", 59.466, 24.698, pts)).toBe(0);
    expect(g07CleanlinessAt("odorsrc", 59.466, 24.698, [])).toBeNull();
    const far = g07CleanlinessAt("odorsrc", 59.2, 24.5, pts);
    expect(far).not.toBeNull();
    expect(far as number).toBeGreaterThan(90);
  });

  it("bonus specs match the locked calibration", () => {
    expect(G07_CAL.industprox.halfM).toBe(500);
    expect(G07_CAL.odorsrc.sigma).toBe(0.5);
  });

  it("contract matcher accepts matching docs, rejects drift", () => {
    expect(g07MatchesContract({ half: 500, sigma: 0.5 }, "industprox")).toBe(true);
    expect(g07MatchesContract({ half: 501, sigma: 0.5 }, "industprox")).toBe(false);
    expect(g07MatchesContract({ half: 500, sigma: 0.3 }, "odorsrc")).toBe(false);
    expect(g07MatchesContract({ half: 500, sigma: 0.5 }, "odorsrc")).toBe(true);
    expect(g07MatchesContract(null, "odorsrc")).toBe(false);
  });
});
