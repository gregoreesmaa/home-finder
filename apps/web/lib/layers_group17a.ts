// Group 17 municipal-services-A layers (parameters3.md §5.17, issue #177):
// p187 ships as an honest composting-station count hinnang ("compost"),
// p311 ships as an honest grit-bin winter-service count hinnang
// ("gritbin"), p312 ships as an honest green-waste drop-off count
// hinnang ("leafdrop"); p60/p347 are documented no-map with scorer
// dims (see G17A_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = serviced (green = near mapped service, red = far /
// unknown); unknown stays 255 (renders red). This file owns ALL G17A
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `G17A-HOOK (#177)`
// blocks, so the sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Tallinna Linnavalitsus / KOV service
// registers — waste-collection calendars, street plow-priority classes
// (hooldusklassid), courtyard bin-enclosure records — are NOT in the
// 2026-09-12 snapshot, so NONE of the three shipped layers is registry
// data:
// * compost is a mapped-station *hinnang* — nearness to OSM-mapped
//   recycling centres accepting green/garden waste (the city's
//   jäätmejaamad: Pääsküla, Rahumäe, Pärnamäe, Paljassaare, …) plus
//   mapped bio/food-waste collection points, never a municipal
//   composting-capacity ruling.
// * gritbin is a mapped-grit-bin *hinnang* — count of OSM-mapped
//   grit bins (liivakastid) nearby. Bins sit on city-maintained
//   winter-service streets, so the kernel marks serviced streets —
//   but it is NOT the city's plow-priority register, and it says so.
//   Deliberately NOT a road-class field: p446 (snowplow berms,
//   services/scoring/dims_group18veg.py) already scores road class
//   INVERTED (near arterials = berm burden); a second road-class
//   gradient would duplicate it with the arrow flipped.
// * leafdrop is a mapped-drop-off *hinnang* — count of OSM-mapped
//   green/garden-waste recycling points + green-accepting household
//   waste points nearby, never a municipal collection-route ruling.
//   The 555 untagged waste_disposal litter/dog bins are OUT by design
//   (a litter bin is not yard-waste collection).
//
// Overlap (documented, ehitus/buildout G05A+G05B precedent — same
// source, different buyer question): the 18 green centres and the
// food+green containers sit in BOTH the compost and the leafdrop
// source sets (a jäätmejaam both composts and takes yard waste).
// Neither overlaps the p54 taara/waste drop-off layer's general
// containers: compost/leafdrop keep ONLY green/garden/bio-tagged
// features, plain paper/glass/plastic containers stay p54's.
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — schedule and
// per-parcel facts ship as scorer NULLs, never gradients):
// * p60 municipal service schedules: a per-district SCHEDULE fact
//   (collection calendars live with the operators). No schedule keys
//   exist anywhere in the snapshot — a proximity gradient cannot
//   discriminate a calendar. Scorer dim stays NULL with an operator
//   reason (dims_group17a.dim_sched).
// * p347 garbage-can concealment: a per-parcel COURTYARD fact (whether
//   bins sit screened in an enclosure). The snapshot carries zero
//   enclosure keys — a proximity gradient cannot discriminate a
//   courtyard attribute. Scorer dim stays NULL with a viewing reason
//   (dims_group17a.dim_binconceal).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/amenity=recycling nwr/amenity=waste_disposal
//     nwr/amenity=waste_transfer_station nwr/amenity=grit_bin
//   1899 features; the keep_compost predicate (green/garden centre or
//   bio/food-waste recycling) keeps 44 county-wide (35 in the Tallinn
//   window: Pääsküla/Rahumäe/Pärnamäe/Paljassaare jäätmejaamad +
//   bio-containers); the keep_leaf predicate (any green/garden
//   recycling + green-accepting household waste_disposal) keeps 131
//   county-wide (122 in the Tallinn window); the keep_grit predicate
//   (amenity=grit_bin) keeps 30 county-wide (25 in the Tallinn
//   window). 555 untagged waste_disposal bins drop out BY DESIGN.
//   osmium tags-filter ... w/highway=motorway w/highway=trunk
//     w/highway=primary w/highway=secondary  (+ the same grit_bin
//   nwr/ clause)  7917 features incl. referenced member nodes; the
//   arterial ways (2650 secondary + 1232 trunk + 1099 primary,
//   corroborating dims_group18veg.py's 4979-arterial probe) are
//   DOCUMENTED but not consumed — road class already scores inverted
//   as p446 berms (see HONESTY above).
//   winter_service=* tags: ZERO in the snapshot; Tallinna
//   hooldusklassid: not in the snapshot registries.
//
// Calibration (judgment calls, documented for the reviewer): all three
// layers are area-kind count kernels (Gaussian sigma 0.3, score
// 100·S/(S+1), viewshed/moorage precedent): ONE mapped feature already
// reads 50 on its own cell instead of vanishing, and feature deserts
// read honestly unknown. Sigmas equal the Euclidean fallback decay
// (DECAY hook) and the raster contract (matchesContract). Halves live
// in G17A_CAL below and in scripts/build/batch_g17_a.py G17A_CAL
// (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group17ALayerId = "compost" | "gritbin" | "leafdrop";

export const GROUP17A_LAYER_IDS: Group17ALayerId[] = ["compost", "gritbin", "leafdrop"];

/** parameters3.md number per Group-17A layer (no-map params have no layer). */
export const GROUP17A_PARAM_IDS: Record<Group17ALayerId, number> = {
  compost: 187,
  gritbin: 311,
  leafdrop: 312,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP17A_ALL_PARAMS = [60, 187, 311, 312, 347] as const;

export type Group17AParam = (typeof GROUP17A_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP17A_LAYERS: LayerDef[] = [
  {
    id: "compost",
    paramIds: [187],
    title: "Kompostimine ja jäätmejaamad (hinnang)",
    goodLabel: "roheline = jäätmejaama / biokogumise lähedal (hinnang)",
    badLabel: "punane = kompostitaristust kaugel või kaardistamata (hinnang)",
    source: `${SNAP} (kaardistatud 18 haljasjäätmeid vastuvõtvat jäätmejaama — Pääsküla, Rahumäe, Pärnamäe, Paljassaare jt — + 26 bio-/toidujäätmete kogumispunkti = 44 objekti, sh Tallinnas 35; PROKSI-hinnang läheduse järgi — see EI OLE linna kompostimisvõimsuse register)`,
    fallbackPoints: [
      { lat: 59.36103, lon: 24.64352 }, // Pääsküla jäätmejaam (jaama lähedal)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (jaamadest kaugel)
    ],
  },
  {
    id: "gritbin",
    paramIds: [311],
    title: "Talvine libedustõrje (hinnang)",
    goodLabel: "roheline = talvise hoolduse punkti (liivakasti) lähedal (hinnang)",
    badLabel: "punane = hoolduspunktidest kaugel, sahajärjekord teadmata (hinnang)",
    source: `${SNAP} (kaardistatud 30 liivakasti hooldatavatel tänavatel, sh Tallinnas 25; hõre, kuid aus talvise hoolduse PROKSI-hinnang — see EI OLE linna sahaplaan / hooldusklasside register; teesklass on juba p446 sahavallide all)`,
    fallbackPoints: [
      { lat: 59.428, lon: 24.83925 }, // Liivakast Lasnamäel (hoolduse lähedal)
      { lat: 59.51, lon: 24.83 }, // Viimsi (hoolduspunktidest kaugel)
    ],
  },
  {
    id: "leafdrop",
    paramIds: [312],
    title: "Lehe- ja aiajäätmete kogumine (hinnang)",
    goodLabel: "roheline = haljasjäätmete kogumispunkti lähedal (hinnang)",
    badLabel: "punane = kogumispunktidest kaugel või kaardistamata (hinnang)",
    source: `${SNAP} (kaardistatud 77 haljasjäätmete taarapunkti + 54 haljasjäätmeid vastuvõtvat majapidamispunkti = 131 objekti, sh Tallinnas 122; 555 sildistamata prügikasti VÄLJA — prügikast ei ole aiajäätmete kogumine; PROKSI-hinnang — see EI OLE linna veograafik)`,
    fallbackPoints: [
      { lat: 59.39576, lon: 24.66856 }, // Haljasjäätmete konteiner Mustamäel (punkti lähedal)
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (kogumispunktidest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 17A layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped jäätmejaam areas). The builder consumes the
 * same predicate offline (see keep_compost / keep_grit / keep_leaf);
 * the green/bio-tag checks live in the scorer mapping (kinds_from_tags),
 * so the fragment stays a plain source-tags query like sibling batches.
 */
export const GROUP17A_TAGS: Record<Group17ALayerId, string> = {
  compost: 'n["amenity"="recycling"];n["recycling:green_waste"="yes"];n["recycling:food_waste"="yes"];',
  gritbin: 'n["amenity"="grit_bin"];',
  leafdrop: 'n["amenity"="recycling"];n["amenity"="waste_disposal"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP17A_DECAY: Record<Group17ALayerId, number> = {
  compost: 0.3,
  gritbin: 0.3,
  leafdrop: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g17_a.py G17A_CAL exactly — a pytest
 * parses this file and fails on drift). All three carry the area-kind
 * half (saturating count, viewshed/moorage precedent).
 */
export const G17A_CAL = {
  compost: { half: 1, sigma: 0.3 },
  gritbin: { half: 1, sigma: 0.3 },
  leafdrop: { half: 1, sigma: 0.3 },
} as const;

/**
 * All three: nearby-service count 100·S/(S+half) (area-kind,
 * viewshed/moorage precedent — green NEAR the service).
 */
export const GROUP17A_BONUS: Record<Group17ALayerId, BonusSpec> = {
  compost: { kind: "area", half: 1 },
  gritbin: { kind: "area", half: 1 },
  leafdrop: { kind: "area", half: 1 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup17ALayerId(layer: string): layer is Group17ALayerId {
  return (GROUP17A_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-17A bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup17A(layer: string): BonusSpec | undefined {
  return (GROUP17A_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 17A layer (built by batch_g17_a.py). */
export const G17A_RASTER_FILE: Record<Group17ALayerId, string> = {
  compost: "compost-walk-raster.json",
  gritbin: "gritbin-walk-raster.json",
  leafdrop: "leafdrop-walk-raster.json",
};

/**
 * NO metro masters (documented): sparse count kernels at 9.375 m cells
 * would be fake precision. The window route serves county everywhere
 * for these layers (metro slot stays empty, like G07B/G03D/G08B/G05C).
 */
export const G17A_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group17aHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface Group17APoint {
  lat: number;
  lon: number;
}

/**
 * Area-kind saturating score 100·S/(S+half) (mirrors
 * walk_raster.saturate). Exported for the Euclidean fallback path.
 */
export function group17aAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group17aMatchesContract(
  layer: Group17ALayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G17A_CAL[layer].half && doc.sigma === G17A_CAL[layer].sigma;
}

export type Group17AVerdictKind = "proxy" | "real" | "no-map";

export interface Group17AVerdict {
  param: Group17AParam;
  name: string;
  kind: Group17AVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 17 batch A (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group17a.py).
 */
export const G17A_VERDICTS: Group17AVerdict[] = [
  {
    param: 60,
    name: "Municipal service schedules",
    kind: "no-map",
    reason:
      "A per-district schedule fact (collection calendars live with the operators); the snapshot carries zero schedule keys, so a proximity gradient cannot discriminate a calendar.",
  },
  {
    param: 187,
    name: "Municipal composting infrastructure",
    kind: "proxy",
    reason:
      "Shipped as compost: count of 44 mapped bio/composting features nearby (18 green-accepting jäätmejaamad — Pääsküla, Rahumäe, Pärnamäe, Paljassaare — + 26 bio/food-waste collection points, 35 in Tallinn) as service hinnang, area-kind like viewshed/moorage — honestly labelled, never a municipal capacity ruling.",
  },
  {
    param: 311,
    name: "Snow plowing priority",
    kind: "proxy",
    reason:
      "Shipped as gritbin: count of 30 mapped grit bins nearby (25 in Tallinn) as winter-service hinnang, area-kind like viewshed — thin but honest; deliberately not a road-class field because road class already scores inverted as p446 berms, and winter_service tags plus the hooldusklass register are both absent from the snapshot.",
  },
  {
    param: 312,
    name: "Leaf collection and yard waste",
    kind: "proxy",
    reason:
      "Shipped as leafdrop: count of 131 mapped green-waste drop-offs nearby (77 green recycling points + 54 green-accepting household points, 122 in Tallinn) as collection hinnang, area-kind like viewshed — honestly labelled, never a municipal route ruling; 555 untagged litter bins are out (a litter bin is not yard-waste collection).",
  },
  {
    param: 347,
    name: "Garbage can storage concealment",
    kind: "no-map",
    reason:
      "A per-parcel courtyard fact (whether bins sit screened in an enclosure); the snapshot carries zero enclosure keys, so a proximity gradient cannot discriminate a courtyard attribute.",
  },
];

/** Batch-A params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP17A_NO_MAP_PARAMS: number[] = G17A_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP17A_HOOK =
  "G17A-HOOK (#177): compost + gritbin + leafdrop wired into layers/overlays/snapshot; p60/p347 verdicts + dims only.";
