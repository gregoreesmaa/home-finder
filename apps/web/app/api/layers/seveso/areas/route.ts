import { NextResponse } from "next/server";
import { loadSevesoAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/seveso/areas -> { areas: [{ zone_id, nimi, danger,
 * danger_label, aadress, b, r }] }
 *
 * SEVESO-HOOK (#613): Päästeamet danger-area polygons for drawing
 * danger-class fills on the seveso layer, so scored-inside vs
 * honestly-unknown-outside reads at a glance. Served from the harvest
 * sidecar (seveso/seveso-areas.json, CC BY-NC-ND 4.0 — attributed,
 * unmodified); a missing sidecar is honestly empty (register
 * unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadSevesoAreas(snapshotDir());
  return NextResponse.json({ areas });
}
