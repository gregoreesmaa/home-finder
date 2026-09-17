import { NextResponse } from "next/server";
import { loadDensityAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/density/areas -> { areas: [{ zone_id, value, cls,
 * b, r }] }
 *
 * DENSITY-HOOK (#622): INSPIRE PD 1 km squares for drawing class fills
 * on the density layer, so tranquil<->urban character reads at a
 * glance. Served from the harvest sidecar
 * (density/density-areas.json, CC0 — attributed); a missing sidecar is
 * honestly empty (PD unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadDensityAreas(snapshotDir());
  return NextResponse.json({ areas });
}
