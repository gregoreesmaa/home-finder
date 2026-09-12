// Group 14 public-safety layers (parameters3.md §5.14, issue #102).
//
// One layer per mappable Group 14 parameter, Harjumaa scope, local
// 2026-09-12 snapshot ONLY. Scores are absolute 0..100; unknown stays 255
// (renders red). This file owns ALL Batch-5 runtime data; shared files
// (lib/layers.ts, lib/server/snapshot.ts) touch it only through small
// marked `B5-HOOK (#102)` blocks, so the nine sibling batches stay disjoint.
//
// HONESTY (load-bearing): the PPA crime CSVs are NOT in the snapshot, so
// p13 MUST NOT be presented as measured crime rates. It is a
// police-proximity safety *hinnang* (estimate) — the title, legend and
// source say so, and the test below pins those markers. Likewise p315
// scores hydrant *proximity*, not measured flow rate; p78/p467 score
// station *proximity*, not measured response/dispatch times; p335 scores
// major-road *proximity*, not an official evacuation plan.
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-count ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
//     emergency=fire_hydrant amenity=fire_station amenity=police \
//     amenity=hospital highway=trunk highway=primary
//   723  emergency=fire_hydrant
//   30   amenity=fire_station
//   21   amenity=police
//   21   amenity=hospital
//   1231 highway=trunk / 1099 highway=primary (evac egress ways;
//   highway=motorway is ~absent in Harjumaa — Estonia has no motorways —
//   so the evac query targets trunk/primary only).
//
// Calibration (judgment calls, documented for the reviewer): all five are
// unweighted count kernels (evac: trunk/primary road-km), area-kind
// saturating scores (100·S/(S+half)), mirroring the grocery/healthcare
// path. Sparse station layers use small halves so a lone station still
// reads mid-ramp (safety 50 / emergency 33 / dispatch 25 next to the
// feature); hydrants use the grocery half (6) at the same urban density.
// Evac half is 2, not pedinfra's 12: trunk/primary road-km is sparse
// (2330 ways county-wide) and a Tallinn-window histogram with half=2
// reads median 36 / max 71 (corridors green), while half=12 capped the
// window at 29. Sigmas equal the Euclidean fallback decay (DECAY_KM hook)
// and the raster contract (matchesContract): station layers 0.8 km
// (coverage scale, like healthcare), hydrants 0.3 km (block scale, like
// grocery), evac 0.5 km (corridor scale). Recalibrate from Tallinn
// histograms if a county build shows blobbing — halves live in one dict
// below and in scripts/build/batch_b5_safety.py LAYER_DEFAULTS (kept in
// sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Batch5LayerId = "safety" | "emergency" | "hydrants" | "evac" | "dispatch";

export const BATCH5_LAYER_IDS: Batch5LayerId[] = [
  "safety",
  "emergency",
  "hydrants",
  "evac",
  "dispatch",
];

/** parameters3.md number per Batch-5 layer. */
export const BATCH5_PARAMS: Record<Batch5LayerId, number> = {
  safety: 13,
  emergency: 78,
  hydrants: 315,
  evac: 335,
  dispatch: 467,
};

export const BATCH5_DEFS: LayerDef[] = [
  {
    id: "safety",
    paramIds: [13],
    title: "Turvalisus (politsei läheduse hinnang)",
    goodLabel: "roheline = politseipunkt lähedal (hinnang)",
    badLabel: "punane = politseipunkt kaugel või andmed puuduvad",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM amenity=police; PPA kuriteo-CSV-d hetktõmmises pole — see EI OLE mõõdetud kuritegevus)",
    fallbackPoints: [
      { lat: 59.4372, lon: 24.7536 }, // Tallinna kesklinn
      { lat: 58.378, lon: 26.729 }, // Tartu kesklinn
    ],
  },
  {
    id: "emergency",
    paramIds: [78],
    title: "Päästeteenistuse lähedus (hinnang)",
    goodLabel: "roheline = päästekomando/haigla lähedal (hinnang)",
    badLabel: "punane = abi kaugel või andmed puuduvad",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM amenity=fire_station/hospital; kauguse-hinnang, mitte mõõdetud reageerimisajad)",
    fallbackPoints: [
      { lat: 59.4372, lon: 24.7536 }, // Tallinna kesklinn
      { lat: 58.378, lon: 26.729 }, // Tartu kesklinn
    ],
  },
  {
    id: "hydrants",
    paramIds: [315],
    title: "Tuletõrjehüdrantide lähedus",
    goodLabel: "roheline = hüdrant lähedal",
    badLabel: "punane = hüdrant kaugel või andmed puuduvad",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM emergency=fire_hydrant; lähedus, mitte mõõdetud vooluhulk)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn
      { lat: 59.44, lon: 24.82 }, // Lasnamäe
    ],
  },
  {
    id: "evac",
    paramIds: [335],
    title: "Evakuatsiooniteede lähedus (hinnang)",
    goodLabel: "roheline = magistraaltee lähedal (hinnang)",
    badLabel: "punane = magistraalteed kaugel või andmed puuduvad",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM highway=trunk/primary; teede läheduse hinnang, mitte ametlik evakuatsiooniplaan)",
    fallbackPoints: [
      { lat: 59.4372, lon: 24.7536 }, // Tallinna kesklinn
      { lat: 58.378, lon: 26.729 }, // Tartu kesklinn
    ],
  },
  {
    id: "dispatch",
    paramIds: [467],
    title: "Hädaabiteenuste lähedus 112 (hinnang)",
    goodLabel: "roheline = politsei/pääste/haigla lähedal (hinnang)",
    badLabel: "punane = hädaabiteenused kaugel või andmed puuduvad",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM amenity=police/fire_station/hospital; läheduse hinnang, mitte mõõdetud väljakutseajad)",
    fallbackPoints: [
      { lat: 59.4372, lon: 24.7536 }, // Tallinna kesklinn
      { lat: 58.378, lon: 26.729 }, // Tartu kesklinn
    ],
  },
];

/** Influence radii in km (== walk-kernel sigma == Euclidean fallback decay). */
export const BATCH5_DECAY: Record<Batch5LayerId, number> = {
  safety: 0.8,
  emergency: 0.8,
  hydrants: 0.3,
  evac: 0.5,
  dispatch: 0.8,
};

/**
 * Overpass QL fragments for the layer inside the bbox. Snapshot-only
 * serving never queries live; these document the source tags (and the
 * evac `w[` way fragment stays a way query through overpassQueryFor,
 * which only rewrites `n[`).
 */
export const BATCH5_TAGS: Record<Batch5LayerId, string> = {
  safety: 'n["amenity"="police"];',
  emergency: 'n["amenity"~"fire_station|hospital"];',
  hydrants: 'n["emergency"="fire_hydrant"];',
  evac: 'w["highway"~"motorway|trunk|primary"];',
  dispatch: 'n["amenity"~"police|fire_station|hospital"];',
};

/** Saturation midpoints (area-kind), see calibration note above. */
export const BATCH5_HALVES: Record<Batch5LayerId, number> = {
  safety: 1,
  emergency: 2,
  hydrants: 6,
  evac: 2,
  dispatch: 3,
};

export const BATCH5_BONUS: Record<Batch5LayerId, BonusSpec> = {
  safety: { kind: "area", half: 1 },
  emergency: { kind: "area", half: 2 },
  hydrants: { kind: "area", half: 6 },
  evac: { kind: "area", half: 2 },
  dispatch: { kind: "area", half: 3 },
};

/**
 * Batch-5 bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for the original eight layers (their switch handles them).
 */
export function bonusSpecForBatch5(layer: string): BonusSpec | undefined {
  return (BATCH5_BONUS as Record<string, BonusSpec>)[layer];
}
