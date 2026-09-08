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
