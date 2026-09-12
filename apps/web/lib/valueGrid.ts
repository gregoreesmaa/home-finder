// Data-space value field for the shader heat: scored cells are splatted
// with a Gaussian kernel onto a lon/lat grid, normalized (average, never
// pileup), with per-node coverage so data-free areas render transparent.
// Equirectangular over the bbox — fine at Estonia's span for small cells.

import type { BBoxLike } from "./layers";
import { colorForValue } from "./valueScale";

export interface GridInput {
  lon: number;
  lat: number;
  score: number; // 0..100
}

/** Kernel sigma in grid cells: gap-free for ~3-cell point spacing. */
const SIGMA_CELLS = 1.5;
const COVER_EPS = 1e-6;

/**
 * Gaussian weight splat with a true-kilometer sigma (anisotropic cells):
 * returns Σw per node — the agglomeration substrate (extras = Σw − 1).
 */
export function splatWeights(
  points: { lon: number; lat: number }[],
  bbox: BBoxLike,
  cols: number,
  rows: number,
  sigmaKm: number,
): Float64Array {
  return splatBoth(points, bbox, cols, rows, sigmaKm, () => 1, 3).weights;
}

/**
 * Weighted splat: returns Σ v·k per node (the values accumulator) for a
 * per-point value function. Powers (v = w^p with σ/√p) accumulate exactly.
 * radiusSigma truncates the kernel (default 3); the power score passes 5 so
 * the p-th root cannot turn the cutoff into a visible cliff.
 */
export function splatValues(
  points: { lon: number; lat: number }[],
  bbox: BBoxLike,
  cols: number,
  rows: number,
  sigmaKm: number,
  valueOf: (p: { lon: number; lat: number }) => number,
  radiusSigma = 3,
): Float64Array {
  return splatBoth(points, bbox, cols, rows, sigmaKm, valueOf, radiusSigma).values;
}

function splatBoth(
  points: { lon: number; lat: number }[],
  bbox: BBoxLike,
  cols: number,
  rows: number,
  sigmaKm: number,
  valueOf: (p: { lon: number; lat: number }) => number,
  radiusSigma: number,
): { values: Float64Array; weights: Float64Array } {
  const spanLon = bbox.maxlon - bbox.minlon;
  const spanLat = bbox.maxlat - bbox.minlat;
  const midLat = ((bbox.minlat + bbox.maxlat) / 2) * (Math.PI / 180);
  const kmPerCellX = ((spanLon * 111.32 * Math.cos(midLat)) / cols) || 1;
  const kmPerCellY = ((spanLat * 110.57) / rows) || 1;
  const nodes: { x: number; y: number; v: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lon) || !Number.isFinite(p.lat)) continue;
    const v = valueOf(p);
    if (!Number.isFinite(v) || v === 0) continue;
    nodes.push({
      x: ((p.lon - bbox.minlon) / spanLon) * (cols - 1),
      y: ((p.lat - bbox.minlat) / spanLat) * (rows - 1),
      v,
    });
  }
  return splat(
    nodes,
    cols,
    rows,
    Math.max(0.4, sigmaKm / kmPerCellX),
    Math.max(0.4, sigmaKm / kmPerCellY),
    radiusSigma,
  );
}

export interface ValueGrid {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  values: Float64Array;
  weights: Float64Array;
  /** Normalized 0..100 value, or null where nothing was splatted. */
  valueAt(ix: number, iy: number): number | null;
  /** 0..1 confidence; drives pixel alpha. */
  coverageAt(ix: number, iy: number): number;
}

/** Gaussian splat of scored nodes; anisotropic sigma in grid cells. */
function splat(
  nodes: { x: number; y: number; v: number }[],
  cols: number,
  rows: number,
  sigmaX: number,
  sigmaY: number,
  radiusSigma = 3,
): { values: Float64Array; weights: Float64Array } {
  const values = new Float64Array(cols * rows);
  const weights = new Float64Array(cols * rows);
  const radiusX = Math.max(1, Math.ceil(radiusSigma * sigmaX));
  const radiusY = Math.max(1, Math.ceil(radiusSigma * sigmaY));
  for (const n of nodes) {
    const x0 = Math.max(0, Math.floor(n.x - radiusX));
    const x1 = Math.min(cols - 1, Math.ceil(n.x + radiusX));
    const y0 = Math.max(0, Math.floor(n.y - radiusY));
    const y1 = Math.min(rows - 1, Math.ceil(n.y + radiusY));
    for (let iy = y0; iy <= y1; iy++) {
      for (let ix = x0; ix <= x1; ix++) {
        const dx = (ix - n.x) / sigmaX;
        const dy = (iy - n.y) / sigmaY;
        const w = Math.exp(-(dx * dx + dy * dy) / 2);
        const k = iy * cols + ix;
        values[k] += w * n.v;
        weights[k] += w;
      }
    }
  }
  return { values, weights };
}

export function accumulateGrid(
  cells: GridInput[],
  bbox: BBoxLike,
  cols: number,
  rows: number,
  sigmaCells = SIGMA_CELLS,
): ValueGrid {
  const spanLon = bbox.maxlon - bbox.minlon;
  const spanLat = bbox.maxlat - bbox.minlat;
  const nodes: { x: number; y: number; v: number }[] = [];
  for (const c of cells) {
    if (!Number.isFinite(c.lon) || !Number.isFinite(c.lat)) continue;
    if (!Number.isFinite(c.score)) continue;
    nodes.push({
      x: ((c.lon - bbox.minlon) / spanLon) * (cols - 1),
      y: ((c.lat - bbox.minlat) / spanLat) * (rows - 1),
      v: Math.min(100, Math.max(0, c.score)),
    });
  }
  const { values, weights } = splat(nodes, cols, rows, sigmaCells, sigmaCells);

  const at = (ix: number, iy: number): number => weights[iy * cols + ix];
  return {
    cols,
    rows,
    bbox,
    values,
    weights,
    valueAt(ix, iy) {
      if (ix < 0 || iy < 0 || ix >= cols || iy >= rows) return null;
      const w = at(ix, iy);
      return w > COVER_EPS ? values[iy * cols + ix] / w : null;
    },
    coverageAt(ix, iy) {
      if (ix < 0 || iy < 0 || ix >= cols || iy >= rows) return 0;
      return Math.min(1, at(ix, iy)); // kernel peak is 1: full cover at a cell
    },
  };
}

/**
 * Bilinear readback for the hover readout: exact interpolated value under
 * any lon/lat, or null where there is no data. Mirrors the GPU sampling.
 */
export function sampleBilinear(
  grid: ValueGrid,
  lon: number,
  lat: number,
): { value: number; coverage: number } | null {
  const { cols, rows, bbox } = grid;
  const gx = ((lon - bbox.minlon) / (bbox.maxlon - bbox.minlon)) * (cols - 1);
  const gy = ((lat - bbox.minlat) / (bbox.maxlat - bbox.minlat)) * (rows - 1);
  if (gx < 0 || gy < 0 || gx > cols - 1 || gy > rows - 1) return null;
  const x0 = Math.floor(gx);
  const y0 = Math.floor(gy);
  const x1 = Math.min(cols - 1, x0 + 1);
  const y1 = Math.min(rows - 1, y0 + 1);
  const fx = gx - x0;
  const fy = gy - y0;
  let swv = 0;
  let sw = 0;
  let cov = 0;
  const corners: [number, number, number][] = [
    [x0, y0, (1 - fx) * (1 - fy)],
    [x1, y0, fx * (1 - fy)],
    [x0, y1, (1 - fx) * fy],
    [x1, y1, fx * fy],
  ];
  for (const [ix, iy, f] of corners) {
    const w = grid.weights[iy * cols + ix];
    if (w <= COVER_EPS) continue;
    swv += f * grid.values[iy * cols + ix];
    sw += f * w;
    cov += f * Math.min(1, w);
  }
  if (sw <= COVER_EPS) return null;
  return { value: swv / sw, coverage: cov };
}

/** Byte RGBA texture upload: LUT color + coverage alpha (0 = no data). */
export function gridToRgba(grid: ValueGrid): Uint8ClampedArray {
  const out = new Uint8ClampedArray(grid.cols * grid.rows * 4);
  for (let iy = 0; iy < grid.rows; iy++) {
    for (let ix = 0; ix < grid.cols; ix++) {
      const k = (iy * grid.cols + ix) * 4;
      const v = grid.valueAt(ix, iy);
      if (v === null) {
        out[k + 3] = 0;
        continue;
      }
      const [r, g, b] = colorForValue(v);
      out[k] = r;
      out[k + 1] = g;
      out[k + 2] = b;
      out[k + 3] = Math.round(grid.coverageAt(ix, iy) * 255);
    }
  }
  return out;
}
