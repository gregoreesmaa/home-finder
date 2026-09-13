// Group 17 municipal-services-B layers (parameters3.md §5.17, issue #178):
// p469 ships as an honest mown-lawn count hinnang ("lawncare");
// p463/p464/p465 are documented no-map with scorer dims (see
// G17B_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = upkeep-visible (green = near mapped mown lawns, red =
// far / unknown); unknown stays 255 (renders red). This file owns ALL
// G17B runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `G17B-HOOK (#178)`
// blocks, so the sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Tallinna Linnavalitsus / KOV upkeep
// registers — sidewalk-duty records (heakorraeeskiri), street-sweeping
// calendars and ticketing logs, shoveling-duty enforcement, lawn-height
// inspection records — are NOT in the 2026-09-12 snapshot, so the one
// shipped layer is NOT registry data:
// * lawncare is a mapped-lawn *hinnang* — count of OSM-mapped mown
//   grass areas (landuse=grass: courtyard lawns, roadside verges,
//   panel-district greens) nearby. Streets lined with mapped lawns are
//   upkeep-visible — mowing duty bites there and the buyer sees the
//   streetscape — but it is NOT a lawn-height inspection register,
//   and it says so.
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — legal duties and
// schedule/enforcement facts ship as scorer NULLs, never gradients):
// * p463 sidewalk maintenance laws: a per-parcel LEGAL fact (Tallinna
//   heakorraeeskiri: the abutting owner maintains the sidewalk). Mapped
//   footway density already scores as pedinfra (layers.ts pedinfra
//   TAGS cover highway footway|path|pedestrian|steps) — a second
//   footway gradient would duplicate it. Scorer dim stays NULL with a
//   heakorra-check reason (dims_group17b.dim_sidewalk).
// * p464 street sweeping ticketing: a SCHEDULE + ENFORCEMENT fact
//   (cleaning calendars live with the operator; tickets with the
//   municipal police). sweeping/street_cleaning/cleaning/snow_removal
//   keys are all ZERO in the snapshot — nothing to calibrate. Scorer
//   dim stays NULL with an operator reason (dims_group17b.dim_sweeping).
// * p465 snow shoveling mandates: a per-parcel LEGAL fact (the
//   abutting owner clears snow). winter_service tags are ZERO in the
//   snapshot; winter-service proximity already scores via gritbin p311
//   (G17A) and footway density via pedinfra — a third winter gradient
//   would duplicate them. Scorer dim stays NULL with a KOV reason
//   (dims_group17b.dim_shoveling).
//
// Overlap (documented, ehitus/buildout G05A+G05B precedent — same
// source, different buyer question): landuse=grass also feeds
// livability's nearest-"park" scorer kind (dims_group09 nature,
// dims_group13 p270 yard leg, dims_group18b/c cooling) and the parks
// map layer's amenity side. Those ask amenity/distance questions
// (how far is green relief); lawncare asks an upkeep-pressure count
// question (how much mown grass surrounds the listing — area-kind,
// viewshed/moorage precedent). Neither re-skins the other.
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/landuse=grass   (+ export)
//   41389 features; the keep_lawn predicate (landuse=grass exactly,
//   first-value) keeps 40499 county-wide (33524 in the Tallinn window:
//   Mustamäe/Õismäe/Lasnamäe panel lawns, Kadriorg verges). 890
//   untagged relation members drop out. landuse=meadow (1799 ways +
//   79 relations) is OUT by design: a meadow is unmown BY DEFINITION,
//   not a mowing-duty lawn — and it stays livability's "park" kind.
//   leisure=garden stays the parks layer's (#98 amenity side).
//   osmium tags-filter ... nwr/sweeping nwr/street_cleaning
//     nwr/cleaning nwr/snow_removal → 0 nodes + 0 ways each; and
//   nwr/winter_service → empty (G17A corroboration). Footways:
//   nwr/highway=footway keeps 30360 ways — already pedinfra's.
//
// Calibration (judgment calls, documented for the reviewer): lawncare
// is an area-kind count kernel (Gaussian sigma 0.3, score
// 100·S/(S+20), viewshed/moorage/G17A shape with a DENSITY half).
// half=20, NOT 1: with 18179 deduped lawn centroids a half of 1
// saturates all of Tallinn to 99 (verified 2026-09-12 probe) and the
// field answers nothing. half=20 spreads the real variation —
// Mustamäe S=238 reads 92, Vanalinn S=68 reads 77, Pirita S=20 reads
// 50 — while forgiving unmapped private gardens (a lower half would
// paint garden-city streets red for a mapping gap). Nõmme's near-zero
// (S=0.03, n800=0: private gardens unmapped there) is a documented
// mapping hole, not upkeep truth; rural Harjumaa reads 255 unknown
// (ordinances are KOV-specific anyway). Sigma equals the Euclidean
// fallback decay (DECAY hook) and the raster contract
// (matchesContract). Halves live in G17B_CAL below and in
// scripts/build/batch_g17_b.py G17B_CAL (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group17BLayerId = "lawncare";

export const GROUP17B_LAYER_IDS: Group17BLayerId[] = ["lawncare"];

/** parameters3.md number per Group-17B layer (no-map params have no layer). */
export const GROUP17B_PARAM_IDS: Record<Group17BLayerId, number> = {
  lawncare: 469,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP17B_ALL_PARAMS = [463, 464, 465, 469] as const;

export type Group17BParam = (typeof GROUP17B_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP17B_LAYERS: LayerDef[] = [
  {
    id: "lawncare",
    paramIds: [469],
    title: "Niidetavad haljasalad (hinnang)",
    goodLabel: "roheline = niidetavate murualade lähedal, hooldus nähtav (hinnang)",
    badLabel: "punane = murualadest kaugel, niitmisnõuete jõustamine teadmata (hinnang)",
    source: `${SNAP} (kaardistatud 40499 niidetavat muruala — hoovimurud, teeservad, paneelrajoonide haljastus — sh Tallinnas 33524; 1799 + 79 niitmata aasa VÄLJA — aas ei ole muru; PROKSI-hinnang läheduse järgi — see EI OLE linna niitmisnõuete kontrollregister)`,
    fallbackPoints: [
      { lat: 59.412, lon: 24.655 }, // Õismäe paneelhaljastus (muru lähedal)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (kaardistatud murualadest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 17B layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped lawn polygons). The builder consumes the
 * same predicate offline (see keep_lawn); the meadow exclusion lives in
 * the scorer mapping (kinds_from_tags), so the fragment stays a plain
 * source-tags query like sibling batches.
 */
export const GROUP17B_TAGS: Record<Group17BLayerId, string> = {
  lawncare: 'n["landuse"="grass"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP17B_DECAY: Record<Group17BLayerId, number> = {
  lawncare: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g17_b.py G17B_CAL exactly — a pytest
 * parses this file and fails on drift). Area-kind half (saturating
 * count, viewshed/moorage/G17A precedent).
 */
export const G17B_CAL = {
  lawncare: { half: 20, sigma: 0.3 },
} as const;

/**
 * Nearby-lawn count 100·S/(S+half) (area-kind, viewshed/moorage/G17A
 * shape with a density half — green NEAR the upkeep-visible lawns).
 */
export const GROUP17B_BONUS: Record<Group17BLayerId, BonusSpec> = {
  lawncare: { kind: "area", half: 20 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup17BLayerId(layer: string): layer is Group17BLayerId {
  return (GROUP17B_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-17B bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup17B(layer: string): BonusSpec | undefined {
  return (GROUP17B_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 17B layer (built by batch_g17_b.py). */
export const G17B_RASTER_FILE: Record<Group17BLayerId, string> = {
  lawncare: "lawncare-walk-raster.json",
};

/**
 * NO metro masters (documented): a dense count kernel at 9.375 m cells
 * would be fake precision. The window route serves county everywhere
 * for this layer (metro slot stays empty, like G07B/G03D/G08B/G05C/G17A).
 */
export const G17B_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group17bHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface Group17BPoint {
  lat: number;
  lon: number;
}

/**
 * Area-kind saturating score 100·S/(S+half) (mirrors
 * walk_raster.saturate). Exported for the Euclidean fallback path.
 */
export function group17bAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group17bMatchesContract(
  layer: Group17BLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G17B_CAL[layer].half && doc.sigma === G17B_CAL[layer].sigma;
}

export type Group17BVerdictKind = "proxy" | "real" | "no-map";

export interface Group17BVerdict {
  param: Group17BParam;
  name: string;
  kind: Group17BVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 17 batch B (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group17b.py).
 */
export const G17B_VERDICTS: Group17BVerdict[] = [
  {
    param: 463,
    name: "Sidewalk maintenance laws",
    kind: "no-map",
    reason:
      "A per-parcel legal fact (Tallinna heakorraeeskiri: the abutting owner maintains the sidewalk); the snapshot carries zero duty records, and mapped footway density already scores as pedinfra — a second footway gradient would duplicate it.",
  },
  {
    param: 464,
    name: "Street sweeping ticketing",
    kind: "no-map",
    reason:
      "A schedule-plus-enforcement fact (cleaning calendars live with the operator, tickets with the municipal police); sweeping/street_cleaning/cleaning/snow_removal keys are all zero in the snapshot, so there is nothing to calibrate.",
  },
  {
    param: 465,
    name: "Snow shoveling mandates",
    kind: "no-map",
    reason:
      "A per-parcel legal fact (the abutting owner clears snow); winter_service tags are zero in the snapshot, and winter-service proximity already scores via gritbin p311 (G17A) with footway density via pedinfra — a third winter gradient would duplicate them.",
  },
  {
    param: 469,
    name: "Weed and lawn ordinances",
    kind: "proxy",
    reason:
      "Shipped as lawncare: count of 40499 mapped mown-grass areas nearby (33524 in Tallinn — Õismäe/Mustamäe/Lasnamäe panel lawns, Kadriorg verges) as upkeep-visibility hinnang, area-kind like viewshed/G17A — honestly labelled, never a mowing-inspection ruling; 1799 + 79 unmown meadows are out (a meadow is not a lawn).",
  },
];

/** Batch-B params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP17B_NO_MAP_PARAMS: number[] = G17B_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP17B_HOOK =
  "G17B-HOOK (#178): lawncare wired into layers/overlays/snapshot; p463/p464/p465 verdicts + dims only.";
