import { NextResponse } from "next/server";
import { loadCanopyTint, snapshotDir } from "../../../../../lib/server/snapshot";

export const dynamic = "force-dynamic";

/**
 * GET /api/layers/canopy/areas -> { grid: tint-grid sidecar doc | null }
 *
 * CANOPY-HOOK (#620): CHM class tint grid for drawing the taste-only
 * character tint on the canopy layer, so tree character reads at a
 * glance. Served from the harvest sidecar (canopy/canopy-tint.json,
 * CC BY 4.0 — attributed) VERBATIM: the client decodes + validates
 * (see decodeCanopyGrid — a corrupt grid renders honestly-empty,
 * never a shifted tint). A missing sidecar is honestly null (CHM
 * unharvested), never an error.
 */
export async function GET(): Promise<NextResponse> {
  const grid = await loadCanopyTint(snapshotDir());
  return NextResponse.json({ grid: grid ?? null });
}
