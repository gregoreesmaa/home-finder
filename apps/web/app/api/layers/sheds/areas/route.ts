import { NextResponse } from "next/server";
import { isShedLayerId } from "../../../../../lib/layers_p4_tomtom_sheds";
import {
  loadShedSnapshot,
  shedAreasResult,
} from "../../../../../lib/server/sheds";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/sheds/areas?layer=shed-15-peak
 * -> 200 { areas: [{ hub, ring }], builtAtMs } when the weekly
 * operator cache serves; 503 { error, reason } when it is missing or
 * fully stale (issue #787 — honest 503-with-reason, never 200-empty
 * and never demo polygons).
 *
 * TomTom shed hub polygons for the polygons-only shed layers (issues
 * #670 + #763): 15/30-min peak/off-peak reachable-range fills around
 * the 5 job hubs. Served from the keyed harvester's git-ignored
 * operator cache (SHED_CACHE_DIR, 7-day TTL per hub — SHORT-TERM CACHE
 * ONLY verdict, never committed, never live). The weekly pole refill
 * (pole/bin/run-tomtom-sheds.sh) is the only writer; until its first
 * keyed pull this endpoint stays honestly-503.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const layer = new URL(request.url).searchParams.get("layer");
  if (!layer || !isShedLayerId(layer)) {
    return NextResponse.json({ error: "unknown shed layer" }, { status: 404 });
  }
  const snap = await loadShedSnapshot();
  const { status, body } = shedAreasResult(snap, layer);
  return NextResponse.json(body, { status });
}
