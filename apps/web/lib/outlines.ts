import type { ParkOutline } from "./layers";
import type { FloodArea } from "./layers_flood";
import type { EelisArea } from "./layers_eelis";
import { MAAPARCEL_CLASS_FILL, type MaaParcelArea } from "./layers_maaparcel";
import { SEVESO_CLASS_FILL, type SevesoArea } from "./layers_p4_seveso";
import { STATELAND_CLASS_FILL, type StatelandArea } from "./layers_p4_stateland";
import { SOIL_CLASS_FILL, type SoilArea } from "./layers_p4_soil";
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
// EELIS-HOOK (#488): nature-polygon slot (choropleth fills, never a
// gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const EELIS_SRC = "eelis-nature-polys";
const EELIS_FILL = "eelis-nature-fill";
const EELIS_CASING = "eelis-nature-casing";
// PLANKTPR-HOOK (#492): designated-use fill slot (polygons only —
// per-parcel fills colored by fit band, never kernels or points).
const USE_SRC = "planktpr-use-polys";
const USE_FILL = "planktpr-use-fill";
const USE_CASING = "planktpr-use-casing";
// SEVESO-HOOK (#613): danger-polygon slot (danger-class fills, never a
// gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const SEVESO_SRC = "seveso-danger-polys";
const SEVESO_FILL = "seveso-danger-fill";
const SEVESO_CASING = "seveso-danger-casing";
// STATELAND-HOOK (#615): state/auction-polygon slot (class fills, never
// a gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const STATELAND_SRC = "stateland-parcel-polys";
const STATELAND_FILL = "stateland-parcel-fill";
const STATELAND_CASING = "stateland-parcel-casing";
// SOIL-HOOK (#617): soil-contour slot (family fills, never a
// gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const SOIL_SRC = "soil-contour-polys";
const SOIL_FILL = "soil-contour-fill";
const SOIL_CASING = "soil-contour-casing";
const POINT_SRC = "layer-overlay-src";
const POINT_CASING = "layer-overlay-casing";
const POINT_CORE = "layer-overlay-core";

/** One overlay slot: painting any kind clears the others, never stacks. */
export function clearVectorOverlays(mapObj: OutlineMap): void {
  // FLOOD-HOOK (#487): flood fill + casing join the cleared slot.
  // MAAPARCEL-HOOK (#491): parcel fill + casing join the cleared slot.
  // EELIS-HOOK (#488): eelis fill + casing join the cleared slot.
  // PLANKTPR-HOOK (#492): use fill + casing join the cleared slot.
  // SEVESO-HOOK (#613): danger fill + casing join the cleared slot.
  // STATELAND-HOOK (#615): parcel fill + casing join the cleared slot.
  // STATELAND-HOOK (#615): parcel fill + casing join the cleared slot.
  // SOIL-HOOK (#617): contour fill + casing join the cleared slot.
  for (const id of [PARK_CASING, PARK_CORE, POINT_CASING, POINT_CORE, FLOOD_FILL, FLOOD_CASING, MAAPARCEL_FILL, MAAPARCEL_CASING, EELIS_FILL, EELIS_CASING, USE_FILL, USE_CASING, SEVESO_FILL, SEVESO_CASING, STATELAND_FILL, STATELAND_CASING, SOIL_FILL, SOIL_CASING]) {
    try {
      if (mapObj.getLayer(id)) mapObj.removeLayer(id);
    } catch {
      /* already gone */
    }
  }
  // FLOOD-HOOK (#487): flood source joins the cleared slot.
  // MAAPARCEL-HOOK (#491): parcel source joins the cleared slot.
  // EELIS-HOOK (#488): eelis source joins the cleared slot.
  // PLANKTPR-HOOK (#492): the use-fill source joins the same slot.
  // SEVESO-HOOK (#613): the danger-fill source joins the same slot.
  // STATELAND-HOOK (#615): the parcel-fill source joins the same slot.
  // SOIL-HOOK (#617): the contour-fill source joins the same slot.
  for (const id of [PARK_SRC, POINT_SRC, FLOOD_SRC, MAAPARCEL_SRC, EELIS_SRC, USE_SRC, SEVESO_SRC, STATELAND_SRC, SOIL_SRC]) {
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

// EELIS-HOOK (#488): EELIS nature-polygon choropleth fills.

/**
 * Paint EELIS nature polygons (translucent fill + white casing) so the
 * inside-a-named-zone vs honestly-unknown-outside boundary reads at a
 * glance. This is a CHOROPLETH, never a gradient: membership is binary
 * per parcel (centre and edge of a polygon read alike — the scorer pins
 * that the LABEL scores, distance only gates), and no score field is
 * painted anywhere. Clears stale overlay layers first; no-op when the
 * style is not loaded yet or areas is nullish. Malformed rings are
 * skipped, never faked.
 */
export function applyEelisPolygons(
  mapObj: OutlineMap,
  areas: EelisArea[] | null | undefined,
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
      properties: {
        nimi: typeof a.nimi === "string" ? a.nimi : "",
        kiht: typeof a.kiht === "string" ? a.kiht : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(EELIS_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: EELIS_FILL,
      type: "fill",
      source: EELIS_SRC,
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
      id: EELIS_CASING,
      type: "line",
      source: EELIS_SRC,
      paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.9 },
    },
    before,
  );
}

/** One scored designated-use fill: outer rings + their band color. */
export interface UseFillPolygon {
  rings: number[][][];
  /** Hex fill color (the caller's band color — unscored rows never arrive). */
  color: string;
}

// PLANKTPR-HOOK (#492): designated-use fills (p47 exact per-parcel
// joins). Paints translucent fills (white casing + band-colored core)
// ABOVE the base field, so harvested kehtestatud polygons read at a
// glance while everything outside them stays the honest unknown field.
// Clears stale overlays first; no-op when the style is not loaded yet
// or fills is nullish. Unscored rows (non-decree stage, unknown use,
// non-Tallinn) must be filtered by the CALLER — the painter draws what
// it is given, one feature per ring.
export function applyUsePolygons(
  mapObj: OutlineMap,
  fills: UseFillPolygon[] | null | undefined,
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!fills || fills.length === 0) return;
  const features = [];
  for (const f of fills) {
    if (!f || typeof f.color !== "string" || !Array.isArray(f.rings)) continue;
    for (const ring of f.rings) {
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
        properties: { color: f.color },
        geometry: { type: "Polygon", coordinates: [closed] },
      });
    }
  }
  if (features.length === 0) return;
  mapObj.addSource(USE_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: USE_CASING,
      type: "line",
      source: USE_SRC,
      paint: { "line-color": "#ffffff", "line-width": 3, "line-opacity": 0.9 },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: USE_FILL,
      type: "fill",
      source: USE_SRC,
      paint: {
        "fill-color": ["get", "color"],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
}

// SEVESO-HOOK (#613): Päästeamet danger-class choropleth fills.

/**
 * Paint Seveso danger polygons (danger-class fills + white casing) so
 * the inside-a-named-danger-area vs honestly-unknown-outside boundary
 * reads at a glance. This is a CHOROPLETH of register facts, never a
 * gradient: colors encode the danger class (see SEVESO_CLASS_FILL —
 * toxic worst red, heat/overpressure orange family, unknown slate),
 * and no score field is painted anywhere. Clears stale overlay layers
 * first; no-op when the style is not loaded yet or areas is nullish.
 * Malformed rings are skipped, never faked; unknown classes fall back
 * to unknown (never dropped).
 */
export function applySevesoPolygons(
  mapObj: OutlineMap,
  areas: SevesoArea[] | null | undefined,
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
    const danger =
      typeof a.danger === "string" && a.danger in SEVESO_CLASS_FILL ? a.danger : "unknown";
    features.push({
      type: "Feature",
      properties: {
        danger,
        zone_id: typeof a.zone_id === "string" ? a.zone_id : "",
        nimi: typeof a.nimi === "string" ? a.nimi : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(SEVESO_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: SEVESO_FILL,
      type: "fill",
      source: SEVESO_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "danger"],
          "toxic", SEVESO_CLASS_FILL.toxic,
          "heat", SEVESO_CLASS_FILL.heat,
          "overpressure", SEVESO_CLASS_FILL.overpressure,
          "combustion", SEVESO_CLASS_FILL.combustion,
          SEVESO_CLASS_FILL.unknown,
        ],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: SEVESO_CASING,
      type: "line",
      source: SEVESO_SRC,
      paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.9 },
    },
    before,
  );
}

// STATELAND-HOOK (#615): KATRI state + auction-flag class choropleth fills.

/**
 * Paint state/auction parcels (class fills + white casing) so the
 * inside-a-named-state-parcel vs honestly-unknown-outside boundary
 * reads at a glance. This is a CHOROPLETH of register facts, never a
 * gradient: colors encode the class (see STATELAND_CLASS_FILL — state
 * assurance-olive, auction caution-yellow with the deadline carried on
 * the row), and no score field is painted anywhere. Auction flags
 * EXPIRE upstream (only live deadlines join the sidecar — the painter
 * draws what it is given). Clears stale overlay layers first; no-op
 * when the style is not loaded yet or areas is nullish. Malformed
 * rings are skipped, never faked; unknown classes fall back to state
 * (never dropped).
 */
export function applyStatelandPolygons(
  mapObj: OutlineMap,
  areas: StatelandArea[] | null | undefined,
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
    const cls =
      typeof a.cls === "string" && a.cls in STATELAND_CLASS_FILL ? a.cls : "state";
    features.push({
      type: "Feature",
      properties: {
        cls,
        zone_id: typeof a.zone_id === "string" ? a.zone_id : "",
        nimi: typeof a.nimi === "string" ? a.nimi : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(STATELAND_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: STATELAND_FILL,
      type: "fill",
      source: STATELAND_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "cls"],
          "state", STATELAND_CLASS_FILL.state,
          STATELAND_CLASS_FILL.auction,
        ],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: STATELAND_CASING,
      type: "line",
      source: STATELAND_SRC,
      paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.9 },
    },
    before,
  );
}

// SOIL-HOOK (#617): Maa-amet soil-contour family choropleth fills.

/**
 * Paint soil contours (family fills + white casing) so the
 * inside-a-named-contour vs honestly-unknown-outside boundary reads at
 * a glance. This is a CHOROPLETH of register facts, never a gradient:
 * colors encode the family band (see SOIL_CLASS_FILL — saviliiv lime
 * through turvas near-black, scorer parity 85→25), and no score field
 * is painted anywhere. The viewport proxy upstream already drops urban
 * / water / undecoded contours (the painter draws what it is given).
 * Clears stale overlay layers first; no-op when the style is not loaded
 * yet or areas is nullish. Malformed rings are skipped, never faked;
 * unknown classes fall back to liiv (never dropped — defensive only:
 * upstream only sends decoded bands).
 */
export function applySoilPolygons(
  mapObj: OutlineMap,
  areas: SoilArea[] | null | undefined,
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
    const cls =
      typeof a.cls === "string" && a.cls in SOIL_CLASS_FILL ? a.cls : "liiv";
    features.push({
      type: "Feature",
      properties: {
        cls,
        zone_id: typeof a.zone_id === "string" ? a.zone_id : "",
        family: typeof a.family === "string" ? a.family : "",
        code: typeof a.code === "string" ? a.code : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(SOIL_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: SOIL_FILL,
      type: "fill",
      source: SOIL_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "cls"],
          "saviliiv",
          SOIL_CLASS_FILL.saviliiv,
          "liiv",
          SOIL_CLASS_FILL.liiv,
          "liivsavi",
          SOIL_CLASS_FILL.liivsavi,
          "leede",
          SOIL_CLASS_FILL.leede,
          "paepealne",
          SOIL_CLASS_FILL.paepealne,
          "savi",
          SOIL_CLASS_FILL.savi,
          "glei",
          SOIL_CLASS_FILL.glei,
          "turvas",
          SOIL_CLASS_FILL.turvas,
          SOIL_CLASS_FILL.liiv,
        ],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: SOIL_CASING,
      type: "line",
      source: SOIL_SRC,
      paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.9 },
    },
    before,
  );
}
