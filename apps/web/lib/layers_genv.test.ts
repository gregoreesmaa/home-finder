import { describe, expect, it } from "vitest";
import {
  GENV_CAL,
  GENV_DECAY_KM,
  GENV_LAYERS,
  GENV_NO_METRO,
  GENV_RASTER_FILE,
  GENV_TAGS,
  genvBonusSpec,
  genvHavKm,
  genvIsMajorRunway,
  genvMatchesContract,
  genvQuietFromHalf,
  genvQuietnessAt,
  genvRadiusKmFor,
  type GenvLayerId,
} from "./layers_genv";

const IDS: GenvLayerId[] = ["vibration", "lowspec", "flightcorr", "darksky", "coolisland"];

describe("genv layer registry", () => {
  it("covers exactly the five assigned params", () => {
    expect(GENV_LAYERS.map((l) => l.id).sort()).toEqual([...IDS].sort());
    expect(GENV_LAYERS.flatMap((l) => l.paramIds).sort((a, b) => a - b)).toEqual([
      63, 181, 234, 408, 445,
    ]);
  });

  it("labels every layer honestly: proksi+hinnang everywhere, units nowhere", () => {
    for (const l of GENV_LAYERS) {
      for (const s of [l.title, l.goodLabel, l.badLabel, l.source]) {
        expect(s.toLowerCase()).toContain("proksi");
        expect(s).not.toMatch(/dBA?/);
        expect(s).not.toMatch(/Bortle|magnituud|Celsius|°C/);
      }
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
    }
    expect(GENV_LAYERS.find((l) => l.id === "flightcorr")?.title).toContain(
      "hooajalisus teadmata",
    );
  });

  it("has finite Estonian fallback points", () => {
    for (const l of GENV_LAYERS) {
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat) && Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(57);
        expect(p.lat).toBeLessThan(60);
      }
    }
  });

  it("documents nwr source tags per layer (no live fetch)", () => {
    for (const id of IDS) {
      expect(GENV_TAGS[id].length).toBeGreaterThan(0);
    }
    expect(GENV_TAGS.vibration).toContain("rail");
    expect(GENV_TAGS.vibration).toContain("motorway");
    expect(GENV_TAGS.vibration).not.toContain("node[");
    expect(GENV_TAGS.flightcorr).toContain("aeroway");
    expect(GENV_TAGS.darksky).toContain("street_lamp");
    expect(GENV_TAGS.coolisland).toContain("building");
  });

  it("ships no metro masters by documented decision", () => {
    expect(GENV_NO_METRO).toBe(true);
    for (const id of IDS) {
      expect(GENV_RASTER_FILE[id]).toBe(`${id}-walk-raster.json`);
    }
  });

  it("keeps decay radii positive with matching radius helper", () => {
    for (const id of IDS) {
      expect(GENV_DECAY_KM[id]).toBeGreaterThan(0);
      expect(genvRadiusKmFor(id)).toBe(GENV_DECAY_KM[id]);
    }
  });
});

describe("genv math mirrors the Python builder", () => {
  it("uses the 57.29/110.57 equirectangular scale", () => {
    expect(genvHavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(genvHavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("quietness is 0 on the source, 50 at half, 100 at infinity", () => {
    expect(genvQuietFromHalf(0, 300)).toBe(0);
    expect(genvQuietFromHalf(300, 300)).toBe(50);
    expect(genvQuietFromHalf(Infinity, 300)).toBe(100);
  });

  it("distance fallback: near vibration is red, far is green, empty is null", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536 }];
    expect(genvQuietnessAt("vibration", 59.4372, 24.7536, pts)).toBe(0);
    expect(genvQuietnessAt("vibration", 59.4372, 24.7536, [])).toBeNull();
    const far = genvQuietnessAt("vibration", 59.5, 25.0, pts);
    expect(far).not.toBeNull();
    expect(far as number).toBeGreaterThan(90);
  });

  it("flightcorr tiers runways by surface tags", () => {
    expect(genvIsMajorRunway({ lat: 0, lon: 0, tags: { surface: "asphalt" } })).toBe(true);
    expect(genvIsMajorRunway({ lat: 0, lon: 0, tags: { surface: "grass" } })).toBe(false);
    expect(genvIsMajorRunway({ lat: 0, lon: 0 })).toBe(false);
    // Same geometry, paved reads worse (1500 m half) than grass (400 m).
    const paved = [{ lat: 59.4372, lon: 24.7536, tags: { surface: "asphalt" } }];
    const grass = [{ lat: 59.4372, lon: 24.7536, tags: { surface: "grass" } }];
    const at = genvQuietnessAt("flightcorr", 59.4472, 24.7536, paved);
    const atGrass = genvQuietnessAt("flightcorr", 59.4472, 24.7536, grass);
    expect(at).not.toBeNull();
    expect(atGrass).not.toBeNull();
    expect(at as number).toBeLessThan(atGrass as number);
    expect(genvQuietnessAt("flightcorr", 59.4, 24.7, [])).toBeNull();
  });

  it("density fallback: null when empty, dark when far, lit when heavy", () => {
    expect(genvQuietnessAt("darksky", 59.2, 24.5, [])).toBeNull();
    const pts = [{ lat: 59.2, lon: 24.5, a: 1 }];
    expect(genvQuietnessAt("darksky", 59.5, 25.0, pts)).toBe(100);
    const heavy = [{ lat: 59.4372, lon: 24.7536, a: 500 }];
    expect(genvQuietnessAt("darksky", 59.4372, 24.7536, heavy)).toBeLessThan(25);
  });

  it("coolisland adds the green ramp only when mapped", () => {
    const pts = [{ lat: 59.4372, lon: 24.7536, a: 500 }];
    const without = genvQuietnessAt("coolisland", 59.4372, 24.7536, pts, null);
    const withNature = genvQuietnessAt("coolisland", 59.4372, 24.7536, pts, 0);
    expect((withNature as number) - (without as number)).toBe(8);
    const edge = genvQuietnessAt("coolisland", 59.4372, 24.7536, pts, 500);
    expect(edge).toBe(without);
  });

  it("bonus specs match the locked calibration", () => {
    expect(genvBonusSpec("vibration")).toEqual({ kind: "quiet", halfM: 300 });
    expect(genvBonusSpec("lowspec")).toEqual({ kind: "quiet", halfM: 500 });
    expect(genvBonusSpec("flightcorr")).toEqual({ kind: "quiet", halfM: 1500 });
    expect(genvBonusSpec("darksky")).toEqual({ kind: "area", half: 120 });
    expect(GENV_CAL.coolisland.greenBonus).toBe(8);
  });

  it("contract matcher accepts matching docs, rejects drift", () => {
    expect(genvMatchesContract({ half: 300, sigma: 0.3 }, "vibration")).toBe(true);
    expect(genvMatchesContract({ half: 301, sigma: 0.3 }, "vibration")).toBe(false);
    expect(genvMatchesContract({ half: 1500, sigma: 0.3 }, "flightcorr")).toBe(true);
    expect(genvMatchesContract({ half: 400, sigma: 0.3 }, "flightcorr")).toBe(false);
    expect(genvMatchesContract({ half: 120, sigma: 0.3 }, "darksky")).toBe(true);
    expect(genvMatchesContract(null, "darksky")).toBe(false);
  });
});
