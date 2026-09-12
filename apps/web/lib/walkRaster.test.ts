import { describe, expect, it } from "vitest";
import { colorForValue } from "./valueScale";
import { decodeRaster, rasterToRgba, sampleRaster } from "./walkRaster";

const BBOX = { minlon: 24.0, minlat: 59.0, maxlon: 24.2, maxlat: 59.1 };

function docFor(values: number[]) {
  return {
    cols: 2,
    rows: 2,
    bbox: BBOX,
    step_m: 75,
    half: 1500,
    sigma: 0.2,
    unknown: 255,
    dtype: "uint8" as const,
    // Row-major, row 0 = south: [SW, SE, NW, NE].
    data: Buffer.from(values).toString("base64"),
  };
}

describe("walk raster decode", () => {
  it("accepts a well-formed doc and rejects corruption", () => {
    const r = decodeRaster(docFor([80, 255, 40, 60]));
    expect(r?.cols).toBe(2);
    expect(r?.values).toEqual(new Uint8Array([80, 255, 40, 60]));
    expect(decodeRaster({ ...docFor([80]), cols: 2, rows: 2 })).toBeNull(); // short
    expect(decodeRaster({ ...docFor([80, 255, 40, 60]), data: "!!!" })).toBeNull();
    expect(decodeRaster({ ...docFor([80, 255, 40, 60]), cols: 0 })).toBeNull();
    expect(decodeRaster({ ...docFor([80, 255, 40, 150]) })).toBeNull(); // >100
    expect(decodeRaster(null)).toBeNull();
  });
});

describe("walk raster sampling", () => {
  it("reads cell centers, interpolates, and stays honest on unknown", () => {
    // [SW, SE, NW, NE] = [80, 255, 40, 60].
    const r = decodeRaster(docFor([80, 255, 40, 60]))!;
    expect(sampleRaster(r, 24.05, 59.025)?.value).toBeCloseTo(80, 5); // SW center
    expect(sampleRaster(r, 24.15, 59.075)?.value).toBeCloseTo(60, 5); // NE center
    expect(sampleRaster(r, 24.05, 59.075)?.value).toBeCloseTo(40, 5); // NW center
    // Bilinear over valid corners only: west edge midpoint = (80+40)/2.
    expect(sampleRaster(r, 24.05, 59.05)?.value).toBeCloseTo(60, 5);
    // Near the unknown SE corner: a blend of valid neighbors only
    // (no fake zero, no unknown leak).
    const seNear = sampleRaster(r, 24.14, 59.026)?.value ?? NaN;
    expect(seNear).toBeGreaterThan(60);
    expect(seNear).toBeLessThan(85);
    // Edge clamps into range; outside the bbox is null.
    expect(sampleRaster(r, 24.0, 59.0)?.value).toBeCloseTo(80, 5);
    expect(sampleRaster(r, 23.0, 58.0)).toBeNull(); // outside
  });

  it("a lone known corner answers its whole neighborhood", () => {
    // Only NE known: anywhere nearby reads 70 (bilinear weight or the
    // nearest-valid fallback when all weight lands on unknown corners).
    const r = decodeRaster(docFor([255, 255, 255, 70]))!;
    expect(sampleRaster(r, 24.15, 59.075)?.value).toBeCloseTo(70, 5);
    expect(sampleRaster(r, 24.15, 59.03)?.value).toBeCloseTo(70, 5);
    expect(sampleRaster(r, 24.1, 59.05)?.value).toBeCloseTo(70, 5);
  });

  it("all-unknown neighborhoods read as no-data, never zero", () => {
    const r = decodeRaster(docFor([255, 255, 255, 255]))!;
    expect(sampleRaster(r, 24.1, 59.05)).toBeNull();
  });
});

describe("walk raster texture", () => {
  it("paints known cells by score and unknown as opaque red", () => {
    const r = decodeRaster(docFor([95, 255, 5, 60]))!;
    const rgba = rasterToRgba(r);
    expect(rgba.length).toBe(2 * 2 * 4);
    const at = (k: number) => k * 4;
    expect(rgba[at(0) + 3]).toBe(255); // 95: opaque...
    expect(rgba[at(0) + 1]).toBeGreaterThan(rgba[at(0)]); // ...green-dominant
    // Unknown renders as the same red as score 0 (user-asked; hover still
    // reports no-data, so the distinction survives in the readout).
    const [zr, zg, zb] = colorForValue(0);
    expect(rgba[at(1) + 3]).toBe(255);
    expect([rgba[at(1)], rgba[at(1) + 1], rgba[at(1) + 2]]).toEqual([zr, zg, zb]);
    expect(rgba[at(2) + 3]).toBe(255);
    expect(rgba[at(2)]).toBeGreaterThan(rgba[at(2) + 1]); // 5: red-dominant
  });
});
