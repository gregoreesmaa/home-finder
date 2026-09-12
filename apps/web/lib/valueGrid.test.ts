import { describe, expect, it } from "vitest";
import { accumulateGrid, gridToRgba, sampleBilinear } from "./valueGrid";
import type { BBoxLike } from "./layers";

const BBOX: BBoxLike = { minlon: 24.5, minlat: 59.35, maxlon: 24.9, maxlat: 59.5 };

describe("accumulation grid", () => {
  it("peaks at the cell with its score and full coverage", () => {
    const g = accumulateGrid([{ lon: 24.7, lat: 59.42, score: 80 }], BBOX, 40, 15);
    const ix = Math.round(((24.7 - BBOX.minlon) / (BBOX.maxlon - BBOX.minlon)) * (g.cols - 1));
    const iy = Math.round(((59.42 - BBOX.minlat) / (BBOX.maxlat - BBOX.minlat)) * (g.rows - 1));
    expect(g.valueAt(ix, iy)).toBeGreaterThan(70);
    expect(g.valueAt(ix, iy)).toBeLessThanOrEqual(80);
    expect(g.coverageAt(ix, iy)).toBeGreaterThan(0.9);
  });

  it("leaves empty regions transparent (no fake fill)", () => {
    const g = accumulateGrid([{ lon: 24.55, lat: 59.37, score: 90 }], BBOX, 40, 15);
    expect(g.coverageAt(g.cols - 1, g.rows - 1)).toBeLessThan(0.05);
    const rgba = gridToRgba(g);
    const a = rgba[((g.rows - 1) * g.cols + (g.cols - 1)) * 4 + 3];
    expect(a).toBe(0);
  });

  it("averages overlaps instead of piling up", () => {
    const g = accumulateGrid(
      [
        { lon: 24.69, lat: 59.42, score: 20 },
        { lon: 24.71, lat: 59.42, score: 100 },
      ],
      BBOX,
      40,
      15,
    );
    const ix = Math.round(((24.7 - BBOX.minlon) / (BBOX.maxlon - BBOX.minlon)) * (g.cols - 1));
    const iy = Math.round(((59.42 - BBOX.minlat) / (BBOX.maxlat - BBOX.minlat)) * (g.rows - 1));
    const v = g.valueAt(ix, iy) as number;
    expect(v).toBeGreaterThan(20);
    expect(v).toBeLessThan(100);
    // Dense overlap sums past 1: capped to fully opaque.
    const rgba = gridToRgba(g);
    let maxA = 0;
    for (let i = 3; i < rgba.length; i += 4) maxA = Math.max(maxA, rgba[i]);
    expect(maxA).toBe(255);
  });

  it("bilinear sample reads exact values under the cursor", () => {
    const g = accumulateGrid(
      [
        { lon: 24.69, lat: 59.42, score: 20 },
        { lon: 24.71, lat: 59.42, score: 100 },
      ],
      BBOX,
      40,
      15,
    );
    const mid = sampleBilinear(g, 24.7, 59.42);
    expect(mid).not.toBeNull();
    expect(mid?.value).toBeGreaterThan(20);
    expect(mid?.value).toBeLessThan(100);
    expect(mid?.coverage).toBeGreaterThan(0.5);
    expect(sampleBilinear(g, 24.5, 59.5)).toBeNull(); // far corner: no data
    expect(sampleBilinear(g, 0, 0)).toBeNull(); // outside bbox: no data
  });

  it("empty input yields a fully transparent grid", () => {
    const g = accumulateGrid([], BBOX, 40, 15);
    const rgba = gridToRgba(g);
    for (let i = 3; i < rgba.length; i += 4) expect(rgba[i]).toBe(0);
  });

  it("RGBA bytes stay in range with a near-opaque lone peak", () => {
    const g = accumulateGrid([{ lon: 24.7, lat: 59.42, score: 80 }], BBOX, 40, 15);
    const rgba = gridToRgba(g);
    let maxA = 0;
    for (let i = 0; i < rgba.length; i++) {
      expect(rgba[i]).toBeGreaterThanOrEqual(0);
      expect(rgba[i]).toBeLessThanOrEqual(255);
      if (i % 4 === 3) maxA = Math.max(maxA, rgba[i]);
    }
    // Lone cell falls between grid nodes: ~0.9 cover, full opacity only
    // where kernels overlap (see averaging test).
    expect(maxA).toBeGreaterThan(200);
  });
});
