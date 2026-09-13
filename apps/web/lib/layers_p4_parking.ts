// P4 OSM parking proximity layer (parameters4.md P4-013, issue #479).
//
// ONE layer: mapped amenity=parking count nearby (bays + lots, the
// p4_osm.md verdict "P4-013 parking (bays+lots ≤800 m)"). Harjumaa
// scope, local 2026-09-12 snapshot ONLY. Scores are absolute 0..100;
// unknown stays 255 (renders red). This file owns ALL P4-parking
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `P4PARK-HOOK
// (#479)` blocks, so the sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef):
// no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Tallinna parkimine zone regime (fees,
// hours, resident/guest permits — dims_p4_park.py, docs/p4_park.md),
// the kataster courtyard ratio, live occupancy counts and any
// availability feed are NOT in the snapshot, so this layer is an
// honestly-labeled OSM-derived PROXY. Title, legend and source say
// "kaardistatud" (mapped) and "hinnang"/"proksi" (estimate/proxy) —
// never measured parking availability, never a resident-permit or
// courtyard-spot guarantee (pinned by layers_p4_parking.test.ts).
//
// Overlap (documented, ehitus/buildout G05A+G05B precedent — same
// source, different buyer question): amenity=parking ALSO feeds
// dims_p4_osm.dim_parking (nearest mapped bay/lot ≤800 m, bands
// 80/72/62 + absence fallback 50) and dims_group18's on-street
// "street_parking" kind. Those ask a nearest-distance question (how
// far is the closest mapped bay); this layer asks a COUNT question
// (how much mapped parking surrounds the listing — area-kind, the
// grocery/waste/lawncare shape). Neither re-skins the other.
// On-street subtypes (street_side/lane/on_kerb/layby) stay IN the
// count: the verdict says bays+lots, and the scorer reads both kinds.
//
// Tag verification (2026-09-13, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/amenity=parking   (+ export)
//   78 071 objects Harjumaa-wide (docs/p4_osm.md §3 — P4-013 viable);
//   13 858 features in the Tallinn probe window
//   (lon 24.4–25.1, lat 59.3–59.55: 699 nodes, 6605 polygons,
//   6554 open ways — street-side bays mapped as lines along kerbs).
//
// Calibration (judgment calls, documented for the reviewer): parking
// is an area-kind count kernel (Gaussian sigma 0.8 == the P4-013
// 800 m tier, score 100·S/(S+half), grocery/waste/lawncare shape
// with a DENSITY half). half=75, NOT 1/6/20: with 13 858 window
// centroids a small half saturates the whole city to ~99 (verified
// 2026-09-13 probe: half=20 reads Vanalinn 98, Mustamäe 98,
// Lasnamäe 96 — the field answers nothing) and the streets stop
// discriminating. half=75 spreads the real variation — built-master
// probe on the 75 m grid (13 282 reader points, 6368 after the
// 20 m twin dedupe):
//   Vanalinn 87, Mustamäe 84, Lasnamäe 76, Õismäe 71,
//   Viimsi 46, Pirita 31, rural W (Saue) 28, Nõmme 5 —
// while forgiving unmapped private driveways (a lower half would
// paint garden-city streets red for a mapping gap). Nõmme's
// near-zero is a documented mapping hole, not parking truth;
// water/forest cells read 255 unknown. Sigma equals the
// Euclidean fallback decay (DECAY hook) and the raster contract
// (matchesContract). Halves live in P4PARK_CAL below and in
// scripts/build/batch_p4_parking.py P4PARK_CAL (kept in sync
// by test).
//
// P4 NUMBERING (canary convention, for the reviewer + sibling P4
// layers): P4 params live in the parameters4.md P4-XXX namespace,
// which has no numbers in the parameters3 registry the LayerDef
// buttons print as "(pN)". This first P4 map layer reserves the
// 4XXX block (4000 + P4 ordinal → paramIds [4013]) so P4 buttons
// never collide with a parameters3 number; the title carries the
// true "P4-013" id. A future page change may render the P4
// namespace natively.

import type { BonusSpec, LayerDef } from "./layers";

export type P4ParkingLayerId = "parking";

export const P4PARK_LAYER_IDS: P4ParkingLayerId[] = ["parking"];

/** parameters4.md P4 id per layer, in the reserved 4XXX registry block (see note above). */
export const P4PARK_PARAMS: Record<P4ParkingLayerId, number> = {
  parking: 4013,
};

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const P4PARK_DEFS: LayerDef[] = [
  {
    id: "parking",
    paramIds: [4013],
    title: "Kaardistatud parklad lähedal (P4-013 proksi-hinnang)",
    goodLabel: "roheline = kaardistatud parklaid (taskud + platsid) lähedal palju (hinnang)",
    badLabel: "punane = kaardistatud parklaid lähedal pole (hinnang — kaardistamata hoovid välja)",
    source: `${SNAP} (kaardistatud 78 071 amenity=parking objekti Harjumaal, sh Tallinna aknas 13 858 — teetaskud + platsid; tasulise parkimise tsoonirežiim, elanikload, hoovisuhe ja VABADE KOHTADE arv kaardil pole — kiht näitab asukoha-PROKSIT, mitte mõõdetud saadavust)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe kaardistus)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (kaardistatud parklatest kaugel)
    ],
  },
];

/**
 * Overpass QL fragment (documents the source tag; the app serves the
 * frozen snapshot, never live Overpass). n/ shape: the shared
 * overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped parking polygons). Bays + lots both
 * count (p4_osm.md verdict); the on-street/off-street subtype split
 * lives in the scorer mapping (kinds_from_tags), so the fragment
 * stays a plain source-tags query like sibling batches.
 */
export const P4PARK_TAGS: Record<P4ParkingLayerId, string> = {
  parking: 'n["amenity"="parking"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay == P4-013 800 m tier). */
export const P4PARK_DECAY: Record<P4ParkingLayerId, number> = {
  parking: 0.8,
};

/**
 * Calibration locked 2026-09-13 from snapshot probes (mirrors
 * scripts/build/batch_p4_parking.py P4PARK_CAL exactly — a pytest
 * parses this file and fails on drift). Area-kind half (saturating
 * count, grocery/waste/lawncare precedent with a density half).
 */
export const P4PARK_CAL = {
  parking: { half: 75, sigma: 0.8 },
} as const;

/**
 * Nearby-parking count 100·S/(S+half) (area-kind, grocery/waste/
 * lawncare shape with a density half — green where mapped parking
 * is dense).
 */
export const P4PARK_BONUS: Record<P4ParkingLayerId, BonusSpec> = {
  parking: { kind: "area", half: 75 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isP4ParkingLayerId(layer: string): layer is P4ParkingLayerId {
  return (P4PARK_LAYER_IDS as string[]).includes(layer);
}

/**
 * P4-parking bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForP4Parking(layer: string): BonusSpec | undefined {
  return (P4PARK_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master file (built by scripts/build/batch_p4_parking.py). */
export const P4PARK_RASTER_FILE: Record<P4ParkingLayerId, string> = {
  parking: "parking-walk-raster.json",
};

/**
 * NO metro master (documented): a dense count kernel at 9.375 m
 * cells would be fake precision. The window route serves county
 * everywhere for this layer (metro slot stays empty, like
 * G02B/G03/G03D/G08B/G05C/G17A/G17B).
 */
export const P4PARK_NO_METRO = true;

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const P4PARK_HOOK =
  "P4PARK-HOOK (#479): parking wired into layers/overlays/snapshot; P4-013 OSM bays+lots proxy, half 75 / sigma 0.8.";
