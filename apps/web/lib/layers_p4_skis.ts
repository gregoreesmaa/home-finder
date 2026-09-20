// Groomed ski-track (suusarajad) entry overlay (issue #692,
// seasonal leisure layer; scorer input arrives with the in-season
// table, no separate dims module by design — see below).
// This file owns ALL skis runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/server/snapshot.ts) touch it only through small
// marked `SKIS-HOOK (#692)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// SOURCE VERDICT (2026-09-19, two polite GETs, probe UA
// `home-finder-research/0.1`, `--max-time` 25, raw in /tmp only —
// full evidence in docs/p4_skis.md §6): groomed-track status is
// HUMAN-ONLY. piritaspordikeskus.ee 302s to tallinn.ee/
// et/piritaspordikeskus (human HTML), which says verbatim:
// "2025/26 suusahooaeg on selleks korraks läbi. Kohtume järgmisel
// hooajal!" — off-season confirmed live; the status channel is the
// page + phone 600 8333. No machine feed exists, so this layer ships
// an HONEST-EMPTY point set (DATEX SRTI pattern: empty pins,
// total 0) and every surface says EI OLE + hooajaväline + the
// buyer-side check (tallinn.ee leht + kohapeal).
//
// SEASONALITY (load-bearing): in season the operator reads the human
// page and drops a verified status.json on the pole; the pole build
// (scripts/build/batch_skis.py) plots ONLY groomed,
// coordinate-carrying known tracks. Off-season (like today) the
// table is honestly empty — never faked, never carried over from
// last winter. No dims module: the layer IS the seasonal signal
// (pins mark groomed entries, hinnang); ranking joins the same
// table when the joint winter-weights change lands (per-batch
// rebalancing stays one joint change).
//
// OVERLAY-ONLY (documented): no raster / metro master is built —
// the named files resolve absent so the layer degrades through the
// designed path (API 500 → honestly-labeled demo with ZERO markers,
// never invented ones).

import type { BonusSpec, LayerDef, LayerId, LayerPoint } from "./layers";

export type SkisLayerId = "skis";

export const SKIS_LAYER_IDS: SkisLayerId[] = ["skis"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const SKIS_PARAM_LABEL = "P4-skis";

/**
 * Dated source this layer rests on (see header + docs/p4_skis.md §6).
 * The Python builder (scripts/build/batch_skis.py) and its pytest pin
 * the same verdict, so the two sides cannot silently disagree.
 */
export const SKIS_PROBE = {
  date: "2026-09-19",
  season: "off",
  quote: "2025/26 suusahooaeg on selleks korraks läbi",
  machineFeed: false,
} as const;

/**
 * Hard entry radius in metres — leisure-entry scale (suusarajale
 * sõidetakse; a groomed entry 1 km away is the neighbourhood
 * story, past that it says nothing about the backyard).
 */
export const SKIS_RADIUS_M = 1000;

export const SKIS_LAYERS: LayerDef[] = [
  {
    id: "skis",
    paramIds: [],
    paramLabel: SKIS_PARAM_LABEL,
    title: "Hooldatud suusarajad (hooaeg)",
    goodLabel:
      "roheline = hooldatud suusaraja sissepääs 1 km raadiuses (hooaja-hinnang)",
    badLabel:
      "punane = hooldatud rada 1 km raadiuses puudu VÕI hooaeg läbi (EI OLE masinloetavat rajaoleku-voogu)",
    source:
      "tallinn.ee Pirita Spordikeskus (inimloetav HTML, 2026-09-19: 2025/26 hooaeg läbi; oleku-kanal leht + tel 600 8333) — EI OLE masinloetavat hooldusoleku-voogu; hooajal loeb operaator lehelt ja kinnitab oleku, väljaspool hooaega on kaart ausalt tühi",
    // EMPTY BY HONESTY (load-bearing): off-season confirmed live, so
    // the demo fallback plots ZERO markers. Never carry last
    // winter's tracks over — stale groomed dots would be fake snow.
    fallbackPoints: [],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — track-grooming
 * status is not OSM data; inventing piste:type plumbing would be
 * dishonest, paaste #493 precedent). overpassQueryFor("skis") is
 * never called in production; the string only satisfies the
 * registry shape.
 */
export const SKIS_TAGS: Record<SkisLayerId, string> = {
  skis:
    "tallinn.ee Pirita Spordikeskus (inimloetav hooldusoleku-leht; serveeritakse operaatori kinnitatud hooaja-väljavõttest, mitte Overpassist — väljaspool hooaega tühi)",
};

/** Raster master filename (intentionally never built — see header). */
export const SKIS_RASTER_FILE: Record<SkisLayerId, string> = {
  skis: "skis-walk-raster.json",
};

/** Metro master name (intentionally never built — overlay-only). */
export const SKIS_METRO_NAME: Record<SkisLayerId, string> = {
  skis: "skis-metro",
};

/**
 * NO raster master (documented): overlay-only — the window route is
 * skipped and empty windows serve county everywhere.
 */
export const SKIS_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the metro name
 * resolves absent so windows fall back cleanly.
 */
export const SKIS_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 1 km entry radius: the
 * scale story is the drive-to-the-tracks window, same as the
 * kernel). Dormant today (zero points → goodnessAt null
 * everywhere).
 */
export const SKIS_DECAY: Record<SkisLayerId, number> = {
  skis: 1.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isSkisLayerId(layer: LayerId): layer is SkisLayerId {
  return (SKIS_LAYER_IDS as string[]).includes(layer);
}

/**
 * Honest-empty status line (issue #785). Skis ships ZERO points BY
 * DECISION (off-season confirmed live, SKIS_PROBE) and always renders
 * through the demo fallback — so the generic "live ebaõnnestus"
 * (live failed) label reads as breakage. This names the dated
 * verdict instead: ootel + source + buyer-side check, never a count
 * claim beyond the served points, never a failure. Pure (pinned by
 * test, silly #774 precedent).
 */
export function skisDemoStatus(pointCount: number): string {
  return (
    "Hooaeg läbi, ootel (tallinn.ee Pirita Spordikeskus, 2026-09-19: " +
    `2025/26 hooaeg läbi) · ${pointCount} punkti — olekut näitab ` +
    "tallinn.ee leht, tel 600 8333"
  );
}

/**
 * Goodness spec for the skis layer (issue #807; called from the
 * bonusSpecFor hook). A groomed entry within the 1 km entry radius
 * (SKIS_RADIUS_M) reads 75; past it the tracks say nothing about the
 * backyard (unknown, never zero). Dormant off-season: zero points
 * still score null everywhere (SKIS_PROBE), markers + field honest.
 */
export const SKIS_DBANDS: { radiusM: number; edges: Array<[number, number]> } = {
  radiusM: 1000,
  edges: [[1000, 75]],
};

export function skisBonusSpecFor(layer: SkisLayerId): BonusSpec {
  void layer;
  return { kind: "dbands", radiusM: SKIS_DBANDS.radiusM, edges: SKIS_DBANDS.edges };
}

/**
 * Served-points status line (issue #807): the in-season operator
 * extract names its source (demo/off-season keeps skisDemoStatus).
 */
export function skisSnapshotStatus(pointCount: number): string {
  return `operaatori hooaja-väljavõte (Pirita Spordikeskus, hooaeg) · ${pointCount} punkti`;
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function skisHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/**
 * Groomed entries within the hard entry radius, nearest first
 * (pure). No averaging, no smoothing — a groomed track 2 km away
 * says nothing about the backyard.
 */
export function skisNearby(
  lat: number,
  lon: number,
  points: LayerPoint[],
  radiusM: number = SKIS_RADIUS_M,
): { point: LayerPoint; distM: number }[] {
  const out: { point: LayerPoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = skisHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const SKIS_HOOK =
  "SKIS-HOOK (#692): skis wired into layers/overlays/snapshot; seasonal leisure pins, honest off-season empty (no machine feed, never carried-over tracks).";
