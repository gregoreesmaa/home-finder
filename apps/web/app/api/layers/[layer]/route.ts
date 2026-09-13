import { NextResponse } from "next/server";
import { LAYERS, tileForView, type BBoxLike, type LayerPoint } from "../../../../lib/layers";
import { isSenscomLayerId } from "../../../../lib/layers_p4_senscom";
// TERVISE-HOOK (#494): committed bathing-water points (see below).
import {
  TERVISE_POINTS,
  TERVISE_VINTAGE,
  isTerviseLayerId,
  tervisePointsIn,
} from "../../../../lib/layers_tervise";
// FLOOD-HOOK (#487): polygons-only branch guard (see below).
import { isFloodLayerId } from "../../../../lib/layers_flood";
// OOKLA-HOOK (#489): ookla tile points come from the Ookla Tallinn
// extract (never the OSM snapshot, never live).
import { isOoklaLayerId } from "../../../../lib/layers_p4_ookla";
// ACCBLACK-HOOK (#490): accblack serves honestly-empty (never 500/demo).
import { isAccBlackLayerId } from "../../../../lib/layers_accblack";
// MAAPARCEL-HOOK (#491): polygons-only branch guard (see below).
import { isMaaParcelLayerId } from "../../../../lib/layers_maaparcel";

// EELIS-HOOK (#488): polygons-only branch guard (see below).
import { isEelisLayerId } from "../../../../lib/layers_eelis";

import {
  intersectsCoverage,
  loadLayerRaster,
  loadSnapshotPoints,
  SNAPSHOT_AS_OF_MS,
  SnapshotUnavailable,
} from "../../../../lib/server/snapshot";
import { loadSenscomSnapshot, senscomPointsIn } from "../../../../lib/server/senscom";
import { loadOoklaSnapshot, ooklaPointsIn } from "../../../../lib/server/ookla";

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
  // TERVISE-HOOK (#494): tervise points come from the committed
  // projected extract (TERVISE_POINTS in lib/layers_tervise.ts, built
  // offline by scripts/build/batch_tervise.py — never the OSM snapshot,
  // never live). Provenance "snapshot" (local static data); the status
  // line names the Terviseamet vintage instead of the OSM snapshot date
  // (see app/layers/page.tsx). An empty view bbox is honestly-empty.
  if (isTerviseLayerId(def.id)) {
    const points = tervisePointsIn(TERVISE_POINTS, bbox);
    // Vintage midnight parses in SERVER-LOCAL time (no Z suffix): the
    // vintage is a local calendar date (harvest 2026-09-14 00:04 EEST),
    // and a UTC-midnight parse goes negative before 03:00 UTC.
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: Date.now() - Date.parse(`${TERVISE_VINTAGE}T00:00:00`),
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
  // EELIS-HOOK (#488): eelis layers are polygons-only (zero points,
  // zero raster — the /eelis/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or a
  // raster here would 500 a healthy layer into labeled demo points (a
  // fake gradient), and demo fallback points are refused by the layer
  // defs (empty fallbackPoints, pinned by test).
  if (isEelisLayerId(def.id)) {

    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // MAAPARCEL-HOOK (#491): maaparcel is polygons-only (zero points,
  // zero raster — the /maaparcel/areas sidecar carries the data). Answer
  // honestly-empty points on snapshot provenance: requiring points or a
  // raster here would 500 a healthy layer into labeled demo points (a
  // fake gradient), and demo fallback points are refused by the layer
  // def (empty fallbackPoints, pinned by test).
  if (isMaaParcelLayerId(def.id)) {
    const { distance } = await loadLayerRaster(def.id);
    return NextResponse.json({
      points: [],
      provenance: "snapshot",
      ageMs: Date.now() - SNAPSHOT_AS_OF_MS,
      distance,
    });
  }
  // OOKLA-HOOK (#489): ookla points come from the Ookla Tallinn
  // extract (never the OSM snapshot, never live). A missing or
  // corrupt extract is a 500 (client shows labeled demo); a valid
  // extract with no tiles in view is honestly-empty. The extract
  // carries no fetch date (quarter label lives in OOKLA_QUARTER), so
  // ageMs stays null.
  if (isOoklaLayerId(def.id)) {
    const snap = await loadOoklaSnapshot();
    if (!snap) {
      return NextResponse.json({ error: "no ookla snapshot data" }, { status: 500 });
    }
    const points = ooklaPointsIn(snap, def.id === "ookla_fixed" ? "fixed" : "mobile", bbox);
    return NextResponse.json({
      points,
      provenance: points.length > 0 ? "snapshot" : "empty",
      ageMs: null,
    });
  }
  // ACCBLACK-HOOK (#490): the measured blackspot set is empty on
  // purpose (L-EST97 verdict 2026-09-13 — zero projected points, see
  // lib/layers_accblack.ts). Serve honestly-empty: the map renders
  // "no data", never a faked zero and never labeled demo. A layer with
  // neither points nor raster would otherwise be a 500 here.
  if (isAccBlackLayerId(def.id)) {
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
