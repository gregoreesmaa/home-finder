import { promises as fs } from "node:fs";
import { NextResponse } from "next/server";
import { snapshotDir } from "../../../../../lib/server/snapshot";
import { fetchSoilViewport } from "../../../../../lib/server/soil";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/soil/areas?bbox=minlon,minlat,maxlon,maxlat ->
 * { areas: [{ zone_id, family, cls, score, code, b, r }],
 *   cached, undecoded, urbanDropped }
 * or { error, note } with 400 (bad bbox) / 404-as-empty (too-wide
 * viewports answer honestly-empty + a zoom-in note, never a sample).
 *
 * SOIL-HOOK (#617): Maa-amet mullastiku contours for drawing family
 * fills on the soil layer, so mapped-inside vs honestly-unknown-outside
 * reads at a glance. Viewport-driven (the full Harjumaa harvest is
 * ~600 MB — no sidecar, no page-load fetch): grid-snapped annual disk
 * cache beside the snapshot dir, one polite WFS pull per cell per year.
 * Rings verbatim; urban/water/undecoded contours dropped + counted.
 */
export async function GET(req: Request): Promise<NextResponse> {
  const raw = new URL(req.url).searchParams.get("bbox") ?? "";
  const parts = raw.split(",").map((v) => Number(v));
  const bbox =
    parts.length === 4
      ? { minlon: parts[0], minlat: parts[1], maxlon: parts[2], maxlat: parts[3] }
      : { minlon: NaN, minlat: NaN, maxlon: NaN, maxlat: NaN };
  const cacheRoot = `${snapshotDir()}-soil-cache`;
  const res = await fetchSoilViewport(bbox, {
    fetchImpl: fetch,
    readCache: async (key: string) => {
      try {
        return await fs.readFile(`${cacheRoot}/${key}`, "utf8");
      } catch {
        return null;
      }
    },
    writeCache: async (key: string, body: string) => {
      await fs.mkdir(`${cacheRoot}/soil`, { recursive: true });
      await fs.writeFile(`${cacheRoot}/${key}`, body, "utf8");
    },
  });
  if (!res.ok && res.reason === "bad-bbox") {
    return NextResponse.json(
      { error: "bad bbox (want ?bbox=minlon,minlat,maxlon,maxlat)" },
      { status: 400 },
    );
  }
  if (!res.ok && res.reason === "too-wide") {
    return NextResponse.json(
      {
        areas: [],
        note: "Liiga lai vaade mullakaardile — suumi sisse (üle 5000 kontuuri korraga EI SERVITA, valimit ei tehta).",
      },
      { status: 200 },
    );
  }
  if (!res.ok) {
    return NextResponse.json({ areas: [], note: "Mullakaardi teenus hetkel kättesaamatu." });
  }
  return NextResponse.json({
    areas: res.areas,
    cached: res.cached,
    undecoded: res.undecoded,
    urbanDropped: res.urbanDropped,
  });
}
