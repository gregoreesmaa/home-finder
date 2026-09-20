// Standard monochrome goodness raster (#809).
//
// Every `/layers` goodness map is its own kernel, color scale, and grid
// today (distanceField.ts, valueGrid.ts, valueScale.ts, walk-raster
// masters). This module standardises them to ONE composable byte raster
// so layers can later be averaged/blended (the aggregate agreement view
// is blocked on this contract). It changes no visible colors: the
// standard byte carries exactly the goodness value the color LUT
// already renders — same pixels, standard bytes.
//
// CONTRACT
// - Range: one byte per node, 0..100 = goodness (100 = best).
// - White end: white ALWAYS means the same end of goodness (best).
//   Every kernel already emits goodness-high scores, including the
//   inverted ones — `avoid` scores 0 on the feature → 100 far away,
//   `quiet` scores 0 on the source → 100 far away — so no inversion
//   happens at the byte level; byte 100 renders white, byte 0 black.
// - Grid: cols x rows nodes over bbox, corner-registered exactly like
//   the source field (fencepost nodes: node (ix,iy) sits at
//   minlon + ix/(cols-1)*spanLon, same as buildDistanceField and the
//   band kernels). `step_m` rides along when the source has one (walk
//   rasters), else null. Grid conformance = identical cols/rows/bbox.
// - Nodata: 255 = unknown (the WalkRasterDoc `unknown = 255`
//   precedent). Unknown stays unknown: never faked zero, never
//   averaged in as a number. Valid bytes never exceed 100, so 255 is
//   unambiguous.

import type { BBoxLike, WalkRasterDoc } from "./layers";
import {
  type DistanceField,
  type ScoredField,
  proximityValue,
  scoredAt,
} from "./distanceField";
import { type ValueGrid } from "./valueGrid";
import { decodeRaster } from "./walkRaster";

/** Nodata sentinel: unknown stays unknown, never a number. */
export const STANDARD_UNKNOWN = 255;
/** Best goodness: renders white. */
export const STANDARD_MAX = 100;

/**
 * One composable goodness raster: white (100) = best, black (0) =
 * worst, 255 = unknown. Grid matches the source field node-for-node.
 */
export interface StandardRaster {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  /** Cell pitch in metres when the source has one (walk rasters); else null. */
  step_m: number | null;
  /** cols*rows bytes: 0..100 goodness, or STANDARD_UNKNOWN. */
  bytes: Uint8Array;
}

/** Encode one goodness value; null/NaN/non-finite -> unknown. */
export function encodeStandardValue(v: number | null): number {
  if (v === null || !Number.isFinite(v)) return STANDARD_UNKNOWN;
  return Math.min(STANDARD_MAX, Math.max(0, Math.round(v)));
}

/** Decode one standard byte; unknown -> null. */
export function decodeStandardValue(b: number): number | null {
  if (b === STANDARD_UNKNOWN) return null;
  return b;
}

/**
 * Per-kernel adapter for every buildScoredField kind (area, trips,
 * variety, avoid, quiet, sparse, cover, bands, tileband, qbands,
 * dbands, pins): the byte carries Math.round(scoredAt), the same
 * value scoredToRgba feeds the color LUT — hence pixel parity.
 */
export function standardFromScoredField(s: ScoredField): StandardRaster {
  const { cols, rows, bbox } = s.field;
  const bytes = new Uint8Array(cols * rows);
  for (let iy = 0; iy < rows; iy++) {
    for (let ix = 0; ix < cols; ix++) {
      bytes[iy * cols + ix] = encodeStandardValue(scoredAt(s, ix, iy));
    }
  }
  return { cols, rows, bbox: { ...bbox }, step_m: null, bytes };
}

/**
 * Adapter for the proximity kernel (the variety base, and any bare
 * distance field rendered via fieldToRgba): byte carries
 * Math.round(proximityValue), the same value the color LUT renders.
 */
export function standardFromDistanceField(f: DistanceField, sigmaKm: number): StandardRaster {
  const { cols, rows, bbox } = f;
  const bytes = new Uint8Array(cols * rows);
  for (let k = 0; k < cols * rows; k++) {
    bytes[k] = encodeStandardValue(proximityValue(f.distKm[k], sigmaKm));
  }
  return { cols, rows, bbox: { ...bbox }, step_m: null, bytes };
}

/** Adapter for scored value grids (gridToRgba input): null stays unknown. */
export function standardFromValueGrid(g: ValueGrid): StandardRaster {
  const { cols, rows, bbox } = g;
  const bytes = new Uint8Array(cols * rows);
  for (let iy = 0; iy < rows; iy++) {
    for (let ix = 0; ix < cols; ix++) {
      bytes[iy * cols + ix] = encodeStandardValue(g.valueAt(ix, iy));
    }
  }
  return { cols, rows, bbox: { ...bbox }, step_m: null, bytes };
}

/**
 * Adapter for walk-raster masters (loadLayerRaster / fetchWindow
 * docs): the wire bytes already ARE standard bytes (0..100 scores,
 * 255 unknown), so this is a validated passthrough — grid and bytes
 * preserved exactly, step_m carried for the common-grid check.
 */
export function standardFromWalkRaster(doc: WalkRasterDoc): StandardRaster | null {
  const decoded = decodeRaster(doc);
  if (!decoded) return null;
  return {
    cols: decoded.cols,
    rows: decoded.rows,
    bbox: { ...decoded.bbox },
    step_m: doc.step_m,
    bytes: decoded.values.slice(),
  };
}

/**
 * Monochrome render of a standard raster: white (255 gray) = best
 * goodness, black = worst, transparent where unknown. The existing
 * color renderers (fieldToRgba / scoredToRgba / gridToRgba) are
 * untouched — this is the composable twin, not a replacement.
 */
export function standardToGrayscaleRgba(r: StandardRaster): Uint8ClampedArray {
  const out = new Uint8ClampedArray(r.cols * r.rows * 4);
  for (let k = 0; k < r.cols * r.rows; k++) {
    const b = r.bytes[k];
    const o = k * 4;
    if (b === STANDARD_UNKNOWN) {
      out[o + 3] = 0;
      continue;
    }
    const gray = Math.round((b / STANDARD_MAX) * 255);
    out[o] = gray;
    out[o + 1] = gray;
    out[o + 2] = gray;
    out[o + 3] = 255;
  }
  return out;
}

/**
 * Common-grid check: two rasters share a grid when cols/rows match
 * and the bboxes agree exactly (same corner registration as
 * buildDistanceField — node ix sits at minlon+ix/(cols-1)*span).
 */
export function conformsToGrid(
  r: StandardRaster,
  grid: { cols: number; rows: number; bbox: BBoxLike },
): boolean {
  return (
    r.cols === grid.cols &&
    r.rows === grid.rows &&
    r.bbox.minlon === grid.bbox.minlon &&
    r.bbox.minlat === grid.bbox.minlat &&
    r.bbox.maxlon === grid.bbox.maxlon &&
    r.bbox.maxlat === grid.bbox.maxlat
  );
}
