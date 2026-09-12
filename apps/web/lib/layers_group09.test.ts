import { describe, expect, it } from "vitest";
import {
  GROUP09_CAL,
  GROUP09_DECAY_KM,
  GROUP09_LAYERS,
  GROUP09_NO_METRO,
  GROUP09_RASTER_FILE,
  GROUP09_TAGS,
  group09BonusSpec,
  group09HavKm,
  group09MatchesContract,
  group09QuietFromHalf,
  group09QuietnessAt,
  group09RadiusKmFor,
  type Group09LayerId,
} from "./layers_group09";

const IDS: Group09LayerId[] = ["trafficnoise", "quietnature", "nuisance", "lowfreq", "braking"];

describe("group09 layer registry", () => {
  it("covers exactly the five assigned params", () => {
    expect(GROUP09_LAYERS.map((l) => l.id).sort()).toEqual([...IDS].sort());
    expect(GROUP09_LAYERS.flatMap((l) => l.paramIds).sort((a, b) => a - b)).toEqual([
      16, 138, 162, 301, 493,
    ]);
  });

  it("labels every layer honestly: proksi everywhere, dBA nowhere", () => {
    for (const l of GROUP09_LAYERS) {
      for (const s of [l.title, l.goodLabel, l.badLabel, l.source]) {
        expect(s.toLowerCase()).toContain("proksi");
        expect(s).not.toMatch(/dBA?/);
      }
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
    }
  });

  it("has finite Estonian fallback points with tags for tooltips", () => {
    for (const l of GROUP09_LAYERS) {
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat) && Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(57);
        expect(p.lat).toBeLessThan(60);
      }
    }
  });

  it("documents source tags per layer (no live fetch)", () => {
    for (const id of IDS) {
      expect(GROUP09_TAGS[id].length).toBeGreaterThan(0);
    }
    expect(GROUP09_TAGS.nuisance).toContain("bar");
    expect(GROUP09_TAGS.nuisance).not.toContain("cinema");
    expect(GROUP09_TAGS.lowfreq).toContain("rail");
  });

  it("ships no metro masters by documented decision", () => {
    expect(GROUP09_NO_METRO).toBe(true);
    for (const id of IDS) {
      expect(GROUP09_RASTER_FILE[id]).toBe(`${id}-walk-raster.json`);
    }
  });

  it("keeps decay radii positive with matching radius helper", () => {
    for (const id of IDS) {
      expect(GROUP09_DECAY_KM[id]).toBeGreaterThan(0);
      expect(group09RadiusKmFor(id)).toBe(GROUP09_DECAY_KM[id]);
    }
  });
});

describe("group09 math mirrors the Python builder", () => {
  it("uses the 57.29/110.57 equirectangular scale", () => {
    expect(group09HavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(group09HavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("quietness is 0 on the source, 50 at half, 100 at infinity", () => {
    expect(group09QuietFromHalf(0, 300)).toBe(0);
    expect(group09QuietFromHalf(300, 300)).toBe(50);
    expect(group09QuietFromHalf(Infinity, 300)).toBe(100);
  });

  it("distance fallback: near nuisance is red, far is green, empty is null", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536 }];
    expect(group09QuietnessAt("nuisance", 59.4372, 24.7536, pts)).toBe(0);
    expect(group09QuietnessAt("nuisance", 59.4372, 24.7536, [])).toBeNull();
    const far = group09QuietnessAt("nuisance", 59.5, 25.0, pts);
    expect(far).not.toBeNull();
    expect(far as number).toBeGreaterThan(90);
  });

  it("density fallback: null when empty, quiet when far, loud when heavy", () => {
    // No points at all -> null (never faked); points far away -> 100.
    expect(group09QuietnessAt("braking", 59.2, 24.5, [])).toBeNull();
    const pts = [{ lat: 59.2, lon: 24.5, a: 1 }];
    expect(group09QuietnessAt("braking", 59.5, 25.0, pts)).toBe(100);
    // A heavy junction rep on top of the reader -> near zero.
    const heavy = [{ lat: 59.4372, lon: 24.7536, a: 500 }];
    expect(group09QuietnessAt("braking", 59.4372, 24.7536, heavy)).toBeLessThan(25);
  });

  it("quietnature adds the nature ramp only when mapped", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536, a: 500 }];
    const without = group09QuietnessAt("quietnature", 59.4372, 24.7536, pts, null);
    const withNature = group09QuietnessAt("quietnature", 59.4372, 24.7536, pts, 0);
    expect((withNature as number) - (without as number)).toBe(10);
    const edge = group09QuietnessAt("quietnature", 59.4372, 24.7536, pts, 600);
    expect(edge).toBe(without);
  });

  it("bonus specs match the locked calibration", () => {
    expect(group09BonusSpec("nuisance")).toEqual({ kind: "quiet", halfM: 300 });
    expect(group09BonusSpec("lowfreq")).toEqual({ kind: "quiet", halfM: 500 });
    expect(group09BonusSpec("braking")).toEqual({ kind: "area", half: 120 });
    expect(GROUP09_CAL.trafficnoise.roadHalf).toBe(400);
    expect(GROUP09_CAL.quietnature.natureBonus).toBe(10);
  });

  it("contract matcher accepts matching docs, rejects drift", () => {
    expect(group09MatchesContract({ half: 300, sigma: 0.3 }, "nuisance")).toBe(true);
    expect(group09MatchesContract({ half: 301, sigma: 0.3 }, "nuisance")).toBe(false);
    expect(group09MatchesContract({ half: 300, sigma: 0.5 }, "nuisance")).toBe(false);
    expect(group09MatchesContract({ half: 120, sigma: 0.3 }, "braking")).toBe(true);
    expect(group09MatchesContract(null, "braking")).toBe(false);
  });
});
