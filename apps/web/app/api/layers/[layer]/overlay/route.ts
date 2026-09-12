import { NextResponse } from "next/server";
import { graphOverlayFor, isDensityLayer } from "../../../../../lib/server/graphSample";
import type { BBoxLike } from "../../../../../lib/layers";

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

function parseCap(url: URL): number {
  const raw = Number(url.searchParams.get("cap"));
  if (!Number.isFinite(raw)) return 800;
  return Math.min(2000, Math.max(1, Math.floor(raw)));
}

/**
 * GET /api/layers/<walkability|pedinfra|cycling>/overlay?minlon&minlat&maxlon&maxlat&cap
 * -> { points: [{ lon, lat, w }], provenance: snapshot|empty }
 *
 * Vector overlay samples for density layers (which have no snapshot
 * points file): walkability junctions, otherwise a strided street-network
 * sample from the foot-graph sidecar. Served exclusively from the local
 * 2026-09-12 snapshot — no upstream requests. Outside coverage (or a
 * missing sidecar) resolves to honestly-empty; the map then shows the
 * raster alone. Other layers 404: parks uses /parks/areas, point layers
 * reuse their /api/layers/<layer> points client-side.
 */
export async function GET(
  request: Request,
  { params }: { params: { layer: string } },
): Promise<NextResponse> {
  if (!isDensityLayer(params.layer)) {
    return NextResponse.json({ error: "no overlay endpoint for this layer" }, { status: 404 });
  }
  const url = new URL(request.url);
  const bbox = parseBBox(url);
  if (!bbox) {
    return NextResponse.json({ error: "bad bbox" }, { status: 400 });
  }
  const points = await graphOverlayFor(params.layer, bbox, parseCap(url));
  return NextResponse.json({
    points,
    provenance: points.length > 0 ? "snapshot" : "empty",
  });
}
