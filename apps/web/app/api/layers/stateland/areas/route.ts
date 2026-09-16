import { NextResponse } from "next/server";
import { loadStatelandAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/stateland/areas -> { areas: [{ zone_id, nimi, cls,
 * tunnus, valitseja, deadline, purpose, url, b, r }] }
 *
 * STATELAND-HOOK (#615): KATRI state parcels + active auction parcels
 * for drawing class fills on the stateland layer, so scored-inside vs
 * honestly-unknown-outside reads at a glance. Served from the harvest
 * sidecar (stateland/stateland-areas.json, CC BY 4.0 — attributed); a
 * missing sidecar is honestly empty (register unharvested), never an
 * error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadStatelandAreas(snapshotDir());
  return NextResponse.json({ areas });
}
