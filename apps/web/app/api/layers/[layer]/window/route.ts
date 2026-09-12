import { NextResponse } from "next/server";
import { LAYERS } from "../../../../../lib/layers";
import { loadWindowRaster } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

function num(v: string | null): number | null {
  if (v === null) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * GET /api/layers/<id>/window?minlon&minlat&maxlon&maxlat&cols&rows
 * -> per-view score window { cols, rows, bbox, step_m, data(base64 u8) }.
 *
 * The grid composites the 8x metro master (9.375 m cells) where it covers
 * and knows, county 75 m cells elsewhere, 255 past both. Sizes clamp to
 * 512^2. Null (500) degrades to the client's points-splat fallback.
 */
export async function GET(
  request: Request,
  { params }: { params: { layer: string } },
): Promise<NextResponse> {
  const def = LAYERS.find((l) => l.id === params.layer);
  if (!def) {
    return NextResponse.json({ error: "unknown layer" }, { status: 404 });
  }
  const url = new URL(request.url);
  const minlon = num(url.searchParams.get("minlon"));
  const minlat = num(url.searchParams.get("minlat"));
  const maxlon = num(url.searchParams.get("maxlon"));
  const maxlat = num(url.searchParams.get("maxlat"));
  const cols = num(url.searchParams.get("cols")) ?? 256;
  const rows = num(url.searchParams.get("rows")) ?? 256;
  if (minlon === null || minlat === null || maxlon === null || maxlat === null) {
    return NextResponse.json({ error: "bad bbox" }, { status: 400 });
  }
  const win = await loadWindowRaster(
    def.id,
    { minlon, minlat, maxlon, maxlat },
    cols,
    rows,
  );
  if (!win) {
    return NextResponse.json({ error: `no ${def.id} raster window` }, { status: 500 });
  }
  return NextResponse.json(win);
}
