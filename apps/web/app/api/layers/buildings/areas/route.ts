import { NextResponse } from "next/server";
import { loadBuildingsTint, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/buildings/areas -> { grid: tint-grid sidecar doc | null }
 *
 * BUILDINGS-HOOK (#621): LoD1 height tint grid for drawing the
 * taste-only character tint on the buildings layer, so built character
 * reads at a glance. Served from the harvest sidecar
 * (buildings/buildings-tint.json, CC BY 4.0 — attributed) VERBATIM:
 * the client decodes + validates (see decodeBuildingsGrid — a corrupt
 * grid renders honestly-empty, never a shifted tint). A missing
 * sidecar is honestly null (LoD1 unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const grid = await loadBuildingsTint(snapshotDir());
  return NextResponse.json({ grid: grid ?? null });
}
