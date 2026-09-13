import { describe, expect, it } from "vitest";
import {
  G08A_ALL_PARAMS,
  G08A_CAL,
  G08A_DECAY_KM,
  G08A_HOOK,
  G08A_LAYER_IDS,
  G08A_LAYERS,
  G08A_NO_MAP_PARAMS,
  G08A_PARAM_IDS,
  G08A_RASTER_FILE,
  G08A_NO_METRO,
  G08A_TAGS,
  G08A_VERDICTS,
  bonusSpecForGroup08A,
  g08aHavKm,
  g08aMatchesContract,
  g08aQuietFromHalf,
  g08aQuietnessAt,
  g08aRadiusKmFor,
  isG08ALayerId,
} from "./layers_group08a";

describe("group08a layer registry", () => {
  it("ships exactly the p69 wildfire proxy", () => {
    expect([...G08A_LAYER_IDS].sort()).toEqual(["wildfire"]);
    expect(G08A_LAYERS.map((l) => l.id).sort()).toEqual(["wildfire"]);
    expect(G08A_LAYERS.flatMap((l) => l.paramIds)).toEqual([69]);
    expect(G08A_PARAM_IDS.wildfire).toEqual([69]);
    expect([...G08A_ALL_PARAMS].sort((a, b) => a - b)).toEqual([46, 69, 112, 117]);
  });

  it("documents one verdict per owned param (proxy + three no-maps)", () => {
    expect(G08A_VERDICTS.map((v) => v.param).sort((a, b) => a - b)).toEqual([46, 69, 112, 117]);
    expect(G08A_VERDICTS.find((v) => v.param === 69)?.kind).toBe("proxy");
    for (const v of G08A_VERDICTS) expect(v.reason.length).toBeGreaterThan(10);
    expect([...G08A_NO_MAP_PARAMS].sort((a, b) => a - b)).toEqual([46, 112, 117]);
  });

  it("labels the layer honestly: proksi+hinnang everywhere, units nowhere", () => {
    for (const l of G08A_LAYERS) {
      for (const s of [l.title, l.goodLabel, l.badLabel, l.source]) {
        expect(s.toLowerCase()).toContain("proksi");
        expect(s.toLowerCase()).toContain("hinnang");
        expect(s).not.toMatch(/põlengute arv|tulekahjuseire|EFFIS|mg\/kg/);
      }
      expect(l.goodLabel).toContain("roheline");
      expect(l.badLabel).toContain("punane");
    }
  });

  it("has finite Estonian fallback points (fuel edge + clear witness)", () => {
    for (const l of G08A_LAYERS) {
      expect(l.fallbackPoints.length).toBeGreaterThan(0);
      for (const p of l.fallbackPoints) {
        expect(Number.isFinite(p.lat) && Number.isFinite(p.lon)).toBe(true);
        expect(p.lat).toBeGreaterThan(57);
        expect(p.lat).toBeLessThan(60);
      }
    }
  });

  it("documents forest-fuel source tags per layer (no live fetch)", () => {
    expect(G08A_TAGS.wildfire).toContain("forest");
    expect(G08A_TAGS.wildfire).toContain("wood");
    expect(G08A_TAGS.wildfire).toContain("scrub");
    expect(G08A_TAGS.wildfire).toContain("heath");
    // Meadow/wetland stay out: hayfields and bogs are not wildfire fuel
    // (p257 vectorhabitat owns the habitat reading).
    expect(G08A_TAGS.wildfire).not.toContain("meadow");
    expect(G08A_TAGS.wildfire).not.toContain("wetland");
  });

  it("ships no metro masters by documented decision", () => {
    expect(G08A_NO_METRO).toBe(true);
    expect(G08A_RASTER_FILE.wildfire).toBe("wildfire-walk-raster.json");
  });

  it("keeps the decay radius positive with a matching radius helper", () => {
    expect(G08A_DECAY_KM.wildfire).toBeGreaterThan(0);
    expect(g08aRadiusKmFor("wildfire")).toBe(G08A_DECAY_KM.wildfire);
  });

  it("guards the hook and emits the quiet spec at the locked half", () => {
    expect(G08A_HOOK).toContain("G08A-HOOK (#167)");
    expect(isG08ALayerId("wildfire")).toBe(true);
    expect(isG08ALayerId("parks")).toBe(false);
    expect(isG08ALayerId("woodfire")).toBe(false);
    expect(bonusSpecForGroup08A("wildfire")).toEqual({ kind: "quiet", halfM: 100 });
    expect(bonusSpecForGroup08A("parks")).toBeUndefined();
  });
});

describe("group08a math mirrors the Python builder", () => {
  it("uses the 57.29/110.57 equirectangular scale", () => {
    expect(g08aHavKm(0, 0, 1, 0)).toBeCloseTo(57.29, 9);
    expect(g08aHavKm(0, 0, 0, 1)).toBeCloseTo(110.57, 9);
  });

  it("clearance is 0 in the fuel, 50 at half, 100 at infinity", () => {
    expect(g08aQuietFromHalf(0, 100)).toBe(0);
    expect(g08aQuietFromHalf(100, 100)).toBe(50);
    expect(g08aQuietFromHalf(Infinity, 100)).toBe(100);
  });

  it("distance fallback: forest edge is red, far is green, empty is null", () => {
    const pts = [{ lat: 59.3862, lon: 24.6611 }]; // Nõmme forest edge
    expect(g08aQuietnessAt(59.3862, 24.6611, pts)).toBe(0);
    expect(g08aQuietnessAt(59.3862, 24.6611, [])).toBeNull();
    const far = g08aQuietnessAt(59.45, 24.75, pts);
    expect(far).not.toBeNull();
    expect(far as number).toBeGreaterThan(70);
  });

  it("bonus spec matches the locked calibration", () => {
    expect(G08A_CAL.wildfire.halfM).toBe(100);
    expect(G08A_CAL.wildfire.sigma).toBe(0.3);
  });

  it("contract matcher accepts matching docs, rejects drift", () => {
    expect(g08aMatchesContract({ half: 100, sigma: 0.3 }, "wildfire")).toBe(true);
    expect(g08aMatchesContract({ half: 300, sigma: 0.3 }, "wildfire")).toBe(false);
    expect(g08aMatchesContract({ half: 100, sigma: 0.5 }, "wildfire")).toBe(false);
    expect(g08aMatchesContract(null, "wildfire")).toBe(false);
  });
});
