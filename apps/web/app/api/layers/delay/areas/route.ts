import { NextResponse } from "next/server";
import { loadDelayAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/delay/areas -> { areas: [{ corridor, factors,
 * ns, rep, b, r }] }
 *
 * DELAY-HOOK (#629): typical-delay corridor bands for painting
 * factor fills on the five delay layers, so the Tuesday pattern
 * reads at a glance. Served from the harvest sidecar
 * (delay/delay-corridors.json, Tallinna Linnavalitsus GPS + TLT GTFS
 * vintage — attributed); a missing sidecar is honestly empty
 * (sampler unrun), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadDelayAreas(snapshotDir());
  return NextResponse.json({ areas });
}
