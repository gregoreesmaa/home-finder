import { NextResponse } from "next/server";
import { loadPlanktprAreas, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/planktpr/areas -> { areas: [{ plan_id, use, stage, kov, rings }] }
 *
 * PLANKTPR-HOOK (#492): harvested kehtestatud designated-use polygons
 * for drawing exact per-parcel fills on the planktpr layer, so scored-
 * inside vs honestly-unknown-outside reads at a glance. Served from the
 * harvest sidecar (plank/areas.json); a missing sidecar is honestly
 * empty (the dated NULL — PLANK WFS gone, TPR has no bulk), never an
 * error.
 */
export async function GET(): Promise<NextResponse> {
  const areas = await loadPlanktprAreas(snapshotDir());
  return NextResponse.json({ areas });
}
