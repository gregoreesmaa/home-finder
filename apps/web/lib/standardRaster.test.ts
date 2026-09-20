// Contract tests for the standard monochrome goodness raster (#809):
// per-kernel adapters, nodata propagation, grid conformance, and
// pixel parity vs the current color rendering (no visual change).

import { describe, expect, it } from "vitest";
import {
  buildScoredField,
  scoredAt,
  type ScoredField,
} from "./distanceField";
import { accumulateGrid } from "./valueGrid";
import { buildDistanceField, type ScoredPoint } from "./distanceField";
import { cleanRaster, type BBoxLike, type BonusSpec } from "./layers";
import {
  STANDARD_UNKNOWN,
  STANDARD_MAX,
  conformsToGrid,
  decodeStandardValue,
  encodeStandardValue,
  standardFromDistanceField,
  standardFromScoredField,
  standardFromValueGrid,
  standardFromWalkRaster,
  standardToGrayscaleRgba,
  type StandardRaster,
} from "./standardRaster";

/** 11x11 unit grid: (0.5, 0.5) sits exactly on node (5, 5). */
const UNIT: BBoxLike = { minlon: 0, minlat: 0, maxlon: 1, maxlat: 1 };
const COLS = 11;
const ROWS = 11;
const SIGMA = 0.35;

const CENTER = { lon: 0.5, lat: 0.5 };

/** One representative spec per buildScoredField kernel kind. */
const KERNELS: { name: string; spec: BonusSpec; points: ScoredPoint[] }[] = [
  { name: "area", spec: { kind: "area", half: 3 }, points: [{ ...CENTER, a: 10 }] },
  {
    name: "trips",
    spec: { kind: "trips", half: 1500, modeBonus: 10, minModes: 2 },
    points: [
      { ...CENTER, t: 900, tags: { highway: "bus_stop" } },
      { lon: 0.51, lat: 0.5, t: 900, tags: { railway: "tram_stop" } },
    ],
  },
  {
    name: "variety",
    spec: { kind: "variety", key: "school", values: ["primary", "secondary"], per: 5, cap: 15 },
    points: [
      { ...CENTER, tags: { school: "primary" } },
      { lon: 0.52, lat: 0.5, tags: { school: "secondary" } },
    ],
  },
  { name: "avoid", spec: { kind: "avoid", half: 0.21 }, points: [{ ...CENTER }] },
  { name: "quiet", spec: { kind: "quiet", halfM: 300 }, points: [{ ...CENTER }] },
  { name: "sparse", spec: { kind: "sparse", half: 150 }, points: [{ ...CENTER }] },
  {
    name: "cover",
    spec: { kind: "cover", sigma: 1 },
    points: [{ ...CENTER, tags: { ulatus_m: "500" } }],
  },
  {
    name: "bands",
    spec: { kind: "bands", radiusM: 500, one: 60, twoThree: 70, fourPlus: 80 },
    points: [{ ...CENTER }, { lon: 0.5001, lat: 0.5 }, { lon: 0.5002, lat: 0.5 }],
  },
  {
    name: "tileband",
    spec: {
      kind: "tileband", radiusM: 1000, minTests: 5,
      weak: 35, mid: 55, strong: 75, top: 85,
    },
    points: [{ ...CENTER, tags: { avg_d: "200000", tests: "10" } }],
  },
  {
    name: "qbands",
    spec: { kind: "qbands", radiusM: 1000 },
    points: [{ ...CENTER, q: 70 }],
  },
  {
    name: "dbands",
    spec: { kind: "dbands", radiusM: 2000, edges: [[500, 80], [1000, 65], [2000, 50]] },
    points: [{ ...CENTER }],
  },
  { name: "pins", spec: { kind: "pins" }, points: [{ ...CENTER }] },
];

function buildKernel(name: string): ScoredField {
  const k = KERNELS.find((e) => e.name === name);
  if (!k) throw new Error(`no kernel ${name}`);
  return buildScoredField(k.points, UNIT, COLS, ROWS, SIGMA, k.spec);
}

describe("raster contract (range, nodata)", () => {
  it("unknown sentinel is 255 and valid bytes never reach it", () => {
    expect(STANDARD_UNKNOWN).toBe(255);
    expect(STANDARD_MAX).toBe(100);
    for (let v = 0; v <= 100; v++) expect(encodeStandardValue(v)).toBe(v);
  });

  it("null/NaN/non-finite encode to unknown and decode back to null", () => {
    expect(encodeStandardValue(null)).toBe(255);
    expect(encodeStandardValue(NaN)).toBe(255);
    expect(encodeStandardValue(Infinity)).toBe(255);
    expect(decodeStandardValue(255)).toBeNull();
    for (let b = 0; b <= 100; b++) expect(decodeStandardValue(b)).toBe(b);
  });

  it("out-of-range values clamp instead of wrapping into the sentinel", () => {
    expect(encodeStandardValue(-5)).toBe(0);
    expect(encodeStandardValue(142)).toBe(100);
  });
});

describe.each(KERNELS.map((k) => k.name))("kernel adapter: %s", (name) => {
  it("round-trips every node through the standard byte", () => {
    const s = buildKernel(name);
    const r = standardFromScoredField(s);
    expect(r.bytes.length).toBe(COLS * ROWS);
    for (let iy = 0; iy < ROWS; iy++) {
      for (let ix = 0; ix < COLS; ix++) {
        const v = scoredAt(s, ix, iy);
        const b = r.bytes[iy * COLS + ix];
        if (v === null) expect(b).toBe(STANDARD_UNKNOWN);
        else {
          expect(b).toBeLessThanOrEqual(100);
          expect(b).toBe(encodeStandardValue(v));
          expect(decodeStandardValue(b)).toBe(b);
        }
      }
    }
  });

  it("propagates nodata: unknown in, unknown out, never a faked number", () => {
    const s = buildKernel(name);
    const r = standardFromScoredField(s);
    let known = 0;
    let unknown = 0;
    for (const b of r.bytes) {
      if (b === STANDARD_UNKNOWN) unknown++;
      else {
        known++;
        expect(b).toBeLessThanOrEqual(100);
      }
    }
    if (name === "pins") {
      // Pins are markers only by decision: the field stays unknown everywhere.
      expect(known).toBe(0);
      expect(unknown).toBe(COLS * ROWS);
    } else {
      expect(known).toBeGreaterThan(0);
    }
    // Sparse/quiet/variety are legitimately known everywhere (measured
    // open / calm / nearby); kernels with gaps must keep them unknown.
    if (["area", "trips", "cover", "bands", "tileband", "qbands", "dbands", "avoid"].includes(name)) {
      expect(unknown).toBeGreaterThan(0);
    }
  });

  it("empty input stays all-unknown: nothing loaded is never faked", () => {
    const k = KERNELS.find((e) => e.name === name);
    if (!k) throw new Error(`no kernel ${name}`);
    const s = buildScoredField([], UNIT, COLS, ROWS, SIGMA, k.spec);
    const r = standardFromScoredField(s);
    expect([...r.bytes].every((b) => b === STANDARD_UNKNOWN)).toBe(true);
  });

  it("keeps the source grid node-for-node", () => {
    const s = buildKernel(name);
    const r = standardFromScoredField(s);
    expect(conformsToGrid(r, { cols: COLS, rows: ROWS, bbox: UNIT })).toBe(true);
    expect(conformsToGrid(r, { cols: COLS + 1, rows: ROWS, bbox: UNIT })).toBe(false);
    expect(
      conformsToGrid(r, {
        cols: COLS, rows: ROWS,
        bbox: { ...UNIT, maxlon: UNIT.maxlon + 0.1 },
      }),
    ).toBe(false);
  });

  it("holds pixel parity with the color rendering (same value, same rank)", () => {
    const s = buildKernel(name);
    const r = standardFromScoredField(s);
    const pairs: [number, number][] = [];
    for (let iy = 0; iy < ROWS; iy++) {
      for (let ix = 0; ix < COLS; ix++) {
        const v = scoredAt(s, ix, iy);
        if (v === null) continue;
        const b = r.bytes[iy * COLS + ix];
        pairs.push([v, b]);
        // The byte feeds the same LUT index the value would. Byte rounding
        // (<=0.5 value units) amplifies through the 255-entry LUT, so the
        // index can differ by up to 2 steps at a .5 boundary — never more.
        const lutIdx = (x: number) => Math.round(Math.min(1, Math.max(0, x / 100)) * 255);
        expect(Math.abs(lutIdx(b) - lutIdx(v))).toBeLessThanOrEqual(2);
      }
    }
    if (pairs.length === 0) return; // pins: nothing rendered, nothing to rank
    // Rank parity: sorting by value and by byte gives the same order —
    // the monochrome ramp can never flip two pixels the LUT orders.
    const byValue = [...pairs].sort((a, b2) => a[0] - b2[0]);
    for (let i = 1; i < byValue.length; i++) {
      expect(byValue[i][1]).toBeGreaterThanOrEqual(byValue[i - 1][1]);
    }
  });
});

describe("white end of goodness (inverted layers included)", () => {
  it("avoid: far reads whiter than near (white = safe = good)", () => {
    // City-block bbox so the half=0.21 km gradient spans the grid.
    const city: BBoxLike = { minlon: 24.74, minlat: 59.43, maxlon: 24.76, maxlat: 59.44 };
    const s = buildScoredField(
      [{ lon: 24.75, lat: 59.435 }],
      city, COLS, ROWS, SIGMA, { kind: "avoid", half: 0.21 },
    );
    const r = standardFromScoredField(s);
    const near = r.bytes[5 * COLS + 6]; // one cell off the feature
    const far = r.bytes[0]; // corner, farthest
    expect(near).not.toBe(STANDARD_UNKNOWN);
    expect(far).not.toBe(STANDARD_UNKNOWN);
    expect(far).toBeGreaterThan(near);
    expect(far).toBeGreaterThan(50);
  });

  it("quiet: calm far from the source reads whiter than the source edge", () => {
    const r = standardFromScoredField(buildKernel("quiet"));
    const on = r.bytes[5 * COLS + 5];
    const far = r.bytes[0];
    expect(on).toBe(0); // black on the source
    expect(far).toBeGreaterThan(on);
  });

  it("grayscale ramp: 100 is white, 0 is black, unknown is transparent", () => {
    const mk = (byte: number): StandardRaster => ({
      cols: 1, rows: 1, bbox: UNIT, step_m: null, bytes: new Uint8Array([byte]),
    });
    const white = standardToGrayscaleRgba(mk(100));
    expect([...white]).toEqual([255, 255, 255, 255]);
    const black = standardToGrayscaleRgba(mk(0));
    expect([...black]).toEqual([0, 0, 0, 255]);
    const nodata = standardToGrayscaleRgba(mk(255));
    expect(nodata[3]).toBe(0);
  });

  it("grayscale luminance never decreases with goodness", () => {
    const bytes = new Uint8Array(101);
    for (let b = 0; b <= 100; b++) bytes[b] = b;
    const rgba = standardToGrayscaleRgba({ cols: 101, rows: 1, bbox: UNIT, step_m: null, bytes });
    for (let b = 1; b <= 100; b++) {
      expect(rgba[b * 4]).toBeGreaterThanOrEqual(rgba[(b - 1) * 4]);
    }
  });
});

describe("distance-field and value-grid adapters", () => {
  it("proximity kernel round-trips; empty input stays all-unknown", () => {
    const f = buildDistanceField([{ ...CENTER }], UNIT, COLS, ROWS);
    const r = standardFromDistanceField(f, SIGMA);
    expect(r.bytes[5 * COLS + 5]).toBe(100);
    expect(r.bytes.length).toBe(COLS * ROWS);
    const empty = standardFromDistanceField(buildDistanceField([], UNIT, COLS, ROWS), SIGMA);
    expect([...empty.bytes].every((b) => b === STANDARD_UNKNOWN)).toBe(true);
  });

  it("value grid round-trips; data-free grids stay unknown", () => {
    // One scored cell splats (normalized average) across this small grid.
    const g = accumulateGrid([{ lon: 0.5, lat: 0.5, score: 80 }], UNIT, COLS, ROWS);
    const r = standardFromValueGrid(g);
    expect(r.bytes[5 * COLS + 5]).toBe(80);
    expect(r.bytes[0]).toBe(80);
    const blank = standardFromValueGrid(accumulateGrid([], UNIT, COLS, ROWS));
    expect([...blank.bytes].every((b) => b === STANDARD_UNKNOWN)).toBe(true);
  });
});

describe("walk-raster adapter (loadLayerRaster / fetchWindow grid)", () => {
  const doc = () => {
    const raw = new Uint8Array(COLS * ROWS).fill(255);
    raw[5 * COLS + 5] = 87;
    raw[0] = 12;
    return {
      cols: COLS, rows: ROWS, bbox: UNIT, step_m: 12,
      half: 15, sigma: 0.35, per: 0, cap: 0,
      unknown: 255, dtype: "uint8",
      data: Buffer.from(raw).toString("base64"),
    };
  };

  it("passes cleanRaster-accepted docs through byte-identical (grid + bytes)", () => {
    const d = doc();
    expect(cleanRaster(d)).not.toBeNull();
    const r = standardFromWalkRaster(d as never);
    expect(r).not.toBeNull();
    const raw = Buffer.from(d.data, "base64");
    expect([...(r as StandardRaster).bytes]).toEqual([...raw]);
    // Common-grid check: identical grid to the served doc, step carried.
    expect(conformsToGrid(r as StandardRaster, { cols: COLS, rows: ROWS, bbox: UNIT })).toBe(true);
    expect((r as StandardRaster).step_m).toBe(12);
    // Nodata survives positionally.
    expect((r as StandardRaster).bytes[1]).toBe(STANDARD_UNKNOWN);
    expect((r as StandardRaster).bytes[5 * COLS + 5]).toBe(87);
  });

  it("rejects corrupt raster docs instead of faking a field", () => {
    expect(standardFromWalkRaster({ ...doc(), data: "!!!not-base64!!!" } as never)).toBeNull();
    const short = Buffer.from(new Uint8Array([1, 2, 3])).toString("base64");
    expect(standardFromWalkRaster({ ...doc(), data: short } as never)).toBeNull();
  });
});
