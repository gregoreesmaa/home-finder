import type { ParkOutline } from "./layers";
import type { FloodArea } from "./layers_flood";
// SHED-HOOK (#763): shed-hub fills (reachable range, never a gradient).
import type { ShedArea } from "./layers_p4_tomtom_sheds";
import type { EelisArea } from "./layers_eelis";
import { MAAPARCEL_CLASS_FILL, type MaaParcelArea } from "./layers_maaparcel";
import { SEVESO_CLASS_FILL, type SevesoArea } from "./layers_p4_seveso";
import { STATELAND_CLASS_FILL, type StatelandArea } from "./layers_p4_stateland";
import { QUARRY_CLASS_FILL, type QuarryArea } from "./layers_p4_quarry";
import { MAAPARANDUS_CLASS_FILL, type MaaparandusArea } from "./layers_p4_maaparandus";
import { SOIL_CLASS_FILL, type SoilArea } from "./layers_p4_soil";
import { ETAK_CLASS_FILL, type EtakArea } from "./layers_p4_etak";
import { renderReliefTint, type ReliefTintGrid } from "./layers_p4_relief";
import { renderCanopyTint, type CanopyTintGrid } from "./layers_p4_canopy";
// BUILDINGS-HOOK (#621): LoD1 height-tint image slot (character tint,
// never a gradient/score). Same discipline as the canopy slot.
import { renderBuildingsTint, type BuildingsTintGrid } from "./layers_p4_buildings";
import { DENSITY_CLASS_FILL, type DensityArea } from "./layers_p4_density";
import { FOREST_CLASS_FILL, type ForestArea } from "./layers_p4_forest";
import { NOISE_BAND_FILL, type NoiseArea } from "./layers_p4_noise";
import {
  HARBOUR_CELL_FILL,
  type HarbourCell,
  type HarbourPort,
} from "./layers_p4_harbour";
import { KPO_BAND_FILL, kpoFillKey, type KpoArea } from "./layers_p4_kpo";
import {
  DELAY_BAND_FILL,
  delayBandForFactor,
  type DelayArea,
} from "./layers_p4_delay";
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
// SHED-HOOK (#763): shed-hub polygon slot (reachable-range fills, never
// a gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const SHED_SRC = "shed-hub-polys";
const SHED_FILL_LYR = "shed-hub-fill";
const SHED_CASING = "shed-hub-casing";
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
// QUARRY-HOOK (#614): permit/watch-polygon slot (class fills, never a
// gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const QUARRY_SRC = "quarry-permit-polys";
const QUARRY_FILL = "quarry-permit-fill";
const QUARRY_CASING = "quarry-permit-casing";
// DRAINAGE-HOOK (#616): network/invalid fill + outflow line slot
// (class fills + thin centerlines, never a gradient). Clearing covers
// these ids too — one overlay slot paints either kind, never stacks
// (see clearVectorOverlays).
const MAAPARANDUS_SRC = "drainage-network-polys";
const MAAPARANDUS_FILL = "drainage-network-fill";
const MAAPARANDUS_CASING = "drainage-network-casing";
const MAAPARANDUS_LINES = "drainage-outflow-lines";
const MAAPARANDUS_OUTFLOW_SRC = "drainage-outflow-lines-src";
// SOIL-HOOK (#617): soil-contour slot (family fills, never a
// gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const SOIL_SRC = "soil-contour-polys";
const SOIL_FILL = "soil-contour-fill";
const SOIL_CASING = "soil-contour-casing";
// ETAK-HOOK (#618): wetland/water/yard-polygon slot (class fills, never
// a gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const ETAK_SRC = "etak-contour-polys";
const ETAK_FILL = "etak-contour-fill";
const ETAK_CASING = "etak-contour-casing";
// RELIEF-HOOK (#619): hypsometric tint image slot (character tint,
// never a gradient/score). Clearing covers these ids too — one overlay
// slot paints either kind, never stacks (see clearVectorOverlays).
const RELIEF_SRC = "relief-tint-src";
const RELIEF_LYR = "relief-tint-lyr";
// CANOPY-HOOK (#620): canopy class-tint image slot (character tint,
// never a gradient/score). Clearing covers these ids too — one overlay
// slot paints either kind, never stacks (see clearVectorOverlays).
const CANOPY_SRC = "canopy-tint-src";
const CANOPY_LYR = "canopy-tint-lyr";
// BUILDINGS-HOOK (#621): buildings height-tint image slot (character
// tint, never a gradient/score). Clearing covers these ids too — one
// overlay slot paints either kind, never stacks (see
// clearVectorOverlays).
const BUILDINGS_SRC = "buildings-tint-src";
const BUILDINGS_LYR = "buildings-tint-lyr";
// DENSITY-HOOK (#622): density-square slot (class fills, never a
// gradient/score). Clearing covers these ids too — one overlay slot
// paints either kind, never stacks (see clearVectorOverlays).
const DENSITY_SRC = "density-square-polys";
const DENSITY_FILL = "density-square-fill";
const DENSITY_CASING = "density-square-casing";
// FOREST-HOOK (#624): forest-change slot (class fills, never a
// gradient). Clearing covers these ids too — one overlay slot paints
// either kind, never stacks (see clearVectorOverlays).
const FOREST_SRC = "forest-change-polys";
const FOREST_FILL = "forest-change-fill";
const FOREST_CASING = "forest-change-casing";
const NOISE_SRC = "noise-band-polys";
const NOISE_FILL = "noise-band-fill";
const NOISE_CASING = "noise-band-casing";
const HARBOUR_SRC = "harbour-cell-polys";
// KPO-HOOK (#626): kpo zone slot (ban/conditioned fills, never a
// gradient/score). Clearing covers these ids too — one overlay slot
// paints either kind, never stacks (see clearVectorOverlays).
const KPO_SRC = "kpo-zone-polys";
const KPO_FILL = "kpo-zone-fill";
const KPO_CASING = "kpo-zone-casing";
// DELAY-HOOK (#629): delay band slot (factor fills, never a
// score/gradient). Clearing covers these ids too — one overlay slot
// paints either kind, never stacks (see clearVectorOverlays).
const DELAY_SRC = "delay-band-polys";
const DELAY_FILL = "delay-band-fill";
const DELAY_CASING = "delay-band-casing";
const HARBOUR_FILL = "harbour-cell-fill";
const HARBOUR_CASING = "harbour-cell-casing";
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
  // QUARRY-HOOK (#614): permit fill + casing join the cleared slot.
  // DRAINAGE-HOOK (#616): network fill + casing + outflow lines join
  // the cleared slot.
  // SOIL-HOOK (#617): contour fill + casing join the cleared slot.
  // ETAK-HOOK (#618): etak contour fill + casing join the cleared
  // slot.
  // DELAY-HOOK (#629): delay fill + casing join the cleared slot.
  // SHED-HOOK (#763): shed fill + casing join the cleared slot.
  for (const id of [PARK_CASING, PARK_CORE, POINT_CASING, POINT_CORE, FLOOD_FILL, FLOOD_CASING, MAAPARCEL_FILL, MAAPARCEL_CASING, EELIS_FILL, EELIS_CASING, USE_FILL, USE_CASING, SEVESO_FILL, SEVESO_CASING, STATELAND_FILL, STATELAND_CASING, QUARRY_FILL, QUARRY_CASING, MAAPARANDUS_FILL, MAAPARANDUS_CASING, MAAPARANDUS_LINES, SOIL_FILL, SOIL_CASING, ETAK_FILL, ETAK_CASING, RELIEF_LYR, CANOPY_LYR, BUILDINGS_LYR, DENSITY_FILL, DENSITY_CASING, FOREST_FILL, FOREST_CASING, NOISE_FILL, NOISE_CASING, HARBOUR_FILL, HARBOUR_CASING, KPO_FILL, KPO_CASING, DELAY_FILL, DELAY_CASING, SHED_FILL_LYR, SHED_CASING]) {
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
  // QUARRY-HOOK (#614): the permit-fill source joins the same slot.
  // DRAINAGE-HOOK (#616): the network-fill source joins the same slot.
  // SOIL-HOOK (#617): the contour-fill source joins the same slot.
  // ETAK-HOOK (#618): the etak-contour source joins the same slot.
  // DELAY-HOOK (#629): the delay-band source joins the same slot.
  // SHED-HOOK (#763): the shed-hub source joins the same slot.
  for (const id of [PARK_SRC, POINT_SRC, FLOOD_SRC, MAAPARCEL_SRC, EELIS_SRC, USE_SRC, SEVESO_SRC, STATELAND_SRC, QUARRY_SRC, MAAPARANDUS_SRC, MAAPARANDUS_OUTFLOW_SRC, SOIL_SRC, ETAK_SRC, RELIEF_SRC, CANOPY_SRC, BUILDINGS_SRC, DENSITY_SRC, FOREST_SRC, NOISE_SRC, HARBOUR_SRC, KPO_SRC, DELAY_SRC, SHED_SRC]) {
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

// SHED-HOOK (#763): shed-hub reachable-range fills.

/**
 * Paint TomTom shed-hub polygons (reachable-range fills + white casing)
 * so the 15/30-min peak/off-peak work reach reads at a glance. These
 * are ISOCHRONE fills, never a gradient: inside-hub-reach vs outside/
 * unknown, and no score field is painted anywhere. Ring order is
 * [lat, lon] (harvester cache shape) — flipped to GeoJSON [lon, lat]
 * here. Clears stale overlay layers first; no-op when the style is not
 * loaded yet or areas is nullish. Malformed rings are skipped, never
 * faked; unmeasured hubs have no ring and paint nothing (never a dot).
 */
export function applyShedPolygons(
  mapObj: OutlineMap,
  areas: ShedArea[] | null | undefined,
  opts: { color: string },
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!areas || areas.length === 0) return;
  const features = [];
  for (const a of areas) {
    if (!a || typeof a.hub !== "string" || !Array.isArray(a.ring)) continue;
    const pts = a.ring.filter(
      (pt) =>
        Array.isArray(pt) &&
        pt.length === 2 &&
        pt.every((n) => typeof n === "number" && Number.isFinite(n)),
    );
    if (pts.length < 3) continue;
    const flipped = pts.map(([lat, lon]) => [lon, lat]);
    const first = flipped[0];
    const last = flipped[flipped.length - 1];
    const closed =
      first[0] === last[0] && first[1] === last[1]
        ? flipped
        : [...flipped, [first[0], first[1]]];
    features.push({
      type: "Feature",
      properties: { hub: a.hub },
      geometry: { type: "MultiPolygon", coordinates: [[closed]] },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(SHED_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: SHED_FILL_LYR,
      type: "fill",
      source: SHED_SRC,
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
      id: SHED_CASING,
      type: "line",
      source: SHED_SRC,
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

// DRAINAGE-HOOK (#616): maaparandus network/invalid fills + outflow lines.

function closeRingMaaparandus(pts: number[][]): number[][] {
  const first = pts[0];
  const last = pts[pts.length - 1];
  return first[0] === last[0] && first[1] === last[1]
    ? pts
    : [...pts, [first[0], first[1]]];
}

/**
 * Paint drainage shapes (network/invalid class fills + white casing +
 * outflow centerlines) so the inside-a-named-network vs
 * honestly-unknown-outside boundary reads at a glance. This is a
 * CHOROPLETH of register facts, never a gradient: fills encode the
 * polygon class (see MAAPARANDUS_CLASS_FILL — network wetness-blue with
 * condition unproven, invalid derelict-brown), outflow lines paint as
 * thin centerlines (no fill, no buffer — the <= 100 m band stays
 * scorer-side), and no score field is painted anywhere. Clears stale
 * overlay layers first; no-op when the style is not loaded yet or
 * areas is nullish. Malformed shapes are skipped, never faked;
 * unknown classes fall back to network (never dropped).
 */
export function applyMaaparandusPolygons(
  mapObj: OutlineMap,
  areas: MaaparandusArea[] | null | undefined,
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!areas || areas.length === 0) return;
  const polys = [];
  const lines = [];
  for (const a of areas) {
    if (!a) continue;
    if (a.cls === "outflow") {
      if (!Array.isArray(a.l)) continue;
      const clean = [];
      for (const ln of a.l) {
        if (!Array.isArray(ln)) continue;
        const pts = ln.filter(
          (pt) =>
            Array.isArray(pt) &&
            pt.length === 2 &&
            pt.every((n) => typeof n === "number" && Number.isFinite(n)),
        );
        if (pts.length >= 2) clean.push(pts);
      }
      if (clean.length === 0) continue;
      lines.push({
        type: "Feature",
        properties: {
          zone_id: typeof a.zone_id === "string" ? a.zone_id : "",
          nimi: typeof a.nimi === "string" ? a.nimi : "",
        },
        geometry: {
          type: clean.length === 1 ? "LineString" : "MultiLineString",
          coordinates: clean.length === 1 ? clean[0] : clean,
        },
      });
      continue;
    }
    if (!Array.isArray(a.r)) continue;
    const rings = [];
    for (const ring of a.r) {
      if (!Array.isArray(ring) || ring.length < 3) continue;
      const pts = ring.filter(
        (pt) =>
          Array.isArray(pt) &&
          pt.length === 2 &&
          pt.every((n) => typeof n === "number" && Number.isFinite(n)),
      );
      if (pts.length < 3) continue;
      rings.push([closeRingMaaparandus(pts)]);
    }
    if (rings.length === 0) continue;
    const cls =
      a.cls === "invalid" ? "invalid" : "network";
    polys.push({
      type: "Feature",
      properties: {
        cls,
        zone_id: typeof a.zone_id === "string" ? a.zone_id : "",
        nimi: typeof a.nimi === "string" ? a.nimi : "",
      },
      geometry: { type: "MultiPolygon", coordinates: rings },
    });
  }
  if (polys.length === 0 && lines.length === 0) return;
  const before = abovePaint(mapObj);
  if (polys.length > 0) {
    mapObj.addSource(MAAPARANDUS_SRC, {
      type: "geojson",
      data: { type: "FeatureCollection", features: polys },
    });
    mapObj.addLayer(
      {
        id: MAAPARANDUS_FILL,
        type: "fill",
        source: MAAPARANDUS_SRC,
        paint: {
          "fill-color": [
            "match",
            ["get", "cls"],
            "invalid", MAAPARANDUS_CLASS_FILL.invalid,
            MAAPARANDUS_CLASS_FILL.network,
          ],
          "fill-opacity": 0.45,
        },
      },
      before,
    );
    mapObj.addLayer(
      {
        id: MAAPARANDUS_CASING,
        type: "line",
        source: MAAPARANDUS_SRC,
        paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.9 },
      },
      before,
    );
  }
  if (lines.length > 0) {
    mapObj.addSource(MAAPARANDUS_OUTFLOW_SRC, {
      type: "geojson",
      data: { type: "FeatureCollection", features: lines },
    });
    mapObj.addLayer(
      {
        id: MAAPARANDUS_LINES,
        type: "line",
        source: MAAPARANDUS_OUTFLOW_SRC,
        paint: {
          "line-color": MAAPARANDUS_CLASS_FILL.outflow,
          "line-width": 2,
          "line-opacity": 0.9,
        },
      },
      before,
    );
  }
}

// QUARRY-HOOK (#614): Maa-amet permit/watch class choropleth fills.

/**
 * Paint quarry permit/watch polygons (class fills + white casing) so
 * the inside-a-named-permit vs honestly-unknown-outside boundary reads
 * at a glance. This is a CHOROPLETH of register facts, never a
 * gradient: colors encode the class (see QUARRY_CLASS_FILL — active
 * avoidance-red, exploration caution-yellow), and no score field is
 * painted anywhere. The <= 2 km near-band is scorer-side only (no
 * buffered fills — fake precision refused). Clears stale overlay
 * layers first; no-op when the style is not loaded yet or areas is
 * nullish. Malformed rings are skipped, never faked; unknown classes
 * fall back to exploration (never dropped).
 */
// QUARRY-HOOK (#614): Maa-amet permit/watch class choropleth fills.

/**
 * Paint quarry permit/watch polygons (class fills + white casing) so
 * the inside-a-named-permit vs honestly-unknown-outside boundary reads
 * at a glance. This is a CHOROPLETH of register facts, never a
 * gradient: colors encode the class (see QUARRY_CLASS_FILL — active
 * avoidance-red, exploration caution-yellow), and no score field is
 * painted anywhere. The <= 2 km near-band is scorer-side only (no
 * buffered fills — fake precision refused). Clears stale overlay
 * layers first; no-op when the style is not loaded yet or areas is
 * nullish. Malformed rings are skipped, never faked; unknown classes
 * fall back to exploration (never dropped).
 */
export function applyQuarryPolygons(
  mapObj: OutlineMap,
  areas: QuarryArea[] | null | undefined,
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
      typeof a.cls === "string" && a.cls in QUARRY_CLASS_FILL ? a.cls : "exploration";
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
  mapObj.addSource(QUARRY_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: QUARRY_FILL,
      type: "fill",
      source: QUARRY_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "cls"],
          "active", QUARRY_CLASS_FILL.active,
          QUARRY_CLASS_FILL.exploration,
        ],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: QUARRY_CASING,
      type: "line",
      source: QUARRY_SRC,
      paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.9 },
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

// ETAK-HOOK (#618): ETAK wetland/water/yard class choropleth fills.

/**
 * Paint ETAK contours (wetland-class fills + water + yard fills, white
 * casing) so measured land-cover reads at a glance. This is a
 * CHOROPLETH of register facts, never a gradient: colors encode the
 * etak class (see ETAK_CLASS_FILL — wetland blues wettest-first,
 * standing/flowing water blue, impervious stone, green-yard green, yard
 * other stone-light), and no score field is painted anywhere. Clears
 * stale overlay layers first; no-op when the style is not loaded yet or
 * areas is nullish. Malformed rings are skipped, never faked; unknown
 * classes fall back to wet_other (never dropped). Outside every contour
 * is unknown (never dry land): unmapped ground is not dry ground.
 */
export function applyEtakPolygons(
  mapObj: OutlineMap,
  areas: EtakArea[] | null | undefined,
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
      typeof a.cls === "string" && a.cls in ETAK_CLASS_FILL ? a.cls : "wet_other";
    features.push({
      type: "Feature",
      properties: {
        cls,
        zone_id: typeof a.zone_id === "string" ? a.zone_id : "",
        label: typeof a.label === "string" ? a.label : "",
        name: typeof a.name === "string" ? a.name : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(ETAK_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: ETAK_FILL,
      type: "fill",
      source: ETAK_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "cls"],
          "wet_wettest", ETAK_CLASS_FILL.wet_wettest,
          "wet_mid", ETAK_CLASS_FILL.wet_mid,
          "wet_other", ETAK_CLASS_FILL.wet_other,
          "water", ETAK_CLASS_FILL.water,
          "yard_impervious", ETAK_CLASS_FILL.yard_impervious,
          "yard_green", ETAK_CLASS_FILL.yard_green,
          ETAK_CLASS_FILL.yard_other,
        ],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: ETAK_CASING,
      type: "line",
      source: ETAK_SRC,
      paint: { "line-color": "#ffffff", "line-width": 2, "line-opacity": 0.9 },
    },
    before,
  );
}

// RELIEF-HOOK (#619): DTM hypsometric character-tint image overlay.

/**
 * Paint the relief tint grid as a semi-transparent image overlay so
 * ground character reads at a glance. This is a CHARACTER TINT, never
 * a score: colors encode height bands (see RELIEF_LUT — moss lowlands
 * to pale rock, deliberately not green/red), and no score field is
 * painted anywhere. Clears stale overlay layers first; no-op when the
 * style is not loaded yet, when grid is nullish, or when there is no
 * document (canvas glue — the pure renderer renderReliefTint is
 * unit-tested; this seam only moves its bytes into an image source).
 */
export function applyReliefTint(
  mapObj: OutlineMap,
  grid: ReliefTintGrid | null | undefined,
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!grid) return;
  if (typeof document === "undefined") return;
  const { cols, rows, rgba } = renderReliefTint(grid);
  const canvas = document.createElement("canvas");
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.putImageData(new ImageData(rgba, cols, rows), 0, 0);
  const url = canvas.toDataURL("image/png");
  const b = grid.bbox;
  mapObj.addSource(RELIEF_SRC, {
    type: "image",
    url,
    coordinates: [
      [b.minlon, b.maxlat],
      [b.maxlon, b.maxlat],
      [b.maxlon, b.minlat],
      [b.minlon, b.minlat],
    ],
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: RELIEF_LYR,
      type: "raster",
      source: RELIEF_SRC,
      paint: { "raster-opacity": 0.85 },
    },
    before,
  );
}

// CANOPY-HOOK (#620): CHM class character-tint image overlay.

/**
 * Paint the canopy tint grid as a semi-transparent image overlay so
 * tree character reads at a glance. This is a CHARACTER TINT, never
 * a score: colors are the publisher's own CHM classes (see CANOPY_LUT),
 * and no score field is painted anywhere. Clears stale overlay layers
 * first; no-op when the style is not loaded yet, when grid is nullish,
 * or when there is no document (canvas glue — the pure renderer
 * renderCanopyTint is unit-tested; this seam only moves its bytes into
 * an image source).
 */
export function applyCanopyTint(
  mapObj: OutlineMap,
  grid: CanopyTintGrid | null | undefined,
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!grid) return;
  if (typeof document === "undefined") return;
  const { cols, rows, rgba } = renderCanopyTint(grid);
  const canvas = document.createElement("canvas");
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.putImageData(new ImageData(rgba, cols, rows), 0, 0);
  const url = canvas.toDataURL("image/png");
  const b = grid.bbox;
  mapObj.addSource(CANOPY_SRC, {
    type: "image",
    url,
    coordinates: [
      [b.minlon, b.maxlat],
      [b.maxlon, b.maxlat],
      [b.maxlon, b.minlat],
      [b.minlon, b.minlat],
    ],
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: CANOPY_LYR,
      type: "raster",
      source: CANOPY_SRC,
      paint: { "raster-opacity": 0.85 },
    },
    before,
  );
}

// BUILDINGS-HOOK (#621): LoD1 height character-tint image overlay.

/**
 * Paint the buildings tint grid as a semi-transparent image overlay so
 * built character reads at a glance. This is a CHARACTER TINT, never
 * a score: colors are OUR bins over measuredHeight (see BUILDINGS_LUT;
 * bins stated in the legend), and no score field is painted anywhere.
 * Clears stale overlay layers first; no-op when the style is not
 * loaded yet, when grid is nullish, or when there is no document
 * (canvas glue — the pure renderer renderBuildingsTint is
 * unit-tested; this seam only moves its bytes into an image source).
 */
export function applyBuildingsTint(
  mapObj: OutlineMap,
  grid: BuildingsTintGrid | null | undefined,
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  if (!grid) return;
  if (typeof document === "undefined") return;
  const { cols, rows, rgba } = renderBuildingsTint(grid);
  const canvas = document.createElement("canvas");
  canvas.width = cols;
  canvas.height = rows;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.putImageData(new ImageData(rgba, cols, rows), 0, 0);
  const url = canvas.toDataURL("image/png");
  const b = grid.bbox;
  mapObj.addSource(BUILDINGS_SRC, {
    type: "image",
    url,
    coordinates: [
      [b.minlon, b.maxlat],
      [b.maxlon, b.maxlat],
      [b.maxlon, b.minlat],
      [b.minlon, b.minlat],
    ],
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: BUILDINGS_LYR,
      type: "raster",
      source: BUILDINGS_SRC,
      paint: { "raster-opacity": 0.85 },
    },
    before,
  );
}

// DENSITY-HOOK (#622): INSPIRE PD 1 km square class choropleth fills.

/**
 * Paint density squares (class fills + white casing) so the
 * tranquil<->urban character reads at a glance. This is a CHOROPLETH
 * of census facts, never a gradient/score: colors encode OUR
 * inhabitants bins (see DENSITY_CLASS_FILL — bone to plum), and no
 * score field is painted anywhere. Squares paint EXACTLY (1 km cells
 * are the field, edges included — never interpolated). Clears stale
 * overlay layers first; no-op when the style is not loaded yet or
 * areas is nullish. Malformed rings are skipped, never faked; unknown
 * classes fall back to class 0 (never dropped).
 */
export function applyDensityPolygons(
  mapObj: OutlineMap,
  areas: DensityArea[] | null | undefined,
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
      typeof a.cls === "number" && Number.isInteger(a.cls) && a.cls >= 0 && a.cls <= 5
        ? String(a.cls)
        : "unknown";
    features.push({
      type: "Feature",
      properties: {
        cls,
        zone_id: typeof a.zone_id === "string" ? a.zone_id : "",
        value: typeof a.value === "number" ? a.value : 0,
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(DENSITY_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: DENSITY_FILL,
      type: "fill",
      source: DENSITY_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "cls"],
          "0",
          DENSITY_CLASS_FILL["0"],
          "1",
          DENSITY_CLASS_FILL["1"],
          "2",
          DENSITY_CLASS_FILL["2"],
          "3",
          DENSITY_CLASS_FILL["3"],
          "4",
          DENSITY_CLASS_FILL["4"],
          "5",
          DENSITY_CLASS_FILL["5"],
          DENSITY_CLASS_FILL.unknown,
        ],
        "fill-opacity": 0.45,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: DENSITY_CASING,
      type: "line",
      source: DENSITY_SRC,
      paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.5 },
    },
    before,
  );
}

// FOREST-HOOK (#624): metsamuutused detected-change class fills.

/**
 * Paint forest changes (detection-class fills + white casing) so the
 * 2024 detected-change warning reads at a glance. This is a CHOROPLETH
 * of detection facts, never a score: colors encode the detection age
 * class (see FOREST_CLASS_FILL — fresh umber darkest), and the
 * per-listing distance bands (<=3y<=500m->30 etc.) are the scorer's
 * job. Outside every polygon is NULL — never "safe forest". Clears
 * stale overlay layers first; no-op when the style is not loaded yet
 * or areas is nullish. Malformed rings are skipped, never faked;
 * unknown classes fall back oldest (never dropped).
 */
export function applyForestPolygons(
  mapObj: OutlineMap,
  areas: ForestArea[] | null | undefined,
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
      typeof a.cls === "number" && Number.isInteger(a.cls) && a.cls >= 1 && a.cls <= 3
        ? String(a.cls)
        : "unknown";
    features.push({
      type: "Feature",
      properties: {
        cls,
        change_id: typeof a.change_id === "string" ? a.change_id : "",
        season: typeof a.season === "string" ? a.season : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(FOREST_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: FOREST_FILL,
      type: "fill",
      source: FOREST_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "cls"],
          "1",
          FOREST_CLASS_FILL["1"],
          "2",
          FOREST_CLASS_FILL["2"],
          "3",
          FOREST_CLASS_FILL["3"],
          FOREST_CLASS_FILL.unknown,
        ],
        "fill-opacity": 0.5,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: FOREST_CASING,
      type: "line",
      source: FOREST_SRC,
      paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.5 },
    },
    before,
  );
}

// NOISE-HOOK (#625): myrakaart Lden/Lnight band fills.

/**
 * Paint noise bands (quiet-green to loud-red fills + white casing) so
 * modelled loud vs quiet reads at a glance. This is a CHOROPLETH of
 * modelled facts, never a score: colors encode the 5 dB band lower
 * bound (see NOISE_BAND_FILL), and the per-listing binding leg
 * (min wins) is the scorer's job. Lnight paints the same ramp on top
 * at lower opacity (night binds sleep). Outside every polygon is NULL
 * — never "quiet". Clears stale overlay layers first; no-op when the
 * style is not loaded yet or areas is nullish. Malformed rings are
 * skipped, never faked; unknown bands fall back gray (never dropped).
 */
export function applyNoisePolygons(
  mapObj: OutlineMap,
  areas: NoiseArea[] | null | undefined,
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
    const band =
      typeof a.band_db === "number" && Number.isFinite(a.band_db)
        ? String(a.band_db)
        : "unknown";
    const leg = a.leg === "Lnight" ? "Lnight" : "Lden";
    features.push({
      type: "Feature",
      properties: {
        band,
        leg,
        noise_id: typeof a.noise_id === "string" ? a.noise_id : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(NOISE_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: NOISE_FILL,
      type: "fill",
      source: NOISE_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "band"],
          "45",
          NOISE_BAND_FILL["45"],
          "50",
          NOISE_BAND_FILL["50"],
          "55",
          NOISE_BAND_FILL["55"],
          "60",
          NOISE_BAND_FILL["60"],
          "65",
          NOISE_BAND_FILL["65"],
          "70",
          NOISE_BAND_FILL["70"],
          NOISE_BAND_FILL.unknown,
        ],
        "fill-opacity": [
          "match",
          ["get", "leg"],
          "Lnight",
          0.35,
          0.5,
        ],
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: NOISE_CASING,
      type: "line",
      source: NOISE_SRC,
      paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.5 },
    },
    before,
  );
}

// KPO-HOOK (#626): restriction-zone ban/conditioned fills.

/**
 * Paint KPO restriction zones (ban-red to conditioned-amber fills +
 * white casing) so build limits read at a glance. This is a
 * CHOROPLETH of joined facts, never a score: colors encode the zone
 * band key (see kpoFillKey — ban 20-35, conditioned 50-65), and the
 * per-parcel worst/min band is the scorer's job. Outside every
 * polygon is NULL — never "clean title" (zones are not title truth).
 * Clears stale overlay layers first; no-op when the style is not
 * loaded yet or areas is nullish. Malformed rings are skipped, never
 * faked; unknown types fall back gray (never dropped).
 */
export function applyKpoPolygons(
  mapObj: OutlineMap,
  areas: KpoArea[] | null | undefined,
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
        band: kpoFillKey(
          typeof a.voond === "string" ? a.voond : "",
          typeof a.family === "string" ? a.family : "",
        ),
        family: typeof a.family === "string" ? a.family : "",
        nimi: typeof a.nimi === "string" ? a.nimi : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(KPO_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: KPO_FILL,
      type: "fill",
      source: KPO_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "band"],
          "ban",
          KPO_BAND_FILL.ban,
          "conditioned",
          KPO_BAND_FILL.conditioned,
          KPO_BAND_FILL.unknown,
        ],
        "fill-opacity": 0.5,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: KPO_CASING,
      type: "line",
      source: KPO_SRC,
      paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.5 },
    },
    before,
  );
}

// DELAY-HOOK (#629): typical-delay corridor band fills.

/**
 * Paint harvested typical-delay corridor bands for one hour band (or
 * "worst") as factor fills so the Tuesday pattern reads at a glance.
 * This is a CHOROPLETH of table facts, never a score or a live jam:
 * colors encode the factor band (see delayBandForFactor — free green,
 * jammed red, thin/missing slate), and no score field is painted
 * anywhere. Clears stale overlay layers first; no-op when the style
 * is not loaded yet or areas is nullish. Malformed rings are skipped,
 * never faked; unknown bands fall back to unknown (never dropped,
 * never free-flow green).
 */
export function applyDelayCorridors(
  mapObj: OutlineMap,
  areas: DelayArea[] | null | undefined,
  band: string,
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
    const factors =
      a.factors && typeof a.factors === "object" ? a.factors : {};
    features.push({
      type: "Feature",
      properties: {
        band: delayBandForFactor(
          (factors as Record<string, unknown>)[band],
        ),
        corridor: typeof a.corridor === "string" ? a.corridor : "",
      },
      geometry: { type: "MultiPolygon", coordinates: polys },
    });
  }
  if (features.length === 0) return;
  mapObj.addSource(DELAY_SRC, {
    type: "geojson",
    data: { type: "FeatureCollection", features },
  });
  const before = abovePaint(mapObj);
  mapObj.addLayer(
    {
      id: DELAY_FILL,
      type: "fill",
      source: DELAY_SRC,
      paint: {
        "fill-color": [
          "match",
          ["get", "band"],
          "free",
          DELAY_BAND_FILL.free,
          "steady",
          DELAY_BAND_FILL.steady,
          "slow",
          DELAY_BAND_FILL.slow,
          "jammed",
          DELAY_BAND_FILL.jammed,
          DELAY_BAND_FILL.unknown,
        ],
        "fill-opacity": 0.5,
      },
    },
    before,
  );
  mapObj.addLayer(
    {
      id: DELAY_CASING,
      type: "line",
      source: DELAY_SRC,
      paint: { "line-color": "#ffffff", "line-width": 1, "line-opacity": 0.5 },
    },
    before,
  );
}

// HARBOUR-HOOK (#627): AIS pleasure-cell fills.

/**
 * Paint AIS pleasure-craft cells as 500 m squares (pale → deep green
 * by annual count) so sailing pressure reads at a glance. This is a
 * CHOROPLETH of grid facts, never a score: the grid is used as-is
 * (no interpolation), and the per-listing legs are the scorer's job.
 * Clears stale overlay layers first; no-op when the style is not
 * loaded yet or cells is nullish. Malformed cells are skipped, never
 * faked.
 */
/** 500 m AIS cell squares as GeoJSON features (grid as-is, junk skipped). */
function harbourCellFeatures(cells: HarbourCell[]): object[] {
  // 500 m grid: half-side in degrees (~250 m lat, lon scaled).
  const HALF_LAT = 250 / 111320;
  const features = [];
  for (const c of cells) {
    if (
      !c ||
      typeof c.lon !== "number" ||
      typeof c.lat !== "number" ||
      !Number.isFinite(c.lon) ||
      !Number.isFinite(c.lat)
    )
      continue;
    const halfLon = HALF_LAT / Math.max(0.2, Math.cos((c.lat * Math.PI) / 180));
    const key =
      !Number.isFinite(c.pleasure) || c.pleasure < 1
        ? "unknown"
        : c.pleasure >= 50
          ? "high"
          : c.pleasure >= 10
            ? "mid"
            : "low";
    const ring = [
      [c.lon - halfLon, c.lat - HALF_LAT],
      [c.lon + halfLon, c.lat - HALF_LAT],
      [c.lon + halfLon, c.lat + HALF_LAT],
      [c.lon - halfLon, c.lat + HALF_LAT],
      [c.lon - halfLon, c.lat - HALF_LAT],
    ];
    features.push({
      type: "Feature",
      properties: { band: key },
      geometry: { type: "MultiPolygon", coordinates: [[ring]] },
    });
  }
  return features;
}

/** Joined ports as point features (finite coords only, junk skipped). */
function harbourPortFeatures(ports: HarbourPort[]): object[] {
  const features = [];
  for (const p of ports) {
    if (
      !p ||
      typeof p.lon !== "number" ||
      typeof p.lat !== "number" ||
      !Number.isFinite(p.lon) ||
      !Number.isFinite(p.lat)
    )
      continue;
    features.push({
      type: "Feature",
      properties: { name: typeof p.name === "string" ? p.name : "" },
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
    });
  }
  return features;
}

/**
 * Paint the full harbour picture in ONE overlay-slot pass: AIS
 * pleasure-cell fills (grid as-is) UNDER joined-port dots. One
 * clearVectorOverlays only — the peers clear first, so stacking a
 * separate point pass after applyHarbourPolygons would wipe the
 * cells (and vice versa). No-op when the style is not loaded yet;
 * paints whichever half has data (cells without ports, or ports
 * without cells, still read). Malformed records are skipped, never
 * faked.
 */
export function applyHarbourOverlays(
  mapObj: OutlineMap,
  cells: HarbourCell[] | null | undefined,
  ports: HarbourPort[] | null | undefined,
  opts: { color: string },
): void {
  if (!mapObj.getStyle()) return;
  clearVectorOverlays(mapObj);
  const before = abovePaint(mapObj);
  const cellFeatures = cells && cells.length > 0 ? harbourCellFeatures(cells) : [];
  if (cellFeatures.length > 0) {
    mapObj.addSource(HARBOUR_SRC, {
      type: "geojson",
      data: { type: "FeatureCollection", features: cellFeatures },
    });
    mapObj.addLayer(
      {
        id: HARBOUR_FILL,
        type: "fill",
        source: HARBOUR_SRC,
        paint: {
          "fill-color": [
            "match",
            ["get", "band"],
            "low",
            HARBOUR_CELL_FILL.low,
            "mid",
            HARBOUR_CELL_FILL.mid,
            "high",
            HARBOUR_CELL_FILL.high,
            HARBOUR_CELL_FILL.unknown,
          ],
          "fill-opacity": 0.5,
        },
      },
      before,
    );
    mapObj.addLayer(
      {
        id: HARBOUR_CASING,
        type: "line",
        source: HARBOUR_SRC,
        paint: {
          "line-color": "#ffffff",
          "line-width": 1,
          "line-opacity": 0.5,
        },
      },
      before,
    );
  }
  const portFeatures = ports && ports.length > 0 ? harbourPortFeatures(ports) : [];
  if (portFeatures.length > 0) {
    mapObj.addSource(POINT_SRC, {
      type: "geojson",
      data: { type: "FeatureCollection", features: portFeatures },
    });
    mapObj.addLayer(
      {
        id: POINT_CASING,
        type: "circle",
        source: POINT_SRC,
        paint: {
          "circle-radius": 6.5,
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
          "circle-radius": 5,
          "circle-color": opts.color,
          "circle-opacity": 0.9,
        },
      },
      before,
    );
  }
}
