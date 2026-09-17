import { NextResponse } from "next/server";
import { loadKpoAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/kpo/areas -> { areas: [{ family, nimi,
 * voond, reegel, b, r }] }
 *
 * KPO-HOOK (#626): KMA restriction-zone polygons for
 * drawing ban/conditioned fills on the kpo layer, so build limits
 * read at a glance. Served from the harvest sidecar
 * (kpo/kpo-areas.json, CC-BY 4.0 — attributed, parcel windows, never
 * the whole county); a missing sidecar is honestly
 * empty (KMA unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadKpoAreas(snapshotDir());
  return NextResponse.json({ areas });
}
