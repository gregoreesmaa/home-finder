import type { ParkOutline } from "./layers";

/** Minimal map surface for the outline overlay (source + two line layers). */
export interface OutlineMap {
  getStyle: () => unknown;
  addSource: (id: string, src: unknown) => void;
  addLayer: (l: unknown) => void;
  removeLayer: (id: string) => void;
  removeSource: (id: string) => void;
  getLayer: (id: string) => unknown;
  getSource: (id: string) => unknown;
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
  const SRC = "park-outlines";
  const CASING = "park-outline-casing";
  const CORE = "park-outline-core";
  for (const id of [CASING, CORE]) {
    try {
      if (mapObj.getLayer(id)) mapObj.removeLayer(id);
    } catch {
      /* already gone */
    }
  }
  try {
    if (mapObj.getSource(SRC)) mapObj.removeSource(SRC);
  } catch {
    /* already gone */
  }
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
  mapObj.addSource(SRC, { type: "geojson", data: { type: "FeatureCollection", features } });
  mapObj.addLayer({
    id: CASING,
    type: "line",
    source: SRC,
    paint: { "line-color": "#ffffff", "line-width": 4, "line-opacity": 0.9 },
  });
  mapObj.addLayer({
    id: CORE,
    type: "line",
    source: SRC,
    paint: { "line-color": "#166534", "line-width": 1.5, "line-opacity": 0.95 },
  });
}
