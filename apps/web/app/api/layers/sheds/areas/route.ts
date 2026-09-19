import { NextResponse } from "next/server";
import { isShedLayerId } from "../../../../../lib/layers_p4_tomtom_sheds";
import {
  loadShedSnapshot,
  shedAreasForLayer,
} from "../../../../../lib/server/sheds";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/sheds/areas?layer=shed-15-peak
 * -> { areas: [{ hub, ring }], builtAtMs }.
 *
 * TomTom shed hub polygons for the polygons-only shed layers (issues
 * #670 + #763): 15/30-min peak/off-peak reachable-range fills around
 * the 5 job hubs. Served from the keyed harvester's git-ignored
 * operator cache (SHED_CACHE_DIR, 7-day TTL per hub — SHORT-TERM CACHE
 * ONLY verdict, never committed, never live); a missing or fully stale
 * cache is honestly empty ({ areas: [] }), never an error and never
 * demo polygons.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const layer = new URL(request.url).searchParams.get("layer");
  if (!layer || !isShedLayerId(layer)) {
    return NextResponse.json({ error: "unknown shed layer" }, { status: 404 });
  }
  const snap = await loadShedSnapshot();
  if (!snap) {
    return NextResponse.json({ areas: [], builtAtMs: null });
  }
  return NextResponse.json({
    areas: shedAreasForLayer(snap, layer),
    builtAtMs: snap.builtAtMs,
  });
}
