import { NextResponse } from "next/server";
import { loadParkAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/parks/areas -> { areas: [{ b, a, r }] }
 *
 * Park polygon rings for drawing boundaries on the parks layer, so
 * inside (scored green) vs outside (honestly scored surroundings) is
 * visible. Served from the local 2026-09-12 snapshot sidecar; a missing
 * sidecar is honestly empty, never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadParkAreas(snapshotDir());
  return NextResponse.json({ areas });
}
