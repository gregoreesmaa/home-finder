import { NextResponse } from "next/server";
import { loadQuarryAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/quarry/areas -> { areas: [{ zone_id, nimi, cls, loa,
 * loa_lopp, operaator, b, r }] }
 *
 * QUARRY-HOOK (#614): Maa-amet extraction-permit + exploration-area
 * polygons for drawing class fills on the quarry layer, so
 * scored-inside vs honestly-unknown-outside reads at a glance. Served
 * from the harvest sidecar (quarry/quarry-areas.json, CC BY 4.0 —
 * attributed); a missing sidecar is honestly empty (register
 * unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadQuarryAreas(snapshotDir());
  return NextResponse.json({ areas });
}
