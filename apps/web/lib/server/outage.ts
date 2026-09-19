// Elektrilevi hetkeseis sidecar points for the P4-009 outage overlay
// (issue #729; pole-first read issue #775). Serves the operator-pulled
// sidecar (outage-table.json: {pulled_at, ttl_s, areas, ...}, written
// by scripts/build/batch_outage.py --pull, mirrored on the pole as
// built/outage/table.json) to the /api/layers/outage route. The route
// reads the pole live table first (DATEX #763 precedent, server-side
// only — never browser-direct) and falls back to the local sidecar;
// both shapes validate through outageSnapshotFromBody below. A
// missing, corrupt or STALE (> 5 min) sidecar is never data:
// loaders return null and the route degrades to labeled demo (same
// honesty contract as SnapshotUnavailable in ./snapshot). Only the
// Tallinn row arrives here (city grain — the Harju county row is the
// dims fallback, never averaged in, never a second point).

import * as fs from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import {
  OUTAGE_RELIABILITY_TTL_S,
  OUTAGE_RELIABILITY_WINDOW_DAYS,
  OUTAGE_TAG_FC,
  OUTAGE_TAG_FCC,
  OUTAGE_TAG_PC,
  OUTAGE_TAG_PCC,
  OUTAGE_TAG_UC,
  OUTAGE_TAG_UCC,
  OUTAGE_TALLINN,
  OUTAGE_TTL_S,
  outageBandForRow,
} from "../layers_p4_outage";
import type {
  OutageAreaReliability,
  OutageReliability,
} from "../layers_p4_outage";
import type { BBoxLike, LayerPoint } from "../layers";

/** Sidecar filename (same name the harvester step writes). */
export const OUTAGE_SNAPSHOT_NAME = "outage-table.json";

/** Default cache dir (same default as batch_outage --cache-dir). */
export function outageCacheDir(): string {
  return path.join(os.tmpdir(), "hf-outage");
}

/**
 * Sidecar file path. OUTAGE_SNAPSHOT_PATH overrides the default for
 * operators who keep the 5-min pull outside /tmp (docker: mount the
 * cron cache here so the map serves the hetkeseis, not demo).
 */
export function outageSnapshotPath(): string {
  return process.env.OUTAGE_SNAPSHOT_PATH ?? path.join(outageCacheDir(), OUTAGE_SNAPSHOT_NAME);
}

export interface OutageAreaRow {
  label: string;
  fc?: number | null;
  fcc?: number | null;
  pc?: number | null;
  pcc?: number | null;
  uc?: number | null;
  ucc?: number | null;
}

export interface OutageSnapshot {
  /** ISO pull time (UTC) as stamped by the harvester. */
  pulledAt: string;
  /** Tallinn area row (city grain — the only row served). */
  tallinn: OutageAreaRow;
}

function isFiniteNum(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/** One counters object -> canonical row, null when labelless. */
export function outageRowToArea(row: unknown): OutageAreaRow | null {
  if (typeof row !== "object" || row === null) return null;
  const r = row as Record<string, unknown>;
  if (typeof r.label !== "string" || r.label.trim().length === 0) return null;
  const area: OutageAreaRow = { label: r.label.trim() };
  for (const k of ["fc", "fcc", "pc", "pcc", "uc", "ucc"] as const) {
    area[k] = isFiniteNum(r[k]) ? (r[k] as number) : null;
  }
  return area;
}

/**
 * Validate one parsed hetkeseis body (local sidecar file OR pole live
 * table — same sidecar shape, issue #775), or null when it is
 * Tallinn-less, corrupt, or older than OUTAGE_TTL_S (never throws:
 * stale data is a gap, not an error to present). nowMs is injectable
 * so tests stay hermetic (no clock dependence). Pure: no I/O.
 */
export function outageSnapshotFromBody(
  parsed: unknown,
  nowMs: number = Date.now(),
): OutageSnapshot | null {
  if (typeof parsed !== "object" || parsed === null) return null;
  const { pulled_at, areas } = parsed as { pulled_at?: unknown; areas?: unknown };
  if (typeof pulled_at !== "string" || !Array.isArray(areas)) return null;
  const pulledMs = Date.parse(pulled_at);
  if (!Number.isFinite(pulledMs) || nowMs - pulledMs > OUTAGE_TTL_S * 1000) return null;
  const tallinn = areas.map(outageRowToArea).find((a) => a?.label === "Tallinn") ?? null;
  if (!tallinn) return null;
  return { pulledAt: pulled_at, tallinn };
}

/**
 * Load + validate the cached hetkeseis sidecar, or null when it is
 * absent, unreadable, Tallinn-less, or older than OUTAGE_TTL_S
 * (never throws: stale data is a gap, not an error to present).
 * nowMs is injectable so tests stay hermetic (no clock dependence).
 */
export async function loadOutageSnapshot(
  file: string = outageSnapshotPath(),
  nowMs: number = Date.now(),
): Promise<OutageSnapshot | null> {
  let raw: string;
  try {
    raw = await fs.readFile(file, "utf8");
  } catch {
    return null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  return outageSnapshotFromBody(parsed, nowMs);
}

/** Tallinn row -> served city-grain point (band + counters in tags). */
export function outageSnapshotToPoint(snap: OutageSnapshot): LayerPoint | null {
  const band = outageBandForRow(snap.tallinn);
  if (band === null) return null;
  const tags: Record<string, string> = {};
  const put = (key: string, v: number | null | undefined) => {
    if (typeof v === "number" && Number.isFinite(v)) tags[key] = String(v);
  };
  put(OUTAGE_TAG_FC, snap.tallinn.fc);
  put(OUTAGE_TAG_FCC, snap.tallinn.fcc);
  put(OUTAGE_TAG_PC, snap.tallinn.pc);
  put(OUTAGE_TAG_PCC, snap.tallinn.pcc);
  put(OUTAGE_TAG_UC, snap.tallinn.uc);
  put(OUTAGE_TAG_UCC, snap.tallinn.ucc);
  const pt: LayerPoint = { lat: OUTAGE_TALLINN.lat, lon: OUTAGE_TALLINN.lon, q: band };
  if (Object.keys(tags).length > 0) pt.tags = tags;
  return pt;
}

/** Served point clipped to the view bbox (empty when out of view). */
export function outagePointsIn(snap: OutageSnapshot, bbox: BBoxLike): LayerPoint[] {
  const pt = outageSnapshotToPoint(snap);
  if (!pt) return [];
  if (pt.lon < bbox.minlon || pt.lon > bbox.maxlon || pt.lat < bbox.minlat || pt.lat > bbox.maxlat)
    return [];
  return [pt];
}

function isFiniteNumRecord(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** One per-label aggregate -> canonical counters, null when unshaped. */
export function outageReliabilityAreaToTallinn(row: unknown): OutageAreaReliability | null {
  if (typeof row !== "object" || row === null) return null;
  const r = row as Record<string, unknown>;
  const nObs = isFiniteNumRecord(r.n_obs);
  const faultObs = isFiniteNumRecord(r.fault_obs);
  const plannedObs = isFiniteNumRecord(r.planned_obs);
  const upcomingObs = isFiniteNumRecord(r.upcoming_obs);
  const faultCustomers = isFiniteNumRecord(r.fault_customers);
  const plannedCustomers = isFiniteNumRecord(r.planned_customers);
  const coverage = isFiniteNumRecord(r.coverage);
  if (
    nObs === null || faultObs === null || plannedObs === null ||
    upcomingObs === null || faultCustomers === null ||
    plannedCustomers === null || coverage === null
  )
    return null;
  return {
    nObs, faultObs, plannedObs, upcomingObs,
    faultCustomers, plannedCustomers, coverage,
  };
}

/**
 * Validate one parsed reliability body (pole live table
 * `outage-reliability`, issue #780), or null when it is corrupt,
 * Tallinn-less, built for a different window, or older than
 * OUTAGE_RELIABILITY_TTL_S (never throws: a stale build is a gap,
 * not an error to present — the hetkeseis point serves without it).
 * nowMs is injectable so tests stay hermetic. Pure: no I/O.
 */
export function outageReliabilityFromBody(
  parsed: unknown,
  nowMs: number = Date.now(),
): OutageReliability | null {
  if (typeof parsed !== "object" || parsed === null) return null;
  const { built_at, window_days, areas, n_obs_total } = parsed as {
    built_at?: unknown; window_days?: unknown; areas?: unknown; n_obs_total?: unknown;
  };
  if (typeof built_at !== "string") return null;
  const builtMs = Date.parse(built_at);
  if (!Number.isFinite(builtMs) || nowMs - builtMs > OUTAGE_RELIABILITY_TTL_S * 1000)
    return null;
  if (window_days !== OUTAGE_RELIABILITY_WINDOW_DAYS) return null;
  if (typeof areas !== "object" || areas === null) return null;
  const tallinn = outageReliabilityAreaToTallinn(
    (areas as Record<string, unknown>).Tallinn,
  );
  if (!tallinn) return null;
  return {
    builtAt: built_at,
    windowDays: OUTAGE_RELIABILITY_WINDOW_DAYS,
    tallinn,
    nObsTotal: typeof n_obs_total === "number" && Number.isFinite(n_obs_total)
      ? n_obs_total
      : tallinn.nObs,
  };
}
