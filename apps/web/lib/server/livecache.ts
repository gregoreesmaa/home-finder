// Live-table reads for pole/operator-cache layers (issue #763).
//
// Thin NO-STORE primitive (sibling fileCache.ts WRITES upstream loads to
// disk — forbidden here by the TomTom 11.4 / DATEX SHORT-TERM CACHE ONLY
// verdicts: no committed sidecars, no stored tables). Two sources:
//
// 1. Pole live tables: server-side GET to POLE_BASE_URL (default the Mac
//    LAN tunnel 127.0.0.1:18001 -> pole:8001, AGENTS.md section 9),
//    freshness from the X-Pole-Built-At header. Short timeout, no
//    retries, nothing written anywhere.
// 2. Local operator-cache files (TomTom sheds/incidents keyed harvesters
//    fill git-ignored cache dirs, outage #729 precedent): TTL enforced
//    on file mtime, missing/stale/corrupt reads null.
//
// Transport errors are never cached as data and never throw: every
// failure reads null so the route degrades to labeled demo (or
// honestly-empty for geometry-less feeds).

import { readFile, stat } from "node:fs/promises";
import { join } from "node:path";

/** Default pole read API (Mac ssh tunnel -> pole:8001). */
export const POLE_DEFAULT_URL = "http://127.0.0.1:18001";

/** Pole base URL (operator override for docker/pole-hosted web). */
export function poleBaseUrl(
  env: Record<string, string | undefined> = process.env,
): string {
  return env.POLE_BASE_URL ?? POLE_DEFAULT_URL;
}

export interface PoleTable {
  /** Parsed JSON object body (arrays/strings are never tables). */
  table: Record<string, unknown>;
  /** Freshness source: X-Pole-Built-At, else the fetch moment. */
  builtAtMs: number;
}

type FetchImpl = (
  url: string,
  init?: { signal?: AbortSignal },
) => Promise<{
  ok: boolean;
  status?: number;
  headers: { get(name: string): string | null };
  json(): Promise<unknown>;
}>;

/**
 * GET /v1/<name> from the pole. Null on 404/503/transport/junk —
 * the caller decides demo vs honestly-empty (never throws).
 */
export async function fetchPoleTable(
  name: string,
  opts: {
    baseUrl?: string;
    timeoutMs?: number;
    fetchImpl?: FetchImpl;
  } = {},
): Promise<PoleTable | null> {
  const base = opts.baseUrl ?? poleBaseUrl();
  const fetchImpl =
    opts.fetchImpl ?? (fetch as unknown as FetchImpl);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), opts.timeoutMs ?? 5000);
  try {
    const res = await fetchImpl(`${base}/v1/${name}`, {
      signal: ctrl.signal,
    });
    if (!res.ok) return null;
    const body = await res.json();
    if (typeof body !== "object" || body === null || Array.isArray(body)) {
      return null;
    }
    const header = res.headers.get("X-Pole-Built-At");
    const built = header ? Date.parse(header) : NaN;
    return {
      table: body as Record<string, unknown>,
      builtAtMs: Number.isFinite(built) ? built : Date.now(),
    };
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Read one JSON object file from an operator cache dir, ignoring TTL.
 * Null when missing, corrupt, or not an object (never throws). The
 * caller decides fresh vs stale: fresh serves snapshot, stale serves
 * the "stale" provenance (visible age, never as live) or nothing —
 * per-layer honesty contract, never this helper's call.
 */
export async function readOpCacheFile(
  dir: string,
  filename: string,
): Promise<PoleTable | null> {
  const path = join(dir, filename);
  try {
    const st = await stat(path);
    const body: unknown = JSON.parse(await readFile(path, "utf8"));
    if (typeof body !== "object" || body === null || Array.isArray(body)) {
      return null;
    }
    return { table: body as Record<string, unknown>, builtAtMs: st.mtimeMs };
  } catch {
    return null;
  }
}

/**
 * Read one JSON object file from an operator cache dir. Null when the
 * file is missing, stale (mtime older than ttlS), corrupt, or not an
 * object — stale data is a gap, never served (outage #729 rule).
 * nowMs is injectable so tests stay hermetic.
 */
export async function readOpCacheTable(
  dir: string,
  filename: string,
  ttlS: number,
  nowMs: number = Date.now(),
): Promise<PoleTable | null> {
  const cached = await readOpCacheFile(dir, filename);
  if (!cached) return null;
  if (nowMs - cached.builtAtMs > ttlS * 1000) return null;
  return cached;
}
