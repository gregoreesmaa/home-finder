// Nearest-feature distance field for proximity parameters (parameters3.md
// prescribes ST_Distance for these): value(x) = 100·e^(−d/σ), the same
// exponential falloff the scoring pipeline uses, so map colors and scores
// agree. Unlike density splatting this cannot saturate — one nearest
// feature means block-level gradients even in feature-dense cities.
//
// Distances are EXACT (Felzenszwalb–Huttenlocher squared EDT, O(cells)) on
// a grid with square-in-km cells, so equirectangular anisotropy never
// enters. Empty input leaves +Inf everywhere: transparent, never faked.

import { stopMode, type BBoxLike, type BonusSpec } from "./layers";
import { colorForValue } from "./valueScale";
import { splatValues, splatWeights } from "./valueGrid";

export interface DistanceField {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  /** Nearest-feature km per node; +Inf where nothing is known. */
  distKm: Float64Array;
}

const INF = Number.POSITIVE_INFINITY;

/**
 * 1D squared Euclidean distance transform (Felzenszwalb & Huttenlocher),
 * generalized to uniform spacing `step` (km per index) so anisotropic
 * grids stay exact: sample positions are h[q] = q·step.
 */
function edt1d(
  f: Float64Array,
  n: number,
  stride: number,
  offset: number,
  out: Float64Array,
  step: number,
): void {
  // Lower envelope over FINITE samples only (+Inf parabolas never win, and
  // keeping them poisons the intersection tests with NaN). Positions are
  // in km so anisotropic grids stay exact.
  const idx: number[] = [];
  for (let i = 0; i < n; i++) {
    if (f[offset + i * stride] !== INF) idx.push(i);
  }
  if (idx.length === 0) {
    for (let i = 0; i < n; i++) out[offset + i * stride] = INF;
    return;
  }
  const m = idx.length;
  const h = (j: number) => idx[j] * step;
  const g = (j: number) => f[offset + idx[j] * stride];
  const v = new Int32Array(m);
  const z = new Float64Array(m + 1);
  let k = 0;
  v[0] = 0;
  z[0] = -INF;
  z[1] = INF;
  const sep = (j: number, vk: number) =>
    (g(j) + h(j) * h(j) - (g(vk) + h(vk) * h(vk))) / (2 * (h(j) - h(vk)));
  for (let j = 1; j < m; j++) {
    let s = sep(j, v[k]);
    while (s <= z[k]) {
      k--;
      s = sep(j, v[k]);
    }
    k++;
    v[k] = j;
    z[k] = s;
    z[k + 1] = INF;
  }
  k = 0;
  for (let q = 0; q < n; q++) {
    const x = q * step;
    while (z[k + 1] < x) k++;
    const dx = x - h(v[k]);
    out[offset + q * stride] = dx * dx + g(v[k]);
  }
}

export function buildDistanceField(
  points: { lon: number; lat: number }[],
  bbox: BBoxLike,
  cols: number,
  rows: number,
): DistanceField {
  const spanLon = bbox.maxlon - bbox.minlon;
  const spanLat = bbox.maxlat - bbox.minlat;
  const midLat = ((bbox.minlat + bbox.maxlat) / 2) * (Math.PI / 180);
  // Fencepost: n nodes span n−1 intervals.
  const kmPerCellX = (cols > 1 ? (spanLon * 111.32 * Math.cos(midLat)) / (cols - 1) : 0) || 1;
  const kmPerCellY = (rows > 1 ? (spanLat * 110.57) / (rows - 1) : 0) || 1;

  const f = new Float64Array(cols * rows).fill(INF);
  for (const p of points) {
    if (!Number.isFinite(p.lon) || !Number.isFinite(p.lat)) continue;
    const ix = Math.round(((p.lon - bbox.minlon) / spanLon) * (cols - 1));
    const iy = Math.round(((p.lat - bbox.minlat) / spanLat) * (rows - 1));
    if (ix < 0 || iy < 0 || ix >= cols || iy >= rows) continue;
    f[iy * cols + ix] = 0;
  }

  // Separable exact transform: columns in row-km, then rows in column-km.
  // out[] holds squared km; unreachable stays +Inf (transparent, not faked).
  const tmp = new Float64Array(cols * rows);
  for (let ix = 0; ix < cols; ix++) edt1d(f, rows, cols, ix, tmp, kmPerCellY);
  const squared = new Float64Array(cols * rows);
  for (let iy = 0; iy < rows; iy++) edt1d(tmp, cols, 1, iy * cols, squared, kmPerCellX);
  const distKm = new Float64Array(cols * rows);
  for (let k = 0; k < squared.length; k++) {
    distKm[k] = squared[k] === INF ? INF : Math.sqrt(squared[k]);
  }
  return { cols, rows, bbox, distKm };
}

/**
 * Agglomeration bonus: nearest-distance base stays honest (a lone feature
 * peaks exactly as scored), while clusters earn extra — park count, transit
 * stop count + mode mix, school subtype ladder. Always capped, so the
 * combined score never exceeds 100.
 */
export interface ScoredPoint {
  lon: number;
  lat: number;
  tags?: Record<string, string>;
  /** Weekday departures for the "trips" score; absent means unknown. */
  t?: number;
  /** Hectares for the "area" score (parks); absent means no area. */
  a?: number;
}

export interface ScoredField {
  field: DistanceField;
  /** Bonus per node (same geometry as field). */
  bonus: Float64Array;
  sigmaKm: number;
  /** Direct per-node score (NaN = unknown) for the "area" spec; else null. */
  direct: Float64Array | null;
}

/** A class counts as "nearby" past half a kernel — robust to tails. */
const PRESENT = 0.5;

function classSplats(
  points: ScoredPoint[],
  pick: (p: ScoredPoint) => string | null,
  bbox: BBoxLike,
  cols: number,
  rows: number,
  sigmaKm: number,
): Map<string, Float64Array> {
  const byClass = new Map<string, ScoredPoint[]>();
  for (const p of points) {
    const c = pick(p);
    if (c === null) continue;
    const list = byClass.get(c);
    if (list) list.push(p);
    else byClass.set(c, [p]);
  }
  const out = new Map<string, Float64Array>();
  for (const [c, list] of byClass) {
    out.set(c, splatWeights(list, bbox, cols, rows, sigmaKm));
  }
  return out;
}

export function buildScoredField(
  points: ScoredPoint[],
  bbox: BBoxLike,
  cols: number,
  rows: number,
  sigmaKm: number,
  spec: BonusSpec,
): ScoredField {
  const field = buildDistanceField(points, bbox, cols, rows);
  const bonus = new Float64Array(cols * rows);
  if (spec.kind === "area") {
    // Total nearby hectares, saturating: score = 100·S/(S+half), linear in
    // area (two 10-ha parks equal one 20-ha park) with Gaussian falloff.
    // NaN below the noise floor or where nothing lands.
    const area = splatValues(
      points,
      bbox,
      cols,
      rows,
      sigmaKm,
      (pt) => (pt as ScoredPoint).a ?? 0,
      5,
    );
    const direct = new Float64Array(cols * rows);
    for (let k = 0; k < direct.length; k++) {
      const s = area[k];
      const raw = (100 * s) / (s + spec.half);
      direct[k] = s > 0 && raw >= 3 ? Math.min(100, raw) : NaN;
    }
    return { field, bonus, sigmaKm, direct };
  }
  if (spec.kind === "trips") {
    // Total nearby weekday departures, saturating: score = 100·S/(S+half),
    // linear in service (two 500-trip stops equal one 1000-trip stop) with
    // Gaussian falloff. Only the multi-mode kicker lands in bonus; the
    // combined score adds it on top (capped at 100).
    const trips = splatValues(
      points,
      bbox,
      cols,
      rows,
      sigmaKm,
      (p) => (p as ScoredPoint).t ?? 0,
      5,
    );
    const classes = classSplats(points, (p) => stopMode(p.tags), bbox, cols, rows, sigmaKm);
    const direct = new Float64Array(cols * rows);
    for (let k = 0; k < direct.length; k++) {
      const s = trips[k];
      const raw = (100 * s) / (s + spec.half);
      direct[k] = s > 0 && raw >= 3 ? Math.min(100, raw) : NaN;
      let modes = 0;
      for (const w of classes.values()) {
        if (w[k] > PRESENT) modes++;
      }
      bonus[k] = modes >= spec.minModes ? spec.modeBonus : 0;
    }
    return { field, bonus, sigmaKm, direct };
  }
  // G11D-HOOK (#135): nearest-source calmness for inverted badness
  // layers (trailprivacy): 0 on the source, 50 at halfM; featureless
  // input stays unknown (NaN), never a faked calm 100.
  // G06B-HOOK (#139): inverse ("avoid") proximity — currently only the
  // G06B woodfire layer (p356). Score = 100·(1−2^(−d/half)) from the
  // nearest-feature distance field: 0 on top of a feature, 50 at half
  // km, →100 far away. Mirrors goodnessAt's avoid branch and the
  // walk-raster stamp, so the Euclidean fallback agrees with the raster
  // about direction (near wood = low fire-safety score). NaN past the
  // field (unreachable stays unknown, never faked safe).
  if (spec.kind === "avoid") {
    const direct = new Float64Array(cols * rows);
    for (let k = 0; k < direct.length; k++) {
      const d = field.distKm[k];
      if (!Number.isFinite(d)) {
        direct[k] = NaN;
        continue;
      }
      const raw = 100 * (1 - Math.pow(2, -d / spec.half));
      direct[k] = raw >= 3 ? Math.min(100, raw) : NaN;
    }
    return { field, bonus, sigmaKm, direct };
  }
  // B6-HOOK (#133) + G07-HOOK (#140): quiet layers bake nearest-source
  // calmness/cleanliness directly 100·d/(d+halfM) — 0 on the source,
  // 50 at halfM. The shared proximityValue decay would render them
  // inverted (green ON the airfield), and without this branch quiet
  // layers would fall into the variety path below and crash on
  // spec.key. No bonus splat. droneviab degrades to its clearance leg
  // here (batch4 rideshare precedent: the raster carries the full
  // two-signal field, the fallback the honest subset). +Inf stays NaN
  // (unknown, never faked).
  if (spec.kind === "quiet") {
    const direct = new Float64Array(cols * rows);
    for (let k = 0; k < direct.length; k++) {
      const d = field.distKm[k];
      direct[k] = d === INF ? NaN : Math.min(100, (100 * d * 1000) / (d * 1000 + spec.halfM));
    }
    return { field, bonus, sigmaKm, direct };
  }
  {
    const classes = classSplats(
      points,
      (p) => {
        const v = p.tags?.[spec.key];
        return v !== undefined && spec.values.includes(v) ? v : null;
      },
      bbox,
      cols,
      rows,
      sigmaKm,
    );
    const n = Math.floor(spec.cap / spec.per);
    for (let k = 0; k < bonus.length; k++) {
      let distinct = 0;
      for (const w of classes.values()) {
        if (w[k] > PRESENT) distinct++;
      }
      bonus[k] = spec.per * Math.min(n, Math.max(0, distinct - 1));
    }
  }
  return { field, bonus, sigmaKm, direct: null };
}

/** Combined node score, capped at 100; null where nothing is known. */
export function scoredAt(s: ScoredField, ix: number, iy: number): number | null {
  if (s.direct) {
    const v = s.direct[iy * s.field.cols + ix];
    // Parks carry a zero bonus (no-op); transit adds the mode kicker here.
    return Number.isNaN(v) ? null : Math.min(100, v + s.bonus[iy * s.field.cols + ix]);
  }
  const base = proximityAt(s.field, ix, iy, s.sigmaKm);
  if (base === null) return null;
  return Math.min(100, base + s.bonus[iy * s.field.cols + ix]);
}

/** Bonus lookup (0 outside). Exported for tests. */
export function bonusAt(s: ScoredField, ix: number, iy: number): number {
  if (ix < 0 || iy < 0 || ix >= s.field.cols || iy >= s.field.rows) return 0;
  return s.bonus[iy * s.field.cols + ix];
}

/** Byte RGBA upload of the combined score. */
export function scoredToRgba(s: ScoredField): Uint8ClampedArray {
  const { cols, rows } = s.field;
  const out = new Uint8ClampedArray(cols * rows * 4);
  for (let iy = 0; iy < rows; iy++) {
    for (let ix = 0; ix < cols; ix++) {
      const v = scoredAt(s, ix, iy);
      const o = (iy * cols + ix) * 4;
      // Unknown renders as score-0 red (user-asked); hover still reports
      // no-data, so the distinction survives in the readout.
      const [r, g, b] = colorForValue(v ?? 0);
      out[o] = r;
      out[o + 1] = g;
      out[o + 2] = b;
      out[o + 3] = 255;
    }
  }
  return out;
}

/** Hover readback of the combined score. */
export function sampleScored(
  s: ScoredField,
  lon: number,
  lat: number,
): { value: number; coverage: number } | null {
  const { cols, rows, bbox } = s.field;
  const gx = ((lon - bbox.minlon) / (bbox.maxlon - bbox.minlon)) * (cols - 1);
  const gy = ((lat - bbox.minlat) / (bbox.maxlat - bbox.minlat)) * (rows - 1);
  if (gx < 0 || gy < 0 || gx > cols - 1 || gy > rows - 1) return null;
  const x0 = Math.floor(gx);
  const y0 = Math.floor(gy);
  const fx = gx - x0;
  const fy = gy - y0;
  let sv = 0;
  let sw = 0;
  const corners: [number, number, number][] = [
    [x0, y0, (1 - fx) * (1 - fy)],
    [Math.min(cols - 1, x0 + 1), y0, fx * (1 - fy)],
    [x0, Math.min(rows - 1, y0 + 1), (1 - fx) * fy],
    [Math.min(cols - 1, x0 + 1), Math.min(rows - 1, y0 + 1), fx * fy],
  ];
  for (const [ix, iy, fw] of corners) {
    const vv = scoredAt(s, ix, iy);
    if (vv === null) continue;
    sv += fw * vv;
    sw += fw;
  }
  if (sw <= 0) return null;
  return { value: sv / sw, coverage: 1 };
}

/**
 * Grid resolution for a view: cells ~σ/6 km (block-level at city zoom),
 * clamped so country views stay tractable. Cells are square-in-km.
 */
export function fieldResolution(
  bbox: BBoxLike,
  sigmaKm: number,
  maxCols = 2048,
): { cols: number; rows: number } {
  const midLat = ((bbox.minlat + bbox.maxlat) / 2) * (Math.PI / 180);
  const spanKmX = (bbox.maxlon - bbox.minlon) * 111.32 * Math.cos(midLat);
  const spanKmY = (bbox.maxlat - bbox.minlat) * 110.57;
  let cellKm = Math.max(spanKmX, spanKmY) / 1200;
  cellKm = Math.min(5, Math.max(0.05, cellKm));
  let cols = Math.round(spanKmX / cellKm);
  let rows = Math.round(spanKmY / cellKm);
  if (cols > maxCols) {
    // Shrink the cell to fit: squareness preserved, detail reduced evenly.
    const s = spanKmX / maxCols;
    cols = maxCols;
    rows = Math.round(spanKmY / s);
  }
  rows = Math.min(2048, Math.max(1, rows));
  cols = Math.min(maxCols, Math.max(1, cols));
  void sigmaKm;
  return { cols, rows };
}

/** Scoring-mirroring value: 100 at the feature, exponential falloff. */
export function proximityValue(distKm: number, sigmaKm: number): number | null {
  if (!Number.isFinite(distKm)) return null;
  return 100 * Math.exp(-distKm / sigmaKm);
}

export function proximityAt(
  f: DistanceField,
  ix: number,
  iy: number,
  sigmaKm: number,
): number | null {
  if (ix < 0 || iy < 0 || ix >= f.cols || iy >= f.rows) return null;
  return proximityValue(f.distKm[iy * f.cols + ix], sigmaKm);
}

/** Byte RGBA upload: LUT color; opaque everywhere known, clear where not. */
export function fieldToRgba(f: DistanceField, sigmaKm: number): Uint8ClampedArray {
  const out = new Uint8ClampedArray(f.cols * f.rows * 4);
  for (let k = 0; k < f.cols * f.rows; k++) {
    const v = proximityValue(f.distKm[k], sigmaKm);
    const o = k * 4;
    if (v === null) {
      out[o + 3] = 0;
      continue;
    }
    const [r, g, b] = colorForValue(v);
    out[o] = r;
    out[o + 1] = g;
    out[o + 2] = b;
    out[o + 3] = 255;
  }
  return out;
}

/** Hover readback: bilinear on distance, then mapped — mirrors the GPU. */
export function sampleField(
  f: DistanceField,
  lon: number,
  lat: number,
  sigmaKm: number,
): { value: number; coverage: number } | null {
  const { cols, rows, bbox } = f;
  const gx = ((lon - bbox.minlon) / (bbox.maxlon - bbox.minlon)) * (cols - 1);
  const gy = ((lat - bbox.minlat) / (bbox.maxlat - bbox.minlat)) * (rows - 1);
  if (gx < 0 || gy < 0 || gx > cols - 1 || gy > rows - 1) return null;
  const x0 = Math.floor(gx);
  const y0 = Math.floor(gy);
  const fx = gx - x0;
  const fy = gy - y0;
  let d = 0;
  let wsum = 0;
  const corners: [number, number, number][] = [
    [x0, y0, (1 - fx) * (1 - fy)],
    [Math.min(cols - 1, x0 + 1), y0, fx * (1 - fy)],
    [x0, Math.min(rows - 1, y0 + 1), (1 - fx) * fy],
    [Math.min(cols - 1, x0 + 1), Math.min(rows - 1, y0 + 1), fx * fy],
  ];
  for (const [ix, iy, fw] of corners) {
    const dd = f.distKm[iy * cols + ix];
    if (!Number.isFinite(dd)) continue;
    d += fw * dd;
    wsum += fw;
  }
  if (wsum <= 0) return null;
  const v = proximityValue(d / wsum, sigmaKm);
  return v === null ? null : { value: v, coverage: 1 };
}
