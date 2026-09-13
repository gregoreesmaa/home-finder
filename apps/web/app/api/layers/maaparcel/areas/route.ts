import { NextResponse } from "next/server";
import { loadMaaParcelAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/maaparcel/areas -> { parcels: [{ tunnus, cls, omvorm,
 * siht1, pindala, aadress, kkis, b, r }] }
 *
 * Maa-amet kataster parcel polygons for the polygons-only maaparcel
 * layer (issue #491, verdict docs/overturn_maa.md + #491 addendum):
 * omandivorm-class choropleth of register facts, never suspicion scores
 * and never a gradient. Served from the local snapshot sidecar
 * `maa/parcel-areas.json` (offline build via
 * scripts/build/batch_maaparcel_kataster.py off the cached WFS GeoJSON);
 * a missing sidecar is honestly empty, never an error — the layer covers
 * a harvested sample window anyway (outside = teadmata, mitte tühi).
 */
export async function GET(): Promise<NextResponse> {
  const parcels = await loadMaaParcelAreas(snapshotDir());
  return NextResponse.json({ parcels });
}
