// Regression tests for the aggregate agreement view (#810): combine
// modes on synthetic standard rasters, weight sensitivity, and nodata
// honesty (unknown never averaged in, never rendered mid-orange).

import { describe, expect, it } from "vitest";
import type { BBoxLike } from "./layers";
import {
  AGREE_ALPHA,
  CONTEST_SPREAD,
  agreementColorFor,
  aggregateGridFor,
  aggregateToRgba,
  combineStandardRasters,
  recalibratedMean,
  sampleAggregate,
  viewportScaleFor,
  type AggregateField,
  type AggregateInput,
  type CombineMode,
  type ViewportScale,
} from "./aggregateRaster";
import { STANDARD_UNKNOWN, type StandardRaster } from "./standardRaster";

const UNIT: BBoxLike = { minlon: 0, minlat: 0, maxlon: 1, maxlat: 1 };
const COLS = 8;
const ROWS = 6;

function mkRaster(fill: (ix: number, iy: number) => number): StandardRaster {
  const bytes = new Uint8Array(COLS * ROWS);
  for (let iy = 0; iy < ROWS; iy++) {
    for (let ix = 0; ix < COLS; ix++) {
      bytes[iy * COLS + ix] = fill(ix, iy);
    }
  }
  return { cols: COLS, rows: ROWS, bbox: { ...UNIT }, step_m: null, bytes };
}

const GRID = { cols: COLS, rows: ROWS, bbox: UNIT };
const good = (w = 1): AggregateInput => ({ raster: mkRaster(() => 90), weight: w });
const bad = (w = 1): AggregateInput => ({ raster: mkRaster(() => 10), weight: w });
const mid = (w = 1): AggregateInput => ({ raster: mkRaster(() => 50), weight: w });

const MODES: CombineMode[] = ["average", "multiply", "overlay"];

describe("combine: agreement on synthetic rasters", () => {
  it("unanimous good reads high, unanimous bad reads low (every mode)", () => {
    for (const mode of MODES) {
      const g = combineStandardRasters([good(), good()], GRID, mode);
      const b = combineStandardRasters([bad(), bad()], GRID, mode);
      for (let k = 0; k < COLS * ROWS; k++) {
        expect(g.mean[k]).toBeGreaterThan(75);
        expect(b.mean[k]).toBeLessThan(25);
        expect(g.known[k]).toBe(2);
        expect(g.spread[k]).toBe(0);
      }
    }
  });

  it("average of good+bad lands mid (contested), not at an extreme", () => {
    const f = combineStandardRasters([good(), bad()], GRID, "average");
    for (let k = 0; k < COLS * ROWS; k++) {
      expect(f.mean[k]).toBe(50);
      expect(f.spread[k]).toBe(40); // full split, above CONTEST_SPREAD
    }
    expect(CONTEST_SPREAD).toBeLessThan(40);
  });

  it("multiply is AND-like: never above the average on the same input", () => {
    const layers = [good(), mid(), bad()];
    const avg = combineStandardRasters(layers, GRID, "average");
    const mul = combineStandardRasters(layers, GRID, "multiply");
    for (let k = 0; k < COLS * ROWS; k++) {
      expect(mul.mean[k]).toBeLessThanOrEqual(avg.mean[k] + 1e-9);
    }
  });

  it("multiply: one known-zero layer zeroes the cell (strict, documented)", () => {
    const zero: AggregateInput = { raster: mkRaster(() => 0), weight: 1 };
    const f = combineStandardRasters([good(), zero], GRID, "multiply");
    for (let k = 0; k < COLS * ROWS; k++) expect(f.mean[k]).toBe(0);
  });

  it("overlay: unanimous good stays green-side, unanimous bad red-side", () => {
    const g = combineStandardRasters([good(), good()], GRID, "overlay");
    const b = combineStandardRasters([bad(), bad()], GRID, "overlay");
    for (let k = 0; k < COLS * ROWS; k++) {
      expect(g.mean[k]).toBeGreaterThan(50);
      expect(b.mean[k]).toBeLessThan(50);
    }
  });
});

describe("combine: weights", () => {
  it("weight 0 excludes the layer everywhere (every mode)", () => {
    for (const mode of MODES) {
      const f = combineStandardRasters([good(), { ...bad(), weight: 0 }], GRID, mode);
      for (let k = 0; k < COLS * ROWS; k++) {
        expect(f.known[k]).toBe(1);
      }
      // Same as the good layer alone.
      const solo = combineStandardRasters([good()], GRID, mode);
      for (let k = 0; k < COLS * ROWS; k++) {
        expect(f.mean[k]).toBe(solo.mean[k]);
      }
    }
  });

  it("weight changes re-render: shifting weight moves the average", () => {
    const low = combineStandardRasters([good(3), bad(1)], GRID, "average");
    const high = combineStandardRasters([good(1), bad(3)], GRID, "average");
    expect(low.mean[0]).toBe(70);
    expect(high.mean[0]).toBe(30);
    expect(low.mean[0]).not.toBe(high.mean[0]);
  });

  it("weight changes re-render the overlay coats too", () => {
    const a = combineStandardRasters([good(2), bad(1)], GRID, "overlay");
    const b = combineStandardRasters([good(1), bad(2)], GRID, "overlay");
    expect(a.mean[0]).not.toBe(b.mean[0]);
    expect(a.mean[0]).toBeGreaterThan(b.mean[0]);
  });

  it("non-conforming grids never blend in silently", () => {
    const other: AggregateInput = {
      raster: {
        cols: COLS + 1,
        rows: ROWS,
        bbox: { ...UNIT },
        step_m: null,
        bytes: new Uint8Array((COLS + 1) * ROWS).fill(100),
      },
      weight: 5,
    };
    const f = combineStandardRasters([mid(), other], GRID, "average");
    for (let k = 0; k < COLS * ROWS; k++) {
      expect(f.mean[k]).toBe(50); // the 100-valued intruder ignored
      expect(f.known[k]).toBe(1);
    }
  });
});

describe("combine: nodata honesty", () => {
  it("unknown layers never drag the average: 100 + unknown = 100", () => {
    const unknown: AggregateInput = {
      raster: mkRaster(() => STANDARD_UNKNOWN),
      weight: 1,
    };
    for (const mode of MODES) {
      const f = combineStandardRasters(
        [{ raster: mkRaster(() => 100), weight: 1 }, unknown],
        GRID,
        mode,
      );
      for (let k = 0; k < COLS * ROWS; k++) {
        expect(f.mean[k]).toBe(100);
        expect(f.known[k]).toBe(1);
      }
    }
  });

  it("cells no layer covers stay unknown and render transparent", () => {
    const left: AggregateInput = {
      raster: mkRaster((ix) => (ix < COLS / 2 ? 80 : STANDARD_UNKNOWN)),
      weight: 1,
    };
    const right: AggregateInput = {
      raster: mkRaster((ix) => (ix >= COLS / 2 ? 80 : STANDARD_UNKNOWN)),
      weight: 1,
    };
    // Knock out one cell in BOTH layers: true coverage hole.
    left.raster.bytes[0] = STANDARD_UNKNOWN;
    right.raster.bytes[0] = STANDARD_UNKNOWN;
    for (const mode of MODES) {
      const f = combineStandardRasters([left, right], GRID, mode);
      expect(Number.isNaN(f.mean[0])).toBe(true);
      expect(f.known[0]).toBe(0);
      // Neighbours with exactly one known layer read that layer, not
      // a diluted half.
      expect(f.mean[1]).toBe(80);
      const rgba = aggregateToRgba(f);
      expect(rgba[3]).toBe(0); // hole: transparent, never mid-orange
      expect(rgba[1 * 4 + 3]).toBe(AGREE_ALPHA);
    }
  });

  it("all-unknown input yields an all-transparent field", () => {
    const f = combineStandardRasters(
      [{ raster: mkRaster(() => STANDARD_UNKNOWN), weight: 1 }],
      GRID,
      "average",
    );
    const rgba = aggregateToRgba(f);
    for (let k = 0; k < COLS * ROWS; k++) {
      expect(Number.isNaN(f.mean[k])).toBe(true);
      expect(rgba[k * 4 + 3]).toBe(0);
    }
  });

  it("empty input renders nothing (no faked coverage)", () => {
    const f = combineStandardRasters([], GRID, "average");
    const rgba = aggregateToRgba(f);
    expect([...rgba].every((v, i) => (i % 4 === 3 ? v === 0 : true))).toBe(true);
  });
});

describe("agreement coloring", () => {
  it("unanimous good reads green, unanimous bad reads red", () => {
    const [r, g, b] = agreementColorFor(90, 0);
    expect(g).toBeGreaterThan(r);
    expect(g).toBeGreaterThan(b);
    const [r2, g2] = agreementColorFor(10, 0);
    expect(r2).toBeGreaterThan(g2);
  });

  it("middling mean reads orange-ish (red high, green mid, blue low)", () => {
    const [r, g, b] = agreementColorFor(50, 0);
    expect(r).toBeGreaterThan(200);
    expect(g).toBeGreaterThan(100);
    expect(g).toBeLessThan(r);
    expect(b).toBeLessThan(60);
  });

  it("disagreement pulls a high mean toward orange (contested)", () => {
    const calm = agreementColorFor(90, 0);
    const split = agreementColorFor(90, 40);
    // Contested: red-green gap shrinks toward the orange balance.
    expect(Math.abs(split[0] - split[1])).toBeLessThan(Math.abs(calm[0] - calm[1]));
    // Fully contested agrees with the middling cell.
    expect(split).toEqual(agreementColorFor(50, 0));
  });

  it("ramp endpoints match the documented brand colors", () => {
    expect(agreementColorFor(100, 0)).toEqual([22, 163, 74]);
    expect(agreementColorFor(0, 0)).toEqual([220, 38, 38]);
  });
});

describe("hover readback + grid helper", () => {
  it("sampleAggregate reads the cell, null on nodata or outside", () => {
    const f = combineStandardRasters([good(), bad()], GRID, "average");
    const hit = sampleAggregate(f, 0.5, 0.5);
    expect(hit).not.toBeNull();
    expect(hit?.score).toBe(50);
    expect(hit?.known).toBe(2);
    expect(sampleAggregate(f, 5, 5)).toBeNull();
    const hole = combineStandardRasters(
      [{ raster: mkRaster(() => STANDARD_UNKNOWN), weight: 1 }],
      GRID,
      "average",
    );
    expect(sampleAggregate(hole, 0.5, 0.5)).toBeNull();
  });
});

describe("viewport recalibration (#819)", () => {
  const grad = (): AggregateField =>
    combineStandardRasters(
      [
        { raster: mkRaster((ix) => 60 + ix * 4), weight: 1 }, // 60..88 W-E
        { raster: mkRaster(() => 70), weight: 1 },
      ],
      GRID,
      "average",
    );

  it("viewportScaleFor spans the finite means, ignoring nodata", () => {
    const f = grad();
    const s = viewportScaleFor(f);
    expect(s).not.toBeNull();
    // Column means run (60+70)/2 .. (88+70)/2 = 65..79.
    expect(s?.min).toBeCloseTo(65, 9);
    expect(s?.max).toBeCloseTo(79, 9);
  });

  it("viewportScaleFor is null when nothing is known", () => {
    const hole = combineStandardRasters(
      [{ raster: mkRaster(() => STANDARD_UNKNOWN), weight: 1 }],
      GRID,
      "average",
    );
    expect(viewportScaleFor(hole)).toBeNull();
  });

  it("recalibratedMean maps best visible to 100 and worst to 0", () => {
    const scale: ViewportScale = { min: 65, max: 79 };
    expect(recalibratedMean(79, scale)).toBe(100);
    expect(recalibratedMean(65, scale)).toBe(0);
    expect(recalibratedMean(72, scale)).toBeCloseTo(50, 9);
  });

  it("uniform viewports keep the absolute value (no flip to orange)", () => {
    expect(recalibratedMean(80, { min: 80, max: 80 })).toBe(80);
    expect(recalibratedMean(80, null)).toBe(80);
    expect(recalibratedMean(80, undefined)).toBe(80);
  });

  it("best visible cell reads green, worst reads red — even in a narrow band", () => {
    const scale: ViewportScale = { min: 65, max: 79 };
    const [br, bg] = agreementColorFor(79, 0, scale);
    expect(bg).toBeGreaterThan(br); // best visible: green
    const [wr, wg] = agreementColorFor(65, 0, scale);
    expect(wr).toBeGreaterThan(wg); // worst visible: red
  });

  it("recalibrated paint spans the ramp: worst red, best green", () => {
    const f = grad();
    const rgba = aggregateToRgba(f, viewportScaleFor(f));
    // West column (worst visible) reads red-dominant, east (best)
    // green-dominant — a narrow absolute band still spans the ramp.
    const west = 0 * 4;
    const east = (COLS - 1) * 4;
    expect(rgba[west]).toBeGreaterThan(rgba[west + 1]);
    expect(rgba[east + 1]).toBeGreaterThan(rgba[east]);
    expect(rgba[west + 3]).toBe(AGREE_ALPHA);
    expect(rgba[east + 3]).toBe(AGREE_ALPHA);
  });

  it("nodata stays transparent under recalibration, never an endpoint", () => {
    const left: AggregateInput = {
      raster: mkRaster((ix) => (ix < COLS / 2 ? 80 : STANDARD_UNKNOWN)),
      weight: 1,
    };
    const f = combineStandardRasters([left], GRID, "average");
    const rgba = aggregateToRgba(f, viewportScaleFor(f));
    const hole = ((ROWS - 1) * COLS + (COLS - 1)) * 4;
    expect(rgba[hole + 3]).toBe(0);
  });

  it("contested spread still pulls a best-visible cell to orange", () => {
    // Best visible cell with full disagreement reads orange, like the
    // middling cell — the spread pull uses raw goodness points.
    const best = agreementColorFor(79, 40, { min: 65, max: 79 });
    expect(best).toEqual(agreementColorFor(50, 0));
  });

  it("omitting the scale keeps absolute colors (existing callers)", () => {
    const f = combineStandardRasters([good()], GRID, "average");
    const rgba = aggregateToRgba(f);
    expect(rgba[3]).toBe(AGREE_ALPHA);
    expect([rgba[0], rgba[1], rgba[2]]).toEqual(
      agreementColorFor(90, 0).map((v) => Math.round(v)),
    );
  });
});

describe("hover readback + grid helper", () => {
  it("aggregateGridFor preserves aspect and stays capped", () => {
    const g = aggregateGridFor(UNIT);
    expect(g.cols).toBeLessThanOrEqual(200);
    expect(g.rows).toBeGreaterThan(0);
    expect(g.rows).toBeLessThanOrEqual(512);
    // Estonia spans more E-W km than N-S: rows < cols, aspect kept.
    const estonia: BBoxLike = { minlon: 21.5, minlat: 57.5, maxlon: 28.5, maxlat: 60 };
    const e = aggregateGridFor(estonia);
    expect(e.rows).toBeLessThan(e.cols);
    expect(e.rows / e.cols).toBeCloseTo(276 / 405, 1);
  });
});
