// Combined aggregate agreement view (#810).
//
// Every goodness layer already speaks one language: the standard byte
// raster from #809 (0..100 goodness, white = best, 255 = unknown, never
// blended). This module combines those rasters cell-by-cell into one
// agreement field and paints it green/red/orange:
//
// - green where most layers agree the place is good,
// - red where most agree it is bad,
// - orange-ish where it is ~50/50 (middling mean OR layers disagree).
//
// NODATA HONESTY: only layers with data (byte != 255) at a cell count
// toward that cell. A cell no layer covers stays unknown and renders
// transparent — never mid-orange. A layer with weight 0 is excluded
// everywhere, same as absent.

import type { BBoxLike } from "./layers";
import {
  STANDARD_UNKNOWN,
  conformsToGrid,
  type StandardRaster,
} from "./standardRaster";

/** Combining modes, switchable live on the aggregate route. */
export type CombineMode = "average" | "multiply" | "overlay";
export const COMBINE_MODES: CombineMode[] = ["average", "multiply", "overlay"];

/** Human one-liners for the mode switch (Estonian, like the /layers UI). */
export const COMBINE_MODE_LABEL: Record<CombineMode, string> = {
  average: "Keskmine — kihtide kaalutud keskmine",
  multiply: "Korrutav — üks halb kiht tõmbab alla (range AND)",
  overlay: "Ülekate — iga kiht võimendab/vähendab jooksvalt",
};

/**
 * Weighted disagreement (std) at which a cell reads fully contested
 * (pure orange) regardless of its mean. Below it the base ramp shows;
 * above it the cell is orange. Judgment call: 25 goodness points is
 * roughly the gap between "hea" and "keskmine" on one layer.
 */
export const CONTEST_SPREAD = 25;

/** Ramp ends: unanimous bad / contested / unanimous good. */
export const AGREE_RED: readonly [number, number, number] = [220, 38, 38];
export const AGREE_ORANGE: readonly [number, number, number] = [245, 158, 11];
export const AGREE_GREEN: readonly [number, number, number] = [22, 163, 74];

/** Opaque where known (like scoredToRgba); unknown stays transparent. */
export const AGREE_ALPHA = 255;

export interface AggregateInput {
  raster: StandardRaster;
  /** Relative weight; <= 0 excludes the layer everywhere. */
  weight: number;
}

export interface AggregateField {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  /** Combined 0..100 score; NaN where no layer has data. */
  mean: Float64Array;
  /** Weighted std of the known raw values; NaN where nothing known. */
  spread: Float64Array;
  /** How many layers had data at the cell (weight > 0 and byte known). */
  known: Uint16Array;
}

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function lerp3(
  a: readonly [number, number, number],
  b: readonly [number, number, number],
  t: number,
): [number, number, number] {
  return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
}

/** Photoshop overlay on 0..1: boosts highs, crushes lows, 0.5 neutral. */
function overlayBlend(base: number, coat: number): number {
  return base < 0.5
    ? 2 * base * coat
    : 1 - 2 * (1 - base) * (1 - coat);
}

/**
 * Combine standard rasters on one shared grid. Layers whose grid does
 * not conform (or whose weight is <= 0 / non-finite) are skipped, never
 * resampled silently — the aggregate route builds every layer on the
 * same grid, so a skip always means a caller bug, not a data gap.
 */
export function combineStandardRasters(
  layers: AggregateInput[],
  grid: { cols: number; rows: number; bbox: BBoxLike },
  mode: CombineMode,
): AggregateField {
  const { cols, rows, bbox } = grid;
  const n = cols * rows;
  const mean = new Float64Array(n).fill(NaN);
  const spread = new Float64Array(n).fill(NaN);
  const known = new Uint16Array(n);
  const active = layers.filter(
    (l) => Number.isFinite(l.weight) && l.weight > 0 && conformsToGrid(l.raster, grid),
  );
  if (active.length === 0) {
    return { cols, rows, bbox: { ...bbox }, mean, spread, known };
  }
  for (let k = 0; k < n; k++) {
    let wSum = 0;
    let acc = 0;
    // Raw weighted mean of the known values: the disagreement
    // baseline, identical for every mode (a mode must never fake
    // consensus or dissent — spread measures the layers, not the
    // blend math).
    let rawMean = 0;
    if (mode === "multiply") {
      // Weighted geometric mean (AND-like): every known layer must
      // rate the cell well for the cell to read well. A known 0 from
      // any layer zeroes the cell — strict by decision, documented in
      // the mode label ("range AND").
      let logSum = 0;
      let zeroed = false;
      for (const l of active) {
        const b = l.raster.bytes[k];
        if (b === STANDARD_UNKNOWN) continue;
        if (b <= 0) {
          zeroed = true;
          wSum += l.weight;
          continue;
        }
        logSum += l.weight * Math.log(b / 100);
        wSum += l.weight;
      }
      if (wSum > 0) acc = zeroed ? 0 : 100 * Math.exp(logSum / wSum);
    } else if (mode === "overlay") {
      // Sequential overlay coats over neutral 50: each known layer
      // pulls the running value toward overlay(acc, v) with strength
      // = its share of the cell's known weight (unknown layers never
      // dilute the coats). Order is input (registry) order; weights
      // act as coat opacity, so weight edits re-render. From neutral
      // 50 a lone full-strength coat reproduces its layer exactly
      // (overlay(0.5, x) = x), so single coverage never shifts color.
      let cellW = 0;
      for (const l of active) {
        if (l.raster.bytes[k] !== STANDARD_UNKNOWN) cellW += l.weight;
      }
      acc = 50;
      for (const l of active) {
        const b = l.raster.bytes[k];
        if (b === STANDARD_UNKNOWN) continue;
        const alpha = cellW > 0 ? l.weight / cellW : 0;
        acc = lerp(acc, 100 * overlayBlend(acc / 100, b / 100), alpha);
        wSum += l.weight;
      }
    } else {
      for (const l of active) {
        const b = l.raster.bytes[k];
        if (b === STANDARD_UNKNOWN) continue;
        acc += l.weight * b;
        wSum += l.weight;
      }
      if (wSum > 0) acc /= wSum;
    }
    if (wSum === 0) continue; // no layer knows this cell: stays NaN
    mean[k] = acc;
    for (const l of active) {
      const b = l.raster.bytes[k];
      if (b === STANDARD_UNKNOWN) continue;
      rawMean += l.weight * b;
    }
    rawMean /= wSum;
    // Weighted disagreement around the raw mean over the same known
    // set, whatever the mode.
    let vSum = 0;
    for (const l of active) {
      const b = l.raster.bytes[k];
      if (b === STANDARD_UNKNOWN) continue;
      const d = b - rawMean;
      vSum += l.weight * d * d;
    }
    spread[k] = Math.sqrt(vSum / wSum);
    // known counts layers, not weight: "12 kihti" on hover.
    let c = 0;
    for (const l of active) {
      if (l.raster.bytes[k] !== STANDARD_UNKNOWN) c++;
    }
    known[k] = c;
  }
  return { cols, rows, bbox: { ...bbox }, mean, spread, known };
}

/**
 * Agreement color for one cell: red->orange->green ramp by mean, then
 * pulled toward orange by disagreement. Unanimous 90+ reads green,
 * unanimous 10- reads red, middling or split reads orange-ish.
 */
export function agreementColorFor(
  meanValue: number,
  spreadValue: number,
): [number, number, number] {
  const base =
    meanValue <= 50
      ? lerp3(AGREE_RED, AGREE_ORANGE, meanValue / 50)
      : lerp3(AGREE_ORANGE, AGREE_GREEN, (meanValue - 50) / 50);
  const t = Math.min(1, Math.max(0, spreadValue / CONTEST_SPREAD));
  return lerp3(base, AGREE_ORANGE, t);
}

/** Paint the agreement field; unknown cells stay transparent (alpha 0). */
export function aggregateToRgba(f: AggregateField): Uint8ClampedArray {
  const out = new Uint8ClampedArray(f.cols * f.rows * 4);
  for (let k = 0; k < f.cols * f.rows; k++) {
    const o = k * 4;
    const m = f.mean[k];
    if (!Number.isFinite(m) || f.known[k] === 0) {
      out[o + 3] = 0;
      continue;
    }
    const [r, g, b] = agreementColorFor(m, f.spread[k]);
    out[o] = Math.round(r);
    out[o + 1] = Math.round(g);
    out[o + 2] = Math.round(b);
    out[o + 3] = AGREE_ALPHA;
  }
  return out;
}

/** Nearest-node readback for hover: null outside the grid or on nodata. */
export function sampleAggregate(
  f: AggregateField,
  lon: number,
  lat: number,
): { score: number; spread: number; known: number } | null {
  const gx =
    ((lon - f.bbox.minlon) / (f.bbox.maxlon - f.bbox.minlon)) * (f.cols - 1);
  const gy =
    ((lat - f.bbox.minlat) / (f.bbox.maxlat - f.bbox.minlat)) * (f.rows - 1);
  if (!Number.isFinite(gx) || !Number.isFinite(gy)) return null;
  const ix = Math.round(gx);
  const iy = Math.round(gy);
  if (ix < 0 || iy < 0 || ix >= f.cols || iy >= f.rows) return null;
  const k = iy * f.cols + ix;
  if (f.known[k] === 0 || !Number.isFinite(f.mean[k])) return null;
  return { score: f.mean[k], spread: f.spread[k], known: f.known[k] };
}

/**
 * Shared aggregate grid for a view bbox: aspect-preserved, capped at
 * maxCols so ~90 per-layer EDT builds stay interactive (country view
 * lands near 200x115 ≈ 23k nodes).
 */
export function aggregateGridFor(
  bbox: BBoxLike,
  maxCols = 200,
): { cols: number; rows: number; bbox: BBoxLike } {
  const spanLon = Math.max(1e-9, bbox.maxlon - bbox.minlon);
  const spanLat = Math.max(1e-9, bbox.maxlat - bbox.minlat);
  const midLat = ((bbox.minlat + bbox.maxlat) / 2) * (Math.PI / 180);
  const kmX = spanLon * 111.32 * Math.cos(midLat);
  const kmY = spanLat * 110.57;
  const cols = Math.max(8, Math.min(maxCols, Math.round(maxCols)));
  const rows = Math.max(8, Math.min(512, Math.round((cols * kmY) / Math.max(kmX, 1e-9))));
  return { cols, rows, bbox: { ...bbox } };
}
