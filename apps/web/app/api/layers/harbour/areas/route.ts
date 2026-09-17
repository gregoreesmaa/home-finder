import { NextResponse } from "next/server";
import { loadHarbourAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/harbour/areas -> { ports, cells }
 *
 * HARBOUR-HOOK (#627): joined sadamaregister ports (points) + AIS
 * pleasure cells (fills) for the harbour layer. Served from the
 * harvest sidecar (harbour/harbour-areas.json — register: no licence
 * stated, owner decision 2026-09-17; AIS: CC BY-SA 3.0); a missing
 * sidecar is honestly empty (harbour unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadHarbourAreas(snapshotDir());
  return NextResponse.json(areas);
}
