// Server-side soil viewport proxy (issue #617): bbox-filtered WFS
// reads with a grid-snapped annual disk cache.
//
// Why a proxy, not a sidecar: the Harjumaa soil harvest is ~600 MB of
// 1:10 000 rings (86474 polygons, measured 2026-09-16) — uncommittable
// and unshippable to the browser. The client sends its settled viewport
// bbox; the server snaps it to a 0.05° grid, serves the annual disk
// cache when warm, and otherwise pages one WFS GetFeature per grid cell
// (at most ~5000 decoded polygons per viewport — wider views are
// refused with an honest zoom-in note, never truncated into a fake
// complete picture). Transport errors are never cached as data.
//
// WFS dialect (measured 2026-09-16, one polite GET each): WFS 2.0.0,
// typeNames SO_pinnas:SO.SoilBody, srsName EPSG:4326, bbox in LON-LAT
// order with an explicit ,EPSG:4326 suffix (this GeoServer ignores the
// axis-order rule and wants lon-lat even with the suffix — probed both
// orders, only lon-lat matches the documented 86474 Harjumaa hits).
// Paging via count/startIndex; numberMatched in the GeoJSON body gates
// the too-wide refusal before any page is consumed.
//
// Decode + urban policy live in ../layers_p4_soil (pure, unit-tested):
// family from the gml_name šifr, rähkne folded into the paepealne band,
// urban centroids (Tallinn city bbox) and undecoded/veeala contours
// dropped and COUNTED (reported, never silently lost).

import {
  SOIL_CLASS_SCORE,
  decodeSoilFamily,
  soilClassForFamily,
  type SoilArea,
  type SoilClass,
} from "../layers_p4_soil";

/** Harvest feature type (verified 2026-09-16, DefaultCRS EPSG:3301). */
export const SOIL_WFS_TYPE = "SO_pinnas:SO.SoilBody";

const SOIL_WFS_BASE = "https://inspire.geoportaal.ee/geoserver/SO_pinnas/wfs";

/** Identifying user agent for the polite pull (viewport-driven, cached). */
export const SOIL_WFS_UA = "home-finder soil viewport proxy (grid cache, annual TTL)";

/** Cache grid: settled pans inside one cell share a key (degrees). */
export const SOIL_GRID_DEG = 0.05;

/** IRREG feed: at most one WFS pull per grid cell per year. */
export const SOIL_TTL_MS = 365 * 24 * 3600 * 1000;

/** Viewport polygon cap: wider views get a zoom-in note, never a sample. */
export const SOIL_MAX_FEATURES = 5000;

/** WFS page size (GeoServer count/startIndex paging). */
const SOIL_PAGE_SIZE = 2000;

/**
 * Tallinn city bbox (scorer parity: the NULL-in-cities rule in
 * services/scoring/dims_soil_map.py uses this window — 2226 fringe
 * polygons measured). Centroid-inside polygons are urban (disturbed
 * fill) and render no-data.
 */
export const SOIL_URBAN_BBOX = {
  minlon: 24.55,
  minlat: 59.35,
  maxlon: 24.95,
  maxlat: 59.5,
};

export interface SoilViewportBbox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

export interface SoilViewportDeps {
  fetchImpl: typeof fetch;
  readCache: (key: string) => Promise<string | null>;
  writeCache: (key: string, body: string) => Promise<void>;
  nowMs?: number;
}

export type SoilViewportResult =
  | {
      ok: true;
      areas: SoilArea[];
      cached: boolean;
      undecoded: number;
      urbanDropped: number;
      /** Human Estonian note, present only when areas is empty but
       * urbanDropped > 0 (#662) — the service answered, every contour
       * was urban/water. The too-wide branch keeps its own note. */
      note?: string;
    }
  | { ok: false; reason: "bad-bbox" | "too-wide" | "upstream" };

/**
 * Human note when the service answered but every contour dropped as
 * urban/water (#662): unknown ground, not good soil. Exact string —
 * pinned by test, shown verbatim on the layers page.
 */
export const SOIL_URBAN_NOTE =
  "Asustatud/veekogu alal mullakaarti pole (teadmata, mitte hea pinnas)";

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function isSaneBbox(b: SoilViewportBbox): boolean {
  const vals = [num(b.minlon), num(b.minlat), num(b.maxlon), num(b.maxlat)];
  if (vals.some((v) => v === null)) return false;
  const [w, s, e, n] = vals as number[];
  // Well-formed only (range + order). Width is NOT capped here: wide
  // but sane viewports take the honestly-empty too-wide path (one
  // cheap hits query), never a 400.
  return w >= -180 && e <= 180 && s >= -90 && n <= 90 && w < e && s < n;
}

/** Grid-snapped cache key (settled pans share keys, stable across runs). */
export function soilCacheKey(b: SoilViewportBbox): string {
  const g = SOIL_GRID_DEG;
  const snap = (v: number) => (Math.floor(v / g) * g).toFixed(2);
  return `soil/${snap(b.minlon)}_${snap(b.minlat)}_${snap(b.maxlon)}_${snap(b.maxlat)}.json`;
}

function ringBox(ring: number[][]): [number, number, number, number] | null {
  let w = Infinity,
    s = Infinity,
    e = -Infinity,
    n = -Infinity;
  for (const pt of ring) {
    if (!Array.isArray(pt) || pt.length !== 2) return null;
    const [lon, lat] = pt;
    if (typeof lon !== "number" || typeof lat !== "number") return null;
    if (!Number.isFinite(lon) || !Number.isFinite(lat)) return null;
    if (lon < w) w = lon;
    if (lat < s) s = lat;
    if (lon > e) e = lon;
    if (lat > n) n = lat;
  }
  if (!Number.isFinite(w)) return null;
  return [w, s, e, n];
}

function centroidInUrban(box: [number, number, number, number]): boolean {
  const lon = (box[0] + box[2]) / 2;
  const lat = (box[1] + box[3]) / 2;
  const u = SOIL_URBAN_BBOX;
  return lon >= u.minlon && lon <= u.maxlon && lat >= u.minlat && lat <= u.maxlat;
}

interface WfsFeature {
  properties?: {
    gml_name?: unknown;
    soilbodylabel?: unknown;
    inspireid_identifier_localid?: unknown;
  };
  geometry?: { type?: unknown; coordinates?: unknown };
}

function decodeFeature(f: WfsFeature): { area?: SoilArea; undecoded?: boolean } {
  const props = f?.properties ?? {};
  const name = typeof props.gml_name === "string" ? props.gml_name : null;
  const label = typeof props.soilbodylabel === "string" ? props.soilbodylabel : "";
  const family = decodeSoilFamily(name, label);
  if (!family) return { undecoded: true };
  const coords = f?.geometry?.coordinates;
  if (!Array.isArray(coords) || coords.length === 0) return { undecoded: true };
  // Outer rings only, verbatim coordinates (holes ignored fail-safe
  // towards over-coverage, sibling precedent).
  const rings: number[][][] = [];
  const polys = f.geometry?.type === "MultiPolygon" ? coords : [coords];
  for (const poly of polys as unknown[][][]) {
    if (!Array.isArray(poly) || poly.length === 0) continue;
    const outer = poly[0] as number[][];
    if (Array.isArray(outer) && outer.length >= 3) rings.push(outer);
  }
  if (rings.length === 0) return { undecoded: true };
  const box = ringBox(rings[0]);
  if (!box) return { undecoded: true };
  if (centroidInUrban(box)) return {};
  const cls: SoilClass = soilClassForFamily(family);
  const zoneId =
    typeof props.inspireid_identifier_localid === "string"
      ? props.inspireid_identifier_localid
      : `${box[0].toFixed(4)},${box[1].toFixed(4)}`;
  return {
    area: {
      zone_id: zoneId,
      family,
      cls,
      score: SOIL_CLASS_SCORE[cls],
      code: name ?? "",
      b: box,
      r: rings,
    },
  };
}

/**
 * Viewport soil polygons: grid cache, else lon-lat WFS pages decoded to
 * scorer-parity bands. Urban + undecoded contours are dropped and
 * counted (never guessed, never cached as errors).
 */
export async function fetchSoilViewport(
  bbox: SoilViewportBbox,
  deps: SoilViewportDeps,
): Promise<SoilViewportResult> {
  if (!isSaneBbox(bbox)) return { ok: false, reason: "bad-bbox" };
  const key = soilCacheKey(bbox);
  const now = deps.nowMs ?? Date.now();
  try {
    const hit = await deps.readCache(key);
    if (hit) {
      const parsed = JSON.parse(hit) as {
        areas?: unknown;
        atMs?: unknown;
        undecoded?: unknown;
        urbanDropped?: unknown;
      };
      // Entries must prove freshness: ageless or expired entries are
      // refetched (fail closed — never serve ageless data as current).
      if (
        Array.isArray(parsed.areas) &&
        typeof parsed.atMs === "number" &&
        now - parsed.atMs <= SOIL_TTL_MS
      ) {
        const areas = parsed.areas as SoilArea[];
        const urbanDropped =
          typeof parsed.urbanDropped === "number" ? parsed.urbanDropped : 0;
        return {
          ok: true,
          areas,
          cached: true,
          undecoded: typeof parsed.undecoded === "number" ? parsed.undecoded : 0,
          urbanDropped,
          ...(areas.length === 0 && urbanDropped > 0 ? { note: SOIL_URBAN_NOTE } : {}),
        };
      }
    }
  } catch {
    // Corrupt cache entry: fall through to a fresh WFS pull (never
    // serve corrupt bytes as data).
  }
  const q = (extra: Record<string, string>) =>
    new URLSearchParams({
      service: "WFS",
      version: "2.0.0",
      request: "GetFeature",
      typeNames: SOIL_WFS_TYPE,
      srsName: "EPSG:4326",
      bbox: [bbox.minlon, bbox.minlat, bbox.maxlon, bbox.maxlat].join(",") + ",EPSG:4326",
      outputFormat: "application/json",
      ...extra,
    });
  const headers = { "User-Agent": SOIL_WFS_UA };
  let first: { numberMatched?: unknown; features?: unknown };
  try {
    const res = await deps.fetchImpl(`${SOIL_WFS_BASE}?${q({ count: String(SOIL_PAGE_SIZE) })}`, {
      headers,
    } as RequestInit);
    if (!res.ok) return { ok: false, reason: "upstream" };
    first = (await res.json()) as typeof first;
  } catch {
    return { ok: false, reason: "upstream" };
  }
  const matched =
    typeof first.numberMatched === "number" ? first.numberMatched : Number(first.numberMatched);
  const features = Array.isArray(first.features) ? (first.features as WfsFeature[]) : [];
  if (Number.isFinite(matched) && (matched as number) > SOIL_MAX_FEATURES) {
    return { ok: false, reason: "too-wide" };
  }
  let pages = features;
  if (
    Number.isFinite(matched) &&
    (matched as number) > features.length &&
    features.length > 0
  ) {
    pages = [...features];
    for (let start = features.length; start < (matched as number); start += SOIL_PAGE_SIZE) {
      if (pages.length >= SOIL_MAX_FEATURES) break;
      let page: WfsFeature[];
      try {
        const res = await deps.fetchImpl(
          `${SOIL_WFS_BASE}?${q({ count: String(SOIL_PAGE_SIZE), startIndex: String(start) })}`,
          { headers } as RequestInit,
        );
        if (!res.ok) return { ok: false, reason: "upstream" };
        const body = (await res.json()) as { features?: unknown };
        page = Array.isArray(body.features) ? (body.features as WfsFeature[]) : [];
      } catch {
        return { ok: false, reason: "upstream" };
      }
      if (page.length === 0) break;
      pages.push(...page);
    }
  }
  const areas: SoilArea[] = [];
  let undecoded = 0;
  let urbanDropped = 0;
  for (const f of pages.slice(0, SOIL_MAX_FEATURES)) {
    const { area, undecoded: u } = decodeFeature(f);
    if (area) areas.push(area);
    else if (u) undecoded++;
    else urbanDropped++;
  }
  try {
    await deps.writeCache(key, JSON.stringify({ areas, atMs: now, undecoded, urbanDropped }));
  } catch {
    // Cache write failure: serve the fresh areas anyway (cache is an
    // optimization, never load-bearing).
  }
  return {
    ok: true,
    areas,
    cached: false,
    undecoded,
    urbanDropped,
    ...(areas.length === 0 && urbanDropped > 0 ? { note: SOIL_URBAN_NOTE } : {}),
  };
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const SOIL_SERVER_HOOK =
  "SOIL-HOOK (#617): viewport WFS proxy with grid cache (server); rings verbatim, urban/undecoded dropped+counted.";
