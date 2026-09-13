// OSM road-safety overlay (P4-012 proxy, issue #481).
//
// One layer ("roadsafety"): mapped crossing + traffic-calming furniture
// density as an honest accident-blackspot PROKSI. Harjumaa scope, local
// 2026-09-12 snapshot ONLY. Scores are absolute 0..100; unknown stays 255
// (renders red). This file owns ALL road-safety runtime data; shared files
// (lib/layers.ts, lib/server/snapshot.ts, lib/overlays.ts) touch it only
// through small marked `RSAFE-HOOK (#481)` blocks, so sibling batches stay
// disjoint. This module imports ./layers ONLY as types: no runtime cycle.
//
// HONESTY (load-bearing): the Transpordiamet accident-point register and
// Päästeamet drive times are NOT in the snapshot, so this layer MUST NOT
// be presented as measured road safety. It scores the COUNT of mapped
// crossing/calming furniture nearby (area-kind saturating score,
// grocery/hydrant precedent) — streets with mapped zebra crossings and
// speed furniture read green. The title, legend and source say
// "hinnang"/"proksi" and carry the usage-not-safety caveat (P4-032
// precedent: furniture density reflects mapping usage, never safety
// truth) — pinned by the test below.
//
// Overlap (documented, ehitus/buildout G05A+G05B precedent — same source,
// different buyer question): highway=crossing feeds livability's
// "cornerfurn" scorer kind (dims_group18restb) and traffic_calming feeds
// "calming" (dims_group18); the per-listing P4-012 scorer dim lives in
// services/scoring/dims_p4_osm.py (dim_blackspots, nearest-furniture
// bands ≤500 m). Those answer "how far is the nearest marked crossing";
// this layer answers "how much calming furniture surrounds the listing"
// (count kernel, viewshed/moorage/G17A shape). The B5 "safety" layer
// (p13 police proximity) asks a third question — the shared p13 binding
// below mirrors the fiber/mobile p51 precedent.
//
// Tag verification (2026-09-13, local Harjumaa 2026-09-11 PBF — no network):
//   osmium tags-count harjumaa-260911.osm.pbf highway=crossing traffic_calming
//   12348  "highway"  "crossing"   (matches docs/p4_osm.md §3)
//   2672   "traffic_calming"        (docs/p4_osm.md §3 prints 4860 — that
//     figure counts a broader pre-filter; 2672 is the plain key-use count
//     on the same PBF, dated 2026-09-13)
//   osmium tags-filter ... 'nwr/highway=crossing' 'nwr/traffic_calming' +
//     export → 14445 deduped features with geometry (10527 in the Tallinn
//     window); ~635 carry both tags (raised crossings).
//
// Calibration (judgment calls, documented for the reviewer): area-kind
// count kernel, Gaussian sigma 0.5 (== the ≤500 m blackspot radius from
// the issue AC and dim_blackspots BLACKSPOT_RADIUS_M), score
// 100·S/(S+half) with a DENSITY half. half=60, NOT 1..12: with ~10.5k
// Tallinn-window centroids a grocery half (6) saturates the whole city
// to 93+ (verified 2026-09-13 probe) and the field answers nothing.
// half=60 spreads the real variation (probe S -> score: Viru 345 -> 85,
// Vanalinn 241 -> 80, Balti 208 -> 78, Õismäe 158 -> 72, Lasnamäe
// 109 -> 64, Pirita 59 -> 50, Nõmme 36 -> 37, rural 0 -> 255 unknown)
// while forgiving unmapped crossings on garden-city streets (a lower
// half would paint them red for a mapping gap). Sigma equals the
// Euclidean fallback decay (DECAY hook) and the raster contract
// (matchesContract). Halves live in RSAFE_CAL below and in
// scripts/build/batch_rsafety_osm.py RSAFE_CAL (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type RsafeLayerId = "roadsafety";

export const RSAFE_LAYER_IDS: RsafeLayerId[] = ["roadsafety"];

/** parameters3.md number per road-safety layer (p13, shared with B5 safety). */
export const RSAFE_PARAMS: Record<RsafeLayerId, number> = {
  roadsafety: 13,
};

export const RSAFE_DEFS: LayerDef[] = [
  {
    id: "roadsafety",
    paramIds: [13],
    title: "Ülekäigud ja liiklusrahustid (ohutus-hinnang)",
    goodLabel:
      "roheline = märgistatud ülekäik/rahusti lähedal (kaardistuskasutus, mitte ohutustõde)",
    badLabel: "punane = märgistatud ülekäiku/rahustit lähedal pole või andmed puuduvad",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM highway=crossing 12348 + traffic_calming 2672 kasutusjuhtu, 14445 ainulaadset objekti; Transpordiameti õnnetuspunktid ja Päästeameti sõiduajad hetktõmmises pole — see EI OLE mõõdetud liiklusohutus, vaid kaardistatud mööbli tiheduse proksi)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe kaardistus)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (kaardistatud mööblist kaugel)
    ],
  },
];

/** Influence radius in km (== blackspot kernel sigma == Euclidean fallback decay). */
export const RSAFE_DECAY: Record<RsafeLayerId, number> = {
  roadsafety: 0.5,
};

/**
 * Overpass QL fragment for the layer inside the bbox. Snapshot-only
 * serving never queries live; this documents the source tags (the
 * shared overpassQueryFor() rewrites n[ to nwr/, so way-mapped calming
 * is covered — PR #118 parity).
 */
export const RSAFE_TAGS: Record<RsafeLayerId, string> = {
  roadsafety: 'n["highway"="crossing"];n["traffic_calming"];',
};

/** Raster master filename next to the base masters (gitignored artifact). */
export const RSAFE_RASTER_FILE: Record<RsafeLayerId, string> = {
  roadsafety: "roadsafety-walk-raster.json",
};

/**
 * Calibration locked 2026-09-13 from snapshot probes (mirrors
 * scripts/build/batch_rsafety_osm.py RSAFE_CAL exactly — a pytest
 * parses this file and fails on drift). Area-kind half (saturating
 * count, grocery/hydrant precedent with a density half).
 */
export const RSAFE_CAL = {
  roadsafety: { half: 60, sigma: 0.5 },
} as const;

/** Area-kind saturating score 100·S/(S+half) (mirrors walk_raster.saturate). */
export const RSAFE_BONUS: Record<RsafeLayerId, BonusSpec> = {
  roadsafety: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isRsafeLayerId(layer: string): layer is RsafeLayerId {
  return (RSAFE_LAYER_IDS as string[]).includes(layer);
}

/**
 * Road-safety bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForRsafe(layer: string): BonusSpec | undefined {
  return (RSAFE_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * NO metro master (documented): a dense count kernel at 9.375 m cells
 * would be fake precision. The window route serves county everywhere
 * for this layer (metro slot stays empty, like G17B/G03D/G08B/G05C).
 */
export const RSAFE_NO_METRO = true;

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const RSAFE_HOOK =
  "RSAFE-HOOK (#481): roadsafety wired into layers/overlays/snapshot; P4-012 proxy, usage-not-safety caveat in legend.";
