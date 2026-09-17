import { NextResponse } from "next/server";
import { loadNoiseAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/noise/areas -> { areas: [{ noise_id, leg,
 * band_db, b, r }] }
 *
 * NOISE-HOOK (#625): myrakaart Lden/Lnight band polygons for
 * drawing band fills on the noise layer, so modelled loud vs quiet
 * reads at a glance. Served from the harvest sidecar
 * (noise/noise-areas.json — service: Fees none + AccessConstraints
 * NONE, owner decision 2026-09-17); a missing sidecar is honestly
 * empty (myrakaart unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadNoiseAreas(snapshotDir());
  return NextResponse.json({ areas });
}
