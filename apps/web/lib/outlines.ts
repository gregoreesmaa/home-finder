import type { ParkOutline } from "./layers";
import type { FloodArea } from "./layers_flood";
import { MAAPARCEL_CLASS_FILL, type MaaParcelArea } from "./layers_maaparcel";
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
// FLOOD-HOOK (#487): flood-zone polygon slot (choropleth fills, never a
// gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const FLOOD_SRC = "flood-zone-polys";
const FLOOD_FILL = "flood-zone-fill";
const FLOOD_CASING = "flood-zone-casing";
// MAAPARCEL-HOOK (#491): kataster parcel-class slot (omandivorm fills,
// never a gradient). Clearing covers these ids too — one overlay slot
// paints either kind, never stacks (see clearVectorOverlays).
const MAAPARCEL_SRC = "maaparcel-polys";
const MAAPARCEL_FILL = "maaparcel-fill";
const MAAPARCEL_CASING = "maaparcel-casing";
const POINT_SRC = "layer-overlay-src";
const POINT_CASING = "layer-overlay-casing";
const POINT_CORE = "layer-overlay-core";

/** One overlay slot: painting any kind clears the others, never stacks. */
export function clearVectorOverlays(mapObj: OutlineMap): void {
  // FLOOD-HOOK (#487): flood fill + casing join the cleared slot.
  // MAAPARCEL-HOOK (#491): parcel fill + casing join the cleared slot.
  for (const id of [PARK_CASING, PARK_CORE, POINT_CASING, POINT_CORE, FLOOD_FILL, FLOOD_CASING, MAAPARCEL_FILL, MAAPARCEL_CASING]) {
    try {
      if (mapObj.getLayer(id)) mapObj.removeLayer(id);
    } catch {
      /* already gone */
    }
  }
  // FLOOD-HOOK (#487): flood source joins the cleared slot.
  // MAAPARCEL-HOOK (#491): parcel source joins the cleared slot.
  for (const id of [PARK_SRC, POINT_SRC, FLOOD_SRC, MAAPARCEL_SRC]) {
    try {
      if (mapObj.getSource(id)) mapObj.removeSource(id);
    } catch {
      /* already gone */
    }
  }
}

/**
 * Insert after the LAST paint layer (fill/line/circle/heatmap/
 * fill-extrusion/raster/background/hillshade), so markers sit above
 * buildings and streets but below the label block and stay readable
 * under street names. Basemap styles often put an early symbol layer
 * under their fills — inserting before the FIRST symbol buries markers
 * under buildings, which is the bug this replaces.
 */
const PAINT_TYPES: ReadonlySet<string> = new Set([
  "fill",
  "line",
  "circle",
  "heatmap",
  "fill-extrusion",
  "raster",
  "background",
  "hillshade",
]);

function abovePaint(mapObj: OutlineMap): string | undefined {
  const style = mapObj.getStyle() as { layers?: { id: string; type: string }[] } | null;
  const layers = style?.layers;
  if (!layers || layers.length === 0) return undefined;
  let lastPaint = -1;
  for (let i = 0; i < layers.length; i++) {
    const l = layers[i];
    if (l && typeof l.id === "string" && PAINT_TYPES.has(l.type)) lastPaint = i;
  }
  // No paint layers: bottom of the stack (under labels, above nothing).
  if (lastPaint === -1) return layers[0] && typeof layers[0].id === "string" ? layers[0].id : undefined;
  // Paint runs to the top: topmost.
  const next = layers[lastPaint + 1];
  return next && typeof next.id === "string" ? next.id : undefined;
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
  const before = abovePaint(mapObj);
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

// FLOOD-HOOK (#487): KAUR flood-zone choropleth fills.

/**
 * Paint flood-zone polygons (translucent blue fill + white casing) so
 * the inside-a-named-zone vs honestly-unknown-outside boundary reads at
 * a glance. This is a CHOROPLETH, never a gradient: membership is binary
 * per parcel (centre and edge of a polygon read alike — the scorer pins
 * that), and no score field is painted anywhere. Clears stale overlay
 * layers first; no-op when the style is not loaded yet or areas is
 * nullish. Malformed rings are skipped, never faked.
 */
export function applyFloodPolygons(
  mapObj: OutlineMap,
  areas: FloodArea[] | null | undefined,
  opts: { color: string },
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!areas || areas.length === 0) return;
  const features = [];
  for (const a of areas) {
    if (!a || !Array.isArray(a.r)) continue;
    const polys = [];
    for (const ring of a.r) {
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
      polys.push([closed]);
    }
    if (polys.length === 0) continue;
    features.push({
      type: "Feature",
      properties: { nimi: typeof a.nimi === "string" ? a.nimi : "" },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(FLOOD_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: FLOOD_FILL,
      type: "fill",
      source: FLOOD_SRC,
      paint: {
        "fill-color": opts.color,
        "fill-opacity": 0.25,
        "fill-outline-color": opts.color,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: FLOOD_CASING,
      type: "line",
      source: FLOOD_SRC,
      paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.9 },
    },
    before,
  );
}

// MAAPARCEL-HOOK (#491): kataster parcel-class choropleth fills.

/**
 * Paint kataster parcel polygons (omandivorm-class fills + white casing)
 * so the registered-parcel fabric reads at a glance. This is a
 * CHOROPLETH of register facts, never a gradient: colors encode the
 * omvorm class (see MAAPARCEL_CLASS_FILL), and no score field is painted
 * anywhere. Clears stale overlay layers first; no-op when the style is
 * not loaded yet or parcels is nullish. Malformed rings are skipped,
 * never faked; unknown classes fall back to muu (never dropped).
 */
export function applyMaaParcelPolygons(
  mapObj: OutlineMap,
  parcels: MaaParcelArea[] | null | undefined,
  opts: { casing: string },
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!parcels || parcels.length === 0) return;
  const features = [];
  for (const a of parcels) {
    if (!a || !Array.isArray(a.r)) continue;
    const polys = [];
    for (const ring of a.r) {
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
      polys.push([closed]);
    }
    if (polys.length === 0) continue;
    const cls =
      typeof a.cls === "string" && a.cls in MAAPARCEL_CLASS_FILL ? a.cls : "muu";
    features.push({
      type: "Feature",
      properties: {
        cls,
        tunnus: typeof a.tunnus === "string" ? a.tunnus : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(MAAPARCEL_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: MAAPARCEL_FILL,
      type: "fill",
      source: MAAPARCEL_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "cls"],
          "era", MAAPARCEL_CLASS_FILL.era,
          "muni", MAAPARCEL_CLASS_FILL.muni,
          "riik", MAAPARCEL_CLASS_FILL.riik,
          MAAPARCEL_CLASS_FILL.muu,
        ],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: MAAPARCEL_CASING,
      type: "line",
      source: MAAPARCEL_SRC,
      paint: { "line-color": opts.casing, "line-width": 1, "line-opacity": 0.9 },
    },
    before,
  );
}
