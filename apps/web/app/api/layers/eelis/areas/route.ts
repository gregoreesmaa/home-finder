import { NextResponse } from "next/server";
import { loadEelisAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/eelis/areas -> { areas: [{ kiht, zone_id, nimi, lisa, b, r }] }
 *
 * EELIS nature polygons for the polygons-only eelis layers (issue
 * #488, verdict docs/p4_eelis.md): inside-a-named-polygon vs
 * outside/unknown choropleths, never a gradient. Served from the local
 * snapshot sidecar `eelis/eelis-areas.json` (offline build via
 * scripts/build/batch_eelis_poly.py); a missing sidecar is honestly
 * empty, never an error — the per-parcel join lives in the scorer
 * (services/scoring/dims_p4_eelis.py) and stays NULL.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadEelisAreas(snapshotDir());
  return NextResponse.json({ areas });
}
