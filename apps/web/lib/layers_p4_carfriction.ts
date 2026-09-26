// P4 car-friction layer (issue #829): OSM motor-vehicle access
// restrictions as a driving-hardship hinnang.
//
// ONE layer ("carfriction"): INVERTED nearby-count of car-restrictive
// tags (motor_vehicle/vehicle/motorcar in {no, private, permit,
// destination, customers}) from the frozen 2026-09-12 Harjumaa
// snapshot. Dense restriction clusters (old-town cores like
// Vanalinn) read BAD (low score, red); open suburbs read GOOD
// (high score, green). Harjumaa scope, local snapshot ONLY. Scores
// are absolute 0..100; cells outside every kernel footprint stay
// 255 unknown. This file owns ALL car-friction runtime data;
// shared files (lib/layers.ts, lib/overlays.ts,
// lib/server/snapshot.ts, lib/aggregateWeights.ts) touch it only
// through small marked `CARFRICTION-HOOK (#829)` blocks, so the
// sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef):
// no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Tallinna paid-parking zone regime
// (fees, hours, resident/guest permits) is NOT in the snapshot —
// no verifiable mappable source exists (Tallinn open data carries
// no parking-zone polygons; the snapshot carries zero
// zone:parking / parking:fee / fee tags, verified 2026-09-26) —
// so paid zones ship as a DOCUMENTED GAP, never inferred prices
// or zones (OTA PR #131 precedent). Congestion is NOT duplicated
// here either: the delay-* corridor layers (layers_p4_delay.ts)
// already cover typical delay. Title, legend and source say
// "piirang" (restriction) and "hinnang" (estimate) — never measured
// driving difficulty, never a paid-zone map, never a congestion
// reading (pinned by layers_p4_carfriction.test.ts).
//
// Overlap (documented, ehitus/buildout G05A+G05B precedent — same
// source, different buyer question): amenity=parking ALSO feeds
// the parking layer (P4-013 mapped bays+lots COUNT, green where
// dense) and dims_p4_osm.dim_parking (nearest mapped bay/lot).
// Those ask a nearest/count question about mapped PARKING (a
// convenience); this layer asks an INVERTED count question about
// motor-vehicle RESTRICTIONS (a hardship). Neither re-skins the
// other: parking-green Vanalinn (many mapped bays) can still read
// carfriction-red (many no-entry streets).
//
// Tag verification (2026-09-26, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/motor_vehicle nwr/vehicle nwr/motorcar   (+ export)
//   2382 access-tagged objects Harjumaa-wide, 1545 kept restrictive
//   (motor_vehicle no 955 + private 447 + permit 46 + destination 21
//   + customers 12 + vehicle/motorcar slices); permissive values
//   (yes/designated/permissive) and key-only filter artefacts are
//   dropped by keep_restriction in scripts/build/batch_carfriction.py.
//
// Calibration (judgment calls, documented for the reviewer):
// carfriction is a sparse-kind INVERTED count kernel (Gaussian
// sigma 0.3 == street-scale friction, score 100·half/(S+half),
// G18B-daylight precedent). half=60, NOT 75: built-master probe
// on the 75 m grid reads Vanalinn 29 (red old-town core),
// Mustamäe 73, Õismäe 82, Pirita 68, Lasnamäe 95, Viimsi 88,
// Nõmme 100 (measured open) — while a wider sigma (0.5/0.8
// probed 2026-09-26) smears the core into the suburbs and the
// field answers nothing. Sigma equals the Euclidean fallback
// decay (DECAY hook) and the raster contract (matchesContract).
// Halves live in CARFRICTION_CAL below and in
// scripts/build/batch_carfriction.py CARFRICTION_CAL (kept in sync
// by test).

import type { BonusSpec, LayerDef } from "./layers";

export type CarfrictionLayerId = "carfriction";

export const CARFRICTION_LAYER_IDS: CarfrictionLayerId[] = ["carfriction"];

const SNAP = "kohalik väljavõte 2026-09-12";

export const CARFRICTION_DEFS: LayerDef[] = [
  {
    id: "carfriction",
    paramIds: [],
    paramLabel: "P4-auto",
    title: "Autosõidu piirangud lähedal (PÖÖRATUD proksi-hinnang)",
    goodLabel:
      "roheline = mootorsõiduki piiranguid (keelu-/eramärgid) lähedal vähe — avatud tänavavõrk (hinnang)",
    badLabel:
      "punane = piiranguid lähedal tihedalt (vanalinna tuumikud — autoga raske; hinnang — ummikuid ega tasulisi tsoone kaart ei näita)",
    source: `${SNAP} (1545 piiravat motor_vehicle/vehicle/motorcar-märgendit Harjumaal: no/private/permit/destination/customers; lubavad väärtused välja; TAVALINE VIIVITUS EI OLE — ummikud on delay-* kihtides; TASULISED TSOONID EI OLE — tasulise parkimise tsoonirežiimile, hindadele ega elaniku- ja külalislubadele pole kontrollitavat kaardiallikat, hinnad/tsoonid tuletamata)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe piirangutuumik — punane)
      { lat: 59.32, lon: 24.5 }, // Maapiirkond (avatud tänavavõrk — roheline)
    ],
  },
];

/**
 * Overpass QL fragment (documents the source tags; the app serves the
 * frozen snapshot, never live Overpass). The restrictive-value
 * filter lives in the builder (keep_restriction — the on-street/
 * off-street subtype precedent from parking), so the fragment stays
 * a plain source-tags query like sibling batches. n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped restriction streets).
 */
export const CARFRICTION_TAGS: Record<CarfrictionLayerId, string> = {
  carfriction: 'n["motor_vehicle"];n["vehicle"];n["motorcar"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay, daylight precedent). */
export const CARFRICTION_DECAY: Record<CarfrictionLayerId, number> = {
  carfriction: 0.3,
};

/**
 * Calibration locked 2026-09-26 from snapshot probes (mirrors
 * scripts/build/batch_carfriction.py CARFRICTION_CAL exactly — a
 * pytest parses this file and fails on drift). Sparse-kind half
 * (inverted count, G18B-daylight precedent).
 */
export const CARFRICTION_CAL = {
  carfriction: { half: 60, sigma: 0.3 },
} as const;

/**
 * Nearby-restriction count 100·half/(S+half) (sparse-kind, the
 * mirror image of the area-kind parking count — red where
 * restrictions are dense).
 */
export const CARFRICTION_BONUS: Record<CarfrictionLayerId, BonusSpec> = {
  carfriction: { kind: "sparse", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isCarfrictionLayerId(layer: string): layer is CarfrictionLayerId {
  return (CARFRICTION_LAYER_IDS as string[]).includes(layer);
}

/**
 * Car-friction bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForCarfriction(layer: string): BonusSpec | undefined {
  return (CARFRICTION_BONUS as Record<string, BonusSpec>)[layer];
}

/** Inverted count score 0..100: 100 where open (S=0), 50 at S=half. */
export function carfrictionSparseScore(count: number, half: number): number {
  return (100 * half) / (count + half);
}

export interface CarfrictionPoint {
  lat: number;
  lon: number;
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function carfrictionHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/**
 * Euclidean fallback friction 0..100 (raster missing): Gaussian count
 * (sigma 0.3, 4-sigma cutoff) over the loaded restriction points,
 * then the sparse reading 100·half/(S+half). Null on EMPTY input
 * (no data loaded is unknown — never a faked open 100); S=0 over a
 * loaded set reads 100 (measured open, honestly known). Mirrors the
 * Python builder's score_sparse_cells exactly.
 */
export function carfrictionAt(
  lat: number,
  lon: number,
  points: CarfrictionPoint[],
): number | null {
  if (points.length === 0) return null;
  const sigma = CARFRICTION_CAL.carfriction.sigma;
  const cutoff = 4 * sigma;
  let s = 0;
  for (const p of points) {
    const d = carfrictionHavKm(lon, lat, p.lon, p.lat);
    if (d > cutoff) continue;
    s += Math.exp(-(d * d) / (2 * sigma * sigma));
  }
  return Math.round(carfrictionSparseScore(s, CARFRICTION_CAL.carfriction.half));
}

/** Raster master file (built by scripts/build/batch_carfriction.py). */
export const CARFRICTION_RASTER_FILE: Record<CarfrictionLayerId, string> = {
  carfriction: "carfriction-walk-raster.json",
};

/**
 * NO metro master (documented): a dense count kernel at 9.375 m
 * cells would be fake precision. The window route serves county
 * everywhere for this layer (metro slot stays empty, like
 * G02B/G03/G03D/G08B/G05C/G17A/G17B).
 */
export const CARFRICTION_NO_METRO = true;

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const CARFRICTION_HOOK =
  "CARFRICTION-HOOK (#829): carfriction wired into layers/overlays/snapshot/weights; OSM motor-vehicle restrictions proxy, half 60 / sigma 0.3, paid zones documented gap.";
