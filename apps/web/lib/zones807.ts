// Polygon-membership goodness zones (issue #807).
//
// Many /layers layers paint polygons (fills carry the verdict) but their
// bonusSpecFor() returned an INERT area/60 placeholder — zero points, never
// evaluated — so no 0..100 score existed anywhere. This module is the map
// half of the fix: it turns each such layer's sidecar/viewport polygons
// into scored membership zones (inside = band score, outside = unknown,
// never a faked zero) that the shared field renderer paints + hovers like
// every other kernel. Values ride the leaf modules' scorer-parity tables
// (same constants the fills + services/scoring dims use); this file owns
// only the membership plumbing (ring tests, min-wins, the indexed field).
//
// Semantics per layer (good = ? / bad = ?) live with the scores:
// inside-band tables in the leaf modules + the PR inventory table.

import type { BBoxLike, LayerId } from "./layers";
import type { FloodArea } from "./layers_flood";
import { FLOOD_ZONE_SCORE } from "./layers_flood";
import type { EelisArea } from "./layers_eelis";
import { EELIS_KIND, EELIS_KIND_SCORE } from "./layers_eelis";
import type { SevesoArea } from "./layers_p4_seveso";
import { SEVESO_DANGER_SCORE } from "./layers_p4_seveso";
import type { StatelandArea } from "./layers_p4_stateland";
import { STATELAND_CLASS_SCORE } from "./layers_p4_stateland";
import type { QuarryArea } from "./layers_p4_quarry";
import { QUARRY_CLASS_SCORE } from "./layers_p4_quarry";
import type { MaaparandusArea } from "./layers_p4_maaparandus";
import { MAAPARANDUS_CLASS_SCORE } from "./layers_p4_maaparandus";
import type { SoilArea } from "./layers_p4_soil";
import type { EtakArea } from "./layers_p4_etak";
import type { ForestArea } from "./layers_p4_forest";
import { FOREST_CLASS_SCORE } from "./layers_p4_forest";
import type { NoiseArea } from "./layers_p4_noise";
import { noiseScoreForArea } from "./layers_p4_noise";
import type { HarbourCell, HarbourPort } from "./layers_p4_harbour";
import { harbourCellScoreFor, harbourPortBands } from "./layers_p4_harbour";
import type { KpoArea } from "./layers_p4_kpo";
import { kpoScoreForZone } from "./layers_p4_kpo";
import type { DelayArea } from "./layers_p4_delay";
import {
  DELAY_BAND_SCORE,
  DELAY_LAYER_BAND,
  delayBandForFactor,
} from "./layers_p4_delay";
import type { ShedArea, ShedLayerId } from "./layers_p4_tomtom_sheds";
import { SHED_BUDGET_SCORE, SHED_LAYER_SPEC } from "./layers_p4_tomtom_sheds";
import type { UseFillPolygon } from "./outlines";
import { planktprBandForColor } from "./layers_planktpr";

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const ZONES807_HOOK =
  "807-HOOK (#807): polygon-membership goodness zones — inside = band score, outside = unknown; values ride the leaf scorer-parity tables.";

/** One scored membership zone: rings are GeoJSON [lon, lat] pairs. */
export interface Zone {
  /** Inside score 0..100 (the leaf band table's verdict for this shape). */
  score: number;
  /** Outer rings (holes ignored fail-safe towards over-coverage: a hole
   * misread as inside scores low, never falsely calm — seveso/quarry
   * painter precedent, buyer-conservative). */
  rings: number[][][];
  /** [minlon, minlat, maxlon, maxlat] prefilter box (ParkOutline precedent). */
  bbox: [number, number, number, number];
}

/** Ray-casting point-in-ring over [lon, lat] pairs (shed parity: shedCoversPoint). */
export function zonePointInRing(lon: number, lat: number, ring: number[][]): boolean {
  if (ring.length < 3) return false;
  let inside = false;
  let j = ring.length - 1;
  for (let i = 0; i < ring.length; i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    if (yi > lat !== yj > lat) {
      const xcross = ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
      if (lon < xcross) inside = !inside;
    }
    j = i;
  }
  return inside;
}

function zoneCovers(zone: Zone, lon: number, lat: number): boolean {
  const b = zone.bbox;
  if (lon < b[0] || lon > b[2] || lat < b[1] || lat > b[3]) return false;
  for (const ring of zone.rings) {
    if (zonePointInRing(lon, lat, ring)) return true;
  }
  return false;
}

/**
 * Goodness 0..100 by zone membership (pure). Worst (lowest) covering
 * zone wins — buyer-conservative, the scorer's min-wins precedent
 * (noise binding leg, harbour worst-wins). Null when no zone covers:
 * outside every mapped shape is unknown, never a faked zero/calm.
 */
export function zoneScoreAt(lat: number, lon: number, zones: Zone[]): number | null {
  let best: number | null = null;
  for (const zone of zones) {
    if (!Number.isFinite(zone.score)) continue;
    if (zoneCovers(zone, lon, lat) && (best === null || zone.score < best)) {
      best = zone.score;
    }
  }
  return best;
}

/** Bbox of [lon, lat] rings; null when no finite point exists. */
export function ringsBbox(rings: number[][][]): [number, number, number, number] | null {
  let minlon = Infinity;
  let minlat = Infinity;
  let maxlon = -Infinity;
  let maxlat = -Infinity;
  for (const ring of rings) {
    for (const pt of ring) {
      const lon = pt[0];
      const lat = pt[1];
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) continue;
      if (lon < minlon) minlon = lon;
      if (lat < minlat) minlat = lat;
      if (lon > maxlon) maxlon = lon;
      if (lat > maxlat) maxlat = lat;
    }
  }
  if (!Number.isFinite(minlon)) return null;
  return [minlon, minlat, maxlon, maxlat];
}

/** Disc zone (ports, outflow buffers): 16-gon around lon/lat. */
export function discZone(lon: number, lat: number, radiusM: number, score: number): Zone | null {
  if (!Number.isFinite(lon) || !Number.isFinite(lat) || !Number.isFinite(radiusM) || radiusM <= 0) {
    return null;
  }
  const cosLat = Math.max(0.2, Math.cos((lat * Math.PI) / 180));
  const rLat = radiusM / 110570;
  const rLon = radiusM / (111320 * cosLat);
  const ring: number[][] = [];
  for (let i = 0; i < 16; i++) {
    const a = (2 * Math.PI * i) / 16;
    ring.push([lon + rLon * Math.cos(a), lat + rLat * Math.sin(a)]);
  }
  ring.push([...ring[0]]);
  const bbox = ringsBbox([ring]);
  if (!bbox) return null;
  return { score, rings: [ring], bbox };
}

// ---------------------------------------------------------------------------
// Per-layer assemblers: sidecar areas -> zones. Malformed shapes are
// skipped, never faked; unscored classes (unknown use, thin delay data)
// emit no zone so the field stays unknown there.
// ---------------------------------------------------------------------------

function zonesFromClassAreas<T>(
  areas: T[] | null | undefined,
  ringsOf: (a: T) => number[][][] | undefined,
  bboxOf: (a: T) => [number, number, number, number] | undefined,
  scoreOf: (a: T) => number | null,
): Zone[] {
  const out: Zone[] = [];
  if (!areas) return out;
  for (const a of areas) {
    const score = scoreOf(a);
    if (score === null || !Number.isFinite(score)) continue;
    const rings = ringsOf(a);
    if (!rings || rings.length === 0) continue;
    const bbox = bboxOf(a) ?? ringsBbox(rings);
    if (!bbox) continue;
    out.push({ score, rings, bbox });
  }
  return out;
}

const RINGS = (r: number[][][] | undefined) => r;
const BBOX = (b: [number, number, number, number] | undefined) => b;

export function floodZones(areas: FloodArea[] | null | undefined): Zone[] {
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), () => FLOOD_ZONE_SCORE);
}

export function eelisZones(layer: LayerId, areas: EelisArea[] | null | undefined): Zone[] {
  const score = (EELIS_KIND_SCORE as Record<string, number>)[EELIS_KIND[layer as keyof typeof EELIS_KIND] ?? ""];
  if (!Number.isFinite(score)) return [];
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), () => score);
}

export function sevesoZones(areas: SevesoArea[] | null | undefined): Zone[] {
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) => SEVESO_DANGER_SCORE[a.danger] ?? null);
}

export function statelandZones(areas: StatelandArea[] | null | undefined): Zone[] {
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) => STATELAND_CLASS_SCORE[a.cls] ?? null);
}

export function quarryZones(areas: QuarryArea[] | null | undefined): Zone[] {
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) => QUARRY_CLASS_SCORE[a.cls] ?? null);
}

export function soilZones(areas: SoilArea[] | null | undefined): Zone[] {
  // The server stamps area.score from SOIL_BANDS (validated 0..100 by
  // isSoilArea); the map reuses it verbatim — one table, no fork.
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) =>
    Number.isFinite(a.score) && a.score >= 0 && a.score <= 100 ? a.score : null,
  );
}

export function etakZones(areas: EtakArea[] | null | undefined): Zone[] {
  // Same shape as soil: the server stamps area.score (dims_group18etak
  // vocabulary, validated 0..100 by isEtakArea); reused verbatim.
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) =>
    Number.isFinite(a.score) && a.score >= 0 && a.score <= 100 ? a.score : null,
  );
}

export function forestZones(areas: ForestArea[] | null | undefined): Zone[] {
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) => FOREST_CLASS_SCORE[a.cls] ?? null);
}

export function noiseZones(areas: NoiseArea[] | null | undefined): Zone[] {
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) => noiseScoreForArea(a.leg, a.band_db));
}

export function kpoZones(areas: KpoArea[] | null | undefined): Zone[] {
  return zonesFromClassAreas(areas, (a) => RINGS(a.r), (a) => BBOX(a.b), (a) => kpoScoreForZone(a.voond, a.family));
}

export function delayZones(layer: LayerId, areas: DelayArea[] | null | undefined): Zone[] {
  const bandKey = (DELAY_LAYER_BAND as Record<string, string>)[layer];
  if (!bandKey) return [];
  return zonesFromClassAreas(
    areas,
    (a) => RINGS(a.r),
    (a) => BBOX(a.b),
    (a) => {
      const factor = a.factors?.[bandKey];
      const band = delayBandForFactor(factor);
      // Thin/missing cells (unknown band) emit no zone: the scorer
      // reads the same gap as NULL (never free-flow), so the map
      // stays unknown there too — the slate fill says mõõtmata.
      if (band === "unknown") return null;
      return DELAY_BAND_SCORE[band];
    },
  );
}

export function maaparandusZones(areas: MaaparandusArea[] | null | undefined): Zone[] {
  const out: Zone[] = [];
  if (!areas) return out;
  for (const a of areas) {
    const score = MAAPARANDUS_CLASS_SCORE[a.cls] ?? null;
    if (score === null) continue;
    if (a.cls === "outflow") {
      // Outflow rides centerlines, not polygons: buffer the line into
      // <=50 m densified 100 m discs (the scorer's ≤100 m outflow-near
      // join, MAAPARANDUS_CLASS_SCORE outflow 45). Gaps stay unknown.
      if (!a.l) continue;
      for (const line of a.l) {
        for (const [lon, lat] of densifyLine(line, 50)) {
          const zone = discZone(lon, lat, 100, score);
          if (zone) out.push(zone);
        }
      }
      continue;
    }
    if (!a.r || a.r.length === 0) continue;
    const bbox = a.b ?? ringsBbox(a.r);
    if (!bbox) continue;
    out.push({ score, rings: a.r, bbox });
  }
  return out;
}

/** Points along a [lon, lat] line at most every stepM metres. */
export function densifyLine(line: number[][], stepM: number): number[][] {
  const pts = (line ?? []).filter(
    (pt) => Array.isArray(pt) && Number.isFinite(pt[0]) && Number.isFinite(pt[1]),
  );
  if (pts.length === 0) return [];
  if (pts.length === 1) return [pts[0]];
  const out: number[][] = [pts[0]];
  for (let i = 1; i < pts.length; i++) {
    const [lon0, lat0] = pts[i - 1];
    const [lon1, lat1] = pts[i];
    const cosLat = Math.max(0.2, Math.cos((((lat0 + lat1) / 2) * Math.PI) / 180));
    const segM = Math.hypot((lon1 - lon0) * 111320 * cosLat, (lat1 - lat0) * 110570);
    const steps = Math.max(1, Math.ceil(segM / stepM));
    for (let s = 1; s <= steps; s++) {
      out.push([lon0 + ((lon1 - lon0) * s) / steps, lat0 + ((lat1 - lat0) * s) / steps]);
    }
  }
  return out;
}

export function harbourZones(
  ports: HarbourPort[] | null | undefined,
  cells: HarbourCell[] | null | undefined,
): Zone[] {
  const out: Zone[] = [];
  for (const p of ports ?? []) {
    const bands = harbourPortBands(p.function);
    if (!bands) continue;
    // Nested discs, min-wins: inside 500 m reads the inner band, the
    // 500-1500 m ring the outer band (scorer FUNCTION_BANDS parity —
    // inner < outer for every function, so min picks correctly).
    for (const [radiusM, score] of bands) {
      const zone = discZone(p.lon, p.lat, radiusM, score);
      if (zone) out.push(zone);
    }
  }
  for (const c of cells ?? []) {
    const score = harbourCellScoreFor(c.pleasure);
    if (score === null) continue;
    // 500 m grid quads, byte parity with harbourCellFeatures in
    // ./outlines (250 m half-side, lon scaled) so scores sit exactly
    // under the fills.
    const HALF_LAT = 250 / 111320;
    const halfLon = HALF_LAT / Math.max(0.2, Math.cos((c.lat * Math.PI) / 180));
    const ring = [
      [c.lon - halfLon, c.lat - HALF_LAT],
      [c.lon + halfLon, c.lat - HALF_LAT],
      [c.lon + halfLon, c.lat + HALF_LAT],
      [c.lon - halfLon, c.lat + HALF_LAT],
      [c.lon - halfLon, c.lat - HALF_LAT],
    ];
    const bbox = ringsBbox([ring]);
    if (!bbox) continue;
    out.push({ score, rings: [ring], bbox });
  }
  return out;
}

export function shedZones(layer: ShedLayerId, areas: ShedArea[] | null | undefined): Zone[] {
  const spec = SHED_LAYER_SPEC[layer];
  if (!spec) return [];
  const score = SHED_BUDGET_SCORE[spec.budgetS as keyof typeof SHED_BUDGET_SCORE];
  if (!Number.isFinite(score)) return [];
  const out: Zone[] = [];
  for (const a of areas ?? []) {
    // Shed rings are [lat, lon] pairs — flipped to GeoJSON [lon, lat]
    // once, here, so every downstream test sees one axis order.
    if (!a.ring || a.ring.length < 3) continue;
    const rings = [a.ring.filter((pt) => Number.isFinite(pt[0]) && Number.isFinite(pt[1])).map(([lat, lon]) => [lon, lat])];
    if (rings[0].length < 3) continue;
    const bbox = ringsBbox(rings);
    if (!bbox) continue;
    out.push({ score, rings, bbox });
  }
  return out;
}

export function planktprZones(fills: UseFillPolygon[] | null | undefined): Zone[] {
  const out: Zone[] = [];
  for (const f of fills ?? []) {
    // The caller filters unscored rows (non-kehtestatud, unknown use,
    // non-Tallinn) and stamps the band color; the band rides back off
    // the color (planktprBandForColor round-trip, pinned by test).
    const score = planktprBandForColor(f.color);
    if (score === null || !f.rings || f.rings.length === 0) continue;
    const bbox = ringsBbox(f.rings);
    if (!bbox) continue;
    out.push({ score, rings: f.rings, bbox });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Dispatcher: layer + page-held sidecar state -> zones. Layers without a
// zones spec (points kernels, pins, taste tints, dormant sets) read [] —
// the caller only consults this for zones-kind layers.
// ---------------------------------------------------------------------------

export interface Zones807Context {
  floodAreas?: FloodArea[] | null;
  eelisAreas?: EelisArea[] | null;
  sevesoAreas?: SevesoArea[] | null;
  statelandAreas?: StatelandArea[] | null;
  quarryAreas?: QuarryArea[] | null;
  maaparandusAreas?: MaaparandusArea[] | null;
  soilAreas?: SoilArea[] | null;
  etakAreas?: EtakArea[] | null;
  forestAreas?: ForestArea[] | null;
  noiseAreas?: NoiseArea[] | null;
  kpoAreas?: KpoArea[] | null;
  delayAreas?: DelayArea[] | null;
  shedAreas?: ShedArea[] | null;
  harbourCells?: HarbourCell[] | null;
  harbourPorts?: HarbourPort[] | null;
  usePolygons?: UseFillPolygon[] | null;
}

export function zonesForLayer(layer: LayerId, ctx: Zones807Context = {}): Zone[] {
  switch (layer) {
    case "floodzone":
      return floodZones(ctx.floodAreas);
    case "eeliskaitse":
    case "eelisniit":
    case "eelisraie":
      return eelisZones(layer, ctx.eelisAreas);
    case "seveso":
      return sevesoZones(ctx.sevesoAreas);
    case "stateland":
      return statelandZones(ctx.statelandAreas);
    case "quarry":
      return quarryZones(ctx.quarryAreas);
    case "maaparandus":
      return maaparandusZones(ctx.maaparandusAreas);
    case "soil":
      return soilZones(ctx.soilAreas);
    case "etak":
      return etakZones(ctx.etakAreas);
    case "forest":
      return forestZones(ctx.forestAreas);
    case "noise":
      return noiseZones(ctx.noiseAreas);
    case "harbour":
      return harbourZones(ctx.harbourPorts, ctx.harbourCells);
    case "kpo":
      return kpoZones(ctx.kpoAreas);
    case "delay-morning":
    case "delay-midday":
    case "delay-evening":
    case "delay-offpeak":
    case "delay-worst":
      return delayZones(layer, ctx.delayAreas);
    case "shed-15-peak":
    case "shed-15-offpeak":
    case "shed-30-peak":
    case "shed-30-offpeak":
      return shedZones(layer, ctx.shedAreas);
    case "planktpr":
      return planktprZones(ctx.usePolygons);
    default:
      return [];
  }
}

// ---------------------------------------------------------------------------
// Indexed zone field: exact per-cell membership over a uniform zone
// index (country views hold thousands of forest polygons — a flat
// cells x zones scan would stall the tab; the index keeps each cell to
// its handful of bbox-overlapping candidates).
// ---------------------------------------------------------------------------

const ZONE_INDEX_CELLS = 64;

/**
 * Membership score grid (NaN = outside every zone = unknown, never
 * zero). Geometry mirrors buildDistanceField (fencepost nodes,
 * equirect degrees — membership needs no projection).
 */
export function buildZoneField(zones: Zone[], bbox: BBoxLike, cols: number, rows: number): Float64Array {
  const direct = new Float64Array(cols * rows).fill(NaN);
  if (zones.length === 0 || cols <= 0 || rows <= 0) return direct;
  const spanLon = bbox.maxlon - bbox.minlon;
  const spanLat = bbox.maxlat - bbox.minlat;
  if (!(spanLon > 0) || !(spanLat > 0)) return direct;
  // Zone -> index cells via its bbox (clamped, at least one cell).
  const index: number[][] = Array.from({ length: ZONE_INDEX_CELLS * ZONE_INDEX_CELLS }, () => []);
  zones.forEach((zone, zi) => {
    const b = zone.bbox;
    const x0 = Math.max(0, Math.floor(((b[0] - bbox.minlon) / spanLon) * ZONE_INDEX_CELLS));
    const x1 = Math.min(ZONE_INDEX_CELLS - 1, Math.floor(((b[2] - bbox.minlon) / spanLon) * ZONE_INDEX_CELLS));
    const y0 = Math.max(0, Math.floor(((b[1] - bbox.minlat) / spanLat) * ZONE_INDEX_CELLS));
    const y1 = Math.min(ZONE_INDEX_CELLS - 1, Math.floor(((b[3] - bbox.minlat) / spanLat) * ZONE_INDEX_CELLS));
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) {
        index[y * ZONE_INDEX_CELLS + x].push(zi);
      }
    }
  });
  for (let iy = 0; iy < rows; iy++) {
    const lat = rows > 1 ? bbox.minlat + (iy / (rows - 1)) * spanLat : (bbox.minlat + bbox.maxlat) / 2;
    const cy = Math.min(ZONE_INDEX_CELLS - 1, Math.max(0, Math.floor(((lat - bbox.minlat) / spanLat) * ZONE_INDEX_CELLS)));
    for (let ix = 0; ix < cols; ix++) {
      const lon = cols > 1 ? bbox.minlon + (ix / (cols - 1)) * spanLon : (bbox.minlon + bbox.maxlon) / 2;
      const cx = Math.min(ZONE_INDEX_CELLS - 1, Math.max(0, Math.floor(((lon - bbox.minlon) / spanLon) * ZONE_INDEX_CELLS)));
      let best: number | null = null;
      for (const zi of index[cy * ZONE_INDEX_CELLS + cx]) {
        const zone = zones[zi];
        if (!Number.isFinite(zone.score)) continue;
        if (zoneCovers(zone, lon, lat) && (best === null || zone.score < best)) {
          best = zone.score;
        }
      }
      if (best !== null) direct[iy * cols + ix] = best;
    }
  }
  return direct;
}
