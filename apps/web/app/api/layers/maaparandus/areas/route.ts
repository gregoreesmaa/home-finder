import { NextResponse } from "next/server";
import { loadMaaparandusAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/maaparandus/areas -> { areas: [{ zone_id, nimi, cls,
 * ms_kood, ms_url, b, r? | l? }] }
 *
 * DRAINAGE-HOOK (#616): maaparandus network/invalid polygons +
 * outflow centerlines for drawing class fills + ditch lines on the
 * drainage layer, so scored-inside vs honestly-unknown-outside reads
 * at a glance. Served from the harvest sidecar
 * (maaparandus/maaparandus-areas.json, CC BY 4.0 — attributed); a missing
 * sidecar is honestly empty (register unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadMaaparandusAreas(snapshotDir());
  return NextResponse.json({ areas });
}
