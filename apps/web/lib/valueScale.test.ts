import { describe, expect, it } from "vitest";
import {
  buildValueLut,
  colorForValue,
  lutCssGradient,
  relativeLuminance,
} from "./valueScale";

describe("value LUT", () => {
  it("has 256 byte-triplet entries", () => {
    const lut = buildValueLut();
    expect(lut).toHaveLength(256);
    for (const e of lut) {
      for (const c of [e.r, e.g, e.b]) {
        expect(Number.isInteger(c)).toBe(true);
        expect(c).toBeGreaterThanOrEqual(0);
        expect(c).toBeLessThanOrEqual(255);
      }
    }
  });

  it("is monotonic in lightness (readable without hue)", () => {
    const lut = buildValueLut();
    const ys = lut.map(relativeLuminance);
    for (let i = 1; i < ys.length; i++) {
      // No visible brightness reversals: the continuous ramp rises strictly;
      // 8-bit rounding leaves sub-perceptual ripples (<<1% JND).
      expect(ys[i]).toBeGreaterThanOrEqual(ys[i - 1] - 2e-3);
    }
    // Strong brightness story end to end (the colorblind-readable channel).
    expect(ys[ys.length - 1] - ys[0]).toBeGreaterThan(0.25);
  });

  it("runs red (low) to green (high)", () => {
    const lo = colorForValue(0);
    const hi = colorForValue(100);
    expect(lo[0]).toBeGreaterThan(lo[1]); // red channel dominates
    expect(hi[1]).toBeGreaterThan(hi[0]); // green channel dominates
  });

  it("is smooth (no banding between neighbors)", () => {
    const lut = buildValueLut();
    for (let i = 1; i < lut.length; i++) {
      const d = Math.max(
        Math.abs(lut[i].r - lut[i - 1].r),
        Math.abs(lut[i].g - lut[i - 1].g),
        Math.abs(lut[i].b - lut[i - 1].b),
      );
      expect(d).toBeLessThanOrEqual(12);
    }
  });

  it("clamps out-of-range values", () => {
    expect(colorForValue(-50)).toEqual(colorForValue(0));
    expect(colorForValue(500)).toEqual(colorForValue(100));
  });

  it("legend gradient is sampled from the same LUT (cannot drift)", () => {
    const lut = buildValueLut();
    const css = lutCssGradient(lut);
    const [r, g, b] = colorForValue(0, lut);
    expect(css).toContain(`rgb(${r}, ${g}, ${b})`);
    const [r2, g2, b2] = colorForValue(100, lut);
    expect(css).toContain(`rgb(${r2}, ${g2}, ${b2})`);
  });
});
