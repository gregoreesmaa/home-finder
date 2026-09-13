// Group 5 plans-D layers (parameters3.md §5.5, issue #164): p230 ships
// as an honest tourist-accommodation density hinnang ("strsat");
// p226/p244/p275/p280 are documented no-map with scorer dims
// (see G05D_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = calm (green = residential-calm, red = saturated);
// unknown stays 255 (renders red). This file owns ALL G05D runtime
// data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked
// `G05D-HOOK (#164)` blocks, so the sibling batches stay disjoint
// (no earlier Group 5 batch exists — this is the first).
//
// This module imports ./layers ONLY as types (AvoidSpec, BonusSpec,
// LayerDef): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the PLANK WFS (planeeringud.ee), the Tallinna
// Planeeringute Register and any Airbnb/booking listing register are
// NOT in the snapshot, so the shipped layer is NOT measured STR supply:
// * strsat is a mapped-cause *hinnang* — inverse nearness to OSM-mapped
//   tourist accommodation (tourism=apartment/guest_house/hostel/hotel/
//   motel), whose guest turnover drives the saturation pressure the
//   param names. The beds are the mapped CAUSE, never a listing count:
//   titles/legends/sources say "hinnang"/"proksi", never Airbnb figures.
//   Unmapped holiday flats do not count (said in the source line), so
//   far-from-mapped-beds reads calm with a thin-mapping caveat — the
//   scorer dim keeps the soft bands (dims_group05d.dim_strsat).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p226 heritage tree ordinances: a RESTRICTION param (protected tree
//   on/near the parcel). The whole snapshot PBF carries only 9 mapped
//   significant trees county-wide (7 denotation=natural_monument + 2
//   protected=yes; 2 in the Tallinn window) against hundreds of
//   Keskkonnaamet-protected trees — a proximity gradient would paint
//   unmapped-but-protected parcels green, the UNSAFE direction for a
//   restriction (contrast moorage #154, an opportunity param where thin
//   mapping fails safe). Scorer dim stays NULL with a register-check
//   reason (dims_group05d.dim_heritage_trees).
// * p244 non-conforming use certificate: a per-parcel legal fact (does
//   THIS lot hold a certificate?). Plan geometries cannot carry
//   certificate status and OSM has zero signal. Scorer dim stays NULL
//   with a TPR/register reason (dims_group05d.dim_nonconforming_cert).
// * p275 pre-existing non-conforming (grandfathered use): same shape as
//   p244 — a per-parcel status fact, unmapped. Scorer dim stays NULL
//   (dims_group05d.dim_preexisting_nonconforming).
// * p280 eminent domain history: needs expropriation records (Riigi
//   Teataja / KOV sundvõõrandamise otsused); OSM has zero signal, and
//   corridor geometry would score p221 RISK, not history. Scorer dim
//   stays NULL with a records-check reason
//   (dims_group05d.dim_eminent_history).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/tourism=apartment nwr/tourism=guest_house nwr/tourism=hostel
//     nwr/tourism=hotel nwr/tourism=motel   (+ export -u type_id)
//   334 features in the keep_strstay predicate (first ;-value in the
//   5-value set — hotel 168, guest_house 84, hostel 55, apartment 25,
//   motel 2; 209 in the Tallinn window, blanketing Vanalinn/Kesklinn).
//   Geometry mix: 203 Points + 74 closed footprint rings + 74
//   MultiPolygons (hotels are usually area-mapped; node-only would
//   silently drop them, PR #118). Closed rings are NOT twins —
//   footprints carry their own tourism tags; untagged members drop out
//   in keep_strstay (see scripts/build/batch_g05d_plans.py).
//   Tree check (p226 no-map evidence):
//   osmium tags-filter ... nwr/natural=tree -> 43522 features, but only
//   7 carry denotation=natural_monument and 2 more protected=yes — 9
//   significant trees county-wide, 2 in the Tallinn window (Kelchi pärn
//   59.4356/24.7424 + 59.4226/24.7582). Hundreds of protected trees
//   stand unmapped: no honest gradient.
//
// Calibration (judgment calls, documented for the reviewer): strsat is
// an inverse nearest-source field (kind "avoid", G06B woodfire
// precedent): score = 100·(1−2^(−d/half)), 0 on the beds, 50 at half,
// →100 far away. Exact full-grid Dijkstra, NO cutoff (G08B machinery):
// far reads genuinely calm-green, NOT unknown-red — STR supply really
// is centre-concentrated, so Nõmme/Õismäe calm is honest (this differs
// from woodfire on purpose: unmapped wooden houses stand everywhere,
// unmapped STR clusters do not). half 0.35 km == sigma·ln2 (the
// walk-km 50-score, woodfire convention); sigma 0.5 km is the
// neighbourhood scale of guest-turnover pressure (noise, foot traffic,
// rental competition). Halves live in G05D_CAL below and in
// scripts/build/batch_g05d_plans.py G05D_CAL (kept in sync by test).
// Measured county-raster reads (2026-09-12 full build, --probe):
// Balti 14, Pelgulinn 14, Viru 26, Kalamaja 26, Pirita 47, Kadriorg
// 69, Õismäe 81, Lasnamäe 87, Nõmme 94, rural 100. The centre reads
// saturated BY DESIGN — mapped beds blanket Vanalinn/Kesklinn
// (Viru probe sits ~150 m from the nearest mapped bed, hence 26 not 0).

import type { AvoidSpec, BonusSpec, LayerDef } from "./layers";

export type Group05DLayerId = "strsat";

export const GROUP05D_LAYER_IDS: Group05DLayerId[] = ["strsat"];

/** parameters3.md number per Group-5D layer (no-map params have no layer). */
export const GROUP05D_PARAM_IDS: Record<Group05DLayerId, number> = {
  strsat: 230,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP05D_ALL_PARAMS = [226, 230, 244, 275, 280] as const;

export type Group05DParam = (typeof GROUP05D_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP05D_LAYERS: LayerDef[] = [
  {
    id: "strsat",
    paramIds: [230],
    title: "Lühiajalise üüri küllastus (proksi, hinnang)",
    goodLabel: "roheline = turismimajutust vähe, elurajooni-rahu (hinnang)",
    badLabel: "punane = turismimajutus tihe — kontrolli müra/külaliste voogu (hinnang)",
    source: `${SNAP} (kaardistatud turismimajutus 334 objekti: korterid/külalismajad/hostelid/hotellid/motellid, sh Tallinnas 209 — küllastussurve PROKSI-hinnang majutuse läheduse järgi; kaardistamata üürikorterid ei loe — see EI OLE Airbnb registri mõõtmine)`,
    fallbackPoints: [
      { lat: 59.4366, lon: 24.7449 }, // kaardistatud üürikorter Kesklinnas (küllastunud)
      { lat: 59.36, lon: 24.66 }, // Nõmme eramud (majutusest kaugel)
    ],
  },
];

/**
 * Overpass QL fragment for the strsat layer (documents the source tags;
 * the app serves the frozen snapshot, never live Overpass). n/ shape:
 * the shared overpassQueryFor() rewrites n[ to nwr/ (PR #118:
 * node-only silently drops way-mapped hotels). The builder consumes the
 * same predicate offline (see keep_strstay); the 5-value tourism check
 * lives in the scorer mapping (kinds_from_tags), so the fragment stays
 * a plain source-tags query like sibling batches.
 */
export const GROUP05D_TAGS: Record<Group05DLayerId, string> = {
  strsat: 'n["tourism"~"apartment|guest_house|hostel|hotel|motel"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP05D_DECAY: Record<Group05DLayerId, number> = {
  strsat: 0.5,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g05d_plans.py G05D_CAL exactly — a pytest
 * parses this file and fails on drift). half is the walk-km 50-score
 * (== sigma·ln2, woodfire convention).
 */
export const G05D_CAL = {
  strsat: { half: 0.35, sigma: 0.5 },
} as const;

/**
 * strsat: inverse nearest-bed saturation 100·(1−2^(−d/half))
 * (avoid-kind, G06B woodfire precedent).
 */
export const GROUP05D_BONUS: Record<Group05DLayerId, BonusSpec> = {
  strsat: { kind: "avoid", half: 0.35 } satisfies AvoidSpec,
};

/**
 * Layers scored INVERSELY (kind "avoid"): score falls with proximity.
 * Kept as an explicit set (not kind-sniffing the bonus table) so a
 * future second inverse layer is a one-line addition, and so
 * goodnessAt shares one predicate with the registry (G06B precedent).
 */
const GROUP05D_AVOID: ReadonlySet<string> = new Set(["strsat"]);

/** True for G05D inverse ("avoid") layers. Used by the goodness hook. */
export function isGroup05DAvoidLayer(layer: string): boolean {
  return GROUP05D_AVOID.has(layer);
}

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup05DLayerId(layer: string): layer is Group05DLayerId {
  return (GROUP05D_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-5D bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup05D(layer: string): BonusSpec | undefined {
  return (GROUP05D_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master file for the strsat layer (built by batch_g05d_plans.py). */
export const G05D_RASTER_FILE: Record<Group05DLayerId, string> = {
  strsat: "strsat-walk-raster.json",
};

/**
 * NO metro master (documented): a smooth inverse-distance saturation
 * field at 9.375 m cells would be fake precision. The window route
 * serves county everywhere for this layer (metro slot stays empty,
 * like G02B/G03/G03D).
 */
export const G05D_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group05dHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Inverse saturation 0..100: 0 on the beds, 50 at half km, →100 far. */
export function group05dAvoidScore(dKm: number, half: number): number {
  if (!Number.isFinite(dKm)) return 100;
  return 100 * (1 - Math.pow(2, -dKm / half));
}

export interface Group05DPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback saturation 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the Python
 * builder's score_avoid exactly (same half).
 */
export function group05dAvoidanceAt(
  layer: Group05DLayerId,
  lat: number,
  lon: number,
  points: Group05DPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group05dHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group05dAvoidScore(best, G05D_CAL[layer].half));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group05dMatchesContract(
  layer: Group05DLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G05D_CAL[layer].half && doc.sigma === G05D_CAL[layer].sigma;
}

export type Group05DVerdictKind = "proxy" | "real" | "no-map";

export interface Group05DVerdict {
  param: Group05DParam;
  name: string;
  kind: Group05DVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 5 batch D (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group05d.py).
 */
export const G05D_VERDICTS: Group05DVerdict[] = [
  {
    param: 226,
    name: "Heritage tree ordinances",
    kind: "no-map",
    reason:
      "Restriction param with thin mapping: only 9 significant trees county-wide (7 denotation=natural_monument + 2 protected=yes, 2 in Tallinn) against hundreds of Keskkonnaamet-protected trees — a gradient would paint unmapped-but-protected parcels green, the unsafe direction.",
  },
  {
    param: 230,
    name: "Short-term rental saturation",
    kind: "proxy",
    reason:
      "Shipped as strsat: inverse nearness to 334 mapped tourist beds (hotel 168 + guest_house 84 + hostel 55 + apartment 25 + motel 2, 209 in Tallinn blanketing Vanalinn/Kesklinn) as saturation-pressure hinnang — honestly labelled, never an Airbnb listing count.",
  },
  {
    param: 244,
    name: "Non-conforming use certificate",
    kind: "no-map",
    reason:
      "Per-parcel legal fact (does this lot hold a certificate?); plan geometries cannot carry certificate status and OSM has zero signal — no honest gradient exists.",
  },
  {
    param: 275,
    name: "Pre-existing non-conforming use",
    kind: "no-map",
    reason:
      "Per-parcel grandfathered-status fact like p244; unmapped in OSM and in plan geometries — no honest gradient exists.",
  },
  {
    param: 280,
    name: "Eminent domain history",
    kind: "no-map",
    reason:
      "Needs expropriation records (Riigi Teataja / KOV sundvõõrandamise otsused); OSM has zero signal, and corridor geometry would score p221 risk, not history.",
  },
];

/** Batch-D params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP05D_NO_MAP_PARAMS: number[] = G05D_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP05D_HOOK =
  "G05D-HOOK (#164): strsat wired into layers/overlays/snapshot; p226/p244/p275/p280 verdicts + dims only.";
