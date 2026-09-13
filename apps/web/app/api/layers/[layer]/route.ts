import { NextResponse } from "next/server";
import { LAYERS, tileForView, type BBoxLike, type LayerPoint } from "../../../../lib/layers";
import { isSenscomLayerId } from "../../../../lib/layers_p4_senscom";
// FLOOD-HOOK (#487): polygons-only branch guard (see below).
import { isFloodLayerId } from "../../../../lib/layers_flood";
// TERVISE-HOOK (#494): points-empty branch guard (see below).
import { isTerviseLayerId } from "../../../../lib/layers_tervise";
import {
  intersectsCoverage,
  loadLayerRaster,
  loadSnapshotPoints,
  SNAPSHOT_AS_OF_MS,
  SnapshotUnavailable,
} from "../../../../lib/server/snapshot";
import { loadSenscomSnapshot, senscomPointsIn } from "../../../../lib/server/senscom";

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
  // P4-031-HOOK (#484): senscom points come from the sensor.community
  // Tallinn extract (never the OSM snapshot, never live). A missing or
  // corrupt extract is a 500 (client shows labeled demo); a valid
  // extract with no sensors in view is honestly-empty (the map renders
  // those as "no data", never as zero).
  if (isSenscomLayerId(def.id)) {
    const snap = await loadSenscomSnapshot();
    if (!snap) {
      return NextResponse.json({ error: "no senscom snapshot data" }, { status: 500 });
    }
    const points = senscomPointsIn(snap, bbox);
    const age = snap.fetched ? Date.parse(snap.fetched) : NaN;
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Number.isFinite(age) ? Date.now() - age : null,
    });
  }
  // FLOOD-HOOK (#487): floodzone is polygons-only (zero points, zero
  // raster — the /floodzone/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or a
  // raster here would 500 a healthy layer into labeled demo points (a
  // fake gradient), and demo fallback points are refused by the layer
  // def (empty fallbackPoints, pinned by test).
  if (isFloodLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // TERVISE-HOOK (#494): tervise is points-empty by dated negative
  // verdict (no open machine feed for monitoring-point locations —
  // monitoring points are never invented). Answer honestly-empty
  // points on snapshot provenance: falling through to the generic
  // path would 500 a healthy layer into labeled demo points (a fake
  // gradient), and demo fallback points are refused by the layer def
  // (empty fallbackPoints, pinned by test).
  if (isTerviseLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
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
