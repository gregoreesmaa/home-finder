import { NextResponse } from "next/server";
import { loadFloodAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/floodzone/areas -> { areas: [{ zone_id, nimi, veekogu, tyyp, b, r }] }
 *
 * KAUR flood-zone polygons for the polygons-only floodzone layer (issue
 * #487, verdict docs/overturn_flood.md): inside-a-named-polygon vs
 * outside/unknown choropleth, never a gradient. Served from the local
 * snapshot sidecar `kaur/flood-areas.json` (offline build via
 * scripts/build/batch_flood_kaur.py); a missing sidecar is honestly
 * empty, never an error — the Tallinn market window holds zero register
 * polygons anyway.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadFloodAreas(snapshotDir());
  return NextResponse.json({ areas });
}
