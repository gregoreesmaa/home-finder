import { NextResponse } from "next/server";
import { loadForestAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/forest/areas -> { areas: [{ change_id, season,
 * first, second, area_ha, cls, b, r }] }
 *
 * FOREST-HOOK (#624): metsamuutused detected-change polygons for
 * drawing class fills on the forest layer, so the 2024 detected-change
 * warning reads at a glance. Served from the harvest sidecar
 * (forest/forest-areas.json, ETAK avaandmete litsents — attributed);
 * a missing sidecar is honestly empty (metsamuutused unharvested),
 * never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadForestAreas(snapshotDir());
  return NextResponse.json({ areas });
}
