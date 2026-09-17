import { NextResponse } from "next/server";
import { loadReliefTint, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/relief/areas -> { grid: tint-grid sidecar doc | null }
 *
 * RELIEF-HOOK (#619): DTM hypsometric tint grid for drawing the
 * taste-only character tint on the relief layer, so ground character
 * reads at a glance. Served from the harvest sidecar
 * (relief/relief-tint.json, CC BY 4.0 — attributed) VERBATIM: the
 * client decodes + validates (see decodeReliefGrid — a corrupt grid
 * renders honestly-empty, never a shifted tint). A missing sidecar is
 * honestly null (DTM unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const grid = await loadReliefTint(snapshotDir());
  return NextResponse.json({ grid: grid ?? null });
}
