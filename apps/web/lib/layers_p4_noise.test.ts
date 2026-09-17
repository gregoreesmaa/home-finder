// Tests for layers_p4_noise.ts (issue #625): guard, fetch, fills.
// Fixtures only, never live. No network in tests.

import { describe, expect, it } from "vitest";
import {
  NOISE_BAND_FILL,
  NOISE_BONUS,
  NOISE_DECAY,
  NOISE_DEFS,
  NOISE_HOOK,
  NOISE_LEGS,
  NOISE_NO_METRO,
  NOISE_NO_RASTER,
  fetchNoiseAreas,
  isNoiseArea,
  isNoiseLayerId,
  isNoisePolygonOnlyLayer,
  noiseFillColor,
} from "./layers_p4_noise";

const GOOD = {
  noise_id: "Lden-7-55",
  leg: "Lden",
  band_db: 55,
  b: [24.7, 59.4, 24.8, 59.5],
  r: [[[24.7, 59.4], [24.8, 59.4], [24.8, 59.5], [24.7, 59.4]]],
};

describe("noise areas (#625)", () => {
  it("accepts well-formed bands, refuses wrong legs and degenerate rows", () => {
    expect(isNoiseArea(GOOD)).toBe(true);
    expect(isNoiseArea({ ...GOOD, leg: "Lday" })).toBe(false);
    expect(isNoiseArea({ ...GOOD, band_db: Number.NaN })).toBe(false);
    expect(isNoiseArea({ ...GOOD, r: [] })).toBe(false);
    expect(isNoiseArea(null)).toBe(false);
  });

  it("maps every 5 dB band to the quiet-to-loud ramp", () => {
    expect(noiseFillColor(45)).toBe(NOISE_BAND_FILL["45"]);
    expect(noiseFillColor(55)).toBe(NOISE_BAND_FILL["55"]);
    expect(noiseFillColor(70)).toBe(NOISE_BAND_FILL["70"]);
    expect(noiseFillColor(75)).toBe(NOISE_BAND_FILL["70"]);
    expect(noiseFillColor(40)).toBe(NOISE_BAND_FILL["45"]);
    expect(noiseFillColor(Number.NaN)).toBe(NOISE_BAND_FILL.unknown);
  });

  it("fetches bands from the noise areas endpoint", async () => {
    const fetchImpl = async () =>
      new Response(JSON.stringify({ areas: [GOOD, { nope: 1 }] }));
    const areas = await fetchNoiseAreas(fetchImpl as typeof fetch);
    expect(areas).toHaveLength(1);
    expect(areas?.[0].noise_id).toBe("Lden-7-55");
  });

  it("fails null on transport error or malformed body (never faked)", async () => {
    const boom = async () => {
      throw new Error("down");
    };
    expect(await fetchNoiseAreas(boom as typeof fetch)).toBeNull();
    const bad = async () => new Response(JSON.stringify({ areas: "x" }));
    expect(await fetchNoiseAreas(bad as typeof fetch)).toBeNull();
  });
});

describe("noise registry (#625)", () => {
  it("is a polygons-only P4 layer with no fallback points", () => {
    expect(isNoiseLayerId("noise")).toBe(true);
    expect(isNoisePolygonOnlyLayer("noise")).toBe(true);
    expect(isNoisePolygonOnlyLayer("forest")).toBe(false);
    expect(NOISE_DEFS[0].paramLabel).toBe("P4-müra");
    expect(NOISE_DEFS[0].fallbackPoints).toEqual([]);
  });

  it("pins inert placeholders + attribution + hook marker", () => {
    expect(NOISE_DECAY.noise).toBe(0.5);
    expect(NOISE_BONUS.noise.kind).toBe("area");
    expect(NOISE_NO_RASTER).toBe(true);
    expect(NOISE_NO_METRO).toBe(true);
    expect(NOISE_LEGS).toEqual(["Lden", "Lnight"]);
    expect(NOISE_HOOK).toContain("NOISE-HOOK (#625)");
  });
});
