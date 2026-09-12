import type { BBoxLike, WalkRasterDoc } from "./layers";
import { colorForValue } from "./valueScale";

export interface DecodedRaster {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  values: Uint8Array;
}

/**
 * Decode a transit walk-raster doc (uint8 scores, 255 = unknown). Null on
 * any corruption: wrong byte length, out-of-range scores, insane dims.
 */
export function decodeRaster(input: unknown): DecodedRaster | null {
  if (!input || typeof input !== "object") return null;
  const doc = input as WalkRasterDoc;
  const { cols, rows, bbox, data } = doc;
  if (!Number.isInteger(cols) || !Number.isInteger(rows)) return null;
  if (cols <= 0 || rows <= 0 || cols > 10000 || rows > 10000) return null;
  if (cols * rows > 50_000_000) return null;
  if (!bbox || typeof data !== "string") return null;
  for (const k of ["minlon", "minlat", "maxlon", "maxlat"] as const) {
    if (typeof bbox[k] !== "number" || !Number.isFinite(bbox[k])) return null;
  }
  if (bbox.minlon >= bbox.maxlon || bbox.minlat >= bbox.maxlat) return null;
  let values: Uint8Array;
  try {
    const bin = atob(data);
    values = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) values[i] = bin.charCodeAt(i);
  } catch {
    return null;
  }
  if (values.length !== cols * rows) return null;
  for (let i = 0; i < values.length; i++) {
    if (values[i] !== doc.unknown && values[i] > 100) return null;
  }
  return { cols, rows, bbox, values };
}

/**
 * Bilinear hover readback. Unknown corners are skipped (renormalized);
 * a fully-unknown neighborhood — or outside the bbox — reads as no-data.
 * Exactly on an unknown node with no valid weight, the nearest valid
 * corner answers (coverage holes are not walls).
 */
export function sampleRaster(
  r: DecodedRaster,
  lon: number,
  lat: number,
): { value: number; coverage: number } | null {
  const { cols, rows, bbox, values } = r;
  const gx = ((lon - bbox.minlon) / (bbox.maxlon - bbox.minlon)) * cols - 0.5;
  const gy = ((lat - bbox.minlat) / (bbox.maxlat - bbox.minlat)) * rows - 0.5;
  if (gx < -0.5 || gy < -0.5 || gx > cols - 0.5 || gy > rows - 0.5) return null;
  const x0 = Math.floor(gx);
  const y0 = Math.floor(gy);
  const fx = gx - x0;
  const fy = gy - y0;
  const corners: [number, number, number][] = [
    [x0, y0, (1 - fx) * (1 - fy)],
    [x0 + 1, y0, fx * (1 - fy)],
    [x0, y0 + 1, (1 - fx) * fy],
    [x0 + 1, y0 + 1, fx * fy],
  ];
  let sv = 0;
  let sw = 0;
  let nearest: number | null = null;
  let nearestD = Infinity;
  for (const [ix, iy, fw] of corners) {
    if (ix < 0 || iy < 0 || ix >= cols || iy >= rows) continue;
    const v = values[iy * cols + ix];
    if (v === 255) continue;
    // Corner weight zero happens exactly on a skipped node; track the
    // nearest valid corner as the honest fallback.
    const d = Math.abs(ix - gx) + Math.abs(iy - gy);
    if (d < nearestD) {
      nearestD = d;
      nearest = v;
    }
    sv += fw * v;
    sw += fw;
  }
  if (sw > 0) return { value: sv / sw, coverage: 1 };
  return nearest === null ? null : { value: nearest, coverage: 1 };
}

/**
 * County texture upload: LUT color per known cell (row 0 = south, same
 * order as the scored fields), transparent where unknown.
 */
export function rasterToRgba(r: DecodedRaster): Uint8ClampedArray {
  const out = new Uint8ClampedArray(r.cols * r.rows * 4);
  for (let k = 0; k < r.cols * r.rows; k++) {
    const o = k * 4;
    const v = r.values[k];
    // 255 (unknown) renders as score-0 red (user-asked); hover still
    // reports no-data, so the distinction survives in the readout.
    const [cr, cg, cb] = colorForValue(v === 255 ? 0 : v);
    out[o] = cr;
    out[o + 1] = cg;
    out[o + 2] = cb;
    out[o + 3] = 255;
  }
  return out;
}
