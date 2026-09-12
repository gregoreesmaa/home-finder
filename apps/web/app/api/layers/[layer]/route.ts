import { NextResponse } from "next/server";
import { LAYERS, tileForView, type BBoxLike, type LayerPoint } from "../../../../lib/layers";
import {
  intersectsCoverage,
  loadLayerRaster,
  loadSnapshotPoints,
  SNAPSHOT_AS_OF_MS,
  SnapshotUnavailable,
} from "../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

function parseBBox(url: URL): BBoxLike | null {
  const nums = ["minlon", "minlat", "maxlon", "maxlat"].map((k) =>
    Number(url.searchParams.get(k)),
  );
  if (!nums.every(Number.isFinite)) return null;
  const [minlon, minlat, maxlon, maxlat] = nums;
  if (minlon >= maxlon || minlat >= maxlat) return null;
  return { minlon, minlat, maxlon, maxlat };
}

/**
 * GET /api/layers/<parks|transit|schools>?minlon&minlat&maxlon&maxlat
 * -> { points, provenance: snapshot|empty, ageMs }
 *
 * Served exclusively from the local 2026-09-12 snapshot — no upstream
 * requests, so map pans can never throttle a source service. Tiles outside
 * snapshot coverage resolve to honestly-empty (the map renders those as
 * "no data", never as zero). A broken snapshot is a 500, which the client
 * maps to labeled demo points. The generic fileCache/overpass modules stay
 * for future parameters beyond snapshot coverage; this route does not use
 * them.
 */
export async function GET(
  request: Request,
  { params }: { params: { layer: string } },
): Promise<NextResponse> {
  const def = LAYERS.find((l) => l.id === params.layer);
  if (!def) {
    return NextResponse.json({ error: "unknown layer" }, { status: 404 });
  }
  const bbox = parseBBox(new URL(request.url));
  if (!bbox) {
    return NextResponse.json({ error: "bad bbox" }, { status: 400 });
  }
  const tile = tileForView(bbox);
  if (!intersectsCoverage(tile)) {
    return NextResponse.json({ points: [], provenance: "empty", ageMs: null });
  }
  try {
    // Density layers (walkability/pedinfra/cycling) have no points file:
    // their raster is the data. A layer with neither points nor raster is
    // a 500 (client shows labeled demo), exactly as before.
    let points: LayerPoint[] = [];
    try {
      points = await loadSnapshotPoints(def.id, tile);
    } catch (err) {
      if (!(err instanceof SnapshotUnavailable)) throw err;
    }
    // Per-view score windows ride the dedicated /window endpoint; this
    // payload stays small (points are the Euclidean fallback only).
    // Distance still reports whether a walk raster exists for the layer.
    const { raster, distance } = await loadLayerRaster(def.id);
    if (points.length === 0 && !raster) {
      return NextResponse.json({ error: `no ${def.id} snapshot data` }, { status: 500 });
    }
    return NextResponse.json({
      points,
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  } catch (err) {
    if (err instanceof SnapshotUnavailable) {
      return NextResponse.json({ error: err.message }, { status: 500 });
    }
    throw err;
  }
}
