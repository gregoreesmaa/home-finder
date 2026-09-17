// Server-side ETAK viewport proxy (issue #618): bbox-filtered WFS
// reads across the four measured themes, with a grid-snapped annual
// disk cache.
//
// Why a proxy, not a sidecar: the four Harjumaa themes total ~52k
// polygons (~114 MB raw GeoJSON, measured 2026-09-16) — uncommittable
// and unshippable to the browser. The client sends its settled viewport
// bbox; the server snaps it to a 0.05° grid, serves the annual disk
// cache when warm, and otherwise pulls one WFS GetFeature per theme per
// grid cell (at most ~5000 decoded polygons per viewport in total —
// wider views are refused with an honest zoom-in note, never truncated
// into a fake complete picture). Transport errors are never cached as
// data.
//
// WFS dialect (measured 2026-09-16, polite GETs only): WFS 2.0.0,
// srsName EPSG:4326, bbox in LON-LAT order with an explicit ,EPSG:4326
// suffix (this GeoServer, like the mulla one, wants lon-lat even with
// the suffix — probed both orders; Harjumaa counts verified:
// e_306_margala_a 8824, e_202_seisuveekogu_a 15474,
// e_203_vooluveekogu_a 1332, e_302_ou_a 26024). numberMatched in the
// GeoJSON body gates the too-wide refusal before pages are consumed
// (the server caps hits at 5000 but reports true counts on GetFeature).
//
// Decode lives in ../layers_p4_etak (pure, unit-tested): theme class
// from tyyp_tekst, water type carried (edge unmoved), vintage date per
// row. Relief types are never queried (licence gate).

import {
  ETAK_CLASS_SCORE,
  decodeEtakClass,
  etakVintage,
  type EtakArea,
  type EtakClass,
  type EtakTheme,
} from "../layers_p4_etak";

/** Measured theme -> WFS type (verified 2026-09-16). Relief gated OUT. */
export const ETAK_WFS_TYPES: Record<EtakTheme, string> = {
  wetland: "etak:e_306_margala_a",
  standing: "etak:e_202_seisuveekogu_a",
  flowing: "etak:e_203_vooluveekogu_a",
  yard: "etak:e_302_ou_a",
};

const ETAK_WFS_BASE = "https://gsavalik.envir.ee/geoserver/etak/wfs";

/** Identifying user agent for the polite pull (viewport-driven, cached). */
export const ETAK_WFS_UA = "home-finder etak viewport proxy (grid cache, annual TTL)";

/** Cache grid: settled pans inside one cell share a key (degrees). */
export const ETAK_GRID_DEG = 0.05;

/** DAILY feed, annual client TTL (soil precedent: one pull per cell per year). */
export const ETAK_TTL_MS = 365 * 24 * 3600 * 1000;

/** Viewport polygon cap across all themes: wider views get a zoom-in note. */
export const ETAK_MAX_FEATURES = 5000;

/** WFS page size (GeoServer count/startIndex paging). */
const ETAK_PAGE_SIZE = 2000;

export interface EtakViewportBbox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

export interface EtakViewportDeps {
  fetchImpl: typeof fetch;
  readCache: (key: string) => Promise<string | null>;
  writeCache: (key: string, body: string) => Promise<void>;
  nowMs?: number;
}

export type EtakViewportResult =
  | { ok: true; areas: EtakArea[]; cached: boolean }
  | { ok: false; reason: "bad-bbox" | "too-wide" | "upstream" };

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function isSaneEtakBbox(b: EtakViewportBbox): boolean {
  const vals = [num(b.minlon), num(b.minlat), num(b.maxlon), num(b.maxlat)];
  if (vals.some((v) => v === null)) return false;
  const [w, s, e, n] = vals as number[];
  // Well-formed only (range + order). Width is NOT capped here: wide
  // but sane viewports take the honestly-empty too-wide path (cheap
  // hits queries), never a 400.
  return w >= -180 && e <= 180 && s >= -90 && n <= 90 && w < e && s < n;
}

/** Grid-snapped cache key (settled pans share keys, stable across runs). */
export function etakCacheKey(b: EtakViewportBbox): string {
  const g = ETAK_GRID_DEG;
  const snap = (v: number) => (Math.floor(v / g) * g).toFixed(2);
  return `etak/${snap(b.minlon)}_${snap(b.minlat)}_${snap(b.maxlon)}_${snap(b.maxlat)}.json`;
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

interface WfsFeature {
  properties?: Record<string, unknown>;
  geometry?: { type?: unknown; coordinates?: unknown };
}

function str(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 ? v : null;
}

function decodeFeature(theme: EtakTheme, f: WfsFeature): EtakArea | null {
  const props = f?.properties ?? {};
  const tyyp = str(props.tyyp_tekst) ?? str(props.kood_tekst);
  const name = str(props.nimetus);
  const cls: EtakClass | null = decodeEtakClass(theme, tyyp, name);
  if (!cls) return null;
  const coords = f?.geometry?.coordinates;
  if (!Array.isArray(coords) || coords.length === 0) return null;
  const rings: number[][][] = [];
  const polys = f.geometry?.type === "MultiPolygon" ? coords : [coords];
  for (const poly of polys as unknown[][][]) {
    if (!Array.isArray(poly) || poly.length === 0) continue;
    const outer = poly[0] as number[][];
    if (Array.isArray(outer) && outer.length >= 3) rings.push(outer);
  }
  if (rings.length === 0) return null;
  const box = ringBox(rings[0]);
  if (!box) return null;
  const etakId = props.etak_id;
  const zoneId =
    typeof etakId === "number" || typeof etakId === "string"
      ? `etak:${String(etakId)}`
      : `${theme}:${box[0].toFixed(4)},${box[1].toFixed(4)}`;
  return {
    zone_id: zoneId,
    theme,
    cls,
    score: ETAK_CLASS_SCORE[cls],
    label: tyyp ?? "",
    name,
    vintage: etakVintage(props.muutmisaeg),
    b: box,
    r: rings,
  };
}

/**
 * Viewport ETAK polygons across the four measured themes: grid cache,
 * else lon-lat WFS pages decoded to scorer-parity legs. Undecodable
 * rows are dropped (never guessed, never cached as errors).
 */
export async function fetchEtakViewport(
  bbox: EtakViewportBbox,
  deps: EtakViewportDeps,
): Promise<EtakViewportResult> {
  if (!isSaneEtakBbox(bbox)) return { ok: false, reason: "bad-bbox" };
  const key = etakCacheKey(bbox);
  const now = deps.nowMs ?? Date.now();
  try {
    const hit = await deps.readCache(key);
    if (hit) {
      const parsed = JSON.parse(hit) as { areas?: unknown; atMs?: unknown };
      // Entries must prove freshness: ageless or expired entries are
      // refetched (fail closed — never serve ageless data as current).
      if (
        Array.isArray(parsed.areas) &&
        typeof parsed.atMs === "number" &&
        now - parsed.atMs <= ETAK_TTL_MS
      ) {
        return { ok: true, areas: parsed.areas as EtakArea[], cached: true };
      }
    }
  } catch {
    // Corrupt cache entry: fall through to a fresh WFS pull (never
    // serve corrupt bytes as data).
  }
  const q = (typeNames: string, extra: Record<string, string>) =>
    new URLSearchParams({
      service: "WFS",
      version: "2.0.0",
      request: "GetFeature",
      typeNames,
      srsName: "EPSG:4326",
      bbox: [bbox.minlon, bbox.minlat, bbox.maxlon, bbox.maxlat].join(",") + ",EPSG:4326",
      outputFormat: "application/json",
      ...extra,
    });
  const headers = { "User-Agent": ETAK_WFS_UA };
  const areas: EtakArea[] = [];
  for (const theme of Object.keys(ETAK_WFS_TYPES) as EtakTheme[]) {
    let first: { numberMatched?: unknown; features?: unknown };
    try {
      const res = await deps.fetchImpl(
        `${ETAK_WFS_BASE}?${q(ETAK_WFS_TYPES[theme], { count: String(ETAK_PAGE_SIZE) })}`,
        { headers } as RequestInit,
      );
      if (!res.ok) return { ok: false, reason: "upstream" };
      first = (await res.json()) as typeof first;
    } catch {
      return { ok: false, reason: "upstream" };
    }
    const matched =
      typeof first.numberMatched === "number" ? first.numberMatched : Number(first.numberMatched);
    const features = Array.isArray(first.features) ? (first.features as WfsFeature[]) : [];
    if (Number.isFinite(matched) && (matched as number) > ETAK_MAX_FEATURES) {
      return { ok: false, reason: "too-wide" };
    }
    let pages = features;
    if (Number.isFinite(matched) && (matched as number) > features.length && features.length > 0) {
      pages = [...features];
      for (let start = features.length; start < (matched as number); start += ETAK_PAGE_SIZE) {
        if (areas.length + pages.length >= ETAK_MAX_FEATURES) break;
        let page: WfsFeature[];
        try {
          const res = await deps.fetchImpl(
            `${ETAK_WFS_BASE}?${q(ETAK_WFS_TYPES[theme], {
              count: String(ETAK_PAGE_SIZE),
              startIndex: String(start),
            })}`,
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
    for (const f of pages) {
      if (areas.length >= ETAK_MAX_FEATURES) break;
      const area = decodeFeature(theme, f);
      if (area) areas.push(area);
    }
  }
  try {
    await deps.writeCache(key, JSON.stringify({ areas, atMs: now }));
  } catch {
    // Cache write failure: serve the fresh areas anyway (cache is an
    // optimization, never load-bearing).
  }
  return { ok: true, areas, cached: false };
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const ETAK_SERVER_HOOK =
  "ETAK-HOOK (#618): viewport WFS proxy with grid cache (server); rings verbatim, relief never queried.";
