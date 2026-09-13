// Group 5 plans-E layers (parameters3.md §5.5, issue #165): p381 ships
// as an honest riding-facility proximity hinnang ("equestrian");
// p365/p382/p384/p387 are documented no-map with scorer dims (see
// G05E_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = good access (green = near mapped riding facilities,
// red = far/unknown); unknown stays 255 (renders red). This file owns
// ALL G05E runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts) touch it only through small
// marked `G05E-HOOK (#165)` blocks, so the sibling batches stay
// disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Rahandusministeerium PLANK register, the
// Tallinna Planeeringute Register, any multi-family conversion-zoning
// table, any 55+ community register and any agrihood developer plan
// are NOT in the 2026-09-12 snapshot, so the shipped layer is NOT a
// planned-community map:
// * equestrian is a mapped-facility *hinnang* — count of OSM-mapped
//   riding centres (leisure=horse_riding), equestrian pitches
//   (sport=equestrian, mostly leisure=pitch arenas), stable buildings
//   (building=stable) and bridleways (highway=bridleway) nearby —
//   never a KOV zoning decision and never a riding-community
//   membership list. The param names arenas + stables + bridle trails
//   explicitly, so all four tags are the param's own inventory.
//   Unmapped farm paddocks do not count (said in the source line).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p365 multi-family conversion zoning: a per-parcel LEGAL fact (does
//   THIS lot's zoning allow a duplex/triplex conversion?). PLANK/TPR
//   hold plan geometries, never conversion-pathway rulings, and the
//   snapshot carries zero zoning keys — a proximity gradient cannot
//   discriminate a parcel legal status (p221 eminent-domain precedent,
//   G05C). Scorer dim stays NULL with a KOV-register reason
//   (dims_group05e.dim_multifam).
// * p382 fly-in residential airparks: small-airfield proximity is
//   already scored TWICE (flightcorr p445 corridors + droneclear p220
//   aerodrome distance), so a third airfield gradient would duplicate
//   them (p222 flight re-routing precedent, G05C) — and no fly-in
//   residential community exists in the snapshot area to calibrate
//   against. Scorer dim stays NULL with a Lennuamet reason
//   (dims_group05e.dim_flyin).
// * p384 55+ age-restricted enforcement: a COMMUNITY-RULES legal fact
//   (does THIS development bar younger residents?). No OSM key records
//   age restrictions anywhere in the PBF. Scorer dim stays NULL with
//   a register-check reason (dims_group05e.dim_age55).
// * p387 agrihoods: the growing-soil halves of the concept are already
//   scored TWICE (gardens p106 allotments/community-gardens, G05B +
//   agrifield p409 farmland/orchard, G07D), and no OSM key records
//   master-planned residential communities — a third growing-land
//   gradient would duplicate them (p222-style duplicate precedent).
//   Scorer dim stays NULL with a pointer at those two layers
//   (dims_group05e.dim_agrihood).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/leisure=horse_riding nwr/sport=equestrian
//     nwr/highway=bridleway nwr/building=stable   (+ export)
//   86 features; the keep_equi predicate (leisure horse_riding OR
//   sport equestrian OR highway bridleway OR building stable, see
//   scripts/build/batch_g05e_plans.py) keeps all 86 (~46 unique sites:
//   osmium export doubles closed ways as LineString + MultiPolygon
//   twins; the builder's 20 m cell dedupe collapses them — 15 in the
//   Tallinn window: Veskimetsa ratsakeskus, Vääna tallid, Lagedi
//   Ratsaspordikool, Jüri Tall, Suuresti tall + arena pitches).
//   leisure=pitch WITHOUT sport=equestrian stays OUT by design (a
//   football pitch is not an arena — the sport tag carries the
//   equestrian meaning).
//
// Calibration (judgment calls, documented for the reviewer):
// equestrian is an area-kind count kernel (Gaussian sigma 0.3, score
// 100·S/(S+1), viewshed/moorage/gardens precedent): ONE mapped riding
// facility already reads 50 on its own cell instead of vanishing.
// Green sits NEAR the amenity (access likely). Sigma equals the
// Euclidean fallback decay (DECAY hook) and the raster contract
// (matchesContract). Halves live in G05E_CAL below and in
// scripts/build/batch_g05e_plans.py G05E_CAL (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group05ELayerId = "equestrian";

export const GROUP05E_LAYER_IDS: Group05ELayerId[] = ["equestrian"];

/** parameters3.md number per Group-5E layer (no-map params have no layer). */
export const GROUP05E_PARAM_IDS: Record<Group05ELayerId, number> = {
  equestrian: 381,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP05E_ALL_PARAMS = [365, 381, 382, 384, 387] as const;

export type Group05EParam = (typeof GROUP05E_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP05E_LAYERS: LayerDef[] = [
  {
    id: "equestrian",
    paramIds: [381],
    title: "Ratsutamisvõimalus (hinnang)",
    goodLabel: "roheline = ratsakeskuse/talli lähedal, ratsavõimalus hea (hinnang)",
    badLabel: "punane = ratsutamisaladest kaugel, võimalus teadmata (hinnang)",
    source: `${SNAP} (kaardistatud 46 ratsutamisobjekti: ratsakeskused + maneežid + tallid + ratsateed, sh Tallinnas 15 — Veskimetsa, Lagedi, Jüri; kaardistamata talliplatsid ei loe; juurdepääsu PROKSI-hinnang läheduse järgi, küllastus 1 — see EI OLE KOV planeeringute register ega ratsakogukonna nimekiri)`,
    fallbackPoints: [
      { lat: 59.42642, lon: 24.66428 }, // Veskimetsa ratsakeskus (rajatise ääres)
      { lat: 59.36, lon: 24.66 }, // Nõmme (ratsutamisaladest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 5E layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped arenas and stable campuses). The builder
 * consumes the same predicate offline (see keep_equi); the pitch
 * exclusion (leisure=pitch needs sport=equestrian) lives in the scorer
 * mapping (kinds_from_tags), so the fragment stays a plain source-tags
 * query like sibling batches.
 */
export const GROUP05E_TAGS: Record<Group05ELayerId, string> = {
  equestrian:
    'n["leisure"="horse_riding"];n["sport"="equestrian"];n["highway"="bridleway"];n["building"="stable"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP05E_DECAY: Record<Group05ELayerId, number> = {
  equestrian: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g05e_plans.py G05E_CAL exactly — a pytest
 * parses this file and fails on drift). Area-kind half (saturating
 * count, viewshed/moorage/gardens precedent).
 */
export const G05E_CAL = {
  equestrian: { half: 1, sigma: 0.3 },
} as const;

/**
 * equestrian: nearby-facility count 100·S/(S+half) (area-kind,
 * viewshed/moorage/gardens precedent — green NEAR the amenity).
 */
export const GROUP05E_BONUS: Record<Group05ELayerId, BonusSpec> = {
  equestrian: { kind: "area", half: 1 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup05ELayerId(layer: string): layer is Group05ELayerId {
  return (GROUP05E_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-5E bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup05E(layer: string): BonusSpec | undefined {
  return (GROUP05E_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 5E layer (built by batch_g05e_plans.py). */
export const G05E_RASTER_FILE: Record<Group05ELayerId, string> = {
  equestrian: "equestrian-walk-raster.json",
};

/**
 * NO metro masters (documented): a sparse count kernel at 9.375 m
 * cells would be fake precision. The window route serves county
 * everywhere for this layer (metro slot stays empty, like
 * G07B/G03D/G08B/G05C).
 */
export const G05E_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group05eHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Area-kind saturating score 100·S/(S+half) (mirrors walk_raster.saturate). */
export function group05eAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group05eMatchesContract(
  layer: Group05ELayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G05E_CAL[layer].half && doc.sigma === G05E_CAL[layer].sigma;
}

export type Group05EVerdictKind = "proxy" | "real" | "no-map";

export interface Group05EVerdict {
  param: Group05EParam;
  name: string;
  kind: Group05EVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 5 batch E (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group05e.py).
 */
export const G05E_VERDICTS: Group05EVerdict[] = [
  {
    param: 365,
    name: "Multi-family conversion zoning",
    kind: "no-map",
    reason:
      "A per-parcel legal fact (does this lot's zoning allow a duplex/triplex conversion?); PLANK/TPR hold plan geometries, never conversion-pathway rulings, and the snapshot carries zero zoning keys — a proximity gradient cannot discriminate a parcel legal status.",
  },
  {
    param: 381,
    name: "Equestrian community access",
    kind: "proxy",
    reason:
      "Shipped as equestrian: count of 46 mapped riding facilities nearby (15 in Tallinn — Veskimetsa, Lagedi, Jüri — riding centres + arenas + stables + bridleways, the param's own inventory) as access hinnang — honestly labelled, never a KOV zoning decision or a riding-community membership list.",
  },
  {
    param: 382,
    name: "Fly-in residential airparks",
    kind: "no-map",
    reason:
      "Small-airfield proximity is already scored twice (flightcorr p445 corridors + droneclear p220 aerodrome distance), so a third airfield gradient would duplicate them — and no fly-in residential community exists in the snapshot area to calibrate against.",
  },
  {
    param: 384,
    name: "55+ age-restricted enforcement",
    kind: "no-map",
    reason:
      "A community-rules legal fact (does this development bar younger residents?); no OSM key records age restrictions anywhere in the snapshot PBF — a proximity gradient would invent signal from nothing.",
  },
  {
    param: 387,
    name: "Agrihoods",
    kind: "no-map",
    reason:
      "The growing-soil halves of the concept are already scored twice (gardens p106 allotments/community-gardens + agrifield p409 farmland/orchard), and no OSM key records master-planned residential communities — a third growing-land gradient would duplicate them.",
  },
];

/** Batch-E params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP05E_NO_MAP_PARAMS: number[] = G05E_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP05E_HOOK =
  "G05E-HOOK (#165): equestrian wired into layers/overlays/snapshot; p365/p382/p384/p387 verdicts + dims only.";
