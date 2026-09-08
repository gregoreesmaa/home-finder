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
  weight: number; // 0..1 intensity for HeatmapLayer
  level: HeatLevel;
  fillColor: [number, number, number, number];
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

/** Legend rows for the goodness/badness scale (green -> amber -> red). */
export function legendBuckets(): LegendBucket[] {
  return [
    { level: "good", label: "Hea ≥ 70", min: 70, max: 100, css: LEVEL_CSS.good },
    { level: "mid", label: "Keskmine 40–69", min: 40, max: 69, css: LEVEL_CSS.mid },
    { level: "bad", label: "Halb < 40", min: 0, max: 39, css: LEVEL_CSS.bad },
  ];
}

/** One-line popup content for a clicked heat point. */
export function popupText(p: HeatPoint): string {
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
