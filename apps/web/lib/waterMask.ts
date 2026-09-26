// Open-water mask for the aggregate view (#821).
//
// Sea and large lakes would otherwise paint green/red and stretch the
// viewport-recalibrated gradient (#819). Water cells are excluded from
// the scale and painted fixed blue — never part of the goodness ramp.
//
// GEOMETRY (real data, see waterMaskData.ts header): OSM Estonia
// snapshot estonia-260911.osm.pbf, natural=coastline chained into
// LAND_RINGS, natural=water areas >= 2 ha as LAKE_POLYS.
//
// SEMANTICS: a point is water when it lies inside any lake poly, or
// outside every land ring (sea). Judgment calls, documented:
// - Land beyond Estonia's borders (LV/RU) reads as water: the rings
//   end at the border and foreign soil has no layer coverage anyway.
// - Rivers stay land unless OSM maps them as natural=water areas;
//   lines have no interior to test.
//
// PERFORMANCE: ~23k grid cells x ~2k polys would be fine with bbox
// rejects alone, except the mainland ring's giant bbox admits every
// cell to a full ray cast. A coarse 0.05 deg spatial index (built once
// at module load) keeps each query to a handful of candidates.

import type { BBoxLike } from "./layers";
import { LAKE_POLYS, LAND_RINGS } from "./waterMaskData";

/** Fixed water paint (tailwind blue-500): reads as water, never ramp. */
export const WATER_BLUE: readonly [number, number, number] = [59, 130, 246];

type Ring = readonly (readonly [number, number])[];

interface PolyEntry {
  ring: Ring;
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

function entryOf(ring: Ring): PolyEntry | null {
  if (ring.length < 4) return null;
  let minlon = Infinity;
  let minlat = Infinity;
  let maxlon = -Infinity;
  let maxlat = -Infinity;
  for (const [lon, lat] of ring) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    if (lon < minlon) minlon = lon;
    if (lat < minlat) minlat = lat;
    if (lon > maxlon) maxlon = lon;
    if (lat > maxlat) maxlat = lat;
  }
  return { ring, minlon, minlat, maxlon, maxlat };
}

/** Even-odd ray cast; boundary counts as inside (shore reads water). */
function pointInRing(lon: number, lat: number, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    if (yi === yj) continue;
    if (lat < Math.min(yi, yj) || lat > Math.max(yi, yj)) continue;
    const x = xi + ((lat - yi) / (yj - yi)) * (xj - xi);
    if (lon <= x) inside = !inside;
  }
  return inside;
}

/** Coarse index cell size in degrees (~5 km over Estonia). */
const INDEX_STEP = 0.05;

function buildIndex(
  entries: PolyEntry[],
): Map<string, number[]> {
  const index = new Map<string, number[]>();
  entries.forEach((e, k) => {
    const x0 = Math.floor(e.minlon / INDEX_STEP);
    const x1 = Math.floor(e.maxlon / INDEX_STEP);
    const y0 = Math.floor(e.minlat / INDEX_STEP);
    const y1 = Math.floor(e.maxlat / INDEX_STEP);
    for (let x = x0; x <= x1; x++) {
      for (let y = y0; y <= y1; y++) {
        const key = `${x}:${y}`;
        const bucket = index.get(key);
        if (bucket) bucket.push(k);
        else index.set(key, [k]);
      }
    }
  });
  return index;
}

function candidatesFor(
  index: Map<string, number[]>,
  entries: PolyEntry[],
  lon: number,
  lat: number,
): PolyEntry[] {
  const bucket = index.get(
    `${Math.floor(lon / INDEX_STEP)}:${Math.floor(lat / INDEX_STEP)}`,
  );
  if (!bucket) return [];
  const out: PolyEntry[] = [];
  for (const k of bucket) {
    const e = entries[k];
    if (lon < e.minlon || lon > e.maxlon || lat < e.minlat || lat > e.maxlat) {
      continue;
    }
    out.push(e);
  }
  return out;
}

const LAND: PolyEntry[] = [];
const LAKES: PolyEntry[] = [];
const LAKE_HOLES: PolyEntry[] = [];
// The generated sidecar infers as nested number[] (no tuple
// annotations) — narrow through unknown once, validated per ring by
// entryOf below.
const LAND_SRC = LAND_RINGS as unknown as Ring[];
const LAKE_SRC = LAKE_POLYS as unknown as Ring[][];
for (const r of LAND_SRC) {
  const e = entryOf(r);
  if (e) LAND.push(e);
}
for (const lake of LAKE_SRC) {
  if (lake.length === 0) continue;
  const outer = entryOf(lake[0]);
  if (!outer) continue;
  LAKES.push(outer);
  for (const r of lake.slice(1)) {
    const h = entryOf(r);
    if (h) LAKE_HOLES.push(h);
  }
}
const LAND_INDEX = buildIndex(LAND);
const LAKE_INDEX = buildIndex(LAKES);
const HOLE_INDEX = buildIndex(LAKE_HOLES);

/** How many land rings / lake polys survived validation (tests pin). */
export function waterMaskStats(): { landRings: number; lakePolys: number } {
  return { landRings: LAND.length, lakePolys: LAKES.length };
}

/**
 * True for open water: inside any lake poly, or outside every land
 * ring (sea — and, by documented design, foreign soil past the
 * border, which has no layer coverage regardless).
 */
export function isWater(lon: number, lat: number): boolean {
  if (!Number.isFinite(lon) || !Number.isFinite(lat)) return false;
  for (const e of candidatesFor(LAKE_INDEX, LAKES, lon, lat)) {
    if (!pointInRing(lon, lat, e.ring)) continue;
    // Lake islands (holes, e.g. Piirissaar) read land-side: fall
    // through to the land-ring test instead of reading water.
    let island = false;
    for (const h of candidatesFor(HOLE_INDEX, LAKE_HOLES, lon, lat)) {
      if (pointInRing(lon, lat, h.ring)) {
        island = true;
        break;
      }
    }
    if (!island) return true;
    break;
  }
  for (const e of candidatesFor(LAND_INDEX, LAND, lon, lat)) {
    if (pointInRing(lon, lat, e.ring)) return false;
  }
  return true;
}

/**
 * Per-cell water flags for an aggregate grid (cell centers tested),
 * same length as field.mean / cols*rows. Memoise per view in the
 * caller — the build is ~ms, not free.
 */
export function waterMaskFor(grid: {
  cols: number;
  rows: number;
  bbox: BBoxLike;
}): Uint8Array {
  const { cols, rows, bbox } = grid;
  const out = new Uint8Array(cols * rows);
  for (let iy = 0; iy < rows; iy++) {
    const lat = bbox.minlat + ((iy + 0.5) / rows) * (bbox.maxlat - bbox.minlat);
    for (let ix = 0; ix < cols; ix++) {
      const lon =
        bbox.minlon + ((ix + 0.5) / cols) * (bbox.maxlon - bbox.minlon);
      if (isWater(lon, lat)) out[iy * cols + ix] = 1;
    }
  }
  return out;
}
