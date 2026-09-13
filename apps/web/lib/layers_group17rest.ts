// Group 17 HOA-rest layers (parameters3.md §5.17, issue #196): p245
// ships as an honest private-road proximity hinnang ("privroad");
// p4/p49/p142/p145/p152/p167/p246/p247/p278/p368/p427 are documented
// no-map with scorer dims (see G17R_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = calm (green = public-street area, red = on/near a
// private road where upkeep agreements bite); unknown stays 255
// (renders red). This file owns ALL G17R runtime data; shared files
// (lib/layers.ts, lib/server/snapshot.ts, lib/overlays.ts) touch
// it only through small marked `G17R-HOOK (#196)` blocks, so the
// sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the e-Äriregister KÜ annual reports, board
// cards, Creditinfo/MTA arrears and EKÜL baselines — the real sources
// for all twelve params — are NOT in the 2026-09-12 snapshot, so the
// shipped layer is NOT registry data:
// * privroad is a mapped-road *hinnang* — nearness to OSM-mapped
//   access=private shared roads (erateed: service/track/unclassified/
//   residential/living_street), never a KÜ maintenance-agreement
//   ruling. The map cannot know WHICH private roads carry an upkeep
//   agreement or what it costs — green means "public-street area,
//   no private-road burden expected", red means "on/near a private
//   road — ask the KÜ for the teehooldus agreement".
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — per-document
// facts ship as scorer NULLs, never gradients):
// * p4 maintenance costs: a per-KÜ EUR fact (annual-report line).
//   No cost keys exist anywhere in the snapshot.
// * p49 HOA restrictions: a per-KÜ RULEBOOK fact (house rules live
//   in the KÜ põhikiri). No rulebook keys in the snapshot.
// * p142 HOA financial reserves: a per-KÜ EUR fact (remondifond).
//   No reserve keys in the snapshot.
// * p145 vehicle restrictions: per-KÜ PARKING/vehicle rules. Mapped
//   driving restrictions (motor_vehicle=no/private) are KOV traffic
//   orders — the Old Town pedestrian zone, park paths — not KÜ house
//   rules, so consuming them would relabel municipal orders as HOA
//   policy (fake precision).
// * p152 owner-occupancy ratio: a per-BUILDING demographic fact. No
//   tenure keys in the snapshot.
// * p167 trash/recycling etiquette: per-HOA BEHAVIOUR (whether bins
//   are sorted on time). Waste-point proximity is already scored
//   twice (compost p187 + leafdrop p312, G17A) plus general waste
//   (p54 taara); a third waste gradient would duplicate them while
//   saying nothing about etiquette.
// * p246 special-assessment history: a per-KÜ EUR fact (one-off
//   owner levies). No levy keys in the snapshot.
// * p247 utility sub-metering: a per-BUILDING metering fact. No
//   metering keys in the snapshot.
// * p278 shared-maintenance phrasing: LISTING-TEXT NLP (how the ad
//   phrases upkeep), not a place field at all.
// * p368 HOA rental caps: a per-KÜ RULEBOOK fact (üüripiirang in the
//   põhikiri). No rulebook keys in the snapshot.
// * p427 HOA initiation fees: a per-KÜ EUR fact (sisseastumismaks).
//   No fee keys in the snapshot.
// Scorer dims stay NULL with e-Äriregister/KÜ-document reasons
// (dims_group17rest.py).
//
// Non-duplication (documented): p167 stays out even though waste
// points are mappable — G17A already scores mapped waste proximity
// (compost/leafdrop) and p54 scores general drop-offs. p145 stays
// out even though access tags are mappable — they are municipal
// traffic orders, not HOA rules. Gates (6547 barrier=gate features
// county-wide) are DOCUMENTED but not consumed: a gate marks a
// compound entrance, not a maintenance agreement, and compounds
// would double-count where their private roads already stamp.
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     w/access=private   (+ export)
//   21437 features; the keep_privroad predicate (access=private AND
//   highway in service/track/unclassified/residential/living_street
//   AND service NOT driveway/parking_aisle, see
//   scripts/build/batch_g17_rest.py) keeps 1086 county-wide (541 in
//   the Tallinn window lon 24.55-24.90 lat 59.36-59.50: Tiskrevälja,
//   Kakumäe/Merirahu private streets, Viimsi erateed). 20351 drop
//   out BY DESIGN: 18290 non-road access=private objects (parking
//   lots, pitches, pools — a car park is not a road), 874 private
//   driveways/parking aisles (single-parcel, never an agreement
//   road), the rest footway/path/cycleway/crossing fragments.
//   osmium tags-filter ... nwr/barrier=gate   (+ export)
//   6547 features: documented, NOT consumed (see above).
//   motor_vehicle=no/private + access=no: KOV traffic orders,
//   documented under p145, NOT consumed (see above).
//
// Calibration (judgment call, documented for the reviewer):
// privroad is a nearest-source distance field, quiet-kind calmness
// (100·d/(d+halfM)), the same kind the G05C/G07/G08 batches add —
// identical semantics (0 on the road, 50 at halfM), shared on
// purpose. halfM is 200 m (tighter than commbleed 300 m: a private-
// road upkeep burden is parcel-scale — your street, not the block).
// Sigma equals the Euclidean fallback decay (DECAY hook) and the
// raster contract (matchesContract). Halves live in G17R_CAL below
// and in scripts/build/batch_g17_rest.py G17R_CAL (kept in sync by
// test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group17RestLayerId = "privroad";

export const GROUP17REST_LAYER_IDS: Group17RestLayerId[] = ["privroad"];

/** parameters3.md number per Group-17-rest layer (no-map params have no layer). */
export const GROUP17REST_PARAM_IDS: Record<Group17RestLayerId, number> = {
  privroad: 245,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP17REST_ALL_PARAMS = [4, 49, 142, 145, 152, 167, 245, 246, 247, 278, 368, 427] as const;

export type Group17RestParam = (typeof GROUP17REST_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP17REST_LAYERS: LayerDef[] = [
  {
    id: "privroad",
    paramIds: [245],
    title: "Erateed ja privaatne teehooldus (hinnang)",
    goodLabel: "roheline = avalike tänavate piirkond, eratee-hoolduskoormust pole oodata (hinnang)",
    badLabel: "punane = eratee ääres — küsi KÜ-lt teehoolduslepingut ja kulusid (hinnang)",
    source: `${SNAP} (kaardistatud 1086 jagatud erateed — service/track/unclassified/residential/living_street + access=private — sh Tallinnas 541; 20351 mitterajalist/driveway-objekti VÄLJA — parkla ei ole tee; PROKSI-hinnang kauguse järgi — see EI OLE KÜ teehooldusleping ega Äriregister)`,
    fallbackPoints: [
      { lat: 59.44256, lon: 24.57679 }, // Tiskrevälja (Kakumäe eratee ääres, master 0)
      { lat: 59.466, lon: 24.698 }, // Paljassaare (avalike tänavate piirkond, master 80)
    ],
  },
];

/**
 * Overpass QL fragments per Group 17-rest layer (document the source
 * tags; the app serves the frozen snapshot, never live Overpass).
 * n/ shape: the shared overpassQueryFor() rewrites n[ to nwr/ (PR
 * #118: node-only silently drops way-mapped service roads). The
 * builder consumes the same predicate offline (see keep_privroad);
 * the driveway/parking-aisle exclusion lives in the scorer mapping
 * (kinds_from_tags), so the fragment stays a plain source-tags query
 * like sibling batches.
 */
export const GROUP17REST_TAGS: Record<Group17RestLayerId, string> = {
  privroad: 'n["highway"~"service|track|unclassified|residential|living_street"]["access"="private"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP17REST_DECAY: Record<Group17RestLayerId, number> = {
  privroad: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g17_rest.py G17R_CAL exactly — a pytest
 * parses this file and fails on drift). privroad carries the
 * quiet-kind halfM (metres).
 */
export const G17R_CAL = {
  privroad: { halfM: 200, sigma: 0.3 },
} as const;

/**
 * privroad: nearest-source calmness 100·d/(d+halfM) (quiet-kind,
 * G05C/G07/G08 precedent — green AWAY from the burden).
 */
export const GROUP17REST_BONUS: Record<Group17RestLayerId, BonusSpec> = {
  privroad: { kind: "quiet", halfM: 200 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup17RestLayerId(layer: string): layer is Group17RestLayerId {
  return (GROUP17REST_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-17-rest bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup17Rest(layer: string): BonusSpec | undefined {
  return (GROUP17REST_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 17-rest layer (built by batch_g17_rest.py). */
export const G17R_RASTER_FILE: Record<Group17RestLayerId, string> = {
  privroad: "privroad-walk-raster.json",
};

/**
 * NO metro master (documented): a smooth distance-decay field at
 * 9.375 m cells would be fake precision. The window route serves
 * county everywhere for this layer (metro slot stays empty, like
 * G07B/G03D/G08B/G05C).
 */
export const G17R_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group17RestHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function group17RestQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group17RestPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM).
 */
export function group17RestQuietnessAt(
  layer: "privroad",
  lat: number,
  lon: number,
  points: Group17RestPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group17RestHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group17RestQuietFromHalf(best * 1000, G17R_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group17RestMatchesContract(
  layer: Group17RestLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G17R_CAL[layer].halfM && doc.sigma === G17R_CAL[layer].sigma;
}

export type Group17RestVerdictKind = "proxy" | "real" | "no-map";

export interface Group17RestVerdict {
  param: Group17RestParam;
  name: string;
  kind: Group17RestVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 17 HOA-rest (the no-map rows are the
 * docs evidence; scorer dims live in
 * services/scoring/dims_group17rest.py).
 */
export const G17R_VERDICTS: Group17RestVerdict[] = [
  {
    param: 4,
    name: "Maintenance costs",
    kind: "no-map",
    reason:
      "A per-KÜ EUR fact (the annual-report maintenance line); zero cost keys exist anywhere in the snapshot — a proximity gradient cannot price another building's upkeep.",
  },
  {
    param: 49,
    name: "HOA restrictions",
    kind: "no-map",
    reason:
      "A per-KÜ rulebook fact (house rules live in the KÜ põhikiri); the snapshot carries zero rulebook keys — a proximity gradient cannot read another building's rules.",
  },
  {
    param: 142,
    name: "HOA financial reserves",
    kind: "no-map",
    reason:
      "A per-KÜ EUR fact (the remondifond balance); zero reserve keys exist anywhere in the snapshot — a proximity gradient cannot audit another building's fund.",
  },
  {
    param: 145,
    name: "Vehicle restrictions",
    kind: "no-map",
    reason:
      "Per-KÜ parking/vehicle rules, not municipal traffic orders: mapped motor_vehicle/access restrictions are KOV orders (Old Town pedestrian zone, park paths) — consuming them would relabel city orders as HOA policy.",
  },
  {
    param: 152,
    name: "Condo owner-occupancy ratios",
    kind: "no-map",
    reason:
      "A per-building demographic fact (owner vs tenant share); the snapshot carries zero tenure keys — a proximity gradient cannot survey who lives next door.",
  },
  {
    param: 167,
    name: "Trash and recycling etiquette",
    kind: "no-map",
    reason:
      "Per-HOA behaviour (whether bins are sorted on time), not bin proximity — and waste-point proximity is already scored twice (compost p187 + leafdrop p312, G17A) plus general drop-offs (p54), so a third waste gradient would duplicate them.",
  },
  {
    param: 245,
    name: "Private road maintenance",
    kind: "proxy",
    reason:
      "Shipped as privroad: nearness to 1086 mapped shared private roads (541 in Tallinn — Tiskrevälja, Kakumäe/Merirahu, Viimsi erateed) as upkeep-burden hinnang — honestly labelled, never a KÜ teehooldus agreement; parking lots, pitches and private driveways are out (not shared roads).",
  },
  {
    param: 246,
    name: "HOA special assessment history",
    kind: "no-map",
    reason:
      "A per-KÜ EUR fact (one-off owner levies for big repairs); zero levy keys exist anywhere in the snapshot — a proximity gradient cannot recall another building's levies.",
  },
  {
    param: 247,
    name: "Utility sub-metering",
    kind: "no-map",
    reason:
      "A per-building metering fact (per-flat meters vs building total); the snapshot carries zero metering keys — a proximity gradient cannot read another building's meters.",
  },
  {
    param: 278,
    name: "Shared maintenance phrasing",
    kind: "no-map",
    reason:
      "Listing-text NLP (how the ad phrases upkeep), not a place field at all — there is no geography to map, only words on the listing.",
  },
  {
    param: 368,
    name: "HOA rental caps",
    kind: "no-map",
    reason:
      "A per-KÜ rulebook fact (üüripiirang in the põhikiri); the snapshot carries zero rulebook keys — a proximity gradient cannot read another building's rental cap.",
  },
  {
    param: 427,
    name: "HOA initiation fees",
    kind: "no-map",
    reason:
      "A per-KÜ EUR fact (the sisseastumismaks a buyer pays once); zero fee keys exist anywhere in the snapshot — a proximity gradient cannot price another building's entry fee.",
  },
];

/** Batch-rest params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP17REST_NO_MAP_PARAMS: number[] = G17R_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP17REST_HOOK =
  "G17R-HOOK (#196): privroad wired into layers/overlays/snapshot; p4/p49/p142/p145/p152/p167/p246/p247/p278/p368/p427 verdicts + dims only.";
