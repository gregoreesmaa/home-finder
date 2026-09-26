// Water-mask spot checks against known Estonian geography (#821).
import { describe, expect, it } from "vitest";
import {
  isWater,
  waterMaskFor,
  waterMaskStats,
} from "./waterMask";

describe("water mask geometry (#821)", () => {
  it("loads the sidecar rings (pins unexpected regeneration drift)", () => {
    const stats = waterMaskStats();
    expect(stats.landRings).toBeGreaterThan(300);
    expect(stats.lakePolys).toBeGreaterThan(1000);
  });

  it("sea reads water", () => {
    expect(isWater(24.75, 59.45)).toBe(true); // Tallinn bay
    expect(isWater(23.0, 59.5)).toBe(true); // Baltic proper
    expect(isWater(21.5, 58.0)).toBe(true); // open sea SW
    expect(isWater(24.0, 57.9)).toBe(true); // Gulf of Riga
  });

  it("big lakes read water", () => {
    expect(isWater(27.5, 58.7)).toBe(true); // Lake Peipus center
    expect(isWater(26.0, 58.28)).toBe(true); // Lake Vortsjarv center
    expect(isWater(24.765, 59.397)).toBe(true); // Ulemiste lake
  });

  it("inland towns read land", () => {
    expect(isWater(24.68, 59.39)).toBe(false); // Nomme
    expect(isWater(26.78, 58.365)).toBe(false); // Tartu Annelinn (off the river)
    expect(isWater(24.7454, 59.4374)).toBe(false); // Tallinn Vanalinn
    expect(isWater(27.47, 59.38)).toBe(false); // Johvi
    expect(isWater(22.6, 58.4)).toBe(false); // Saaremaa interior
    expect(isWater(22.9, 58.95)).toBe(false); // Hiiumaa
  });

  it("foreign soil past the border reads water by design", () => {
    // Documented judgment: rings end at the border; foreign land has
    // no layer coverage regardless, so it never skews the scale.
    expect(isWater(25.0, 57.8)).toBe(true); // Latvia
  });

  it("waterMaskFor flags an all-sea grid", () => {
    const mask = waterMaskFor({
      cols: 4,
      rows: 2,
      bbox: { minlon: 22.0, minlat: 59.7, maxlon: 23.0, maxlat: 59.9 },
    });
    expect(mask.length).toBe(8);
    expect(Array.from(mask)).toEqual([1, 1, 1, 1, 1, 1, 1, 1]);
  });

  it("builds a country-size mask fast enough for pan/zoom", () => {
    const t0 = Date.now();
    const mask = waterMaskFor({
      cols: 200,
      rows: 115,
      bbox: { minlon: 21.5, minlat: 57.3, maxlon: 28.5, maxlat: 59.9 },
    });
    const ms = Date.now() - t0;
    const waterCells = mask.reduce((a, b) => a + b, 0);
    expect(waterCells).toBeGreaterThan(1000); // sea + lakes present
    expect(waterCells).toBeLessThan(mask.length); // land present
    expect(ms).toBeLessThan(2000);
  });
});
