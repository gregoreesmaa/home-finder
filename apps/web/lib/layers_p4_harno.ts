// Harno school-quality (riigieksamite keskmised) overlay (issue
// #687, P4-harno slice; static annual refresh, trivial size).
// This file owns ALL harno overlay runtime data; shared files
// (lib/layers.ts, lib/distanceField.ts, lib/overlays.ts,
// lib/server/snapshot.ts, app/layers/page.tsx) touch it only through
// small marked `HARNO-HOOK (#687)` blocks, so sibling batches stay
// disjoint. This module imports ./layers ONLY as types: no runtime
// cycle.
//
// SOURCE VERDICT (2026-09-19, polite single GETs, probe UA
// `home-finder-research/0.1`, `--max-time` 25, paced, raw in /tmp
// only — full evidence in docs/p4_harno.md §6): NO bulk
// machine-readable per-school exam export exists — Haridussilm is a
// JS SPA over a PowerBI backend (41 kB shell, no CSV/XLS/API
// surface), EIS records sit behind school accounts, yearly
// per-school averages reach the public as media graphics. So this
// layer ships an HONEST-EMPTY point set (no verified annual
// snapshot) and every surface says EI OLE + the buyer-side check
// (Haridussilma kooli-leht + kohapeal).
//
// HONESTY (load-bearing): per-point quality q is the coarse P4-harno
// band (80 / 70 / 60 / 45 / 30 off the mean of eesti keel +
// matemaatika + võõrkeel; cap 80 — an exam mean is never a whole
// school; mirrors scripts/build/batch_harno.py quality_band —
// changing the builder without changing the bands here, or vice
// versa, is a drift bug). q absent = quality NULL (plotted for
// location, never scored as a middle). The kernel is the NEAREST
// school's band inside a hard 1 km radius (no smoothing); no school
// in radius stays null/255 (renders red, never a faked score).
// Dormant today (zero points → all-NaN, pinned by test) pending the
// first verified annual snapshot + the joint WEIGHTS rebalancing
// (per-batch rebalancing stays one joint change).
//
// PER-SCHOOL LINKAGE (for the first real drop): EHIS registry id is
// the join key; coordinates are verified at snapshot time against
// the held OSM extract (amenity=school name match checked against
// the EHIS street address — never hand-geocoded, paaste #493 rule);
// thin cohorts (n < 10) never plot. Names never leave the builder
// (TAG_ALLOWLIST precedent — the wire carries lat/lon/q only).
//
// The layer carries NO parameters3.md id: P4-harno is a parameters4
// buyer param (senscom #484 precedent). paramIds stays [] and
// paramLabel carries the slice ("P4-harno") for the layer button.

import type { BBoxLike, BonusSpec, LayerDef, LayerId, LayerPoint } from "./layers";

export type HarnoLayerId = "harno";

export const HARNO_LAYER_IDS: HarnoLayerId[] = ["harno"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const HARNO_PARAM_LABEL = "P4-harno";

/**
 * Dated source this layer rests on (see header + docs/p4_harno.md
 * §6). The Python builder (scripts/build/batch_harno.py) and its
 * pytest pin the same verdict, so the two sides cannot silently
 * disagree.
 */
export const HARNO_PROBE = {
  date: "2026-09-19",
  snapshot: false,
  machineExport: false,
} as const;

/** Vintage of the annual snapshot (absent until the first drop). */
export const HARNO_VINTAGE: string | null = null;

/**
 * Hard join radius in metres — neighbourhood-school scale (same
 * walkable story as the tervise beach radius).
 */
export const HARNO_RADIUS_M = 1000;

/** Coarse quality bands (parity with batch_harno.py quality_band). */
export const HARNO_BANDS = [80, 70, 60, 45, 30] as const;

export const HARNO_LAYERS: LayerDef[] = [
  {
    id: "harno",
    paramIds: [],
    paramLabel: HARNO_PARAM_LABEL,
    title: "Koolide eksamikvaliteet (aasta-hinnang)",
    goodLabel:
      "roheline = tugev eksamikool 1 km raadiuses (snapshot-hinnang, lagi 80 — keskmine, mitte kogu kool)",
    badLabel:
      "punane = tugev kool 1 km raadiuses puudu, kool nõrk VÕI kvaliteet teadmata (EI OLE verifitseeritud snapshotti)",
    source:
      "Haridussilm (visuaalne portaal, 2026-09-19: per-kooli masin-eksporti pole; EIS koolikontode taga; aastakeskmised meedias graafikuna) — EI OLE verifitseeritud aastasnapshotti; kvaliteeti näitab Haridussilma kooli-leht, kool selgub kohapeal",
    // EMPTY BY HONESTY (load-bearing): no verified annual snapshot
    // exists, so the demo fallback plots ZERO markers. Never add a
    // hand-placed school here — addresses are not points.
    fallbackPoints: [],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — exam quality
 * is not OSM data; inventing amenity=school plumbing would be
 * dishonest, paaste #493 precedent). overpassQueryFor("harno") is
 * never called in production; the string only satisfies the
 * registry shape.
 */
export const HARNO_TAGS: Record<HarnoLayerId, string> = {
  harno:
    "Harno/EIS aastasnapshot (riigieksamite koolikeskmised; serveeritakse verifitseeritud EHIS-liidesega väljavõttest, mitte Overpassist — snapshotti pole, väljavõte tühi)",
};

/** Raster master filename (intentionally never built — see HARNO_NO_RASTER). */
export const HARNO_RASTER_FILE: Record<HarnoLayerId, string> = {
  harno: "harno-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat quality kernel IS
 * the field (tervise #494 precedent). A 75 m county stamp of sparse
 * school points would be honest discs plus county-wide unknown —
 * the splat already renders exactly that, so a master would add
 * build machinery without meaning. The window route serves 500 for
 * this layer and the client falls back to the splat (designed
 * path).
 */
export const HARNO_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the window route is
 * skipped by the generic qbands short-circuit and empty windows
 * serve county everywhere.
 */
export const HARNO_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 1 km join radius: the scale
 * story is the neighbourhood-school window, same as the kernel).
 */
export const HARNO_DECAY: Record<HarnoLayerId, number> = {
  harno: 1.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isHarnoLayerId(layer: LayerId): layer is HarnoLayerId {
  return (HARNO_LAYER_IDS as string[]).includes(layer);
}

/** Quality-band spec for the harno layer (called from the bonusSpecFor hook). */
export function harnoBonusSpecFor(layer: HarnoLayerId): BonusSpec {
  void layer;
  return { kind: "qbands", radiusM: HARNO_RADIUS_M };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function harnoHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface HarnoPoint {
  lat: number;
  lon: number;
  /** Coarse P4-harno band (absent = quality NULL, never a faked middle). */
  q?: number;
}

/**
 * Nearest school within the hard radius, nearest first (pure). No
 * averaging, no smoothing — mirrors the qbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function harnoNearby(
  lat: number,
  lon: number,
  points: HarnoPoint[],
  radiusM: number = HARNO_RADIUS_M,
): { point: HarnoPoint; distM: number }[] {
  const out: { point: HarnoPoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = harnoHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Quality hinnang at one address: the NEAREST school's band, null
 * where no school covers the address or the nearest school's
 * quality is NULL (unknown, never zero, never a faked score).
 */
export function harnoBandAt(
  lat: number,
  lon: number,
  points: HarnoPoint[],
  radiusM: number = HARNO_RADIUS_M,
): number | null {
  const near = harnoNearby(lat, lon, points, radiusM);
  if (near.length === 0) return null;
  const q = near[0].point.q;
  return typeof q === "number" && Number.isFinite(q) ? q : null;
}

/** Extract points clipped to the view bbox (same inBBox contract as senscom). */
export function harnoPointsIn(points: HarnoPoint[], bbox: BBoxLike): LayerPoint[] {
  return points.filter(
    (p) =>
      p.lon >= bbox.minlon && p.lon <= bbox.maxlon && p.lat >= bbox.minlat && p.lat <= bbox.maxlat,
  );
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const HARNO_HOOK =
  "HARNO-HOOK (#687): harno wired into layers/overlays/snapshot/page; P4-harno quality leg, honest-empty (no annual snapshot, never invented schools).";
