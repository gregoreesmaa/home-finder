// Sensor.community Tallinn-extract points for the P4-031 senscom overlay
// (issue #484). Serves the cached extract
// (sensor-community-tallinn.json: {fetched, bbox, sensors, n_sensors},
// built by the dims_p4_senscom operator step in docs/p4_senscom.md) to
// the /api/layers/senscom route — no network, ever. A missing or
// corrupt extract is never data: loadSenscomSnapshot returns null and
// the route degrades to labeled demo (same honesty contract as
// SnapshotUnavailable in ./snapshot). Only explicit OUTDOOR extract
// rows arrive here (indoor filtering is the parser's fail-closed job
// in dims_p4_senscom.parse_senscom_dump); rows with unusable coords are
// skipped, never scored as absence.

import * as fs from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import type { BBoxLike, LayerPoint } from "../layers";

/** Extract filename (same name the scorer's operator step writes). */
export const SENSCOM_SNAPSHOT_NAME = "sensor-community-tallinn.json";

/** Default cache dir (same default as dims_p4_senscom.fetch_senscom_dump). */
export function senscomCacheDir(): string {
  return path.join(os.tmpdir(), "hf-senscom");
}

/**
 * Extract file path. SENSCOM_SNAPSHOT_PATH overrides the default for
 * operators who keep the daily pull outside /tmp (docker: mount the
 * cron cache here so the map serves watched air, not demo).
 */
export function senscomSnapshotPath(): string {
  return process.env.SENSCOM_SNAPSHOT_PATH ?? path.join(senscomCacheDir(), SENSCOM_SNAPSHOT_NAME);
}

export interface SenscomSnapshot {
  /** Extract date (YYYY-MM-DD) or null when the extract carries none. */
  fetched: string | null;
  /** Outdoor DIY locations (deduped by location id upstream). */
  points: LayerPoint[];
}

function isFiniteCoord(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/**
 * Load + validate the cached Tallinn extract, or null when it is
 * absent, unreadable, or not an extract (never throws: missing data is
 * a gap, not an error to present).
 */
export async function loadSenscomSnapshot(
  file: string = senscomSnapshotPath(),
): Promise<SenscomSnapshot | null> {
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
  if (typeof parsed !== "object" || parsed === null) return null;
  const sensors = (parsed as { sensors?: unknown }).sensors;
  if (!Array.isArray(sensors)) return null;
  const points: LayerPoint[] = [];
  for (const s of sensors) {
    if (typeof s !== "object" || s === null) continue;
    const { lat, lon } = s as { lat?: unknown; lon?: unknown };
    if (!isFiniteCoord(lat) || !isFiniteCoord(lon)) continue;
    points.push({ lat, lon });
  }
  const fetched = (parsed as { fetched?: unknown }).fetched;
  return { fetched: typeof fetched === "string" ? fetched : null, points };
}

/** Extract points clipped to the view bbox (same inBBox contract as ./snapshot). */
export function senscomPointsIn(snap: SenscomSnapshot, bbox: BBoxLike): LayerPoint[] {
  return snap.points.filter(
    (p) =>
      p.lon >= bbox.minlon && p.lon <= bbox.maxlon && p.lat >= bbox.minlat && p.lat <= bbox.maxlat,
  );
}
