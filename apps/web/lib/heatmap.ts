// Heatmap data transform: area-scores (H3 hex GeoJSON from GET /area-scores)
// -> deck.gl HeatmapLayer points + hex fill colors by goodness level.

export type HeatLevel = "good" | "mid" | "bad";

export interface AreaHex {
  h3: string;
  score_goodness: number; // 0..100
  lon: number;
  lat: number;
}

export interface HeatPoint extends AreaHex {
  weight: number; // 0..1 intensity for HeatmapLayer (normalized to local range)
  level: HeatLevel;
  fillColor: [number, number, number, number];
  localMin?: number;
  localMax?: number;
}

export function heatLevel(score: number): HeatLevel {
  if (score >= 70) return "good";
  if (score >= 40) return "mid";
  return "bad";
}

const FILL: Record<HeatLevel, [number, number, number, number]> = {
  good: [46, 160, 67, 140], // green
  mid: [230, 170, 40, 140], // amber
  bad: [220, 60, 50, 140], // red
};

/** Smoothly interpolate red -> amber -> green based on normalized weight (0..1). */
export function colorForWeight(weight: number): [number, number, number, number] {
  const w = Math.min(1, Math.max(0, weight));
  if (w < 0.5) {
    const t = w * 2;
    return [
      Math.round(220 + 10 * t),
      Math.round(60 + 110 * t),
      Math.round(50 - 10 * t),
      140,
    ];
  }
  const t = (w - 0.5) * 2;
  return [
    Math.round(230 - 184 * t),
    Math.round(170 - 10 * t),
    Math.round(40 + 27 * t),
    140,
  ];
}

export function toHeatPoints(hexes: AreaHex[]): HeatPoint[] {
  return hexes.map((h) => {
    const level = heatLevel(h.score_goodness);
    return {
      ...h,
      weight: Math.min(1, Math.max(0, h.score_goodness / 100)),
      level,
      fillColor: FILL[level],
    };
  });
}

// ---------------------------------------------------------------------------
// Issue #2: hex binning, legend, click popup, mock GeoJSON fallback.
// ---------------------------------------------------------------------------

/** Offline fallback: mirrors lib/mockHexes.geojson + GET /area-scores mock. */
export const MOCK_HEXES: AreaHex[] = [
  { h3: "mock-tallinn", score_goodness: 85, lon: 24.75, lat: 59.43 },
  { h3: "mock-tartu", score_goodness: 62, lon: 26.72, lat: 58.37 },
  { h3: "mock-parnu", score_goodness: 30, lon: 24.5, lat: 58.38 },
];

/**
 * Detailed reference neighborhood points across Estonian cities.
 * Provides micro-granularity for cities like Tallinn so that local
 * gradients reflect actual neighborhood differences (e.g. Vanalinn vs Kopli).
 */
export const DETAILED_NEIGHBORHOOD_HEXES: AreaHex[] = [
  // Tallinn districts
  { h3: "tl-vanalinn", score_goodness: 92, lon: 24.745, lat: 59.437 },
  { h3: "tl-kadriorg", score_goodness: 88, lon: 24.786, lat: 59.438 },
  { h3: "tl-kalamaja", score_goodness: 86, lon: 24.735, lat: 59.445 },
  { h3: "tl-noblessner", score_goodness: 84, lon: 24.725, lat: 59.453 },
  { h3: "tl-kesklinn", score_goodness: 82, lon: 24.755, lat: 59.432 },
  { h3: "tl-pirita", score_goodness: 80, lon: 24.835, lat: 59.467 },
  { h3: "tl-nomme", score_goodness: 77, lon: 24.685, lat: 59.385 },
  { h3: "tl-kristiine", score_goodness: 71, lon: 24.718, lat: 59.418 },
  { h3: "tl-pelgulinn", score_goodness: 68, lon: 24.715, lat: 59.438 },
  { h3: "tl-mustamae", score_goodness: 58, lon: 24.672, lat: 59.402 },
  { h3: "tl-haabersti", score_goodness: 52, lon: 24.646, lat: 59.419 },
  { h3: "tl-lasnamae-w", score_goodness: 48, lon: 24.815, lat: 59.439 },
  { h3: "tl-lasnamae-e", score_goodness: 38, lon: 24.872, lat: 59.448 },
  { h3: "tl-kopli", score_goodness: 35, lon: 24.685, lat: 59.458 },
  { h3: "tl-karjamaa", score_goodness: 44, lon: 24.708, lat: 59.449 },
  // Tartu districts
  { h3: "tr-kesklinn", score_goodness: 88, lon: 26.720, lat: 58.380 },
  { h3: "tr-karlova", score_goodness: 76, lon: 26.732, lat: 58.368 },
  { h3: "tr-supilinn", score_goodness: 82, lon: 26.710, lat: 58.388 },
  { h3: "tr-tahtvere", score_goodness: 85, lon: 26.702, lat: 58.385 },
  { h3: "tr-annelinn", score_goodness: 48, lon: 26.765, lat: 58.375 },
  { h3: "tr-ranilinn", score_goodness: 52, lon: 26.680, lat: 58.355 },
  // Pärnu districts
  { h3: "pr-rannarajoon", score_goodness: 90, lon: 24.498, lat: 58.382 },
  { h3: "pr-kesklinn", score_goodness: 82, lon: 24.502, lat: 58.388 },
  { h3: "pr-ulejoe", score_goodness: 52, lon: 24.495, lat: 58.398 },
  { h3: "pr-mai", score_goodness: 48, lon: 24.535, lat: 58.368 },
  // Regional county centers
  { h3: "narva", score_goodness: 42, lon: 28.190, lat: 59.377 },
  { h3: "kohtla-jarve", score_goodness: 32, lon: 27.273, lat: 59.400 },
  { h3: "viljandi", score_goodness: 68, lon: 25.596, lat: 58.364 },
  { h3: "rakvere", score_goodness: 64, lon: 26.356, lat: 59.346 },
  { h3: "kuressaare", score_goodness: 72, lon: 22.485, lat: 58.253 },
  { h3: "haapsalu", score_goodness: 74, lon: 23.537, lat: 58.943 },
];

/**
 * Involve all available data: combine cells, listings, and neighborhood
 * benchmarks into a unified dataset.
 * - Geocoded listings supply street-level livability detail.
 * - Area cells provide macro regional background.
 * - Neighborhood benchmarks supply micro-neighborhood baselines.
 */
export function mergeHeatData(
  cells: AreaHex[],
  listings: ListingPoint[],
  includeBenchmarks = true,
): AreaHex[] {
  const result: AreaHex[] = [];
  const seenCoords = new Set<string>();

  // 1. Listings (finest local detail)
  for (let i = 0; i < listings.length; i++) {
    const l = listings[i];
    if (!Number.isFinite(l.lon) || !Number.isFinite(l.lat) || !Number.isFinite(l.livability)) continue;
    const key = `${l.lon.toFixed(4)}:${l.lat.toFixed(4)}`;
    seenCoords.add(key);
    result.push({
      h3: `listing-${i}`,
      score_goodness: Math.round(l.livability * 10) / 10,
      lon: l.lon,
      lat: l.lat,
    });
  }

  // 2. Area cells
  for (const c of cells) {
    if (!Number.isFinite(c.lon) || !Number.isFinite(c.lat) || !Number.isFinite(c.score_goodness)) continue;
    const key = `${c.lon.toFixed(4)}:${c.lat.toFixed(4)}`;
    if (!seenCoords.has(key)) {
      result.push(c);
      seenCoords.add(key);
    }
  }

  // 3. Neighborhood benchmarks
  if (includeBenchmarks) {
    for (const d of DETAILED_NEIGHBORHOOD_HEXES) {
      const key = `${d.lon.toFixed(4)}:${d.lat.toFixed(4)}`;
      if (!seenCoords.has(key)) {
        result.push(d);
        seenCoords.add(key);
      }
    }
  }

  return result.length > 0 ? result : cells;
}

/** One listing positioned on the map; heat weight comes from livability fit. */
export interface ListingPoint {
  lon: number;
  lat: number;
  livability: number; // 0..100
}

/**
 * Grid bin (H3 stand-in until h3-js is wired): group listings into
 * cellDegrees x cellDegrees cells, average livability per cell.
 * Cell centre becomes the hex point; empty/invalid input yields [].
 */
export function binListingsToHexes(
  listings: ListingPoint[],
  cellDegrees = 0.25,
): AreaHex[] {
  const cells = new Map<string, { sum: number; count: number; ix: number; iy: number }>();
  for (const l of listings) {
    if (!Number.isFinite(l.lon) || !Number.isFinite(l.lat)) continue;
    const liv = Math.min(100, Math.max(0, l.livability));
    if (!Number.isFinite(liv)) continue;
    const ix = Math.floor(l.lon / cellDegrees);
    const iy = Math.floor(l.lat / cellDegrees);
    const key = `${ix}:${iy}`;
    const cell = cells.get(key);
    if (cell) {
      cell.sum += liv;
      cell.count += 1;
    } else {
      cells.set(key, { sum: liv, count: 1, ix, iy });
    }
  }
  return [...cells.entries()]
    .map(([key, c]) => ({
      h3: `cell-${key}`,
      score_goodness: Math.round((c.sum / c.count) * 10) / 10,
      lon: (c.ix + 0.5) * cellDegrees,
      lat: (c.iy + 0.5) * cellDegrees,
    }))
    .sort((a, b) => (a.h3 < b.h3 ? -1 : 1));
}

const LEVEL_ET: Record<HeatLevel, string> = {
  good: "hea",
  mid: "keskmine",
  bad: "halb",
};

const LEVEL_CSS: Record<HeatLevel, string> = {
  good: "rgb(46, 160, 67)",
  mid: "rgb(230, 170, 40)",
  bad: "rgb(220, 60, 50)",
};

export interface LegendBucket {
  level: HeatLevel;
  label: string;
  min: number;
  max: number;
  css: string;
}

/**
 * Legend rows for the goodness/badness scale (green -> amber -> red).
 * When localMin and localMax are supplied, the legend labels reflect the
 * dynamically computed local range (e.g. Hea (parim: 88), Halb (madalaim: 35)).
 */
export function legendBuckets(
  localMin?: number,
  localMax?: number,
): LegendBucket[] {
  if (
    localMin !== undefined &&
    localMax !== undefined &&
    Number.isFinite(localMin) &&
    Number.isFinite(localMax) &&
    localMax - localMin >= 1
  ) {
    const min = Math.round(localMin);
    const max = Math.round(localMax);
    const midLow = Math.round(min + (max - min) * 0.35);
    const midHigh = Math.round(min + (max - min) * 0.65);
    return [
      {
        level: "good",
        label: `Hea (parim: ${max})`,
        min: midHigh,
        max,
        css: LEVEL_CSS.good,
      },
      {
        level: "mid",
        label: `Keskmine (${midLow}–${midHigh})`,
        min: midLow,
        max: midHigh,
        css: LEVEL_CSS.mid,
      },
      {
        level: "bad",
        label: `Nõrgem (madalaim: ${min})`,
        min,
        max: midLow,
        css: LEVEL_CSS.bad,
      },
    ];
  }
  return [
    { level: "good", label: "Hea ≥ 70", min: 70, max: 100, css: LEVEL_CSS.good },
    { level: "mid", label: "Keskmine 40–69", min: 40, max: 69, css: LEVEL_CSS.mid },
    { level: "bad", label: "Halb < 40", min: 0, max: 39, css: LEVEL_CSS.bad },
  ];
}

/** One-line popup content for a clicked heat point. */
export function popupText(p: HeatPoint): string {
  if (
    p.localMin !== undefined &&
    p.localMax !== undefined &&
    p.localMax > p.localMin
  ) {
    const relPct = Math.round(p.weight * 100);
    return `${p.h3}: headus ${p.score_goodness}/100 — ${LEVEL_ET[p.level]} (kohalik tase: ${relPct}%)`;
  }
  return `${p.h3}: headus ${p.score_goodness}/100 — ${LEVEL_ET[p.level]}`;
}

/** Nearest heat point within maxDegrees, else null (map click -> popup). */
export function nearestHeatPoint(
  points: HeatPoint[],
  lon: number,
  lat: number,
  maxDegrees = 0.5,
): HeatPoint | null {
  let best: HeatPoint | null = null;
  let bestD = maxDegrees;
  for (const p of points) {
    const d = Math.hypot(p.lon - lon, p.lat - lat);
    if (d <= bestD) {
      best = p;
      bestD = d;
    }
  }
  return best;
}

interface HexPointFeature {
  type: string;
  geometry?: { type: string; coordinates?: unknown };
  properties?: { h3?: unknown; score_goodness?: unknown };
}

/**
 * Parse GET /area-scores GeoJSON (FeatureCollection of Point features with
 * {h3, score_goodness} properties). Malformed features are skipped.
 */
export function hexesFromGeoJSON(fc: unknown): AreaHex[] {
  const features = (fc as { features?: unknown })?.features;
  if (!Array.isArray(features)) return [];
  const out: AreaHex[] = [];
  for (const f of features as HexPointFeature[]) {
    const coords = f?.geometry?.coordinates;
    const props = f?.properties;
    if (!Array.isArray(coords) || coords.length < 2) continue;
    const [lon, lat] = coords as unknown[];
    if (typeof props?.h3 !== "string") continue;
    if (typeof props?.score_goodness !== "number") continue;
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
    if (!Number.isFinite(props.score_goodness)) continue;
    out.push({
      h3: props.h3,
      score_goodness: props.score_goodness,
      lon: lon as number,
      lat: lat as number,
    });
  }
  return out;
}

/** Where the painted cells came from (shown next to the map, B1/B4). */
export type HeatSource = "cells" | "listings" | "mock";

export const HEAT_SOURCE_ET: Record<HeatSource, string> = {
  cells: "piirkonna headus",
  listings: "nimekirja tihedus",
  mock: "demo-andmed",
};

/** Listings carrying coordinates become heat input when cells are not live. */
export function listingsToPoints(
  listings: { lon?: number | null; lat?: number | null; score_livability?: number | null }[],
): ListingPoint[] {
  const out: ListingPoint[] = [];
  for (const l of listings) {
    if (typeof l.lon !== "number" || typeof l.lat !== "number") continue;
    if (!Number.isFinite(l.lon) || !Number.isFinite(l.lat)) continue;
    if (typeof l.score_livability !== "number" || !Number.isFinite(l.score_livability)) continue;
    out.push({ lon: l.lon, lat: l.lat, livability: l.score_livability });
  }
  return out;
}

/**
 * Pick heat input (B1): live DB cells win; otherwise bin geocoded listings;
 * mock cells are the last resort. Never returns [] when fallback is non-empty.
 */
export function pickHeatInput(
  cells: AreaHex[],
  live: boolean,
  listings: ListingPoint[],
  fallback: AreaHex[],
): { hexes: AreaHex[]; source: HeatSource } {
  if (live && cells.length > 0) return { hexes: cells, source: "cells" };
  const bins = binListingsToHexes(listings);
  if (bins.length > 0) return { hexes: bins, source: "listings" };
  if (cells.length > 0) return { hexes: cells, source: "mock" };
  return { hexes: fallback, source: "mock" };
}

// ---------------------------------------------------------------------------
// Zoom-aware continuous surface: EVERY visible pixel carries a goodness
// color (no isolated blobs / uncolored gaps when zoomed in), and granularity
// refines dynamically as the user zooms (coarse cells out, fine detail in).
//
// The ingest grid stays 0.25 degrees with MEAN aggregation
// (services/scoring/ingest.py CELL_DEGREES + build_cells): sparse cells are
// resampled here onto a full-viewport IDW grid whose step shrinks per zoom,
// and the deck.gl layers render that dense surface with MEAN aggregation,
// zero threshold (fringe pixels stay colored) and a zoom-scaled radius.
// ---------------------------------------------------------------------------

/** Coarse ingest grid step in degrees (mirrors ingest CELL_DEGREES). */
export const BASE_CELL_DEGREES = 0.25;

/** Viewport bounding box in degrees. */
export interface BBox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

/** Estonia default viewport (matches the map's center/zoom 7). */
export const ESTONIA_BBOX: BBox = {
  minlon: 21.5,
  minlat: 57.3,
  maxlon: 28.5,
  maxlat: 59.9,
};

/**
 * Zoom level -> grid step in degrees. Doubles detail per zoom step around
 * the 0.25-degree ingest grid at zoom 7; clamped so requests stay sane.
 * Monotonic: a higher zoom never yields a coarser step.
 */
export function resolutionForZoom(zoom: number): number {
  if (!Number.isFinite(zoom)) return BASE_CELL_DEGREES;
  const z = Math.min(19, Math.max(0, Math.round(zoom)));
  const step = BASE_CELL_DEGREES * Math.pow(2, 7 - z);
  return Math.min(1, Math.max(0.015625, step));
}

/** Minimum heatmap grid resolution at any given zoom level. */
export const MIN_HEATMAP_COLS = 200;
export const MIN_HEATMAP_ROWS = 100;
export const MAX_HEATMAP_COLS = 400;
export const MAX_HEATMAP_ROWS = 250;

/**
 * deck.gl HeatmapLayer props for the continuous surface. MEAN keeps
 * overlapping cells averaged; threshold 0 keeps fringe pixels colored
 * instead of cut out (no uncolored gaps); the screen-space radius grows
 * with zoom because kernels spread apart in pixels when zoomed in.
 */
export function heatmapLayerProps(zoom: number): {
  aggregation: "MEAN";
  radiusPixels: number;
  intensity: number;
  threshold: number;
} {
  const z = Number.isFinite(zoom) ? zoom : 7;
  return {
    aggregation: "MEAN",
    radiusPixels: Math.min(250, Math.max(25, Math.round(40 * Math.pow(2, (z - 7) * 0.4)))),
    intensity: 1,
    threshold: 0,
  };
}

/**
 * HexagonLayer radius in meters for the gap-free tile view: ~3/4 of the
 * current grid step at Estonia's latitude, so tiles overlap slightly with
 * coverage 1 and no base map shows through.
 */
export function hexRadiusForZoom(zoom: number): number {
  const METERS_PER_DEGREE_LON_EE = 111320 * Math.cos((58.75 * Math.PI) / 180);
  return Math.round(resolutionForZoom(zoom) * METERS_PER_DEGREE_LON_EE * 0.75);
}

/**
 * Inverse-distance (1/d^2) weighted MEAN goodness at any lon/lat.
 * Exact cell hits return the cell value; any query with data nearby
 * returns a finite 0..100 value, so the surface never has holes.
 * Null only when there is no usable input at all.
 */
export function interpolateGoodness(
  points: { lon: number; lat: number; score_goodness: number }[],
  lon: number,
  lat: number,
): number | null {
  let num = 0;
  let den = 0;
  for (const p of points) {
    if (!Number.isFinite(p.lon) || !Number.isFinite(p.lat)) continue;
    if (!Number.isFinite(p.score_goodness)) continue;
    const d2 = (p.lon - lon) * (p.lon - lon) + (p.lat - lat) * (p.lat - lat);
    if (d2 < 1e-12) return Math.min(100, Math.max(0, p.score_goodness));
    const w = 1 / d2;
    num += w * p.score_goodness;
    den += w;
  }
  if (den === 0) return null;
  return Math.min(100, Math.max(0, num / den));
}

/**
 * Grid dimensions (cols x rows) for a viewport bounding box and zoom level.
 * Guaranteed to have a resolution of at least 200x100 (cols >= 200, rows >= 100)
 * at any given zoom level. Detail scales smoothly at higher zooms.
 */
export function viewportGridDimensions(
  bbox: BBox,
  zoom: number,
  minCols = MIN_HEATMAP_COLS,
  minRows = MIN_HEATMAP_ROWS,
): { cols: number; rows: number } {
  const z = Number.isFinite(zoom) ? zoom : 7;
  const dLon = Math.max(1e-6, bbox.maxlon - bbox.minlon);
  const dLat = Math.max(1e-6, bbox.maxlat - bbox.minlat);

  // Zoom detail factor: increases detail at higher zooms while staying bounded
  const zoomFactor = Math.max(1, 1 + Math.max(0, z - 6) * 0.1);

  // Target base resolution with at least minCols x minRows
  let targetCols = Math.round(minCols * zoomFactor);
  let targetRows = Math.round(minRows * zoomFactor);

  // Adjust for aspect ratio so grid cells match the viewport shape
  // while strictly guaranteeing at least minCols x minRows
  const aspect = dLon / dLat;
  if (aspect > 2) {
    targetCols = Math.max(targetCols, Math.round(targetRows * (aspect / 2)));
  } else if (aspect < 1) {
    targetRows = Math.max(targetRows, Math.round(targetCols / aspect));
  }

  const cols = Math.min(MAX_HEATMAP_COLS, Math.max(minCols, targetCols));
  const rows = Math.min(MAX_HEATMAP_ROWS, Math.max(minRows, targetRows));

  return { cols, rows };
}

/**
 * Resample points onto a dense grid tiling the whole bbox (at least 200x100 resolution):
 * 1. Gradient always depends on local worst and best values in the viewport
 *    (local worst -> red/0.0, local best -> green/1.0).
 * 2. Dynamically computed based on position (using current bbox and zoom).
 * 3. Involves all available data surrounding the current position.
 */
export function buildViewportGrid(
  points: HeatPoint[],
  bbox: BBox,
  zoom: number,
  minCols = MIN_HEATMAP_COLS,
  minRows = MIN_HEATMAP_ROWS,
): HeatPoint[] {
  if (points.length === 0) return [];
  const { minlon, minlat, maxlon, maxlat } = bbox;
  if (![minlon, minlat, maxlon, maxlat].every(Number.isFinite)) return [];
  if (!(minlon < maxlon && minlat < maxlat)) return [];

  // Filter valid points upfront
  const validPoints: HeatPoint[] = [];
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    if (
      Number.isFinite(p.lon) &&
      Number.isFinite(p.lat) &&
      Number.isFinite(p.score_goodness)
    ) {
      validPoints.push(p);
    }
  }
  if (validPoints.length === 0) return [];

  // Dynamically select points relevant to the current position (viewport + margin)
  const dLon = maxlon - minlon;
  const dLat = maxlat - minlat;
  const marginLon = dLon * 0.75;
  const marginLat = dLat * 0.75;
  const qMinLon = minlon - marginLon;
  const qMaxLon = maxlon + marginLon;
  const qMinLat = minlat - marginLat;
  const qMaxLat = maxlat + marginLat;

  let localPoints = validPoints.filter(
    (p) => p.lon >= qMinLon && p.lon <= qMaxLon && p.lat >= qMinLat && p.lat <= qMaxLat,
  );
  if (localPoints.length === 0) {
    localPoints = validPoints;
  }

  const nPts = localPoints.length;
  const validLons = new Float64Array(nPts);
  const validLats = new Float64Array(nPts);
  const validScores = new Float64Array(nPts);
  for (let i = 0; i < nPts; i++) {
    validLons[i] = localPoints[i].lon;
    validLats[i] = localPoints[i].lat;
    validScores[i] = localPoints[i].score_goodness;
  }

  const { cols, rows } = viewportGridDimensions(bbox, zoom, minCols, minRows);
  const w = dLon / cols;
  const h = dLat / rows;
  const total = cols * rows;

  // Fast-path: single point colors the whole viewport uniformly
  if (nPts === 1) {
    const singleScore = Math.round(validScores[0] * 10) / 10;
    const level = heatLevel(singleScore);
    const weight = Math.min(1, Math.max(0, singleScore / 100));
    const fillColor = FILL[level];
    const out: HeatPoint[] = new Array(total);
    let idx = 0;
    for (let r = 0; r < rows; r++) {
      const lat = minlat + (r + 0.5) * h;
      for (let c = 0; c < cols; c++) {
        out[idx++] = {
          h3: `interp-${c}:${r}`,
          score_goodness: singleScore,
          lon: minlon + (c + 0.5) * w,
          lat,
          weight,
          level,
          fillColor,
          localMin: singleScore,
          localMax: singleScore,
        };
      }
    }
    return out;
  }

  // 1. Interpolate raw scores across all grid cells dynamically for this position
  const rawScores = new Float64Array(total);
  let minScore = Infinity;
  let maxScore = -Infinity;
  let idx = 0;

  for (let r = 0; r < rows; r++) {
    const lat = minlat + (r + 0.5) * h;
    const cosLat = Math.cos((lat * Math.PI) / 180);
    for (let c = 0; c < cols; c++) {
      const lon = minlon + (c + 0.5) * w;
      let num = 0;
      let den = 0;
      let exactScore = -1;

      for (let i = 0; i < nPts; i++) {
        const dlon = (validLons[i] - lon) * cosLat;
        const dlat = validLats[i] - lat;
        const d2 = dlon * dlon + dlat * dlat;
        if (d2 < 1e-12) {
          exactScore = validScores[i];
          break;
        }
        const inv = 1 / d2;
        num += inv * validScores[i];
        den += inv;
      }

      const val = exactScore >= 0 ? exactScore : (den > 0 ? num / den : 50);
      const score = Math.round(Math.min(100, Math.max(0, val)) * 10) / 10;
      rawScores[idx++] = score;
      if (score < minScore) minScore = score;
      if (score > maxScore) maxScore = score;
    }
  }

  // 2. Compute local range for dynamic gradient scaling (local worst to best)
  const spread = maxScore - minScore;
  const effectiveMin = spread >= 1 ? minScore : Math.max(0, minScore - 0.5);
  const effectiveMax = spread >= 1 ? maxScore : Math.min(100, maxScore + 0.5);
  const effectiveSpread = Math.max(1e-6, effectiveMax - effectiveMin);

  // 3. Assemble output grid with local normalized gradient weights and colors
  const out: HeatPoint[] = new Array(total);
  idx = 0;

  for (let r = 0; r < rows; r++) {
    const lat = minlat + (r + 0.5) * h;
    for (let c = 0; c < cols; c++) {
      const lon = minlon + (c + 0.5) * w;
      const score = rawScores[idx];
      const normalizedWeight = spread >= 1
        ? Math.min(1, Math.max(0, (score - effectiveMin) / effectiveSpread))
        : Math.min(1, Math.max(0, score / 100));

      const level = heatLevel(score);
      const fillColor = colorForWeight(normalizedWeight);

      out[idx] = {
        h3: `interp-${c}:${r}`,
        score_goodness: score,
        lon,
        lat,
        weight: normalizedWeight,
        level,
        fillColor,
        localMin: minScore,
        localMax: maxScore,
      };
      idx++;
    }
  }

  return out;
}

/**
 * Normalise any /area-scores payload (AreaHex[] or GeoJSON FeatureCollection)
 * to hexes; fall back to `fallback` (mock) when nothing usable arrives.
 */
export function resolveHexes(input: unknown, fallback: AreaHex[]): AreaHex[] {
  if (Array.isArray(input)) {
    const valid = (input as AreaHex[]).filter(
      (h) =>
        typeof h?.h3 === "string" &&
        Number.isFinite(h?.score_goodness) &&
        Number.isFinite(h?.lon) &&
        Number.isFinite(h?.lat),
    );
    return valid.length > 0 ? valid : fallback;
  }
  const fromGeo = hexesFromGeoJSON(input);
  return fromGeo.length > 0 ? fromGeo : fallback;
}
