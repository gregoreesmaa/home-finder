import { NextResponse } from "next/server";
import { isShedLayerId } from "../../../../../lib/layers_p4_tomtom_sheds";
import {
  SHED_POLE_DATASET,
  loadShedSnapshot,
  shedAreasResult,
  shedSnapshotFromPoleTable,
} from "../../../../../lib/server/sheds";
import { fetchPoleTable } from "../../../../../lib/server/livecache";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/sheds/areas?layer=shed-15-peak
 * -> 200 { areas: [{ hub, ring }], builtAtMs, source } when the weekly
 * operator cache serves; 503 { error, reason } when it is missing or
 * fully stale (issue #787 — honest 503-with-reason, never 200-empty
 * and never demo polygons).
 *
 * TomTom shed hub polygons for the polygons-only shed layers (issues
 * #670 + #763): 15/30-min peak/off-peak reachable-range fills around
 * the 5 job hubs. Pole-first read (issue #782, outage #775 shape):
 * the pole live table (built/tomtom-sheds/table.json, 7-day TTL
 * enforced on the pole mtime here at serve time) wins; the local
 * keyed harvester cache (SHED_CACHE_DIR) is the fallback. The weekly
 * pole refill (pole/bin/run-tomtom-sheds.sh) is the only writer;
 * until its first keyed pull this endpoint stays honestly-503.
 */
export async function GET(request: Request): Promise<NextResponse> {
  const layer = new URL(request.url).searchParams.get("layer");
  if (!layer || !isShedLayerId(layer)) {
    return NextResponse.json({ error: "unknown shed layer" }, { status: 404 });
  }
  const pole = await fetchPoleTable(SHED_POLE_DATASET);
  const poleSnap = pole
    ? shedSnapshotFromPoleTable(pole.table, pole.builtAtMs, Date.now())
    : null;
  const snap = poleSnap ?? (await loadShedSnapshot());
  const { status, body } = shedAreasResult(
    snap,
    layer,
    poleSnap ? "pole" : "cache",
  );
  return NextResponse.json(body, { status });
}
