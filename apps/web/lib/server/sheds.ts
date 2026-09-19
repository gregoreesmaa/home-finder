// TomTom shed snapshot from the operator cache (issue #763, harvester
// #670). Assembles the { polygons } snapshot the overlay consumes
// through shedPolygonsForLayer (same origin files, never committed)
// from the keyed harvester's git-ignored cache dir:
// tomtom_shed_<hub>_<budget>_<band>.json (raw reachable-range bodies).
// Per-hub TTL (SHED_TTL_S, parity with dims_tomtom_isochrones.py —
// pinned in test): a stale hub drops that hub only, others still
// serve; a fully missing cache reads null (honestly-empty, never demo
// polygons). No network, ever.

import { readdir } from "node:fs/promises";
import type { ShedLayerId, ShedPolygon } from "../layers_p4_tomtom_sheds";
import { SHED_LAYER_SPEC } from "../layers_p4_tomtom_sheds";
import { readOpCacheTable } from "./livecache";

/** 7-day short-term cache (parity with SHED_TTL_S in Python, pinned). */
export const SHED_TTL_S = 7 * 24 * 3600;

/** The 5 job hubs the keyed harvester pulls (batch_tomtom_isochrones). */
export const SHED_HUBS = [
  "city-center",
  "ulemiste",
  "mustamae",
  "port",
  "airport",
] as const;

/** Harvester cache filename for one hub x budget x band. */
export function SHED_CACHE_FILE(hub: string, budget: string, band: string): string {
  return `tomtom_shed_${hub}_${budget}_${band}.json`;
}

/** Default cache dir (same default as the harvester --cache-dir usage). */
export function shedCacheDir(env: NodeJS.ProcessEnv = process.env): string {
  return env.SHED_CACHE_DIR ?? "/tmp/hf-sheds";
}

export interface ShedSnapshot {
  polygons: ShedPolygon[];
  /** Freshness source: oldest hub mtime served (the binding constraint). */
  builtAtMs: number;
}

/** Raw reachable-range body -> boundary ring [[lat, lon]]. */
function boundaryRing(body: unknown): Array<[number, number]> {
  if (typeof body !== "object" || body === null) return [];
  const boundary = (body as { reachableRange?: { boundary?: unknown } })
    .reachableRange?.boundary;
  if (!Array.isArray(boundary)) return [];
  const out: Array<[number, number]> = [];
  for (const pt of boundary) {
    if (typeof pt !== "object" || pt === null) continue;
    const rec = pt as Record<string, unknown>;
    if (typeof rec.latitude === "boolean" || typeof rec.longitude === "boolean") {
      continue;
    }
    const lat = Number(rec.latitude);
    const lon = Number(rec.longitude);
    if (Number.isFinite(lat) && Number.isFinite(lon)) out.push([lat, lon]);
  }
  return out;
}

/** mtime freshness against the 7-day TTL (pure, hermetic tests). */
export function isShedCacheFresh(mtimeMs: number, nowMs: number): boolean {
  const age = nowMs - mtimeMs;
  return age >= 0 && age < SHED_TTL_S * 1000;
}

const BUDGETS = ["900", "1800"] as const;
const BANDS = ["rush", "offpeak"] as const;

/**
 * Assemble the shed snapshot from the operator cache dir. Null when no
 * hub file is fresh (missing dir reads null too — never throws).
 */
export async function loadShedSnapshot(
  dir: string = shedCacheDir(),
  nowMs: number = Date.now(),
): Promise<ShedSnapshot | null> {
  let names: string[];
  try {
    names = await readdir(dir);
  } catch {
    return null;
  }
  const fresh = new Set(names);
  const polygons: ShedPolygon[] = [];
  let oldest = nowMs;
  for (const hub of SHED_HUBS) {
    for (const budget of BUDGETS) {
      for (const band of BANDS) {
        const file = SHED_CACHE_FILE(hub, budget, band);
        if (!fresh.has(file)) continue;
        const cached = await readOpCacheTable(dir, file, SHED_TTL_S, nowMs);
        if (!cached) continue;
        const ring = boundaryRing(cached.table);
        if (ring.length < 3) continue;
        polygons.push({ hub, budgetS: Number(budget), band, ring });
        if (cached.builtAtMs < oldest) oldest = cached.builtAtMs;
      }
    }
  }
  if (polygons.length === 0) return null;
  return { polygons, builtAtMs: oldest };
}

/** Paint areas for one shed layer (rings with <3 points never paint). */
export function shedAreasForLayer(
  snap: ShedSnapshot | null,
  layer: ShedLayerId,
): ShedPolygon[] {
  if (!snap) return [];
  const spec = SHED_LAYER_SPEC[layer];
  return snap.polygons.filter(
    (p) => p.budgetS === spec.budgetS && p.band === spec.band && p.ring.length >= 3,
  );
}

/**
 * Honest-empty reason served with the 503 when the weekly operator
 * cache is missing or fully stale (issue #787): names the weekly
 * keyed cache + 7-day TTL + the refill path, and states that no
 * polygons are invented. Pinned by test (never faked sheds).
 */
export const SHED_EMPTY_REASON =
  "TomTomi nädalapuhver puudub või on aegunud " +
  "(7-päeva TTL; 5 hubi x 15/30 min x tipptund/tipuväline). " +
  "Värskenda võtmega tõmbega: pole iganädalane töö " +
  "(pole/bin/run-tomtom-sheds.sh) või " +
  "batch_tomtom_isochrones.py --pull --cache-dir. " +
  "Tühja puhvrit ei asendata väljamõeldud polügoonidega.";

/**
 * Route payload for one shed layer. 200 { areas, builtAtMs } when the
 * cache serves; 503 { error, reason } when it is missing or fully
 * stale — never 200-empty, never demo polygons. Pure (hermetic
 * tests); the Next route is a thin wrapper around this.
 */
export function shedAreasResult(
  snap: ShedSnapshot | null,
  layer: ShedLayerId,
): { status: number; body: unknown } {
  if (!snap) {
    return {
      status: 503,
      body: { error: "shed cache empty", reason: SHED_EMPTY_REASON },
    };
  }
  return {
    status: 200,
    body: { areas: shedAreasForLayer(snap, layer), builtAtMs: snap.builtAtMs },
  };
}
