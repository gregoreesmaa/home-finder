import { NextResponse } from "next/server";
import { loadMaaParcelCoverage, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/maaparcel/areas -> { parcels, bbox, harvest_date, count }
 *
 * Maa-amet kataster parcel polygons for the polygons-only maaparcel
 * layer (issue #491, verdict docs/overturn_maa.md + #491 addendum):
 * omandivorm-class choropleth of register facts, never suspicion scores
 * and never a gradient. Served from the local snapshot sidecar
 * `maa/parcel-areas.json` (offline build via
 * scripts/build/batch_maaparcel_kataster.py off the cached WFS GeoJSON);
 * a missing sidecar is honestly empty, never an error — the layer covers
 * a harvested sample window anyway (outside = teadmata, mitte tühi).
 *
 * Issue #789: `bbox` + `harvest_date` ride along so the map can DRAW
 * the sample-window boundary (proovivalimi piir) — outside-window
 * unknown stays unmistakable even where no parcel paints.
 */
export async function GET(): Promise<NextResponse> {
  const coverage = await loadMaaParcelCoverage(snapshotDir());
  return NextResponse.json({
    parcels: coverage.parcels,
    bbox: coverage.bbox,
    harvest_date: coverage.harvest_date,
    count: coverage.parcels.length,
  });
}
