import type { ParkOutline } from "./layers";
import type { OverlayPoint } from "./overlays";

/** Minimal map surface for vector overlays (sources + paint layers). */
export interface OutlineMap {
  getStyle: () => unknown;
  addSource: (id: string, src: unknown) => void;
  addLayer: (l: unknown, beforeId?: string) => void;
  removeLayer: (id: string) => void;
  removeSource: (id: string) => void;
  getLayer: (id: string) => unknown;
  getSource: (id: string) => unknown;
}

const PARK_SRC = "park-outlines";
const PARK_CASING = "park-outline-casing";
const PARK_CORE = "park-outline-core";
const POINT_SRC = "layer-overlay-src";
const POINT_CASING = "layer-overlay-casing";
const POINT_CORE = "layer-overlay-core";

/** One overlay slot: painting either kind clears the other, never stacks. */
export function clearVectorOverlays(mapObj: OutlineMap): void {
  for (const id of [PARK_CASING, PARK_CORE, POINT_CASING, POINT_CORE]) {
    try {
      if (mapObj.getLayer(id)) mapObj.removeLayer(id);
    } catch {
      /* already gone */
    }
  }
  for (const id of [PARK_SRC, POINT_SRC]) {
    try {
      if (mapObj.getSource(id)) mapObj.removeSource(id);
    } catch {
      /* already gone */
    }
  }
}

/** First label layer id, so markers stay readable under street names. */
function beforeLabels(mapObj: OutlineMap): string | undefined {
  const style = mapObj.getStyle() as { layers?: { id: string; type: string }[] } | null;
  return style?.layers?.find((l) => l?.type === "symbol")?.id;
}

/**
 * Paint park polygon outlines (white casing + dark-green core) so the
 * scored-inside vs honestly-scored-outside boundary is visible. Clears
 * stale outline layers first; no-op when the style is not loaded yet or
 * outlines is nullish.
 */
export function applyOutlines(
  mapObj: OutlineMap,
  outlines: ParkOutline[] | null | undefined,
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!outlines || outlines.length === 0) return;
  const features = [];
  for (const o of outlines) {
    if (!o || !Array.isArray(o.r)) continue;
    for (const ring of o.r) {
      if (!Array.isArray(ring) || ring.length < 3) continue;
      const pts = ring.filter(
        (pt) =>
          Array.isArray(pt) &&
          pt.length === 2 &&
          pt.every((n) => typeof n === "number" && Number.isFinite(n)),
      );
      if (pts.length < 3) continue;
      const first = pts[0];
      const last = pts[pts.length - 1];
      const closed =
        first[0] === last[0] && first[1] === last[1] ? pts : [...pts, [first[0], first[1]]];
      features.push({
        type: "Feature",
        properties: {},
        geometry: { type: "Polygon", coordinates: [closed] },
      });
    }
  }
  if (features.length === 0) return;
  mapObj.addSource(PARK_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  mapObj.addLayer({
    id: PARK_CASING,
    type: "line",
    source: PARK_SRC,
    paint: { "line-color": "#ffffff", "line-width": 4, "line-opacity": 0.9 },
  });
  mapObj.addLayer({
    id: PARK_CORE,
    type: "line",
    source: PARK_SRC,
    paint: { "line-color": "#166534", "line-width": 1.5, "line-opacity": 0.95 },
  });
}

/**
 * Paint point markers (white casing + colored core) ABOVE the raster
 * heatmap, so the scored features read at a glance. Core radius grows
 * with the feature weight (transit: GTFS weekday trips). Clears stale
 * overlays first; no-op when the style is not loaded yet or points is
 * nullish. Render-capped (defense in depth: callers cap to OVERLAY_CAP).
 */
export function applyPointOverlay(
  mapObj: OutlineMap,
  points: OverlayPoint[] | null | undefined,
  opts: { color: string },
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!points || points.length === 0) return;
  const features = [];
  for (const p of points.slice(0, 2000)) {
    if (!p || !Number.isFinite(p.lon) || !Number.isFinite(p.lat)) continue;
    const w = typeof p.w === "number" && Number.isFinite(p.w) && p.w >= 0 ? p.w : 1;
    features.push({
      type: "Feature",
      properties: { w },
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(POINT_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  // Transit hubs (tens of daily departures) read ~2x a median stop; the
  // legend states the sizing. Stops without GTFS coverage (w = 0) still
  // draw: unknown frequency is not bad frequency.
  const radius = [
    "interpolate",
    ["linear"],
    ["get", "w"],
    0, 3,
    100, 4.5,
    500, 6,
    1500, 8,
  ];
  const before = beforeLabels(mapObj);
  mapObj.addLayer(
    {
      id: POINT_CASING,
      type: "circle",
      source: POINT_SRC,
      paint: {
        "circle-radius": ["+", radius, 1.5],
        "circle-color": "#ffffff",
        "circle-opacity": 0.9,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: POINT_CORE,
      type: "circle",
      source: POINT_SRC,
      paint: {
        "circle-radius": radius,
        "circle-color": opts.color,
        "circle-opacity": 0.9,
      },
    },
    before,
  );
}
