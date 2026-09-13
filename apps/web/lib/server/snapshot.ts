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
// G03D-HOOK(#154): batch G03D raster files live in layers_group03d.ts.
import { G03D_RASTER_FILE } from "../layers_group03d";

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

const areaCache = new Map<string, ParkArea[]>();

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
  // B6-HOOK (#133): "quiet" carries halfM on the wire half field.
  // G07-HOOK (#140): nearest-source cleanliness (0 on the source, 50 at halfM).
  if (spec.kind === "quiet") return doc.half === spec.halfM;
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

export async function loadLayerRaster(
  layer: LayerId,
  dir: string = snapshotDir(),
): Promise<{ raster: WalkRasterDoc | null; distance: TransitDistance }> {
  const doc = await loadWalkRaster(layer, dir);
  if (doc && matchesContract(doc, layer)) {
    const euclidean =
      B6_EUCLIDEAN_MASTER.has(layer) ||
      G03_EUCLIDEAN_MASTER.has(layer) ||
      G03D_EUCLIDEAN_MASTER.has(layer);
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
    half:
      spec.kind === "variety"
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
