// Terviseamet monitoring-point overlay (issue #494, Group B verify-first).
//
// One layer ("tervise", P4-017/P4-024 slices): monitoring-point LOCATIONS
// as points — IF they are openly published. Verdict (docs/p4_tervise.md
// #494 re-check, 2026-09-13): they are NOT. The suplusvesi page defines
// "seirepunkt" as glossary prose and links seasonal quality-class PDFs,
// vtiav.sm.ee is a human POST-filter query UI (the "Avaandmed" tab is a
// JS tab, not a bulk export), and andmed.eesti.ee renders no
// server-side Terviseamet/suplusvesi dataset. So this layer serves ZERO
// points and builds ZERO raster — the map renders basemap + honestly-
// unknown, never a gradient. Per-point quality gradients need a dated
// feed or stay NULL (the scorer dims already stay NULL with Estonian
// reasons in services/scoring/dims_p4_tervise.py).
//
// HONESTY (load-bearing): monitoring points are NEVER invented. A
// hand-transcribed triple (Pirita/Stroomi/Kakumäe from a seasonal PDF)
// would be unanchored geometry with no poll path and no TTL — a
// one-off hand-check painted as a layer is fake precision (OTA PR #131
// precedent, same refusal as dims_p4_tervise.py). fallbackPoints is
// EMPTY (demo points would paint a fake gradient splat — the generic
// labels test carves points-empty layers out, see layers.test.ts);
// TERVISE_DECAY and TERVISE_BONUS below are inert placeholders
// required by the Record<LayerId> tables (zero points and a null
// raster mean neither is ever evaluated — pinned by test). The points
// endpoint answers honestly-empty for this layer (see the TERVISE-HOOK
// branch in app/api/layers/[layer]/route.ts), and /layers names the
// missing feed in the status line instead of a point count.
//
// Overlap (documented): P4-017/P4-024 scorer dims
// (dim_water_quality_monitoring, dim_country_health_nuisances) answer
// the per-listing question with NULL + buyer-side checks; this module
// answers the map question only (currently: nothing openly plottable).
// Group 7 parameters3 radon/air verdicts (G07 batches, nomap.md G7)
// belong to EGT/Keskkonnaagentuur sensor grids — different agencies,
// different future issues, never re-scored here.
//
// Overturn: Terviseamet (or andmed.eesti.ee) publishes a machine
// monitoring-point feed (CSV/JSON/WFS) → re-open #494, build the
// polite cached ingestion, and graduate this layer to real points
// (quality per point stays NULL until a DATED feed arrives).
//
// This file owns ALL tervise runtime data; shared files
// (lib/layers.ts, lib/overlays.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `TERVISE-HOOK (#494)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type TerviseLayerId = "tervise";

export const TERVISE_LAYER_IDS: TerviseLayerId[] = ["tervise"];

/** Buyer-param slices this overlay would visualize (NOT parameters3 ids). */
export const TERVISE_PARAM_LABEL = "P4-017+P4-024";

/**
 * Feed verdict, pinned by test so the honest shape stays greppable:
 * checked 2026-09-13 (4 polite single GETs, headers + visible-text
 * scope only), re-check due 2027-03-13 at the latest.
 */
export const TERVISE_FEED_VERDICT = {
  status: "no-open-feed",
  checked: "2026-09-13",
  recheckBy: "2027-03-13",
} as const;

export const TERVISE_DEFS: LayerDef[] = [
  {
    id: "tervise",
    paramIds: [],
    paramLabel: TERVISE_PARAM_LABEL,
    title: "Terviseameti seirepunktid (voog puudub)",
    goodLabel:
      "seirepunkte masinloetavalt pole — lähima seirekoha hinnang puudub (teadmata, mitte puhas)",
    badLabel:
      "kogu kaardil teadmata: joogivee- ja suplusvee-seirel puudub avatud masinvoog (EI OLE)",
    source:
      "Terviseamet (kontroll 2026-09-13, korduskontroll hiljemalt 2027-03-13): suplusvee kvaliteediklassid elavad hooaja-PDF-ides, joogivee/suplusvee üldhinnangud inimloetavas vtiav.sm.ee päringuliideses — avatud masinvoogu (CSV/JSON/API/WFS) pole, punkte ei leiutata; ostja kontroll: vtiav.sm.ee Joogivesi/suplusvesi-otsing + supluskohtade nimekiri",
    // Points-empty: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // points-empty layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): tervise serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the points-empty test.
 */
export const TERVISE_DECAY: Record<TerviseLayerId, number> = {
  tervise: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: a health board's
 * unpublished monitoring vintage has no honest snapshot tags to query,
 * so there is nothing for the live path to fetch (same stance as
 * dims_p4_tervise.py — no Overpass fragment, no tag mapping).
 */
export const TERVISE_TAGS: Record<TerviseLayerId, string> = {
  tervise: "Terviseamet vtiav.sm.ee päringuliides + hooaja-PDF-id (Overpass-uta, masinvoog EI OLE)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented points-empty decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const TERVISE_RASTER_FILE: Record<TerviseLayerId, string> = {
  tervise: "tervise-walk-raster.json",
};

/** NO metro master (documented): points-empty, windows serve county. */
export const TERVISE_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the points-empty test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const TERVISE_BONUS: Record<TerviseLayerId, BonusSpec> = {
  tervise: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isTerviseLayerId(layer: string): layer is TerviseLayerId {
  return (TERVISE_LAYER_IDS as string[]).includes(layer);
}

/**
 * Tervise bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForTervise(layer: string): BonusSpec | undefined {
  return (TERVISE_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const TERVISE_HOOK =
  "TERVISE-HOOK (#494): tervise wired into layers/overlays/snapshot/routes/page; P4-017+P4-024 monitoring points, points-empty by dated negative verdict, outside stays unknown.";
