// Ookla Tallinn-extract tile points for the P4-009 ookla overlays
// (issue #489). Serves the cached extract
// (ookla-tallinn-2026Q1.json: {quarter, fixed, mobile, n_fixed,
// n_mobile}, built by the dims_p4_ookla operator step in
// docs/p4_ookla.md) to the /api/layers/ookla_* routes — no network,
// ever. A missing or corrupt extract is never data:
// loadOoklaSnapshot returns null and the route degrades to labeled
// demo (same honesty contract as SnapshotUnavailable in ./snapshot).
// Only rows with a usable centroid arrive here; speed-less or thin
// rows arrive with PARTIAL tags (they never qualify in the tileband
// kernel — the kernel applies MIN_TESTS and the avg_d guard, so the
// served set stays a faithful extract, never a pre-scored selection).

import * as fs from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";
import { OOKLA_TAG_AVG_D, OOKLA_TAG_TESTS } from "../layers_p4_ookla";
import type { BBoxLike, LayerPoint } from "../layers";

/** Extract filename (same name the scorer's operator step writes). */
export const OOKLA_SNAPSHOT_NAME = "ookla-tallinn-2026Q1.json";

/** Default cache dir (same default as dims_p4_ookla.fetch_ookla_parquet). */
export function ooklaCacheDir(): string {
  return path.join(os.tmpdir(), "hf-ookla");
}

/**
 * Extract file path. OOKLA_SNAPSHOT_PATH overrides the default for
 * operators who keep the quarterly pull outside /tmp (docker: mount
 * the cron cache here so the map serves measured tiles, not demo).
 */
export function ooklaSnapshotPath(): string {
  return process.env.OOKLA_SNAPSHOT_PATH ?? path.join(ooklaCacheDir(), OOKLA_SNAPSHOT_NAME);
}

export interface OoklaSnapshot {
  /** Extract quarter label (e.g. "2026-Q1") or null when it carries none. */
  quarter: string | null;
  /** Fixed-layer tile centroids (band payload in tags when measured). */
  fixed: LayerPoint[];
  /** Mobile-layer tile centroids (band payload in tags when measured). */
  mobile: LayerPoint[];
}

function isFiniteCoord(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

function isFiniteNum(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/** One extract row -> served point (null when the centroid is unusable). */
export function ooklaRowToPoint(row: unknown): LayerPoint | null {
  if (typeof row !== "object" || row === null) return null;
  const r = row as Record<string, unknown>;
  const lon = r.tile_x;
  const lat = r.tile_y;
  if (!isFiniteCoord(lat) || !isFiniteCoord(lon)) return null;
  // Same join-key precedent as coerce_tile in dims_p4_ookla.py: a
  // centroid outside the planet would fake bbox coverage.
  if (lon < -180 || lon > 180 || lat < -90 || lat > 90) return null;
  const pt: LayerPoint = { lat, lon };
  const tags: Record<string, string> = {};
  if (isFiniteNum(r.avg_d_kbps)) tags[OOKLA_TAG_AVG_D] = String(r.avg_d_kbps);
  if (isFiniteNum(r.tests)) tags[OOKLA_TAG_TESTS] = String(r.tests);
  if (Object.keys(tags).length > 0) pt.tags = tags;
  return pt;
}

/**
 * Load + validate the cached Tallinn extract, or null when it is
 * absent, unreadable, or not an extract (never throws: missing data
 * is a gap, not an error to present).
 */
export async function loadOoklaSnapshot(
  file: string = ooklaSnapshotPath(),
): Promise<OoklaSnapshot | null> {
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
  const { fixed, mobile, quarter } = parsed as {
    fixed?: unknown;
    mobile?: unknown;
    quarter?: unknown;
  };
  if (!Array.isArray(fixed) || !Array.isArray(mobile)) return null;
  const toPoints = (rows: unknown[]): LayerPoint[] => {
    const out: LayerPoint[] = [];
    for (const row of rows) {
      const pt = ooklaRowToPoint(row);
      if (pt) out.push(pt);
    }
    return out;
  };
  return {
    quarter: typeof quarter === "string" ? quarter : null,
    fixed: toPoints(fixed),
    mobile: toPoints(mobile),
  };
}

/** Extract points for one service clipped to the view bbox. */
export function ooklaPointsIn(
  snap: OoklaSnapshot,
  service: "fixed" | "mobile",
  bbox: BBoxLike,
): LayerPoint[] {
  return snap[service].filter(
    (p) =>
      p.lon >= bbox.minlon && p.lon <= bbox.maxlon && p.lat >= bbox.minlat && p.lat <= bbox.maxlat,
  );
}
