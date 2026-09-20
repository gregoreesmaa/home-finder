// Micromobility bike-share (GBFS) point overlay (issue #688,
// verify-first; scorer half in services/scoring/dims_gbfs.py).
// This file owns ALL gbfs runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/server/snapshot.ts) touch it only through small
// marked `GBFS-HOOK (#688)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// FEED VERDICT (2026-09-19, polite single GETs, probe UA
// `home-finder-research/0.1`, `--max-time` 20-25, paced, 429 as stop;
// full evidence in docs/p4_gbfs.md §6): NO keyless GBFS feed exists
// for Tallinn or Tartu —
//   * the official MobilityData GBFS registry (systems.csv) lists
//     ZERO Estonian systems;
//   * "Smart Bike" is a Tartu-only brand (Bewegen/WeGoShare tenant
//     `europe/tartu`): its 2.6 MB app bundle holds ZERO `gbfs`
//     references and its public map endpoint
//     (`/api/map/stations/`) answers anonymous GETs with app-level
//     `{"message":"Wrong request!"}` (HTTP 500) — session-keyed,
//     not pollable;
//   * Dott's public keyless pattern answers `ERR_REGION_NOT_FOUND`
//     for both `tallinn` and `tartu`;
//   * no municipal "Tallinn Smart Bike" system exists at all.
// Station coordinates are not published as a machine feed, so this
// layer ships an HONEST-EMPTY point set (no committed sidecar; the
// harvester in scripts/build/batch_gbfs.py refuses --pull until a
// feed verifies) and every surface says EI OLE + the buyer-side
// check (ratas.tartu.ee kaart / operaatori äpp + kohapeal).
//
// HONESTY (load-bearing): the bands below are PROVISIONAL
// (unobservable today: zero points → all-NaN, pinned by test)
// pending a verified keyless feed + the joint WEIGHTS rebalancing
// (per-batch rebalancing stays one joint change). One rented bike
// nearby is amenity proximity, never mobility truth (cap 80, never
// 100); nothing in radius reads NaN/unknown (never zero).
//
// OVERLAY-ONLY (documented): no walk raster / metro master is built —
// the named files resolve absent so the layer degrades through the
// designed path (API 500 → honestly-labeled demo with ZERO markers,
// never invented ones). `bands` kind skips the /window fetch by the
// generic senscom short-circuit (no console litter).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type GbfsLayerId = "gbfs";

export const GBFS_LAYER_IDS: GbfsLayerId[] = ["gbfs"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const GBFS_PARAM_LABEL = "P4-GBFS";

/**
 * Dated probe this layer rests on (see header + docs/p4_gbfs.md §6).
 * The Python harvester (scripts/build/batch_gbfs.py, empty FEEDS)
 * and its pytest pin the same verdict, so the two sides cannot
 * silently disagree.
 */
export const GBFS_PROBE = {
  date: "2026-09-19",
  registryEstonianSystems: 0,
  tartuBundleGbfsRefs: 0,
  tartuMapApi: "Wrong request!",
  dottTallinn: "ERR_REGION_NOT_FOUND",
  dottTartu: "ERR_REGION_NOT_FOUND",
} as const;

/**
 * Station-count radius in metres — doorstep amenity scale (a rented
 * bike 500 m away is walkable; past that it says nothing about the
 * backyard). PROVISIONAL with the bands (see header).
 */
export const GBFS_FAR_M = 500;

/**
 * Amenity bands by station count in radius: 60 / 70 / 80, capped
 * far below 100 (proximity is not mobility truth). PROVISIONAL
 * until a feed exists (see header); dormant today (zero points →
 * all-NaN).
 */
export const GBFS_BANDS = { one: 60, twoThree: 70, fourPlus: 80 } as const;

export const GBFS_LAYERS: LayerDef[] = [
  {
    id: "gbfs",
    paramIds: [],
    paramLabel: GBFS_PARAM_LABEL,
    title: "Rattaringluse jaamad (hinnang)",
    goodLabel:
      "roheline = rattaringluse jaam 500 m raadiuses (lähedus-hinnang, mitte sõidukindlus)",
    badLabel:
      "punane = jaam 500 m raadiuses puudu või jaama-asukohad teadmata (EI OLE keyless masinvoogu)",
    source:
      "GBFS-register (2026-09-19: Eestit pole) + Tartu Smart Bike äpp (sessioonivõtmega WeGoShare, GBFS-pinda pole) + Dott public-GBFS (Tallinn/Tartu ERR_REGION_NOT_FOUND) — EI OLE keyless jaama-asukoha-voogu; seisu näitab ratas.tartu.ee kaart ja operaatori äpp, lähim jaam selgub kohapeal",
    // EMPTY BY HONESTY (load-bearing): no verified keyless station
    // coordinates exist, so the demo fallback plots ZERO markers.
    // Never add hand-placed stations here.
    fallbackPoints: [],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — GBFS data is
 * not OSM data; inventing amenity=bicycle_rental plumbing would be
 * dishonest, paaste #493 precedent). overpassQueryFor("gbfs") is
 * never called in production; the string only satisfies the
 * registry shape.
 */
export const GBFS_TAGS: Record<GbfsLayerId, string> = {
  gbfs:
    "GBFS auto-discovery (station_information + station_status; serveeritakse verifitseeritud keyless-voost väljavõtte kaudu, mitte Overpassist — voogu pole, väljavõte tühi)",
};

/** Raster master filename (intentionally never built — see header). */
export const GBFS_RASTER_FILE: Record<GbfsLayerId, string> = {
  gbfs: "gbfs-walk-raster.json",
};

/** Metro master name (intentionally never built — overlay-only). */
export const GBFS_METRO_NAME: Record<GbfsLayerId, string> = {
  gbfs: "gbfs-metro",
};

/**
 * NO raster master (documented): overlay-only, like the paaste bands
 * layer — the window route is skipped by the generic bands
 * short-circuit and empty windows serve county everywhere.
 */
export const GBFS_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the metro name
 * resolves absent so windows fall back cleanly.
 */
export const GBFS_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 500 m amenity radius: the
 * scale story is the walkable-to-the-dock window, same as the
 * kernel). Dormant today (zero points → goodnessAt null
 * everywhere).
 */
export const GBFS_DECAY: Record<GbfsLayerId, number> = {
  gbfs: 0.5,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGbfsLayerId(layer: LayerId): layer is GbfsLayerId {
  return (GBFS_LAYER_IDS as string[]).includes(layer);
}

/**
 * Honest-empty status line (issue #785). Gbfs ships ZERO points BY
 * DECISION (no keyless feed verified, GBFS_PROBE) and always renders
 * through the demo fallback — so the generic "live ebaõnnestus"
 * (live failed) label reads as breakage. This names the dated
 * verdict instead: EI OLE + source + buyer-side check, never a count
 * claim beyond the served points, never a failure. Pure (pinned by
 * test, silly #774 precedent).
 */
export function gbfsDemoStatus(pointCount: number): string {
  return (
    "EI OLE keyless jaama-voogu (GBFS-register, 2026-09-19: Eestit " +
    `pole) · ${pointCount} punkti — seisu näitab ratas.tartu.ee kaart ` +
    "ja operaatori äpp"
  );
}

/** Band spec for the gbfs layer (called from the bonusSpecFor hook). */
export function gbfsBonusSpecFor(layer: GbfsLayerId): BonusSpec {
  void layer;
  return {
    kind: "bands",
    radiusM: GBFS_FAR_M,
    one: GBFS_BANDS.one,
    twoThree: GBFS_BANDS.twoThree,
    fourPlus: GBFS_BANDS.fourPlus,
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function gbfsHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface GbfsPoint {
  lat: number;
  lon: number;
}

/**
 * Band for a station count — 60 / 70 / 80 by amenity proximity.
 * Null when no station covers the address: unknown, never zero.
 */
export function gbfsBandForCount(n: number): number | null {
  if (!Number.isFinite(n) || n <= 0) return null;
  if (n >= 4) return GBFS_BANDS.fourPlus;
  if (n >= 2) return GBFS_BANDS.twoThree;
  return GBFS_BANDS.one;
}

/**
 * Stations within the hard amenity radius, nearest first (pure). No
 * averaging, no smoothing — mirrors the scorer's future straight-
 * line station leg (same hard cutoff, same order).
 */
export function gbfsNearby(
  lat: number,
  lon: number,
  points: GbfsPoint[],
  radiusM: number = GBFS_FAR_M,
): { point: GbfsPoint; distM: number }[] {
  const out: { point: GbfsPoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = gbfsHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Amenity hinnang at one address, null where no station covers it
 * (the scorer reads the same gap as NULL with hinnang + EI OLE +
 * buyer-side check — never a faked score).
 */
export function gbfsCoveredAt(
  lat: number,
  lon: number,
  points: GbfsPoint[],
  radiusM: number = GBFS_FAR_M,
): number | null {
  return gbfsBandForCount(gbfsNearby(lat, lon, points, radiusM).length);
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GBFS_HOOK =
  "GBFS-HOOK (#688): gbfs wired into layers/overlays/snapshot; P4-GBFS station leg, honest-empty (no keyless feed, never invented stations).";
