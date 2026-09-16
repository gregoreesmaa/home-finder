import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import {
  fetchEtakViewport,
  isSaneEtakBbox,
} from "../../../../../lib/server/etak";
import { snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/etak/areas?bbox=minlon,minlat,maxlon,maxlat ->
 * { areas: [{ zone_id, theme, cls, score, label, name, vintage, b, r }],
 * note: string | null }
 *
 * ETAK-HOOK (#618): ETAK wetland/water/yard contours for the current
 * viewport, so measured land-cover vs honestly-unknown-outside reads at
 * a glance. Served by the viewport WFS proxy (grid-snapped annual disk
 * cache under <snapshotDir>/etak, else polite lon-lat WFS GetFeature
 * per theme) — never a sidecar: the 114 MB harvest is uncommittable.
 * Honesty mapping: over-wide views get empty areas + a zoom-in note
 * (never truncated into a fake complete picture); WFS outages get
 * empty areas + an outage note (transport errors are never cached as
 * data); malformed bboxes get a 400.
 */
export async function GET(req: Request): Promise<NextResponse> {
  const raw = new URL(req.url).searchParams.get("bbox") ?? "";
  const parts = raw.split(",").map(Number);
  const bbox =
    parts.length === 4 && parts.every(Number.isFinite)
      ? { minlon: parts[0], minlat: parts[1], maxlon: parts[2], maxlat: parts[3] }
      : null;
  if (!bbox || !isSaneEtakBbox(bbox)) {
    return NextResponse.json({ error: "bad bbox (want minlon,minlat,maxlon,maxlat)" }, { status: 400 });
  }
  const dir = path.join(snapshotDir(), "etak");
  const res = await fetchEtakViewport(bbox, {
    fetchImpl: fetch,
    readCache: async (key) => {
      try {
        return await fs.readFile(path.join(dir, key), "utf8");
      } catch {
        return null;
      }
    },
    writeCache: async (key, body) => {
      await fs.mkdir(path.join(dir, path.dirname(key)), { recursive: true });
      await fs.writeFile(path.join(dir, key), body, "utf8");
    },
  });
  if (res.ok) return NextResponse.json({ areas: res.areas, note: null });
  if (res.reason === "too-wide") {
    return NextResponse.json({
      areas: [],
      note: "Liiga lai vaade — suumi sisse, et ETAK kontuurid laadida (üle 5000 kujundi vaatesid ei joonistata)",
    });
  }
  return NextResponse.json({
    areas: [],
    note: "ETAK teenus ei vasta — kontuurid teadmata (väljaspool = teadmata, mitte kuiv maa)",
  });
}
