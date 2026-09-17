import { promises as fs } from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import {
  bonusSpecFor,
  cleanRaster,
  radiusKmFor,
  toPoint,
  type BBoxLike,
  type LayerId,
  type LayerPoint,
  type TransitDistance,
  type WalkRasterDoc,
} from "../layers";
import { haversineKm } from "../poi";
import { sampleRaster } from "../walkRaster";
// B1-HOOK(#98): batch B1 raster files live in layers_batch1.ts.
import { B1_METRO_PREFIXES, B1_RASTER_FILES } from "../layers_batch1";
// G03-HOOK(#151): batch G03 raster file lives in layers_group03.ts.
import { G03_RASTER_FILE } from "../layers_group03";
// G07B-HOOK(#141): batch G07B raster files live in layers_group07b.ts.
import { G07B_RASTER_FILE } from "../layers_group07b";
// G11D-HOOK(#135): leftover-B raster files live in layers_group11d.ts.
import { G11D_METRO_PREFIXES, G11D_RASTER_FILES } from "../layers_group11d";
// G07D-HOOK(#143): batch G07D raster files live in layers_group07d.ts.
import { G07D_RASTER_FILE } from "../layers_group07d";
// G07C-HOOK(#142): batch G07C raster file lives in layers_group07c.ts.
import { G07C_RASTER_FILE } from "../layers_group07c";
// G06B-HOOK (#139): Group 6 leftover raster files live in layers_group06b.ts.
import { GROUP06B_METRO_PREFIXES, GROUP06B_RASTER_FILES } from "../layers_group06b";
// G11C-HOOK(#134): batch G11C raster files live in layers_group11c.ts.
import { G11C_METRO_PREFIX, G11C_RASTER_FILE } from "../layers_group11c";
// B6-HOOK(#133): batch B6 raster files live in layers_batch6.ts.
import { BATCH6_RASTER_FILE } from "../layers_batch6";
// G07-HOOK(#140): batch G07 raster files live in layers_group07.ts.
import { G07_RASTER_FILE } from "../layers_group07";
// G02B-HOOK (#137): lift-proxy raster file lives in ../layers_group02b.
import { G02B_RASTER_FILE } from "../layers_group02b";
// G08A-HOOK(#167): batch G08A raster file lives in layers_group08a.ts.
import { G08A_RASTER_FILE } from "../layers_group08a";
// G03D-HOOK(#154): batch G03D raster files live in layers_group03d.ts.
import { G03D_RASTER_FILE } from "../layers_group03d";
// G08D-HOOK(#170): batch G08D raster file lives in layers_group08d.ts.
import { G08D_RASTER_FILE } from "../layers_group08d";
// G08C-HOOK(#169): batch G08C raster files live in layers_group08c.ts.
import { G08C_RASTER_FILE } from "../layers_group08c";
// G08B-HOOK(#168): batch G08B raster files live in layers_group08b.ts.
import { G08B_RASTER_FILE } from "../layers_group08b";
// G05B-HOOK(#162): batch G05B raster files live in layers_group05b.ts.
import { G05B_RASTER_FILE } from "../layers_group05b";
// G05D-HOOK(#164): batch G05D raster file lives in layers_group05d.ts.
import { G05D_RASTER_FILE } from "../layers_group05d";
// G05A-HOOK(#161): batch G05A raster files live in layers_group05a.ts.
import { G05A_RASTER_FILE } from "../layers_group05a";
// G05C-HOOK(#163): batch G05C raster files live in layers_group05c.ts.
import { G05C_RASTER_FILE } from "../layers_group05c";
// G05E-HOOK(#165): batch G05E raster file lives in layers_group05e.ts.
import { G05E_RASTER_FILE } from "../layers_group05e";
// G05F-HOOK(#166): batch G05F raster file lives in layers_group05f.ts.
import { G05F_RASTER_FILE } from "../layers_group05f";
// G10R-HOOK (#171): batch G10R raster file lives in layers_group10rest.ts.
import { G10R_RASTER_FILE } from "../layers_group10rest";
// G18A-HOOK(#172): batch G18A raster files live in layers_group18resta.ts.
import { G18A_RASTER_FILE } from "../layers_group18resta";
// G18B-HOOK(#173): batch G18B raster files live in layers_group18restb.ts.
import { G18B_RASTER_FILE } from "../layers_group18restb";
// G17A-HOOK(#177): batch G17A raster files live in layers_group17a.ts.
import { G17A_RASTER_FILE } from "../layers_group17a";
// G17B-HOOK(#178): batch G17B raster file lives in layers_group17b.ts.
import { G17B_RASTER_FILE } from "../layers_group17b";
// G17R-HOOK(#196): batch G17R raster file lives in layers_group17rest.ts.
import { G17R_RASTER_FILE } from "../layers_group17rest";
// B10C-HOOK (#230): batch B10C raster files live in layers_batch10c.ts.
import { BATCH10C_RASTER_FILE } from "../layers_batch10c";
// OSMDAILY-HOOK (#482): daily-life raster files live in layers_osmdaily.ts.
import { OSMDAILY_RASTER_FILE } from "../layers_osmdaily";
// GTFS-HOOK (#483): gtfsstops raster file lives in layers_gtfsstops.ts
// (named but NOT built — overlay-only decision, resolves absent so the
// layer rides the Euclidean fallback splat, honestly labeled).
import { GTFSSTOPS_RASTER_FILE } from "../layers_gtfsstops";
// RSAFE-HOOK (#481): road-safety raster file lives in layers_roadsafety.ts.
import { RSAFE_RASTER_FILE } from "../layers_roadsafety";
// P4-031-HOOK (#484): senscom raster filename lives in
// layers_p4_senscom.ts (intentionally never built — SENSCOM_NO_RASTER).
import { SENSCOM_RASTER_FILE } from "../layers_p4_senscom";
// STATKOV-HOOK (#485): statkov raster files live in layers_statkov.ts.
import { STATKOV_RASTER_FILE } from "../layers_statkov";
// P4PARK-HOOK (#479): P4 parking raster file lives in layers_p4_parking.ts.
import { P4PARK_RASTER_FILE } from "../layers_p4_parking";
// MARUKOV-HOOK (#486): maru raster files live in layers_maru.ts
// (unbuilt until the maintainer places the MARU KOV export -- absent
// files degrade to the honest Euclidean fallback, never an error).
import { MARUKOV_RASTER_FILE } from "../layers_maru";
// FLOOD-HOOK (#487): floodzone raster file lives in layers_flood.ts
// (named but NEVER built — polygons-only decision, resolves absent so
// windows serve honestly-empty, never a gradient).
import { FLOOD_RASTER_FILE } from "../layers_flood";
// P4OSM-HOOK (#480): P4OSM raster files live in layers_p4osm.ts.
import { P4OSM_RASTER_FILE } from "../layers_p4osm";
// OOKLA-HOOK (#489): ookla raster filenames live in layers_p4_ookla.ts
// (intentionally never built — OOKLA_NO_RASTER).
import { OOKLA_RASTER_FILE } from "../layers_p4_ookla";
// ACCBLACK-HOOK (#490): accblack raster filename lives in
// layers_accblack.ts (intentionally never built — ACCBLACK_NO_RASTER).
import { ACCBLACK_RASTER_FILE } from "../layers_accblack";

// MAAPARCEL-HOOK (#491): maaparcel raster file lives in
// layers_maaparcel.ts (named but NEVER built — polygons-only decision,
// resolves absent so windows serve honestly-empty, never a gradient).
import { MAAPARCEL_RASTER_FILE } from "../layers_maaparcel";

// EELIS-HOOK (#488): eelis raster files live in layers_eelis.ts
// (named but NEVER built — polygons-only decision, resolve absent so
// windows serve honestly-empty, never a gradient).
import { EELIS_RASTER_FILE } from "../layers_eelis";

// PLANKTPR-HOOK (#492): planktpr raster filename + harvested-polygon
// sidecar live in layers_planktpr.ts (raster intentionally never built
// — PLANKTPR_NO_RASTER; the name resolves to an absent file so rasters
// degrade to null; the sidecar is honestly empty when unharvested).
import type { PlanktprArea } from "../layers_planktpr";
import { PLANKTPR_RASTER_FILE, isPlanktprArea } from "../layers_planktpr";
// TERVISE-HOOK (#494): tervise raster filename lives in
// layers_tervise.ts (intentionally never built — TERVISE_NO_RASTER).
import { TERVISE_RASTER_FILE } from "../layers_tervise";
// ASUMEDIA-HOOK (#495): asumedia raster filename lives in
// layers_asumedia.ts (intentionally never built — ASUMEDIA_NO_RASTER).
import { ASUMEDIA_RASTER_FILE } from "../layers_asumedia";
// PAASTE-HOOK (#493): paaste raster file lives in layers_paaste.ts
// (named but NOT built — honest-empty decision, resolves absent so the
// layer degrades to the designed 500 → demo-empty path, honestly labeled).
import { PAASTE_RASTER_FILE } from "../layers_paaste";
// SPORT-HOOK (#607): sport-venue raster filenames + sidecar point type
// live in layers_p4_sport.ts (rasters intentionally never built —
// SPORT_NO_RASTER; the names resolve to absent files so rasters degrade
// to null; the sidecar is honestly empty when unharvested).
import { SPORT_RASTER_FILE } from "../layers_p4_sport";
import type { SportPoint } from "../layers_p4_sport";
// EHIS-HOOK (#608): measured-school raster filenames + sidecar point
// type live in layers_p4_ehis.ts (rasters intentionally never built —
// EHIS_NO_RASTER; the names resolve to absent files so rasters degrade
// to null; the sidecar is honestly empty when unharvested).
import { EHIS_RASTER_FILE } from "../layers_p4_ehis";
import type { EhisPoint } from "../layers_p4_ehis";
// MEDRE-HOOK (#609): primary-care raster filenames + sidecar point
// type live in layers_p4_medre.ts (rasters intentionally never built —
// MEDRE_NO_RASTER; the names resolve to absent files so rasters degrade
// to null; the sidecar is honestly empty until the Step-2 ADS join).
import { MEDRE_RASTER_FILE } from "../layers_p4_medre";
// KLIIMA-HOOK (#611): climate-normals raster filenames live in
// layers_kliima.ts (intentionally never built — KLIIMA_NO_RASTER; the
// names resolve to absent files so windows fall back to the client
// points-splat quality kernel).
import { KLIIMA_RASTER_FILE } from "../layers_kliima";
import type { MedrePoint } from "../layers_p4_medre";
// FIXIT-HOOK (#623): report-pin raster filename + sidecar point type
// live in layers_p4_fixit.ts (raster intentionally never built —
// FIXIT_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the sidecar is honestly empty when unharvested).
import { FIXIT_RASTER_FILE } from "../layers_p4_fixit";
import type { FixitPoint } from "../layers_p4_fixit";
// SEVESO-HOOK (#613): danger-polygon raster filename + sidecar area
// type live in layers_p4_seveso.ts (raster intentionally never built —
// SEVESO_NO_RASTER, CC BY-NC-ND forbids derivatives; the name resolves
// to an absent file so windows degrade to null; the sidecar is honestly
// empty when unharvested).
import type { SevesoArea } from "../layers_p4_seveso";
import { SEVESO_RASTER_FILE, isSevesoArea } from "../layers_p4_seveso";
// STATELAND-HOOK (#615): state/auction raster filename + sidecar area
// type live in layers_p4_stateland.ts (raster intentionally never built
// — STATELAND_NO_RASTER; the name resolves to an absent file so
// windows degrade to null; the sidecar is honestly empty when
// unharvested).
import type { StatelandArea } from "../layers_p4_stateland";
import { STATELAND_RASTER_FILE, isStatelandArea } from "../layers_p4_stateland";
// QUARRY-HOOK (#614): permit-polygon raster filename + sidecar area
// type live in layers_p4_quarry.ts (raster intentionally never built —
// QUARRY_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the sidecar is honestly empty when unharvested).
import type { QuarryArea } from "../layers_p4_quarry";
import { QUARRY_RASTER_FILE, isQuarryArea } from "../layers_p4_quarry";
// DRAINAGE-HOOK (#616): network/outflow raster filename + sidecar area
// type live in layers_p4_maaparandus.ts (raster intentionally never built
// — MAAPARANDUS_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the sidecar is honestly empty when unharvested).
import type { MaaparandusArea } from "../layers_p4_maaparandus";
import { MAAPARANDUS_RASTER_FILE, isMaaparandusArea } from "../layers_p4_maaparandus";
// SOIL-HOOK (#617): soil contour raster filename lives in
// layers_p4_soil.ts (raster intentionally never built — SOIL_NO_RASTER;
// the name resolves to an absent file so windows degrade to null; the
// viewport proxy is honestly empty when unharvested).
import { SOIL_RASTER_FILE } from "../layers_p4_soil";
// ETAK-HOOK (#618): contour raster filename lives in layers_p4_etak.ts
// (raster intentionally never built — ETAK_NO_RASTER; the name resolves
// to an absent file so windows degrade to null; the viewport proxy is
// honestly empty when the WFS is down).
import { ETAK_RASTER_FILE } from "../layers_p4_etak";
// RELIEF-HOOK (#619): tint raster name lives in layers_p4_relief.ts
// (master intentionally never built — RELIEF_NO_RASTER; the name
// resolves to an absent file so windows degrade to null; the grid
// sidecar is honestly null when unharvested).
import { RELIEF_RASTER_FILE } from "../layers_p4_relief";
// CANOPY-HOOK (#620): tint raster name lives in layers_p4_canopy.ts
// (master intentionally never built — CANOPY_NO_RASTER; the name
// resolves to an absent file so windows degrade to null; the grid
// sidecar is honestly null when unharvested).
import { CANOPY_RASTER_FILE } from "../layers_p4_canopy";
// BUILDINGS-HOOK (#621): tint raster name lives in
// layers_p4_buildings.ts (master intentionally never built —
// BUILDINGS_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the grid sidecar is honestly null when
// unharvested).
import { BUILDINGS_RASTER_FILE } from "../layers_p4_buildings";
// DENSITY-HOOK (#622): square sidecar type lives in
// layers_p4_density.ts (areas intentionally never rasterised —
// DENSITY_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the square sidecar is honestly empty when
// unharvested).
import { DENSITY_RASTER_FILE, isDensityArea, type DensityArea } from "../layers_p4_density";
// FOREST-HOOK (#624): change sidecar type lives in
// layers_p4_forest.ts (polygons intentionally never rasterised —
// FOREST_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the change sidecar is honestly empty when
// unharvested).
import { FOREST_RASTER_FILE, isForestArea, type ForestArea } from "../layers_p4_forest";
// NOISE-HOOK (#625): band sidecar type lives in
// layers_p4_noise.ts (polygons intentionally never rasterised —
// NOISE_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the band sidecar is honestly empty when
// unharvested).
import { NOISE_RASTER_FILE, isNoiseArea, type NoiseArea } from "../layers_p4_noise";
// HARBOUR-HOOK (#627): port/cell sidecar types live in
// layers_p4_harbour.ts (points + fills intentionally never rasterised —
// HARBOUR_NO_RASTER; the name resolves to an absent file so windows
// degrade to null; the sidecar is honestly empty when unharvested).
import { HARBOUR_RASTER_FILE, isHarbourCell, isHarbourPort, type HarbourCell, type HarbourPort } from "../layers_p4_harbour";
// OHUSEIRE-HOOK (#610): station raster filename + sidecar point type
// live in layers_p4_ohuseire.ts (raster intentionally never built —
// OHUSEIRE_NO_RASTER; the name resolves to an absent file so rasters
// degrade to null; the sidecar is honestly empty when unharvested).
import { OHUSEIRE_RASTER_FILE } from "../layers_p4_ohuseire";
import type { OhuseirePoint } from "../layers_p4_ohuseire";
// POI-HOOK (#612): long-tail raster filename + sidecar point type live
// in layers_p4_poi.ts (raster intentionally never built —
// POI_NO_RASTER; the name resolves to an absent file so rasters
// degrade to null; the sidecar is honestly empty when unharvested).
import { POI_RASTER_FILE } from "../layers_p4_poi";
import type { PoiPoint } from "../layers_p4_poi";

/** Permanent as-of date of the local snapshot (all layers frozen together). */
export const SNAPSHOT_AS_OF = "2026-09-12";
export const SNAPSHOT_AS_OF_MS = Date.parse(`${SNAPSHOT_AS_OF}T00:00:00Z`);

/**
 * Snapshot root: override per environment. The snapshot lives outside the
 * repo (no scraped data is committed); only this path points at it.
 */
export function snapshotDir(): string {
  return process.env.HF_SNAPSHOT_DIR ?? path.join(os.homedir(), "hf-data", SNAPSHOT_AS_OF);
}

/**
 * Measured feature bounds of the 2026-09-12 snapshot (Harjumaa + spillover):
 * lon 23.30–25.47, lat 58.42–59.63, rounded outward. Tiles outside this box
 * are served as honestly-empty, never fetched from anywhere.
 */
export const SNAPSHOT_BBOX: BBoxLike = {
  minlon: 23.3,
  minlat: 58.4,
  maxlon: 25.5,
  maxlat: 59.65,
};

export function intersectsCoverage(bbox: BBoxLike): boolean {
  return (
    bbox.minlon < SNAPSHOT_BBOX.maxlon &&
    bbox.maxlon > SNAPSHOT_BBOX.minlon &&
    bbox.minlat < SNAPSHOT_BBOX.maxlat &&
    bbox.maxlat > SNAPSHOT_BBOX.minlat
  );
}

/**
 * Nominal hectares for green points without a measured polygon (p19
 * judgment call): playgrounds and gardens are pocket green, an unmapped
 * park node stands in for a typical small park.
 */
export function nominalArea(tags: Record<string, string> | undefined): number {
  const v = tags?.leisure;
  if (v === "playground") return 0.1;
  if (v === "garden") return 0.15;
  if (v === "park") return 2.0;
  return 0.3;
}

export interface ParkArea {
  /** [minlon, minlat, maxlon, maxlat] prefilter box. */
  b: [number, number, number, number];
  /** Hectares. */
  a: number;
  /** Outer rings as [lon, lat] pairs. */
  r: number[][][];
}

function isParkArea(v: unknown): v is ParkArea {
  const p = v as Partial<ParkArea>;
  return (
    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    typeof p?.a === "number" &&
    Number.isFinite(p.a) &&
    Array.isArray(p?.r) &&
    p.r.every(
      (ring) =>
        Array.isArray(ring) &&
        ring.every(
          (pt) =>
            Array.isArray(pt) &&
            pt.length === 2 &&
            pt.every((n) => typeof n === "number" && Number.isFinite(n)),
        ),
    )
  );
}

function ringContains(ring: number[][], lon: number, lat: number): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

// FLOOD-HOOK (#487): KAUR flood-zone polygon sidecar
// (`kaur/flood-areas.json`): named zone polygons as [lon, lat] rings with
// a prefilter box (ParkOutline precedent — FloodArea mirrors ParkOutline
// with zone identity in place of hectares). Written offline by
// scripts/build/batch_flood_kaur.py off the cached GML snapshot; the
// per-parcel join itself lives in
// services/scoring/dims_overturn_flood.py.
export interface FloodArea {
  zone_id: string;
  nimi: string;
  veekogu: string;
  tyyp: string;
  /** [minlon, minlat, maxlon, maxlat] prefilter box. */
  b: [number, number, number, number];
  /** Zone rings as [lon, lat] pairs (builder flips GML lat/lon on write). */
  r: number[][][];
}

function isFloodArea(v: unknown): v is FloodArea {
  const p = v as Partial<FloodArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.nimi === "string" &&
    typeof p?.veekogu === "string" &&
    typeof p?.tyyp === "string" &&

    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    Array.isArray(p?.r) &&
    p.r.length > 0 &&
    p.r.every(
      (ring) =>
        Array.isArray(ring) &&
        ring.length >= 3 &&
        ring.every(
          (pt) =>
            Array.isArray(pt) &&
            pt.length === 2 &&
            pt.every((n) => typeof n === "number" && Number.isFinite(n)),
        ),
    )
  );
}
// EELIS-HOOK (#488): EELIS nature-polygon sidecar
// (`eelis/eelis-areas.json`): named zone polygons as [lon, lat] rings
// with a prefilter box (ParkOutline precedent — EelisArea mirrors
// ParkOutline with zone identity in place of hectares). Written offline
// by scripts/build/batch_eelis_poly.py off cached WFS GeoJSON; the
// per-parcel join itself lives in services/scoring/dims_p4_eelis.py.
export interface EelisArea {
  kiht: "kaitse" | "niit" | "raie";
  zone_id: string;
  nimi: string;
  lisa: string;
  /** [minlon, minlat, maxlon, maxlat] prefilter box. */
  b: [number, number, number, number];
  /** Zone rings as [lon, lat] pairs (WFS EPSG:4326 GeoJSON order, kept). */
  r: number[][][];
}

function isEelisArea(v: unknown): v is EelisArea {
  const p = v as Partial<EelisArea>;
  return (
    (p?.kiht === "kaitse" || p?.kiht === "niit" || p?.kiht === "raie") &&
    typeof p?.zone_id === "string" &&
    typeof p?.nimi === "string" &&
    typeof p?.lisa === "string" &&

    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    Array.isArray(p?.r) &&
    p.r.length > 0 &&
    p.r.every(
      (ring) =>
        Array.isArray(ring) &&
        ring.length >= 3 &&
        ring.every(
          (pt) =>
            Array.isArray(pt) &&
            pt.length === 2 &&
            pt.every((n) => typeof n === "number" && Number.isFinite(n)),
        ),
    )
  );
}

const floodAreaCache = new Map<string, FloodArea[]>();

/**
 * KAUR flood-zone sidecar (`kaur/flood-areas.json`): named zone polygons.
 * Missing or malformed sidecar degrades to [] (honestly no polygons —
 * the Tallinn market window holds zero register polygons anyway, see
 * docs/overturn_flood.md), never an error.
 */
export async function loadFloodAreas(dir: string): Promise<FloodArea[]> {
  const hit = floodAreaCache.get(dir);
  if (hit) return hit;
  let areas: FloodArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "kaur", "flood-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isFloodArea);
    else console.warn(`snapshot: ignoring malformed flood-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no polygons.
  }
  floodAreaCache.set(dir, areas);

  return areas;
}
const eelisAreaCache = new Map<string, EelisArea[]>();

/**
 * EELIS nature-polygon sidecar (`eelis/eelis-areas.json`): named zone
 * polygons. Missing or malformed sidecar degrades to [] (honestly no
 * polygons — the per-parcel join lives in the scorer and stays NULL),
 * never an error.
 */
export async function loadEelisAreas(dir: string): Promise<EelisArea[]> {
  const hit = eelisAreaCache.get(dir);
  if (hit) return hit;
  let areas: EelisArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "eelis", "eelis-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isEelisArea);
    else console.warn(`snapshot: ignoring malformed eelis-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no polygons.
  }
  eelisAreaCache.set(dir, areas);

  return areas;
}

/** Projected blackspot point (WGS84, L-EST97 inverse-LCC ~1 m). */
export interface AccblackPoint {
  lon: number;
  lat: number;
  sev: number;
  year: string;
}

function isAccblackPoint(v: unknown): v is AccblackPoint {
  const p = v as Partial<AccblackPoint>;
  return (
    typeof p?.lon === "number" && Number.isFinite(p.lon) &&
    typeof p?.lat === "number" && Number.isFinite(p.lat) &&
    typeof p?.sev === "number" && Number.isFinite(p.sev) &&
    typeof p?.year === "string"
  );
}

const accblackPointCache = new Map<string, AccblackPoint[]>();

/**
 * Projected-blackspot sidecar (`accblack/accblack-points.json`): WGS84
 * casualty-accident points for the accblack overlay (issue #522 reopen:
 * L-EST97 -> WGS84 projection landed, so the empty-on-purpose verdict
 * is lifted where the sidecar exists). Missing or malformed sidecar
 * degrades to [] (honestly no points — the map renders "no data",
 * never a faked zero), never an error.
 */
export async function loadAccblackPoints(dir: string): Promise<AccblackPoint[]> {
  const hit = accblackPointCache.get(dir);
  if (hit) return hit;
  let points: AccblackPoint[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "accblack", "accblack-points.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { points?: unknown }).points)
      ? (parsed as { points: unknown[] }).points
      : [];
    points = list.filter(isAccblackPoint);
    if (!Array.isArray((parsed as { points?: unknown }).points)) console.warn(`snapshot: ignoring malformed accblack-points.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no points.
  }
  accblackPointCache.set(dir, points);
  return points;
}

// SPORT-HOOK (#607): sport-venue sidecar cache (same discipline).
const sportPointCache = new Map<string, SportPoint[]>();

/** Sport slice tags the harvester writes (lat/lon/slice only). */
const SPORT_SLICES = new Set(["hall", "field", "pool"]);

function isSportPoint(v: unknown): v is SportPoint {
  const p = v as Partial<SportPoint>;
  return (
    typeof p?.lon === "number" && Number.isFinite(p.lon) &&
    typeof p?.lat === "number" && Number.isFinite(p.lat) &&
    typeof p?.slice === "string" && SPORT_SLICES.has(p.slice)
  );
}

/**
 * Sport-venue sidecar (`sport/sport-points.json`): sliced Harjumaa
 * venue points for the sport_hall/field/pool overlays (issue #607,
 * built offline by scripts/build/batch_sport.py — never live).
 * Missing or malformed sidecar degrades to [] (honestly no points —
 * the map renders "no data", never a faked zero), never an error.
 */
export async function loadSportPoints(dir: string): Promise<SportPoint[]> {
  const hit = sportPointCache.get(dir);
  if (hit) return hit;
  let points: SportPoint[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "sport", "sport-points.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { points?: unknown }).points)
      ? (parsed as { points: unknown[] }).points
      : [];
    points = list.filter(isSportPoint);
    if (!Array.isArray((parsed as { points?: unknown }).points)) console.warn(`snapshot: ignoring malformed sport-points.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no points.
  }
  sportPointCache.set(dir, points);
  return points;
}

// EHIS-HOOK (#608): measured-school sidecar cache (same discipline).
const ehisPointCache = new Map<string, EhisPoint[]>();

/** School slice tags the harvester writes (lat/lon/slice only). */
const EHIS_SLICES = new Set(["school", "kindergarten", "hobby"]);

function isEhisPoint(v: unknown): v is EhisPoint {
  const p = v as Partial<EhisPoint>;
  return (
    typeof p?.lon === "number" && Number.isFinite(p.lon) &&
    typeof p?.lat === "number" && Number.isFinite(p.lat) &&
    typeof p?.slice === "string" && EHIS_SLICES.has(p.slice)
  );
}

/**
 * Measured-school sidecar (`ehis/ehis-points.json`): sliced Harjumaa
 * school-building points for the ehis_school/kindergarten/hobby
 * overlays (issue #608, built offline by scripts/build/batch_ehis.py —
 * never live). Missing or malformed sidecar degrades to [] (honestly
 * no points — the map renders "no data", never a faked zero), never
 * an error.
 */
export async function loadEhisPoints(dir: string): Promise<EhisPoint[]> {
  const hit = ehisPointCache.get(dir);
  if (hit) return hit;
  let points: EhisPoint[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "ehis", "ehis-points.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { points?: unknown }).points)
      ? (parsed as { points: unknown[] }).points
      : [];
    points = list.filter(isEhisPoint);
    if (!Array.isArray((parsed as { points?: unknown }).points)) console.warn(`snapshot: ignoring malformed ehis-points.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no points.
  }
  ehisPointCache.set(dir, points);
  return points;
}

// MEDRE-HOOK (#609): primary-care sidecar cache (same discipline).
const medrePointCache = new Map<string, MedrePoint[]>();

/** Care slice tags the harvester writes (lat/lon/slice only). */
const MEDRE_SLICES = new Set(["gp", "clinic"]);

function isMedrePoint(v: unknown): v is MedrePoint {
  const p = v as Partial<MedrePoint>;
  return (
    typeof p?.lon === "number" && Number.isFinite(p.lon) &&
    typeof p?.lat === "number" && Number.isFinite(p.lat) &&
    typeof p?.slice === "string" && MEDRE_SLICES.has(p.slice)
  );
}

/**
 * Primary-care sidecar (`medre/medre-points.json`): caller-joined GP /
 * clinic points for the medre_gp/medre_clinic overlays (issue #609,
 * built offline by scripts/build/batch_medre.py — never live). Step 1
 * ships the register tallies with points [] (no ADS join owned —
 * honestly no points, never faked); Step 2 fills joined points and
 * the loader serves them unchanged. Missing or malformed sidecar
 * degrades to [], never an error.
 */
export async function loadMedrePoints(dir: string): Promise<MedrePoint[]> {
  const hit = medrePointCache.get(dir);
  if (hit) return hit;
  let points: MedrePoint[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "medre", "medre-points.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { points?: unknown }).points)
      ? (parsed as { points: unknown[] }).points
      : [];
    points = list.filter(isMedrePoint);
    if (!Array.isArray((parsed as { points?: unknown }).points)) console.warn(`snapshot: ignoring malformed medre-points.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no points.
  }
  medrePointCache.set(dir, points);
  return points;
}

// OHUSEIRE-HOOK (#610): station sidecar cache (same discipline).
const ohuseirePointCache = new Map<string, OhuseirePoint[]>();

function isOhuseirePoint(v: unknown): v is OhuseirePoint {
  const p = v as Partial<OhuseirePoint>;
  return (
    typeof p?.lon === "number" && Number.isFinite(p.lon) &&
    typeof p?.lat === "number" && Number.isFinite(p.lat) &&
    typeof p?.name === "string"
  );
}

/**
 * Official air-station sidecar (`ohuseire/ohuseire-points.json`):
 * Tallinn station points for the ohuseire overlay (issue #610, built
 * offline by scripts/build/batch_ohuseire.py — never live). Missing or
 * malformed sidecar degrades to [] (honestly no points — the map
 * renders "no data", never a faked zero), never an error.
 */
export async function loadOhuseirePoints(dir: string): Promise<OhuseirePoint[]> {
  const hit = ohuseirePointCache.get(dir);
  if (hit) return hit;
  let points: OhuseirePoint[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "ohuseire", "ohuseire-points.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { points?: unknown }).points)
      ? (parsed as { points: unknown[] }).points
      : [];
    points = list.filter(isOhuseirePoint);
    if (!Array.isArray((parsed as { points?: unknown }).points)) console.warn(`snapshot: ignoring malformed ohuseire-points.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no points.
  }
  ohuseirePointCache.set(dir, points);
  return points;
}

// POI-HOOK (#612): long-tail sidecar cache (same discipline).
const poiPointCache = new Map<string, PoiPoint[]>();

/** POI slice tags the harvester writes (lat/lon/slice only). */
const POI_SLICES = new Set(["library", "post", "pharmacy"]);

function isPoiPoint(v: unknown): v is PoiPoint {
  const p = v as Partial<PoiPoint>;
  return (
    typeof p?.lon === "number" && Number.isFinite(p.lon) &&
    typeof p?.lat === "number" && Number.isFinite(p.lat) &&
    typeof p?.slice === "string" && POI_SLICES.has(p.slice)
  );
}

/**
 * Long-tail POI sidecar (`poi/poi-points.json`): sliced Harjumaa
 * library/post/pharmacy points for the poi_* overlays (issue #612,
 * built offline by scripts/build/batch_poi.py — never live). Missing
 * or malformed sidecar degrades to [] (honestly no points — the map
 * renders "no data", never a faked zero), never an error.
 */
export async function loadPoiPoints(dir: string): Promise<PoiPoint[]> {
  const hit = poiPointCache.get(dir);
  if (hit) return hit;
  let points: PoiPoint[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "poi", "poi-points.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { points?: unknown }).points)
      ? (parsed as { points: unknown[] }).points
      : [];
    points = list.filter(isPoiPoint);
    if (!Array.isArray((parsed as { points?: unknown }).points)) console.warn(`snapshot: ignoring malformed poi-points.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no points.
  }
  poiPointCache.set(dir, points);
  return points;
}

// FIXIT-HOOK (#623): report-pin sidecar cache (same discipline).
const fixitPointCache = new Map<string, FixitPoint[]>();

function isFixitPoint(v: unknown): v is FixitPoint {
  const p = v as Partial<FixitPoint>;
  return (
    typeof p?.lon === "number" && Number.isFinite(p.lon) &&
    typeof p?.lat === "number" && Number.isFinite(p.lat) &&
    typeof p?.handled === "boolean" &&
    typeof p?.ts === "number" && Number.isFinite(p.ts)
  );
}

/**
 * Report-pin sidecar (`fixit/fixit-points.json`): rolling-window
 * annateada pins for the fixit overlay (issue #623, built offline by
 * scripts/build/batch_fixit.py — never live). Missing or malformed
 * sidecar degrades to [] (honestly no pins — the map renders "no
 * data", never faked pins), never an error. Expiry is enforced by
 * the caller (fixitPointsIn), not here.
 */
export async function loadFixitPoints(dir: string): Promise<FixitPoint[]> {
  const hit = fixitPointCache.get(dir);
  if (hit) return hit;
  let points: FixitPoint[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "fixit", "fixit-points.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = typeof parsed === "object" && parsed !== null && Array.isArray((parsed as { points?: unknown }).points)
      ? (parsed as { points: unknown[] }).points
      : [];
    points = list.filter(isFixitPoint);
    if (!Array.isArray((parsed as { points?: unknown }).points)) console.warn(`snapshot: ignoring malformed fixit-points.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no pins.
  }
  fixitPointCache.set(dir, points);
  return points;
}

const areaCache = new Map<string, ParkArea[]>();
// PLANKTPR-HOOK (#492): harvested-polygon sidecar cache (same discipline).
const planktprAreaCache = new Map<string, PlanktprArea[]>();

/**
 * Green-polygon sidecar (`osm/park-areas.json`): outer rings + hectares.
 * Missing or malformed sidecar degrades to type-only weights — never an error.
 */
export async function loadParkAreas(dir: string): Promise<ParkArea[]> {
  const hit = areaCache.get(dir);
  if (hit) return hit;
  let areas: ParkArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "osm", "park-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isParkArea);
    else console.warn(`snapshot: ignoring malformed park-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: type-only weights below.
  }
  areaCache.set(dir, areas);
  return areas;
}

// MAAPARCEL-HOOK (#491): kataster parcel sidecar
// (`maa/parcel-areas.json`): omandivorm-class polygons as [lon, lat]
// rings with a prefilter box (ParkOutline precedent — MaaParcelArea
// mirrors ParkOutline with parcel identity in place of hectares).
// Written offline by scripts/build/batch_maaparcel_kataster.py off the
// cached WFS GeoJSON; the per-parcel join itself lives in
// services/scoring/dims_overturn_maa.py.
export interface MaaParcelSidecar {
  tunnus: string;
  cls: string;
  omvorm: string;
  siht1: string;
  pindala: number | null;
  aadress: string;
  kkis: number | null;
  /** [minlon, minlat, maxlon, maxlat] prefilter box. */
  b: [number, number, number, number];
  /** Parcel rings as [lon, lat] pairs (WFS cache is EPSG:4326 GeoJSON). */
  r: number[][][];
}

const MAAPARCEL_CLASSES: ReadonlySet<string> = new Set(["era", "muni", "riik", "muu"]);

function isMaaParcelSidecar(v: unknown): v is MaaParcelSidecar {
  const p = v as Partial<MaaParcelSidecar>;
  return (
    typeof p?.tunnus === "string" &&
    typeof p?.cls === "string" &&
    MAAPARCEL_CLASSES.has(p.cls) &&
    typeof p?.omvorm === "string" &&
    typeof p?.siht1 === "string" &&
    (typeof p?.pindala === "number" || p?.pindala === null) &&
    typeof p?.aadress === "string" &&
    (typeof p?.kkis === "number" || p?.kkis === null) &&
    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    Array.isArray(p?.r) &&
    p.r.length > 0 &&
    p.r.every(
      (ring) =>
        Array.isArray(ring) &&
        ring.length >= 3 &&
        ring.every(
          (pt) =>
            Array.isArray(pt) &&
            pt.length === 2 &&
            pt.every((n) => typeof n === "number" && Number.isFinite(n)),
        ),
    )
  );
}

const maaParcelCache = new Map<string, MaaParcelSidecar[]>();

/**
 * Kataster parcel sidecar (`maa/parcel-areas.json`): omandivorm-class
 * polygons. Missing or malformed sidecar degrades to [] (honestly no
 * polygons — the layer covers a harvested sample window anyway, see
 * docs/overturn_maa.md #491 addendum), never an error.
 */
export async function loadMaaParcelAreas(dir: string): Promise<MaaParcelSidecar[]> {
  const hit = maaParcelCache.get(dir);
  if (hit) return hit;
  let areas: MaaParcelSidecar[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "maa", "parcel-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list: unknown = Array.isArray(parsed)
      ? parsed
      : (parsed as { parcels?: unknown } | null)?.parcels;
    if (Array.isArray(list)) areas = list.filter(isMaaParcelSidecar);
    else console.warn(`snapshot: ignoring malformed parcel-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly no polygons.
  }
  maaParcelCache.set(dir, areas);

  return areas;
}
// PLANKTPR-HOOK (#492): designated-use polygon sidecar
// (`plank/areas.json`, written by scripts/build/batch_planktpr_wfs.py):
// plan_id + raw use code + stage + kov + outer rings. A missing sidecar
// is honestly empty (the dated NULL — WFS gone, TPR has no bulk), never
// an error; malformed rows are skipped, never faked.
export async function loadPlanktprAreas(dir: string): Promise<PlanktprArea[]> {
  const hit = planktprAreaCache.get(dir);
  if (hit) return hit;
  let areas: PlanktprArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "plank", "areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isPlanktprArea);
    else console.warn(`snapshot: ignoring malformed plank/areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  planktprAreaCache.set(dir, areas);

  return areas;
}

// SEVESO-HOOK (#613): danger-polygon sidecar cache (same discipline).
const sevesoAreaCache = new Map<string, SevesoArea[]>();

// SEVESO-HOOK (#613): Päästeamet danger-polygon sidecar
// (`seveso/seveso-areas.json`, written by scripts/build/batch_seveso.py
// off the cached danger CSV): zone_id + danger class + outer rings. A
// missing sidecar is honestly empty (register unharvested), never an
// error; malformed rows are skipped, never faked.
export async function loadSevesoAreas(dir: string): Promise<SevesoArea[]> {
  const hit = sevesoAreaCache.get(dir);
  if (hit) return hit;
  let areas: SevesoArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "seveso", "seveso-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isSevesoArea);
    else console.warn(`snapshot: ignoring malformed seveso/seveso-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  sevesoAreaCache.set(dir, areas);

  return areas;
}

// STATELAND-HOOK (#615): state/auction sidecar cache (same discipline).
const statelandAreaCache = new Map<string, StatelandArea[]>();

// STATELAND-HOOK (#615): KATRI state + auction sidecar
// (`stateland/stateland-areas.json`, written by
// scripts/build/batch_stateland.py off the cached WFS GeoJSON):
// zone_id + class + dated auction flags + outer rings. A missing
// sidecar is honestly empty (register unharvested), never an error;
// malformed rows are skipped, never faked.
export async function loadStatelandAreas(dir: string): Promise<StatelandArea[]> {
  const hit = statelandAreaCache.get(dir);
  if (hit) return hit;
  let areas: StatelandArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "stateland", "stateland-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isStatelandArea);
    else console.warn(`snapshot: ignoring malformed stateland/stateland-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  statelandAreaCache.set(dir, areas);
  return areas;
}
// QUARRY-HOOK (#614): permit-polygon sidecar cache (same discipline).
const quarryAreaCache = new Map<string, QuarryArea[]>();

// QUARRY-HOOK (#614): Maa-amet permit-polygon sidecar
// (`quarry/quarry-areas.json`, written by scripts/build/batch_quarry.py
// off the cached WFS GML): zone_id + class + dated permit + outer
// rings. A missing sidecar is honestly empty (register unharvested),
// never an error; malformed rows are skipped, never faked.
export async function loadQuarryAreas(dir: string): Promise<QuarryArea[]> {
  const hit = quarryAreaCache.get(dir);
  if (hit) return hit;
  let areas: QuarryArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "quarry", "quarry-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isQuarryArea);
    else console.warn(`snapshot: ignoring malformed quarry/quarry-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  quarryAreaCache.set(dir, areas);
  return areas;
}
// DRAINAGE-HOOK (#616): network/outflow sidecar cache (same discipline).
const maaparandusAreaCache = new Map<string, MaaparandusArea[]>();

// RELIEF-HOOK (#619): relief tint-grid sidecar cache (same discipline).
const reliefTintCache = new Map<string, unknown | null>();

// RELIEF-HOOK (#619): relief tint grid sidecar
// (`relief/relief-tint.json`, written by scripts/build/batch_relief.py
// off the cached WCS DTM GeoTIFF): county height grid. A missing
// sidecar is honestly null (DTM unharvested), never an error; a
// malformed grid is honestly null (never a shifted tint).
export async function loadReliefTint(dir: string): Promise<unknown | null> {
  const hit = reliefTintCache.get(dir);
  if (hit !== undefined) return hit;
  let grid: unknown | null = null;
  try {
    const raw = await fs.readFile(path.join(dir, "relief", "relief-tint.json"), "utf8");
    grid = JSON.parse(raw);
  } catch {
    // Optional sidecar: honestly null below.
  }
  reliefTintCache.set(dir, grid);
  return grid;
}

// CANOPY-HOOK (#620): canopy tint-grid sidecar cache (same discipline).
const canopyTintCache = new Map<string, unknown | null>();
// BUILDINGS-HOOK (#621): buildings tint-grid sidecar cache (same discipline).
const buildingsTintCache = new Map<string, unknown | null>();

// CANOPY-HOOK (#620): canopy tint grid sidecar
// (`canopy/canopy-tint.json`, written by scripts/build/batch_canopy.py
// off the cached WMS CHM render): county class grid. A missing
// sidecar is honestly null (CHM unharvested), never an error; a
// malformed grid is honestly null (never a shifted tint).
export async function loadCanopyTint(dir: string): Promise<unknown | null> {
  const hit = canopyTintCache.get(dir);
  if (hit !== undefined) return hit;
  let grid: unknown | null = null;
  try {
    const raw = await fs.readFile(path.join(dir, "canopy", "canopy-tint.json"), "utf8");
    grid = JSON.parse(raw);
  } catch {
    // Optional sidecar: honestly null below.
  }
  canopyTintCache.set(dir, grid);
  return grid;
}

// BUILDINGS-HOOK (#621): buildings tint grid sidecar
// (`buildings/buildings-tint.json`, written by
// scripts/build/batch_buildings.py off the cached LoD1 CityGML):
// county height-class grid. A missing sidecar is honestly null
// (LoD1 unharvested), never an error; a malformed grid is honestly
// null (never a shifted tint).
export async function loadBuildingsTint(dir: string): Promise<unknown | null> {
  const hit = buildingsTintCache.get(dir);
  if (hit !== undefined) return hit;
  let grid: unknown | null = null;
  try {
    const raw = await fs.readFile(path.join(dir, "buildings", "buildings-tint.json"), "utf8");
    grid = JSON.parse(raw);
  } catch {
    // Optional sidecar: honestly null below.
  }
  buildingsTintCache.set(dir, grid);
  return grid;
}

// DENSITY-HOOK (#622): density square sidecar
// (`density/density-areas.json`, written by
// scripts/build/batch_density.py off the cached INSPIRE PD GeoJSON):
// zone_id + inhabitants + class + quad ring. A missing sidecar is
// honestly empty (PD unharvested), never an error; malformed rows are
// skipped, never faked.
const densityAreaCache = new Map<string, DensityArea[]>();

export async function loadDensityAreas(dir: string): Promise<DensityArea[]> {
  const hit = densityAreaCache.get(dir);
  if (hit) return hit;
  let areas: DensityArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "density", "density-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      Array.isArray((parsed as { areas: unknown }).areas)
    )
      areas = (parsed as { areas: unknown[] }).areas.filter(isDensityArea);
    else console.warn(`snapshot: ignoring malformed density/density-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  densityAreaCache.set(dir, areas);
  return areas;
}

// FOREST-HOOK (#624): forest change sidecar
// (`forest/forest-areas.json`, written by
// scripts/build/batch_forest.py off the cached metsamuutused SHP):
// change_id + season + dates + area + class + polygons. A missing
// sidecar is honestly empty (metsamuutused unharvested), never an
// error; malformed rows are skipped, never faked.
const forestAreaCache = new Map<string, ForestArea[]>();

export async function loadForestAreas(dir: string): Promise<ForestArea[]> {
  const hit = forestAreaCache.get(dir);
  if (hit) return hit;
  let areas: ForestArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "forest", "forest-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      Array.isArray((parsed as { areas: unknown }).areas)
    )
      areas = (parsed as { areas: unknown[] }).areas.filter(isForestArea);
    else console.warn(`snapshot: ignoring malformed forest/forest-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  forestAreaCache.set(dir, areas);
  return areas;
}

// NOISE-HOOK (#625): noise band sidecar
// (`noise/noise-areas.json`, written by
// scripts/build/batch_noisemap.py off the cached myrakaart WFS):
// noise_id + leg + band_db + polygons. A missing
// sidecar is honestly empty (myrakaart unharvested), never an
// error; malformed rows are skipped, never faked.
const noiseAreaCache = new Map<string, NoiseArea[]>();

export async function loadNoiseAreas(dir: string): Promise<NoiseArea[]> {
  const hit = noiseAreaCache.get(dir);
  if (hit) return hit;
  let areas: NoiseArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "noise", "noise-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      Array.isArray((parsed as { areas: unknown }).areas)
    )
      areas = (parsed as { areas: unknown[] }).areas.filter(isNoiseArea);
    else console.warn(`snapshot: ignoring malformed noise/noise-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  noiseAreaCache.set(dir, areas);
  return areas;
}

// HARBOUR-HOOK (#627): harbour sidecar
// (`harbour/harbour-areas.json`, written by
// scripts/build/batch_harbour.py off the sadamaregister API + INSPIRE
// PortNode join + AIS SHP): ports (joined points) + cells (pleasure
// centroids). A missing sidecar is honestly empty (harbour
// unharvested), never an error; malformed rows are skipped,
// never faked.
const harbourAreaCache = new Map<string, { ports: HarbourPort[]; cells: HarbourCell[] }>();

export async function loadHarbourAreas(dir: string): Promise<{ ports: HarbourPort[]; cells: HarbourCell[] }> {
  const hit = harbourAreaCache.get(dir);
  if (hit) return hit;
  const empty = { ports: [], cells: [] };
  try {
    const raw = await fs.readFile(path.join(dir, "harbour", "harbour-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object") {
      const doc = parsed as { ports?: unknown[]; cells?: unknown[] };
      if (Array.isArray(doc.ports) && Array.isArray(doc.cells)) {
        const loaded = {
          ports: doc.ports.filter(isHarbourPort),
          cells: doc.cells.filter(isHarbourCell),
        };
        harbourAreaCache.set(dir, loaded);
        return loaded;
      }
      console.warn(`snapshot: ignoring malformed harbour/harbour-areas.json in ${dir}`);
    } else console.warn(`snapshot: ignoring malformed harbour/harbour-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  harbourAreaCache.set(dir, empty);
  return empty;
}

// DRAINAGE-HOOK (#616): maaparandus network/outflow sidecar
// (`maaparandus/maaparandus-areas.json`, written by
// scripts/build/batch_maaparandus.py off the cached WFS GeoJSON):
// zone_id + class + MSR check link + polygons/lines. A missing sidecar
// is honestly empty (register unharvested), never an error; malformed
// rows are skipped, never faked.
export async function loadMaaparandusAreas(dir: string): Promise<MaaparandusArea[]> {
  const hit = maaparandusAreaCache.get(dir);
  if (hit) return hit;
  let areas: MaaparandusArea[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "maaparandus", "maaparandus-areas.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed)) areas = parsed.filter(isMaaparandusArea);
    else console.warn(`snapshot: ignoring malformed maaparandus/maaparandus-areas.json in ${dir}`);
  } catch {
    // Optional sidecar: honestly empty below.
  }
  maaparandusAreaCache.set(dir, areas);
  return areas;
}

/** ~20 m dedupe cells; areas SUM (total green nearby is what counts). */
const DEDUPE_LON = 0.0004;
const DEDUPE_LAT = 0.0002;

function round3(n: number): number {
  return Math.round(n * 1000) / 1000;
}

function dedupeSum(points: LayerPoint[]): LayerPoint[] {
  const acc = new Map<string, LayerPoint>();
  for (const p of points) {
    const key = `${Math.round(p.lon / DEDUPE_LON)}:${Math.round(p.lat / DEDUPE_LAT)}`;
    const prev = acc.get(key);
    if (!prev) acc.set(key, { ...p });
    else prev.a = round3((prev.a ?? 0) + (p.a ?? 0));
  }
  return [...acc.values()];
}

interface FreqStop {
  lon: number;
  lat: number;
  trips: number;
}

function isFreqStop(v: unknown): v is FreqStop {
  const s = v as Partial<FreqStop>;
  return (
    typeof s?.lon === "number" &&
    Number.isFinite(s.lon) &&
    typeof s?.lat === "number" &&
    Number.isFinite(s.lat) &&
    typeof s?.trips === "number" &&
    Number.isFinite(s.trips) &&
    s.trips >= 0
  );
}

/** Join radius GTFS stop <-> OSM stop (same station complex). */
const FREQ_JOIN_KM = 0.1;
/**
 * Assumed weekday departures for stops outside GTFS coverage (unknown, not
 * bad): near the Tallinn median so county stops read mid-ramp, while real
 * hubs still tower above them.
 */
const TRANSIT_DEFAULT_TRIPS = 100;

const freqCache = new Map<string, FreqStop[]>();

/**
 * GTFS weekday frequency sidecar (`osm/transit-frequency.json`). Missing or
 * malformed file degrades to neutral weights — never an error.
 */
async function loadFrequency(dir: string): Promise<FreqStop[]> {
  const hit = freqCache.get(dir);
  if (hit) return hit;
  let stops: FreqStop[] = [];
  try {
    const raw = await fs.readFile(path.join(dir, "osm", "transit-frequency.json"), "utf8");
    const parsed: unknown = JSON.parse(raw);
    const list = (parsed as { stops?: unknown })?.stops;
    if (Array.isArray(list)) stops = list.filter(isFreqStop);
  } catch {
    // Optional sidecar: neutral weights below.
  }
  freqCache.set(dir, stops);
  return stops;
}

/** Big-green cutoff: points inside these polygons are represented by them. */
const POLY_CUTOFF_HA = 0.5;

/** Subdivision cap per polygon (elongated greens keep their shape). */
const MAX_SUBDIV = 25;

/**
 * Area features for the parks layer: polygon areas (subdivided so big or
 * elongated greens are not a single centroid spike) plus nominal hectares
 * for points outside measured polygons. Areas SUM per dedupe cell.
 */
export function parksAreas(points: LayerPoint[], areas: ParkArea[]): LayerPoint[] {
  const sigma = radiusKmFor("parks");
  const cellHa = Math.PI * sigma * sigma * 100;
  const feats: LayerPoint[] = [];
  for (const pa of areas) {
    const n = Math.max(1, Math.min(MAX_SUBDIV, Math.ceil(pa.a / cellHa)));
    const nx = Math.max(1, Math.ceil(Math.sqrt((n * (pa.b[2] - pa.b[0])) / (pa.b[3] - pa.b[1] + 1e-9))));
    const ny = Math.max(1, Math.ceil(n / nx));
    // Two passes: sparse shapes place fewer centers than n, so the weight
    // is split over PLACED centers — total stamped hectares always equal
    // the polygon's area (diagonal forests kept none of it before).
    const centers: [number, number][] = [];
    for (let ix = 0; ix < nx; ix++) {
      for (let iy = 0; iy < ny; iy++) {
        const lon = pa.b[0] + ((pa.b[2] - pa.b[0]) * (ix + 0.5)) / nx;
        const lat = pa.b[1] + ((pa.b[3] - pa.b[1]) * (iy + 0.5)) / ny;
        if (pa.r.some((ring) => ringContains(ring, lon, lat))) {
          centers.push([lon, lat]);
        }
      }
    }
    if (centers.length === 0) {
      feats.push({
        lon: round3((pa.b[0] + pa.b[2]) / 2),
        lat: round3((pa.b[1] + pa.b[3]) / 2),
        a: round3(pa.a),
      });
    } else {
      const w = pa.a / centers.length;
      for (const [lon, lat] of centers) {
        feats.push({ lon: round3(lon), lat: round3(lat), a: round3(w) });
      }
    }
  }
  for (const p of points) {
    if (insideBigPoly(p.lon, p.lat, areas)) continue;
    feats.push({ lon: p.lon, lat: p.lat, ...(p.tags ? { tags: p.tags } : null), a: nominalArea(p.tags) });
  }
  return dedupeSum(feats);
}

function insideBigPoly(lon: number, lat: number, areas: ParkArea[]): boolean {
  for (const pa of areas) {
    if (pa.a < POLY_CUTOFF_HA) continue;
    if (lon < pa.b[0] || lon > pa.b[2] || lat < pa.b[1] || lat > pa.b[3]) continue;
    if (pa.r.some((ring) => ringContains(ring, lon, lat))) return true;
  }
  return false;
}

/** The snapshot on disk is unreadable or unusable (missing dir/file, bad JSON). */
export class SnapshotUnavailable extends Error {
  constructor(detail: string) {
    super(`snapshot unavailable: ${detail}`);
    this.name = "SnapshotUnavailable";
  }
}

/** Process-lifetime cache: the snapshot is permanent, so no TTL is needed. */
const allPoints = new Map<string, LayerPoint[]>();

/** Test hook: forget cached layers. */
export function clearSnapshotCache(): void {
  allPoints.clear();
  areaCache.clear();
  planktprAreaCache.clear(); // PLANKTPR-HOOK (#492)
  sevesoAreaCache.clear(); // SEVESO-HOOK (#613)
  statelandAreaCache.clear(); // STATELAND-HOOK (#615)
  quarryAreaCache.clear(); // QUARRY-HOOK (#614)
  maaparandusAreaCache.clear(); // DRAINAGE-HOOK (#616)
  freqCache.clear();
  rasterCache.clear();
  countyBytes.clear();
  metroMeta.clear();
}

/** Process-lifetime cache for the walk raster (immutable snapshot file). */
const rasterCache = new Map<string, WalkRasterDoc | null>();

/** Raster files per layer (built by scripts/build-walk-raster.py). */
const RASTER_FILE: Record<LayerId, string> = {
  transit: "transit-walk-raster.json",
  parks: "parks-walk-raster.json",
  schools: "schools-walk-raster.json",
  walkability: "walkability-walk-raster.json",
  pedinfra: "pedinfra-walk-raster.json",
  cycling: "cycling-walk-raster.json",
  grocery: "grocery-walk-raster.json",
  healthcare: "healthcare-walk-raster.json",
  ...B1_RASTER_FILES, // B1-HOOK(#98)
  // G07B-HOOK (#141): env-health B rasters (built by scripts/build/batch_g07b_envhealth.py).
  ...G07B_RASTER_FILE,
  // G11D-HOOK (#135): leftover-B rasters (built by scripts/build/batch_g11d_leftovers.py).
  ...G11D_RASTER_FILES,
  // G07D-HOOK (#143): env-health D rasters (built by scripts/build/batch_g07d_envhealth.py).
  ...G07D_RASTER_FILE,
  // G07C-HOOK(#142): env-health C raster (built by scripts/build/batch_g07c_envhealth.py).
  ...G07C_RASTER_FILE,
  // G07-HOOK (#140): env-health rasters (built by scripts/build/batch_g07_envhealth.py).
  ...G07_RASTER_FILE,
  // B5-HOOK (#102): Group 14 rasters (built by scripts/build/batch_b5_safety.py).
  safety: "safety-walk-raster.json",
  emergency: "emergency-walk-raster.json",
  hydrants: "hydrants-walk-raster.json",
  evac: "evac-walk-raster.json",
  dispatch: "dispatch-walk-raster.json",
  // G06B-HOOK (#139): Group 6 leftover rasters (built by scripts/build/batch_g06b_heritage.py).
  ...GROUP06B_RASTER_FILES,
  // G11C-HOOK (#134): Group 11 leftover-A rasters (batch_g11c_amenity.py).
  ...G11C_RASTER_FILE,
  // B6-HOOK (#133): mobility/access rasters (scripts/build/batch_b6_mobility.py).
  ...BATCH6_RASTER_FILE,
  // G06-HOOK (#138): Group 6 raster (built by scripts/build/batch_g06_heritage.py).
  heritage: "heritage-walk-raster.json",
  // G02B-HOOK (#137): lift-proxy raster (built by scripts/build/batch_g02b_lift.py).
  ...G02B_RASTER_FILE,
  // G03-HOOK (#151): drainage raster (scripts/build/batch_g03_cadastre.py).
  ...G03_RASTER_FILE,
  // G03D-HOOK (#154): moorage + shoredist rasters (scripts/build/batch_g03d_cadastre.py).
  ...G03D_RASTER_FILE,
  // G08A-HOOK (#167): wildfire raster (scripts/build/batch_g08a_flood.py).
  ...G08A_RASTER_FILE,
  // G08D-HOOK (#170): vernalpool raster (scripts/build/batch_g08d_flood.py).
  ...G08D_RASTER_FILE,
  // G08C-HOOK (#169): surgeroad + slidebuf rasters (scripts/build/batch_g08c_flood.py).
  ...G08C_RASTER_FILE,
  // G08B-HOOK (#168): windtunnel + saltspray rasters (scripts/build/batch_g08b_flood.py).
  ...G08B_RASTER_FILE,
  // G05B-HOOK (#162): gardens + buildout rasters (scripts/build/batch_g05b_plans.py).
  ...G05B_RASTER_FILE,
  // G05D-HOOK (#164): strsat raster (scripts/build/batch_g05d_plans.py).
  ...G05D_RASTER_FILE,
  // G05A-HOOK (#161): ehitus + korterstock rasters (scripts/build/batch_g05a_plans.py).
  ...G05A_RASTER_FILE,
  // G05C-HOOK (#163): commbleed + windsolar + viewshed rasters (scripts/build/batch_g05c_plans.py).
  ...G05C_RASTER_FILE,
  // G05E-HOOK (#165): equestrian raster (scripts/build/batch_g05e_plans.py).
  ...G05E_RASTER_FILE,
  // G05F-HOOK (#166): upcycle raster (scripts/build/batch_g05f_plans.py).
  ...G05F_RASTER_FILE,
  // G10R-HOOK (#171): skyview raster (scripts/build/batch_g10_rest.py).
  ...G10R_RASTER_FILE,
  // G18A-HOOK (#172): dayopen + glassglare rasters (scripts/build/batch_g18_resta.py).
  ...G18A_RASTER_FILE,
  // G18B-HOOK (#173): fishbowl + mossrisk + daylight rasters (scripts/build/batch_g18_restb.py).
  ...G18B_RASTER_FILE,
  // G17A-HOOK (#177): compost + gritbin + leafdrop rasters (scripts/build/batch_g17_a.py).
  ...G17A_RASTER_FILE,
  // G17B-HOOK (#178): lawncare raster (scripts/build/batch_g17_b.py).
  ...G17B_RASTER_FILE,
  // G17R-HOOK (#196): privroad raster (scripts/build/batch_g17_rest.py).
  ...G17R_RASTER_FILE,
  // B10C-HOOK (#230): utility rasters (scripts/build/batch_b10c_utility.py).
  ...BATCH10C_RASTER_FILE,
  // OSMDAILY-HOOK (#482): daily-life rasters (follow-up builds; absent
  // files degrade to the honest Euclidean fallback, never an error).
  ...OSMDAILY_RASTER_FILE,
  // GTFS-HOOK (#483): gtfsstops raster name only (no master built —
  // overlay-only; absent file degrades to Euclidean points scoring).
  ...GTFSSTOPS_RASTER_FILE,
  // RSAFE-HOOK (#481): roadsafety raster (scripts/build/batch_rsafety_osm.py).
  ...RSAFE_RASTER_FILE,
  // P4-031-HOOK (#484): senscom raster name (never built by decision —
  // the points-splat band kernel IS the field, see SENSCOM_NO_RASTER;
  // the name resolves to an absent file so rasters degrade to null).
  ...SENSCOM_RASTER_FILE,
  // STATKOV-HOOK (#485): choropleth rasters
  // (scripts/build/batch_statkov_choropleth.py).
  ...STATKOV_RASTER_FILE,
  // P4PARK-HOOK (#479): parking raster (scripts/build/batch_p4_parking.py).
  ...P4PARK_RASTER_FILE,
  // MARUKOV-HOOK (#486): choropleth rasters
  // (scripts/build/batch_maru_choropleth.py).
  ...MARUKOV_RASTER_FILE,
  // FLOOD-HOOK (#487): floodzone raster name only (no master built —
  // polygons-only; absent file serves honestly-empty, never a gradient).
  ...FLOOD_RASTER_FILE,
  // P4OSM-HOOK (#480): walkability + darkness rasters
  // (scripts/build/batch_p4_osmwalk.py; absent files fall back cleanly).
  ...P4OSM_RASTER_FILE,  // OOKLA-HOOK (#489): ookla raster names only (no masters built —
  // overlay-only; absent files degrade to the tileband points kernel).
  ...OOKLA_RASTER_FILE,
  // ACCBLACK-HOOK (#490): accblack raster name (never built by
  // decision — the measured set is empty, see ACCBLACK_NO_RASTER; the
  // name resolves to an absent file so rasters degrade to null).
  ...ACCBLACK_RASTER_FILE,

  // MAAPARCEL-HOOK (#491): maaparcel raster name only (never built by
  // documented polygons-only decision — resolves absent so windows
  // serve honestly-empty, never a gradient).
  ...MAAPARCEL_RASTER_FILE,

  // EELIS-HOOK (#488): nature-polygon raster names only (no masters built —
  // polygons-only; absent files serve honestly-empty, never a gradient).
  ...EELIS_RASTER_FILE,

  // PLANKTPR-HOOK (#492): planktpr raster name only (no master built —
  // polygons ARE the field; absent file degrades to null, honestly).
  ...PLANKTPR_RASTER_FILE,
  // TERVISE-HOOK (#494): tervise raster name (never built by decision —
  // the points-splat quality kernel IS the field, see TERVISE_NO_RASTER;
  // the name resolves to an absent file so rasters degrade to null).
  ...TERVISE_RASTER_FILE,

  // ASUMEDIA-HOOK (#495): asumedia raster name (never built by
  // decision — the measured set is empty, see ASUMEDIA_NO_RASTER; the
  // name resolves to an absent file so rasters degrade to null).
  ...ASUMEDIA_RASTER_FILE,
  // PAASTE-HOOK (#493): paaste raster name only (no master built —
  // honest-empty; absent file degrades to the designed 500 path).
  ...PAASTE_RASTER_FILE,
  // SPORT-HOOK (#607): sport-venue raster names only (no masters built
  // by decision — SPORT_NO_RASTER; the points-splat distance kernel IS
  // the field; absent files degrade windows to null, honestly).
  ...SPORT_RASTER_FILE,
  // EHIS-HOOK (#608): school raster names only (no masters built by
  // decision — EHIS_NO_RASTER; same points-splat discipline).
  ...EHIS_RASTER_FILE,
  // MEDRE-HOOK (#609): primary-care raster names only (no masters
  // built by decision — MEDRE_NO_RASTER; same points-splat
  // discipline, dormant until Step 2).
  ...MEDRE_RASTER_FILE,
  // OHUSEIRE-HOOK (#610): station raster name only (no master built
  // by decision — OHUSEIRE_NO_RASTER; the points-splat distance
  // kernel IS the field; absent file degrades windows to null).
  ...OHUSEIRE_RASTER_FILE,
  // KLIIMA-HOOK (#611): climate-normals raster names only (no masters
  // built by decision — KLIIMA_NO_RASTER; same points-splat quality
  // discipline as tervise).
  ...KLIIMA_RASTER_FILE,
  // POI-HOOK (#612): long-tail raster names only (no masters built
  // by decision — POI_NO_RASTER; same points-splat discipline).
  ...POI_RASTER_FILE,
  // FIXIT-HOOK (#623): report-pin raster name only (no master built
  // by decision — FIXIT_NO_RASTER; markers only, no field to stamp;
  // the absent file degrades windows to null).
  ...FIXIT_RASTER_FILE,
  // DRAINAGE-HOOK (#616): network/outflow raster name only (no
  // master built — MAAPARANDUS_NO_RASTER; shapes ARE the field; absent
  // file degrades to null, honestly).
  ...MAAPARANDUS_RASTER_FILE,
  // ETAK-HOOK (#618): etak contour raster name only (no master built
  // — ETAK_NO_RASTER; contours ARE the field; absent file degrades to
  // null, honestly).
  ...ETAK_RASTER_FILE,
  // SEVESO-HOOK (#613): danger-polygon raster name only (no master
  // built — SEVESO_NO_RASTER, CC BY-NC-ND forbids derivatives;
  // polygons ARE the field; absent file degrades to null, honestly).
  ...SEVESO_RASTER_FILE,
  // STATELAND-HOOK (#615): state/auction raster name only (no master
  // built — STATELAND_NO_RASTER; polygons ARE the field; absent file
  // degrades to null, honestly).
  ...STATELAND_RASTER_FILE,
  // QUARRY-HOOK (#614): permit-polygon raster name only (no master
  // built — QUARRY_NO_RASTER; polygons ARE the field; absent file
  // degrades to null, honestly).
  ...QUARRY_RASTER_FILE,
  // SOIL-HOOK (#617): soil contour raster name only (no master built —
  // SOIL_NO_RASTER; contours ARE the field; absent file degrades to
  // null, honestly).
  ...SOIL_RASTER_FILE,
  // RELIEF-HOOK (#619): relief tint raster name only (no master built
  // — RELIEF_NO_RASTER; the tint grid IS the field; absent file
  // degrades to null, honestly).
  ...RELIEF_RASTER_FILE,
  // CANOPY-HOOK (#620): canopy tint raster name only (no master built
  // — CANOPY_NO_RASTER; the tint grid IS the field; absent file
  // degrades to null, honestly).
  ...CANOPY_RASTER_FILE,
  // BUILDINGS-HOOK (#621): buildings tint raster name only (no master
  // built — BUILDINGS_NO_RASTER; the tint grid IS the field; absent
  // file degrades to null, honestly).
  ...BUILDINGS_RASTER_FILE,
  // DENSITY-HOOK (#622): density square raster name only (no master
  // built — DENSITY_NO_RASTER; the squares ARE the field; absent file
  // degrades to null, honestly).
  ...DENSITY_RASTER_FILE,
  // FOREST-HOOK (#624): forest change raster name only (no master
  // built — FOREST_NO_RASTER; the polygons ARE the field; absent file
  // degrades to null, honestly).
  ...FOREST_RASTER_FILE,
  // NOISE-HOOK (#625): noise band raster name only (no master
  // built — NOISE_NO_RASTER; the polygons ARE the field; absent file
  // degrades to null, honestly).
  ...NOISE_RASTER_FILE,
  // HARBOUR-HOOK (#627): harbour raster name only (no master
  // built — HARBOUR_NO_RASTER; points + fills ARE the field; absent
  // file degrades to null, honestly).
  ...HARBOUR_RASTER_FILE,
};

/**
 * One layer's walk-access raster for the whole snapshot bbox, or null when
 * it is missing/unreadable. Never throws: degradation is the caller's
 * honest Euclidean fallback, never an error presented as data.
 */
async function loadWalkRaster(layer: LayerId, dir: string): Promise<WalkRasterDoc | null> {
  const key = `${dir}::${layer}`;
  const hit = rasterCache.get(key);
  if (hit !== undefined) return hit;
  let doc: WalkRasterDoc | null;
  try {
    const raw = await fs.readFile(path.join(dir, "osm", RASTER_FILE[layer]), "utf8");
    doc = cleanRaster(JSON.parse(raw));
  } catch {
    doc = null;
  }
  rasterCache.set(key, doc);
  return doc;
}

/**
 * How a layer's distances were measured + the raster when walking applies.
 * Each raster carries its calibration; one built for different scoring
 * numbers is STALE and rejected — it must never render under a legend
 * calibrated otherwise:
 *   transit/parks (area, trips): half + sigma match the spec.
 *   schools (variety): sigma + per + cap match the spec.
 * Missing/corrupt/stale degrades to Euclidean points scoring (the client
 * splats those with the layer spec).
 */
/** True when a raster doc's baked calibration matches the live spec. */
export function matchesContract(
  doc: { half: number | null; sigma: number; per: number; cap: number } | null,
  layer: LayerId,
): boolean {
  if (!doc) return false;
  const spec = bonusSpecFor(layer);
  if (doc.sigma !== radiusKmFor(layer)) return false;
  if (spec.kind === "variety") return doc.per === spec.per && doc.cap === spec.cap;
  // B6-HOOK (#133) + G03-HOOK (#151): "quiet" carries halfM on the wire
  // half field.
  // G07B-HOOK (#141): nearest-source cleanliness (0 on the source, 50 at halfM).
  // G11D-HOOK (#135): quiet layers carry halfM on the wire as half.
  // G07D-HOOK (#143): nearest-source cleanliness (0 on the source, 50 at halfM).
  // G06B-HOOK (#139): the "avoid" kind carries the same half contract as
  // area/trips (50-score walk-km); only the score SHAPE differs (inverse).
  if (spec.kind === "area" || spec.kind === "trips" || spec.kind === "avoid")
    return doc.half === spec.half;
  // G18B-HOOK (#173): the "sparse" kind carries the same half contract
  // as area/trips (inverted-count score 50); only the score SHAPE
  // differs (green where sparse).
  if (spec.kind === "sparse") return doc.half === spec.half;
  // B6-HOOK (#133): "quiet" carries halfM on the wire half field.
  // G07-HOOK (#140): nearest-source cleanliness (0 on the source, 50 at halfM).
  if (spec.kind === "quiet") return doc.half === spec.halfM;
  // B10C-HOOK (#230): "cover" (mobile) is self-scaling discs — null half
  // on the wire (the measured ranges ARE the calibration); sigma must
  // still match the Euclidean fallback kernel width.
  if (spec.kind === "cover") return doc.half === null && doc.sigma === spec.sigma;
  // P4-031-HOOK (#484): "bands" (senscom) has no raster master by
  // documented decision (SENSCOM_NO_RASTER) — any raster on disk is
  // stale by definition and must never render under the band legend.
  if (spec.kind === "bands") return false;
  // OOKLA-HOOK (#489): "tileband" (ookla) has no raster master by
  // documented decision (OOKLA_NO_RASTER) — same stale-by-definition
  // contract as bands.
  if (spec.kind === "tileband") return false;
  // TERVISE-HOOK (#494): "qbands" (tervise) has no raster master by
  // documented decision (TERVISE_NO_RASTER) — same stale-by-definition
  // guard under the quality legend.
  if (spec.kind === "qbands") return false;
  // SPORT-HOOK (#607): "dbands" (sport) has no raster master by
  // documented decision (SPORT_NO_RASTER) — same stale-by-definition
  // guard under the distance legend.
  if (spec.kind === "dbands") return false;
  return false;
}

/**
 * Masters stamped with DIRECT distance, not walk time: airspace cells
 * radiate through air (drones fly, they do not walk), the rentbleed
 * pressure field is a smooth Euclidean grid by construction (see the
 * batch_b6_mobility.py builder), and the G03 drainage proxy field is a
 * smooth Euclidean grid by construction (see batch_g03_cadastre.py).
 * Labeling them "walk" would claim footpath routing the master never used.
 */
// B6-HOOK (#133): Euclidean-by-construction masters.
const B6_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set([
  "droneclear",
  "droneviab",
  "rentbleed",
]);
// G03-HOOK (#151): Euclidean-built drainage master rides "euclidean".
const G03_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["drainage"]);
// G03D-HOOK (#154): Euclidean-built G03D masters ride "euclidean" —
// shoredist (same Dijkstra-by-construction story as drainage) and
// moorage (Euclidean count kernel: marina centroids sit on water where
// the foot graph has no vertices, so walk stamping leaves holes AT the
// facilities — see batch_g03d_cadastre.py).
const G03D_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["moorage", "shoredist"]);
// G08A-HOOK (#167): Euclidean-built wildfire master rides "euclidean"
// (exact-grid Dijkstra by construction, same story as drainage —
// forest-ring centroids need no foot-graph walk stamping).
const G08A_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["wildfire"]);
// G08D-HOOK (#170): Euclidean-built vernalpool master rides
// "euclidean" — same Dijkstra-by-construction story as drainage
// (see batch_g08d_flood.py).
const G08D_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["vernalpool"]);
// G08C-HOOK (#169): Euclidean-built G08C masters ride "euclidean" —
// both are exact-grid Dijkstra fields by construction (same story as
// drainage/shoredist, see scripts/build/batch_g08c_flood.py).
const G08C_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["surgeroad", "slidebuf"]);
// G08B-HOOK (#168): Euclidean-built G08B masters ride "euclidean" —
// windtunnel + saltspray (same Dijkstra-by-construction story as
// drainage/shoredist — see batch_g08b_flood.py).
const G08B_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["windtunnel", "saltspray"]);
// G05B-HOOK (#162): Euclidean-built G05B masters ride "euclidean" —
// gardens + buildout (Euclidean count kernels: garden beds and fenced
// pits sit where the foot graph has no vertices, so walk stamping
// leaves holes AT the facilities — same story as moorage, see
// scripts/build/batch_g05b_plans.py).
const G05B_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["gardens", "buildout"]);
// G05D-HOOK (#164): Euclidean-built G05D master rides "euclidean" —
// strsat (same exact-grid Dijkstra story as drainage/G08B — see
// batch_g05d_plans.py).
const G05D_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["strsat"]);
// G05A-HOOK (#161): Euclidean-built G05A masters ride "euclidean" —
// ehitus + korterstock (same count-kernel-by-construction story as
// moorage — see scripts/build/batch_g05a_plans.py).
const G05A_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["ehitus", "korterstock"]);
// G05C-HOOK (#163): Euclidean-built G05C masters ride "euclidean" —
// commbleed + windsolar (exact-grid Dijkstra by construction) and
// viewshed (Euclidean count kernel, moorage precedent — see
// scripts/build/batch_g05c_plans.py).
const G05C_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["commbleed", "windsolar", "viewshed"]);
// G05E-HOOK (#165): Euclidean-built G05E master rides "euclidean" —
// equestrian (Euclidean count kernel, viewshed/moorage precedent —
// see scripts/build/batch_g05e_plans.py).
const G05E_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["equestrian"]);
// G05F-HOOK (#166): Euclidean-built G05F master rides "euclidean" —
// upcycle (Euclidean count kernel, buildout precedent — see
// scripts/build/batch_g05f_plans.py).
const G05F_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["upcycle"]);
// G10R-HOOK (#171): Euclidean-built G10R master rides "euclidean" —
// skyview (exact-grid Dijkstra by construction — see
// scripts/build/batch_g10_rest.py).
const G10R_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["skyview"]);
// G18A-HOOK (#172): Euclidean-built G18A masters ride "euclidean" —
// dayopen + glassglare (exact-grid Dijkstra by construction — see
// scripts/build/batch_g18_resta.py).
const G18A_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["dayopen", "glassglare"]);
// G18B-HOOK (#173): Euclidean-built G18B masters ride "euclidean" —
// fishbowl + mossrisk (exact-grid Dijkstra by construction) and
// daylight (Euclidean inverted count kernel — see
// scripts/build/batch_g18_restb.py).
const G18B_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["fishbowl", "mossrisk", "daylight"]);
// G17A-HOOK (#177): Euclidean-built G17A masters ride "euclidean" —
// compost + gritbin + leafdrop (Euclidean count kernels, viewshed/
// moorage precedent — see scripts/build/batch_g17_a.py).
const G17A_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["compost", "gritbin", "leafdrop"]);
// G17B-HOOK (#178): Euclidean-built G17B master rides "euclidean" —
// lawncare (Euclidean count kernel, viewshed/moorage/G17A precedent —
// see scripts/build/batch_g17_b.py).
const G17B_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["lawncare"]);
// G17R-HOOK (#196): Euclidean-built G17R master rides "euclidean" —
// privroad (exact-grid Dijkstra by construction, same story as
// drainage/shoredist — see scripts/build/batch_g17_rest.py).
const G17R_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["privroad"]);
// B10C-HOOK (#230): the mobile master stamps DIRECT distance, not walk
// time — radio cells radiate through air (see batch_b10c_utility.py
// stamp_cover). Water/waste/fiber ride the walk graph ("walk").
// Labeling mobile "walk" would claim footpath routing it never used.
const B10C_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["mobile"]);
// RSAFE-HOOK (#481): Euclidean-built road-safety master rides "euclidean" —
// roadsafety (Euclidean count kernel, viewshed/moorage/G17A precedent —
// see scripts/build/batch_rsafety_osm.py).
const RSAFE_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["roadsafety"]);
// STATKOV-HOOK (#485): Euclidean-built statkov masters ride "euclidean" --
// exact KOV fills by construction (no walk graph, no kernel; the page
// skips the otsekaugus suffix for these ids -- see app/layers/page.tsx).
const STATKOV_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set([
  "kovmigr",
  "kovehit",
  "kovfisc",
]);
// P4PARK-HOOK (#479): Euclidean-built P4 parking master rides
// "euclidean" — parking (Euclidean count kernel, lawncare/G17A
// precedent — see scripts/build/batch_p4_parking.py).
const P4PARK_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["parking"]);
// MARUKOV-HOOK (#486): Euclidean-built maru masters ride "euclidean" --
// exact KOV fills by construction (no walk graph, no kernel; the page
// skips the otsekaugus suffix for these ids -- see app/layers/page.tsx).
const MARUKOV_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set([
  "kovkasv",
  "kovkaive",
  "kovedas",
  "kovkiirus",
]);
// P4OSM-HOOK (#480): Euclidean-built P4OSM masters ride "euclidean" —
// blockwalk + darkness (Euclidean count kernels, viewshed/moorage/
// G05B precedent — see scripts/build/batch_p4_osmwalk.py).
const P4OSM_EUCLIDEAN_MASTER: ReadonlySet<string> = new Set(["blockwalk", "darkness"]);

export async function loadLayerRaster(
  layer: LayerId,
  dir: string = snapshotDir(),
): Promise<{ raster: WalkRasterDoc | null; distance: TransitDistance }> {
  const doc = await loadWalkRaster(layer, dir);
  if (doc && matchesContract(doc, layer)) {
    const euclidean =
      B6_EUCLIDEAN_MASTER.has(layer) ||
      G03_EUCLIDEAN_MASTER.has(layer) ||
      G03D_EUCLIDEAN_MASTER.has(layer) ||
      G08A_EUCLIDEAN_MASTER.has(layer) ||
      G08D_EUCLIDEAN_MASTER.has(layer) || // G08D-HOOK (#170)
      G08C_EUCLIDEAN_MASTER.has(layer) || // G08C-HOOK (#169)
      G08B_EUCLIDEAN_MASTER.has(layer) || // G08B-HOOK (#168)
      G05B_EUCLIDEAN_MASTER.has(layer) || // G05B-HOOK (#162)
      G05D_EUCLIDEAN_MASTER.has(layer) || // G05D-HOOK (#164)
      G05A_EUCLIDEAN_MASTER.has(layer) || // G05A-HOOK (#161)
      G05C_EUCLIDEAN_MASTER.has(layer) || // G05C-HOOK (#163)
      G05E_EUCLIDEAN_MASTER.has(layer) || // G05E-HOOK (#165)
      G05F_EUCLIDEAN_MASTER.has(layer) || // G05F-HOOK (#166)
      G10R_EUCLIDEAN_MASTER.has(layer) || // G10R-HOOK (#171)
      G18A_EUCLIDEAN_MASTER.has(layer) || // G18A-HOOK (#172)
      G18B_EUCLIDEAN_MASTER.has(layer) || // G18B-HOOK (#173)
      G17A_EUCLIDEAN_MASTER.has(layer) || // G17A-HOOK (#177)
      G17B_EUCLIDEAN_MASTER.has(layer) || // G17B-HOOK (#178)
      G17R_EUCLIDEAN_MASTER.has(layer) || // G17R-HOOK (#196)
      B10C_EUCLIDEAN_MASTER.has(layer) || // B10C-HOOK (#230)
      RSAFE_EUCLIDEAN_MASTER.has(layer) || // RSAFE-HOOK (#481)
      STATKOV_EUCLIDEAN_MASTER.has(layer) || // STATKOV-HOOK (#485)
      P4PARK_EUCLIDEAN_MASTER.has(layer) || // P4PARK-HOOK (#479)
      MARUKOV_EUCLIDEAN_MASTER.has(layer) || // MARUKOV-HOOK (#486)
      P4OSM_EUCLIDEAN_MASTER.has(layer); // P4OSM-HOOK (#480)
    return { raster: doc, distance: euclidean ? "euclidean" : "walk" };
  }
  return { raster: null, distance: "euclidean" };
}

/** Metro master file prefixes per layer (meta JSON + raw .u8, 8x cells). */
const METRO_PREFIX: Record<LayerId, string> = {
  transit: "transit-metro",
  parks: "parks-metro",
  schools: "schools-metro",
  walkability: "walkability-metro",
  pedinfra: "pedinfra-metro",
  cycling: "cycling-metro",
  grocery: "grocery-metro",
  healthcare: "healthcare-metro",
  ...B1_METRO_PREFIXES, // B1-HOOK(#98)
  // G07B-HOOK (#141): no metro masters by documented decision (see
  // layers_group07b.ts G07B_NO_METRO) — names resolve to absent files so
  // windows fall back to county cleanly.
  brownsoil: "brownsoil-metro",
  oiltank: "oiltank-metro",
  agriland: "agriland-metro",
  // G11D-HOOK (#135): leftover-B metro prefixes (unbuilt by design --
  // county-only; windows fall back to county, B5/GENV precedent).
  ...G11D_METRO_PREFIXES,
  // G07D-HOOK (#143): no metro masters by documented decision (see
  // layers_group07d.ts G07D_NO_METRO) — names resolve to absent files so
  // windows fall back to county cleanly.
  agrifield: "agrifield-metro",
  wildcorr: "wildcorr-metro",
  // G07C-HOOK(#142): no metro master by documented decision (see
  // layers_group07c.ts G07C_NO_METRO) — the name resolves to an absent
  // file so windows fall back to county cleanly.
  vectorhabitat: "vectorhabitat-metro",
  // G07-HOOK (#140): no metro masters by documented decision (see
  // layers_group07.ts G07_NO_METRO) — names resolve to absent files so
  // windows fall back to county cleanly.
  industprox: "industprox-metro",
  odorsrc: "odorsrc-metro",
  // B5-HOOK (#102): Group 14 metro masters (optional; windows fall back to county).
  safety: "safety-metro",
  emergency: "emergency-metro",
  hydrants: "hydrants-metro",
  evac: "evac-metro",
  dispatch: "dispatch-metro",
  // G06B-HOOK (#139): Group 6 leftover metro prefixes (optional; county-only like B5).
  ...GROUP06B_METRO_PREFIXES,
  // G11C-HOOK (#134): county-only layers (no metro masters; windows fall
  // back to county cleanly, B5 precedent).
  ...G11C_METRO_PREFIX,
  // B6-HOOK (#133): no metro masters (documented fake precision — the
  // files are absent, so windows serve county everywhere, like B5).
  droneclear: "droneclear-metro",
  droneviab: "droneviab-metro",
  rentbleed: "rentbleed-metro",
  // G06-HOOK (#138): Group 6 metro master (optional; county-only like B5).
  heritage: "heritage-metro",
  // G02B-HOOK (#137): no liftproxy metro master (documented fake
  // precision — the file is absent, so windows serve county everywhere).
  liftproxy: "liftproxy-metro",
  // G03-HOOK (#151): no drainage metro master (documented fake precision
  // — the file is absent, so windows serve county everywhere, like B5).
  drainage: "drainage-metro",
  // G03D-HOOK (#154): no moorage/shoredist metro masters (documented
  // fake precision — the files are absent, so windows serve county
  // everywhere, like G02B/G03).
  moorage: "moorage-metro",
  shoredist: "shoredist-metro",
  // G08A-HOOK (#167): no wildfire metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03).
  wildfire: "wildfire-metro",
  // G08D-HOOK (#170): no vernalpool metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D).
  vernalpool: "vernalpool-metro",
  // G08C-HOOK (#169): no surgeroad/slidebuf metro masters (documented
  // fake precision — the files are absent, so windows serve county
  // everywhere, like G02B/G03/G03D).
  surgeroad: "surgeroad-metro",
  slidebuf: "slidebuf-metro",
  // G08B-HOOK (#168): no windtunnel/saltspray metro masters (documented
  // fake precision — the files are absent, so windows serve county
  // everywhere, like G02B/G03/G03D).
  windtunnel: "windtunnel-metro",
  saltspray: "saltspray-metro",
  // G05B-HOOK (#162): no gardens/buildout metro masters (documented
  // fake precision — the files are absent, so windows serve county
  // everywhere, like G02B/G03/G03D).
  gardens: "gardens-metro",
  buildout: "buildout-metro",
  // G05D-HOOK (#164): no strsat metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D).
  strsat: "strsat-metro",
  // G05A-HOOK (#161): no ehitus/korterstock metro masters (documented
  // fake precision — the files are absent, so windows serve county
  // everywhere, like G02B/G03/G03D).
  ehitus: "ehitus-metro",
  korterstock: "korterstock-metro",
  // G05C-HOOK (#163): no commbleed/windsolar/viewshed metro masters
  // (documented fake precision — the files are absent, so windows
  // serve county everywhere, like G02B/G03/G03D/G08B).
  commbleed: "commbleed-metro",
  windsolar: "windsolar-metro",
  viewshed: "viewshed-metro",
  // G05E-HOOK (#165): no equestrian metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G08B/G05C).
  equestrian: "equestrian-metro",
  // G05F-HOOK (#166): no upcycle metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G08B/G05B/G05C).
  upcycle: "upcycle-metro",
  // G10R-HOOK (#171): no skyview metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G08B/G05C).
  skyview: "skyview-metro",
  // G18A-HOOK (#172): no dayopen/glassglare metro masters
  // (documented fake precision — the files are absent, so windows
  // serve county everywhere, like G02B/G03/G03D/G08B/G05C).
  dayopen: "dayopen-metro",
  glassglare: "glassglare-metro",
  // G18B-HOOK (#173): no fishbowl/mossrisk/daylight metro masters
  // (documented fake precision — the files are absent, so windows
  // serve county everywhere, like G02B/G03/G03D/G08B/G05C).
  fishbowl: "fishbowl-metro",
  mossrisk: "mossrisk-metro",
  daylight: "daylight-metro",
  // G17A-HOOK (#177): no compost/gritbin/leafdrop metro masters
  // (documented fake precision — the files are absent, so windows
  // serve county everywhere, like G02B/G03/G03D/G08B/G05C).
  compost: "compost-metro",
  gritbin: "gritbin-metro",
  leafdrop: "leafdrop-metro",
  // G17B-HOOK (#178): no lawncare metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G08B/G05C/G05E).
  lawncare: "lawncare-metro",
  // G17R-HOOK (#196): no privroad metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G08B/G05C/G05E).
  privroad: "privroad-metro",
  // B10C-HOOK (#230): no metro masters (sparse count kernels are smooth
  // at 75 m; files absent, windows serve county everywhere).
  water: "water-metro",
  waste: "waste-metro",
  fiber: "fiber-metro",
  mobile: "mobile-metro",
  // OSMDAILY-HOOK (#482): no metro masters (same documented fake
  // precision — the files are absent, so windows serve county
  // everywhere, like B10C/G02B/G03).
  dailyshop: "dailyshop-metro",
  activity: "activity-metro",
  herd: "herd-metro",
  thirdplace: "thirdplace-metro",
  taxidoor: "taxidoor-metro",
  lastshop: "lastshop-metro",
  // GTFS-HOOK (#483): no gtfsstops metro master (overlay-only — the file
  // is absent, so windows serve county everywhere, like G02B/G03/B10C).
  gtfsstops: "gtfsstops-metro",
  // RSAFE-HOOK (#481): no roadsafety metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G08B/G05C/G05E).
  roadsafety: "roadsafety-metro",
  // P4-031-HOOK (#484): no senscom metro master (no county master
  // either — SENSCOM_NO_RASTER; the name resolves to an absent file so
  // windows fall back to the client points-splat band kernel).
  senscom: "senscom-metro",
  // STATKOV-HOOK (#485): no metro masters by documented decision (see
  // layers_statkov.ts STATKOV_NO_METRO) -- names resolve to absent files
  // so windows fall back to county cleanly.
  kovmigr: "kovmigr-metro",
  kovehit: "kovehit-metro",
  kovfisc: "kovfisc-metro",
  // P4PARK-HOOK (#479): no parking metro master (documented fake
  // precision — the file is absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G08B/G05C/G17B).
  parking: "parking-metro",
  // MARUKOV-HOOK (#486): no metro masters by documented decision (see
  // layers_maru.ts MARUKOV_NO_METRO) -- names resolve to absent files
  // so windows fall back to county cleanly.
  kovkasv: "kovkasv-metro",
  kovkaive: "kovkaive-metro",
  kovedas: "kovedas-metro",
  kovkiirus: "kovkiirus-metro",
  // FLOOD-HOOK (#487): no floodzone metro master (polygons-only — the
  // file is absent, so windows serve county everywhere, honestly-empty).
  floodzone: "floodzone-metro",
  // P4OSM-HOOK (#480): no blockwalk/darkness metro masters (documented
  // fake precision — the files are absent, so windows serve county
  // everywhere, like G02B/G03/G03D/G05B).
  blockwalk: "blockwalk-metro",
  darkness: "darkness-metro",  // OOKLA-HOOK (#489): no ookla metro masters by documented decision
  // (see layers_p4_ookla.ts OOKLA_NO_RASTER) — names resolve to absent
  // files so windows fall back to the client tileband splat.
  ookla_fixed: "ookla-fixed-metro",
  ookla_mobile: "ookla-mobile-metro",
  // ACCBLACK-HOOK (#490): no accblack metro master by documented
  // decision (see layers_accblack.ts ACCBLACK_NO_RASTER) — the name
  // resolves to an absent file so windows fall back to county cleanly.
  accblack: "accblack-metro",

  // MAAPARCEL-HOOK (#491): no maaparcel metro master (documented, see
  // layers_maaparcel.ts MAAPARCEL_NO_METRO) -- resolves to an absent
  // file so windows fall back to county cleanly.
  maaparcel: "maaparcel-metro",

  // EELIS-HOOK (#488): no metro masters (polygons-only — the files are
  // absent, so windows serve county everywhere, honestly-empty).
  eeliskaitse: "eeliskaitse-metro",
  eelisniit: "eelisniit-metro",
  eelisraie: "eelisraie-metro",

  // PLANKTPR-HOOK (#492): no planktpr metro master by documented
  // decision (see layers_planktpr.ts PLANKTPR_NO_METRO) — the name
  // resolves to an absent file so windows fall back to county cleanly.
  planktpr: "planktpr-metro",
  // TERVISE-HOOK (#494): no tervise metro master (no county master
  // either — TERVISE_NO_RASTER; the name resolves to an absent file so
  // windows fall back to the client points-splat quality kernel).
  tervise: "tervise-metro",

  // ASUMEDIA-HOOK (#495): no asumedia metro master by documented
  // decision (see layers_asumedia.ts ASUMEDIA_NO_METRO) — the name
  // resolves to an absent file so windows fall back to county cleanly.
  asumedia: "asumedia-metro",
  // PAASTE-HOOK (#493): no paaste metro master (honest-empty — the file
  // is absent, so windows serve county everywhere, like G02B/G03/B10C).
  paaste: "paaste-metro",
  // SPORT-HOOK (#607): no sport metro masters (no county masters either
  // — SPORT_NO_RASTER; the names resolve to absent files so windows
  // fall back to the client points-splat distance kernel).
  sport_hall: "sport-hall-metro",
  sport_field: "sport-field-metro",
  sport_pool: "sport-pool-metro",
  // EHIS-HOOK (#608): no ehis metro masters (no county masters either
  // — EHIS_NO_RASTER; same absent-file fallback to the splat kernel).
  ehis_school: "ehis-school-metro",
  ehis_kindergarten: "ehis-kindergarten-metro",
  ehis_hobby: "ehis-hobby-metro",
  // MEDRE-HOOK (#609): no medre metro masters (no county masters
  // either — MEDRE_NO_RASTER; same absent-file fallback to the splat
  // kernel, dormant until Step 2).
  medre_gp: "medre-gp-metro",
  medre_clinic: "medre-clinic-metro",
  // OHUSEIRE-HOOK (#610): no ohuseire metro master (no county master
  // either — OHUSEIRE_NO_RASTER; the name resolves to an absent file
  // so windows fall back to the client points-splat distance kernel).
  ohuseire: "ohuseire-metro",
  // KLIIMA-HOOK (#611): no kliima metro masters (no county masters
  // either — KLIIMA_NO_RASTER; the names resolve to absent files so
  // windows fall back to the client points-splat quality kernel).
  kliima_frost: "kliima-frost-metro",
  kliima_wet: "kliima-wet-metro",
  // POI-HOOK (#612): no poi metro masters (no county masters either
  // — POI_NO_RASTER; the names resolve to absent files so windows
  // fall back to the client points-splat distance kernel).
  poi_library: "poi-library-metro",
  poi_post: "poi-post-metro",
  poi_pharmacy: "poi-pharmacy-metro",
  // FIXIT-HOOK (#623): no fixit metro master (no county master
  // either — FIXIT_NO_RASTER; the name resolves to an absent file so
  // windows fall back to the markers-only path).
  fixit: "fixit-metro",
  // DRAINAGE-HOOK (#616): no drainage metro master by documented
  // decision (see layers_p4_maaparandus.ts MAAPARANDUS_NO_METRO) — the name
  // resolves to an absent file so windows fall back to county cleanly.
  maaparandus: "maaparandus-metro",
  // ETAK-HOOK (#618): no etak metro master by documented decision
  // (see layers_p4_etak.ts ETAK_NO_METRO) — the name resolves to an
  // absent file so windows fall back to county cleanly.
  etak: "etak-metro",
  // SEVESO-HOOK (#613): no seveso metro master by documented decision
  // (see layers_p4_seveso.ts SEVESO_NO_METRO) — the name resolves to
  // an absent file so windows fall back to county cleanly.
  seveso: "seveso-metro",
  // STATELAND-HOOK (#615): no stateland metro master by documented
  // decision (see layers_p4_stateland.ts STATELAND_NO_METRO) — the
  // name resolves to an absent file so windows fall back to county
  // cleanly.
  stateland: "stateland-metro",
  // QUARRY-HOOK (#614): no quarry metro master by documented decision
  // (see layers_p4_quarry.ts QUARRY_NO_METRO) — the name resolves to
  // an absent file so windows fall back to county cleanly.
  quarry: "quarry-metro",
  // SOIL-HOOK (#617): no soil metro master by documented decision (see
  // layers_p4_soil.ts SOIL_NO_METRO) — the name resolves to an absent
  // file so windows fall back to county cleanly.
  soil: "soil-metro",
  // RELIEF-HOOK (#619): no relief metro master by documented decision
  // (see layers_p4_relief.ts RELIEF_NO_METRO) — the name resolves to
  // an absent file so windows fall back to county cleanly.
  relief: "relief-metro",
  // CANOPY-HOOK (#620): no canopy metro master by documented decision
  // (see layers_p4_canopy.ts CANOPY_NO_METRO) — the name resolves to
  // an absent file so windows fall back to county cleanly.
  canopy: "canopy-metro",
  // BUILDINGS-HOOK (#621): no buildings metro master by documented
  // decision (see layers_p4_buildings.ts BUILDINGS_NO_METRO) — the
  // name resolves to an absent file so windows fall back to county
  // cleanly.
  buildings: "buildings-metro",
  // DENSITY-HOOK (#622): no density metro master by documented
  // decision (see layers_p4_density.ts DENSITY_NO_METRO) — the name
  // resolves to an absent file so windows fall back to county
  // cleanly.
  density: "density-metro",
  // FOREST-HOOK (#624): no forest metro master by documented decision
  // (see layers_p4_forest.ts FOREST_NO_METRO) — the name resolves to
  // an absent file so windows fall back to county cleanly.
  forest: "forest-metro",
  // NOISE-HOOK (#625): no noise metro master by documented decision
  // (see layers_p4_noise.ts NOISE_NO_METRO) — the name resolves to
  // an absent file so windows fall back to county cleanly.
  noise: "noise-metro",
  // HARBOUR-HOOK (#627): no harbour metro master by documented decision
  // (see layers_p4_harbour.ts HARBOUR_NO_METRO) — the name resolves to
  // an absent file so windows fall back to county cleanly.
  harbour: "harbour-metro",
};

/** Decoded county payloads (small); metro .u8 stays on disk per request. */
const countyBytes = new Map<string, Uint8Array>();
const metroMeta = new Map<string, WalkRasterDoc | null>();

const WINDOW_MAX = 512;
const WINDOW_MIN = 1;

function clampGrid(n: unknown): number {
  const v = typeof n === "number" && Number.isFinite(n) ? Math.floor(n) : WINDOW_MIN;
  return Math.min(WINDOW_MAX, Math.max(WINDOW_MIN, v));
}

function validView(bbox: BBoxLike): boolean {
  const { minlon, minlat, maxlon, maxlat } = bbox;
  return (
    [minlon, minlat, maxlon, maxlat].every((v) => typeof v === "number" && Number.isFinite(v)) &&
    minlon < maxlon &&
    minlat < maxlat &&
    maxlon - minlon <= 10 &&
    maxlat - minlat <= 10
  );
}

function nearestAt(
  values: Uint8Array,
  cols: number,
  rows: number,
  bbox: BBoxLike,
  lon: number,
  lat: number,
): number | null {
  const gx = ((lon - bbox.minlon) / (bbox.maxlon - bbox.minlon)) * cols;
  const gy = ((lat - bbox.minlat) / (bbox.maxlat - bbox.minlat)) * rows;
  const ix = Math.floor(gx);
  const iy = Math.floor(gy);
  if (ix < 0 || iy < 0 || ix >= cols || iy >= rows) return null;
  return values[iy * cols + ix];
}

/**
 * Fill pass cap for hole inpainting: bounds cost and leaves holes wider
 * than ~1/8 of the view red (unknown) instead of smearing edge values
 * across the map.
 */
const FILL_PASSES = 64;

/**
 * Inpaint unknown (255) cells inside the coverage mask with the
 * distance-weighted average of surrounding known values (Jacobi Laplace
 * relaxation: each pass fills unknowns touching known neighbors with the
 * neighbor average, so influence decays with distance). Cells outside the
 * mask — true out-of-coverage — stay 255. Mutates `out` in place.
 */
function fillUnknownHoles(out: Uint8Array, cols: number, rows: number, cover: Uint8Array): void {
  // Mask of fillable cells (unknown at start, inside coverage); measured
  // cells are never touched. Relaxation keeps going after the first wave
  // so far-side surroundings diffuse in (two-sided average, not nearest).
  const fill = new Uint8Array(out.length);
  let known = 0;
  for (let i = 0; i < out.length; i++) {
    if (out[i] === 255) {
      if (cover[i] === 1) fill[i] = 1;
    } else {
      known++;
    }
  }
  if (known === 0) return;
  let src = Uint8Array.from(out);
  let dst = Uint8Array.from(out);
  for (let pass = 0; pass < FILL_PASSES; pass++) {
    let maxChange = 0;
    for (let iy = 0; iy < rows; iy++) {
      for (let ix = 0; ix < cols; ix++) {
        const i = iy * cols + ix;
        if (fill[i] !== 1) {
          dst[i] = src[i];
          continue;
        }
        let sum = 0;
        let n = 0;
        if (ix > 0 && src[i - 1] !== 255) {
          sum += src[i - 1];
          n++;
        }
        if (ix + 1 < cols && src[i + 1] !== 255) {
          sum += src[i + 1];
          n++;
        }
        if (iy > 0 && src[i - cols] !== 255) {
          sum += src[i - cols];
          n++;
        }
        if (iy + 1 < rows && src[i + cols] !== 255) {
          sum += src[i + cols];
          n++;
        }
        if (n > 0) {
          const v = Math.round(sum / n);
          // A freshly filled cell counts as changed (sentinel -1) so the
          // loop survives the first wave and relaxes toward the far side.
          const prev = src[i] === 255 ? -1 : src[i];
          const change = Math.abs(v - prev);
          if (change > maxChange) maxChange = change;
          dst[i] = v;
        } else {
          dst[i] = 255;
        }
      }
    }
    const tmp = src;
    src = dst;
    dst = tmp;
    if (maxChange === 0) break;
  }
  out.set(src);
}

/**
 * Per-view score window: metro master (8x cells) where it covers and
 * knows, county raster elsewhere, unknown (255) past both. Grid sizes
 * clamp to 512^2; garbage views read null. Never throws (null degrades
 * to the client's points-splat fallback).
 */
export async function loadWindowRaster(
  layer: LayerId,
  view: BBoxLike,
  cols: number,
  rows: number,
  dir: string = snapshotDir(),
): Promise<WalkRasterDoc | null> {
  if (!validView(view)) return null;
  const county = await loadWalkRaster(layer, dir);
  if (!county || !matchesContract(county, layer)) return null;
  const spec = bonusSpecFor(layer);
  const outCols = clampGrid(cols);
  const outRows = clampGrid(rows);
  const out = new Uint8Array(outCols * outRows);

  let countyVals = countyBytes.get(`${dir}::${layer}`);
  if (!countyVals) {
    try {
      const bin = atob(county.data);
      countyVals = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) countyVals[i] = bin.charCodeAt(i);
    } catch {
      return null;
    }
    if (countyVals.length !== county.cols * county.rows) return null;
    countyBytes.set(`${dir}::${layer}`, countyVals);
  }

  const metaKey = `${dir}::${layer}`;
  let meta = metroMeta.get(metaKey);
  if (meta === undefined) {
    meta = null;
    try {
      const raw = await fs.readFile(path.join(dir, "osm", `${METRO_PREFIX[layer]}.json`), "utf8");
      const doc = cleanRaster({ ...(JSON.parse(raw) as object), data: "AA==" });
      if (doc && matchesContract(doc, layer)) meta = doc;
    } catch {
      meta = null;
    }
    metroMeta.set(metaKey, meta);
  }
  let metroVals: Uint8Array | null = null;
  if (meta) {
    try {
      metroVals = new Uint8Array(await fs.readFile(path.join(dir, "osm", `${METRO_PREFIX[layer]}.u8`)));
    } catch {
      metroVals = null;
    }
    if (metroVals && metroVals.length !== meta.cols * meta.rows) metroVals = null;
  }

  const cover = new Uint8Array(outCols * outRows);
  for (let iy = 0; iy < outRows; iy++) {
    const lat = view.minlat + ((iy + 0.5) / outRows) * (view.maxlat - view.minlat);
    for (let ix = 0; ix < outCols; ix++) {
      const lon = view.minlon + ((ix + 0.5) / outCols) * (view.maxlon - view.minlon);
      let v: number | null = null;
      if (metroVals && meta) {
        const m = nearestAt(metroVals, meta.cols, meta.rows, meta.bbox, lon, lat);
        if (m !== null && m !== 255) v = m;
      }
      if (v === null) {
        // County is a smooth kernel field sampled too coarsely: bilinear
        // reconstructs the gradient instead of nearest-snapping 75 m
        // blocks. Metro stays nearest-exact (real 9 m detail).
        const hit = sampleRaster(
          { cols: county.cols, rows: county.rows, bbox: county.bbox, values: countyVals },
          lon,
          lat,
        );
        if (hit) v = Math.round(hit.value);
      }
      out[iy * outCols + ix] = v === null ? 255 : v;
      cover[iy * outCols + ix] =
        lon >= county.bbox.minlon &&
        lon <= county.bbox.maxlon &&
        lat >= county.bbox.minlat &&
        lat <= county.bbox.maxlat
          ? 1
          : 0;
    }
  }
  // Unmeasurable cells inherit the distance-weighted average of their
  // surroundings; true out-of-coverage stays 255 (red).
  fillUnknownHoles(out, outCols, outRows, cover);
  // Approximate meters-per-cell along longitude at 59N (display-only).
  const stepM = ((view.maxlon - view.minlon) * 57300) / outCols;
  return {
    cols: outCols,
    rows: outRows,
    bbox: view,
    step_m: stepM,
    // B6-HOOK (#133) + G03-HOOK (#151): "quiet" specs carry halfM, not half.
    // G07B-HOOK (#141): quiet specs carry halfM, not half.
    // G07D-HOOK (#143): quiet specs carry halfM, not half.
    // B6-HOOK (#133): "quiet" specs carry halfM, not half.
    // G07-HOOK (#140): quiet specs carry halfM, not half.
    // B10C-HOOK (#230): "cover" (mobile) is self-scaling: null half.
    half:
      spec.kind === "variety" || spec.kind === "cover"
        ? null
        : spec.kind === "quiet"
          ? spec.halfM
          : (spec as { half: number }).half,
    sigma: radiusKmFor(layer),
    per: spec.kind === "variety" ? spec.per : 0,
    cap: spec.kind === "variety" ? spec.cap : 0,
    unknown: 255,
    dtype: "uint8",
    data: Buffer.from(out).toString("base64"),
  };
}

function inBBox(p: LayerPoint, bbox: BBoxLike): boolean {
  return (
    p.lon >= bbox.minlon && p.lon <= bbox.maxlon && p.lat >= bbox.minlat && p.lat <= bbox.maxlat
  );
}

/**
 * Points for one layer clipped to the bbox. Reads
 * `<snapshotDir>/osm/derived-<layer>.json` once per process; coordless junk
 * is skipped. Throws SnapshotUnavailable when the snapshot cannot be read —
 * callers must surface that honestly, never substitute other data.
 */
export async function loadSnapshotPoints(
  layer: LayerId,
  bbox: BBoxLike,
  dir: string = snapshotDir(),
): Promise<LayerPoint[]> {
  const cacheKey = `${dir}::${layer}`;
  let all = allPoints.get(cacheKey);
  if (!all) {
    const file = path.join(dir, "osm", `derived-${layer}.json`);
    let raw: string;
    try {
      raw = await fs.readFile(file, "utf8");
    } catch {
      throw new SnapshotUnavailable(`cannot read ${file}`);
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(raw);
    } catch {
      throw new SnapshotUnavailable(`${file} is not valid JSON`);
    }
    if (!Array.isArray(parsed)) {
      throw new SnapshotUnavailable(`${file} is not a point array`);
    }
    all = [];
    for (const p of parsed) {
      const clean = toPoint(p);
      if (clean) all.push(clean);
    }
    if (layer === "parks") {
      all = await parksAreas(all, await loadParkAreas(dir));
    } else if (layer === "transit") {
      // Winner-takes-all per GTFS stop: a station complex has many OSM
      // nodes but one departures total — counting it at every node would
      // multiply the same buses (Balti: 7 entries × 40 nodes). The nearest
      // node keeps the trips; co-claimants read 0 so the SUM stays honest.
      const freq = await loadFrequency(dir);
      const claim = new Array<number>(all.length).fill(-1);
      const dist = new Array<number>(all.length).fill(Infinity);
      for (let i = 0; i < all.length; i++) {
        const p = all[i];
        for (let j = 0; j < freq.length; j++) {
          const f = freq[j];
          if (Math.abs(f.lon - p.lon) > 0.002 || Math.abs(f.lat - p.lat) > 0.001) continue;
          const d = haversineKm(p.lat, p.lon, f.lat, f.lon);
          if (d < dist[i]) {
            dist[i] = d;
            claim[i] = j;
          }
        }
      }
      const wonBy = new Map<number, number>();
      for (let i = 0; i < all.length; i++) {
        if (claim[i] < 0 || dist[i] > FREQ_JOIN_KM) continue;
        const prev = wonBy.get(claim[i]);
        if (prev === undefined || dist[i] < dist[prev]) wonBy.set(claim[i], i);
      }
      for (let i = 0; i < all.length; i++) {
        if (claim[i] < 0 || dist[i] > FREQ_JOIN_KM) {
          all[i].t = TRANSIT_DEFAULT_TRIPS;
        } else {
          all[i].t = wonBy.get(claim[i]) === i ? freq[claim[i]].trips : 0;
        }
      }
    }
    allPoints.set(cacheKey, all);
  }
  return all.filter((p) => inBBox(p, bbox));
}
