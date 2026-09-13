// Group 8 flood/climate-C layers (parameters3.md §5.8, issue #169):
// p334 ships as an honest surge-exposed-street hinnang ("surgeroad"),
// p336 ships as an honest cliff/slope-proximity hinnang ("slidebuf");
// p371/p372 are documented no-map with scorer dims (see G08C_VERDICTS).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100; unknown stays 255 (renders red). This file owns ALL G08C
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked
// `G08C-HOOK (#169)` blocks, so the sibling batches stay disjoint
// (G03 drainage #151 and G03D shoredist #154 own different files,
// different ids, different params — see the no-reskin notes below).
//
// HONESTY (load-bearing): the Keskkonnaagentuur flood-hazard WFS
// (Üleujutusohuga alad 10/50/100/1000yr), EFAS/CMEMS reanalyses,
// Ilmateenistus gauge series, EFFIS burn perimeters and any
// flood-compensation/buyout register are NOT in the snapshot, so
// NEITHER shipped layer is measured hazard data:
// * surgeroad is a mapped-street *hinnang* — nearness to OSM-mapped
//   carriageways inside the ≤150 m surge band of the MAPPED shoreline
//   (Pirita tee, Reidi tee, Uus-Sadama, Regati pst, Merivälja tee all
//   have vertices in the band). Tallinn's tide range is centimetres;
//   the real street-impassability hazard is Baltic storm surge, and
//   without gauges/DEM the honest signal is WHICH mapped streets sit
//   in the surge band — never a flood map or a passability forecast.
// * slidebuf is a mapped-slope *hinnang* — nearness to OSM-mapped
//   natural=cliff lines (261 county ways, several named: Leetse pank,
//   Kakumäe pank, the Lasnamäe/Maarjamäe and Toompea klint edges) plus
//   natural=earth_bank (20 features, same slope-failure family).
//   Avalanches do not occur in flat Estonia; the mappable half of the
//   param is klint/river-bluff collapse (Türisalu 2023 precedent).
//   Never a geotechnical slide-risk ruling.
//
// NO-RESKIN (reviewer notes — why these are not shoredist/drainage
// duplicates, OTA PR #131 precedent would reject a re-skin):
// * surgeroad vs p340 shoredist (#154): shoredist scores distance to
//   WATER (parcel setback); surgeroad scores distance to EXPOSED
//   STREETS (route impassability). Cliff coast with no road (e.g. the
//   Türisalu pank shore) reads red on shoredist but clean on
//   surgeroad; inland both read high. Different question, visibly
//   different map along roadless shore.
// * slidebuf vs p50 drainage (#151): drainage scores distance to
//   water/wetland (rivers INCLUDED); slidebuf scores distance to
//   mapped STONE slopes (261 cliff lines, rivers/wetlands excluded).
//   The Pirita-river corridor reads mid on drainage and clean on
//   slidebuf — the two maps visibly disagree there by construction.
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p371 burn scar mudslide risk: needs EFFIS-style burn perimeters.
//   natural=burnt has ZERO features in the snapshot and no fire-scar
//   survey exists there; Estonia is flat with small rare fires, so
//   there is no post-fire mudslide mechanism to map either. Scorer
//   dim stays NULL with a forest-service check reason
//   (dims_group08c.dim_burnscar).
// * p372 FEMA buyout history: FEMA buyouts are US-only; the Estonian
//   equivalent (flood-compensation payouts / kindlustus claim history)
//   has no public register in the snapshot — the 11 office=insurance
//   objects are sales points, not payout history, and using them as a
//   "buyout" signal would be fake precision. Scorer dim stays NULL
//   with a kindlustus/KOV check reason (dims_group08c.dim_buyout).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/natural=cliff nwr/natural=earth_bank  -> 270 features
//     (261 LineStrings incl. named pangad + 8 Points + 1 MultiPolygon;
//     144 features touch the Tallinn window 24.5-24.9/59.35-59.5)
//   nwr/natural=coastline -> 105376 vertices (shore gate input)
//   w/highway=motorway|trunk|primary|secondary|tertiary|residential|
//     service|unclassified -> 63610 county ways / 374224 nodes; in the
//     Tallinn-coast slice 24.75-24.85/59.42-59.49, 3524 vertices sit
//     ≤150 m from shore on named streets (Pirita tee 130, Reidi tee
//     82, Uus-Sadama 57, Regati pst 31, Merivälja tee 23).
//   Considered and REJECTED: flood_prone=yes (12 features, all forest
//     tracks/fords — zero streets, so it cannot answer street
//     impassability); hazard=flood (0); natural=burnt (0).
//   Footways/cycleways/tracks/paths are OUT of the surge predicate by
//   design: the param asks about STREET impassability (carriageways),
//   and trail flooding is a different buyer question.
//
// Calibration (judgment calls, documented for the reviewer):
// * surgeroad (p334): exact-grid Dijkstra distance to the nearest
//   surge-band street cell, score 100·d/(d+150). The 150 m halfM is
//   the surge band itself (SURGE_BAND_M in the builder): on an exposed
//   street the score is 0, one band-width inland it is 50. A tighter
//   half (100, shoredist's) would paint whole coastal districts red
//   and stop discriminating WHICH streets; a looser half would wash
//   the band out. Sigma 0.3 (county-smooth, shoredist parity).
// * slidebuf (p336): exact-grid Dijkstra distance to the nearest
//   cliff/earth_bank cell, score 100·d/(d+100). halfM=100 m tracks
//   klint-debris runout plus margin (Türisalu-scale fans are tens of
//   metres; 100 m keeps the red zone on the slope, amber to ~300 m).
//   Mirrors scripts/build/batch_g08c_flood.py G08C_CAL exactly (a
//   pytest parses this file and fails on drift).

import type { BonusSpec, LayerDef } from "./layers";

export type Group08CLayerId = "surgeroad" | "slidebuf";

export const GROUP08C_LAYER_IDS: Group08CLayerId[] = ["surgeroad", "slidebuf"];

/** parameters3.md number per Group-8C layer (no-map params have no layer). */
export const GROUP08C_PARAM_IDS: Record<Group08CLayerId, number> = {
  surgeroad: 334,
  slidebuf: 336,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP08C_ALL_PARAMS = [334, 336, 371, 372] as const;

export type Group08CParam = (typeof GROUP08C_ALL_PARAMS)[number];

export const GROUP08C_LAYERS: LayerDef[] = [
  {
    id: "surgeroad",
    paramIds: [334],
    title: "Rannikutänavad (kõrgvee proksi, hinnang)",
    goodLabel: "roheline = tormilainetuse tsoonist kaugel (proksi, hinnang)",
    badLabel: "punane = lainetustsooni tänava ääres — kõrgveega läbipääsmatu (proksi, hinnang)",
    source:
      "kohalik hetktõmmis 2026-09-12 (rannajoonest ≤150 m kaardistatud sõiduteed: Pirita tee, Reidi tee jt — tänava-läheduse hinnang; see EI OLE üleujutuskaart ega läbitavusprognoos)",
    fallbackPoints: [
      { lat: 59.46048, lon: 24.81723 }, // Pirita tee (lainetustsooni tänaval)
      { lat: 59.39, lon: 24.68 }, // Nõmme keskus (rannast ~4,4 km, tsoonist väljas)
    ],
  },
  {
    id: "slidebuf",
    paramIds: [336],
    title: "Kaljud ja järsakud (varingu proksi, hinnang)",
    goodLabel: "roheline = järsakutest kaugel (varingu proksi, hinnang)",
    badLabel: "punane = kalju või järsaku ääres (varingu proksi, hinnang)",
    source:
      "kohalik hetktõmmis 2026-09-12 (kaardistatud pangad 261 joont + järsakud — kauguse-hinnang; see EI OLE geoloogiline varingurisk ega laviinikaart)",
    fallbackPoints: [
      { lat: 59.44208, lon: 24.80809 }, // Lasnamäe panga serv (järsaku ääres)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (järsakutest ~14 km kaugusel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 8C layer (documents the source tags;
 * the app serves the frozen snapshot, never live Overpass). n[ shape:
 * the shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped cliffs and the coastline). The builder
 * consumes the same predicate offline (see is_surge_road /
 * is_slide_source in scripts/build/batch_g08c_flood.py); the ≤150 m
 * surge gate is applied offline against the mapped shoreline, never in
 * the QL. flood_prone=yes is OUT by design (12 forest-track features,
 * zero streets); footways/tracks/paths are OUT (carriageways only).
 */
export const GROUP08C_TAGS: Record<Group08CLayerId, string> = {
  surgeroad:
    'n["highway"~"motorway|trunk|primary|secondary|tertiary|residential|service|unclassified"];n["natural"="coastline"];',
  slidebuf: 'n["natural"="cliff"];n["natural"="earth_bank"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP08C_DECAY: Record<Group08CLayerId, number> = {
  surgeroad: 0.3,
  slidebuf: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g08c_flood.py G08C_CAL exactly — a pytest
 * parses this file and fails on drift). Both layers carry the
 * quiet-kind halfM (metres).
 */
export const G08C_CAL = {
  surgeroad: { halfM: 150, sigma: 0.3 },
  slidebuf: { halfM: 100, sigma: 0.3 },
} as const;

/**
 * surgeroad + slidebuf: nearest-source goodness 100·d/(d+halfM)
 * (quiet-kind, G03 drainage/shoredist precedent).
 */
export const GROUP08C_BONUS: Record<Group08CLayerId, BonusSpec> = {
  surgeroad: { kind: "quiet", halfM: 150 },
  slidebuf: { kind: "quiet", halfM: 100 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup08CLayerId(layer: string): layer is Group08CLayerId {
  return (GROUP08C_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-8C bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup08C(layer: string): BonusSpec | undefined {
  return (GROUP08C_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 8C layer (built by batch_g08c_flood.py). */
export const G08C_RASTER_FILE: Record<Group08CLayerId, string> = {
  surgeroad: "surgeroad-walk-raster.json",
  slidebuf: "slidebuf-walk-raster.json",
};

/**
 * NO metro masters (documented): smooth distance-decay fields at
 * 9.375 m cells would be fake precision. The window route serves
 * county everywhere for these layers (metro slot stays empty, like
 * G02B/G03/G03D).
 */
export const G08C_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group08cHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source goodness 0..100: 0 at the source, 50 at halfM. */
export function group08cQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group08CPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback goodness 0..100 (raster missing). Null when there
 * is nothing to score — never a faked zero. Mirrors the Python
 * builder's score_distance exactly (same per-layer halfM).
 */
export function group08cQuietnessAt(
  layer: Group08CLayerId,
  lat: number,
  lon: number,
  points: Group08CPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group08cHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group08cQuietFromHalf(best * 1000, G08C_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group08cMatchesContract(
  layer: Group08CLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G08C_CAL[layer].halfM && doc.sigma === G08C_CAL[layer].sigma;
}

export type Group08CVerdictKind = "proxy" | "real" | "no-map";

export interface Group08CVerdict {
  param: Group08CParam;
  name: string;
  kind: Group08CVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 8 batch C (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group08c.py).
 */
export const G08C_VERDICTS: Group08CVerdict[] = [
  {
    param: 334,
    name: "High-tide street impassability",
    kind: "proxy",
    reason:
      "Shipped as surgeroad: nearness to mapped carriageways inside the ≤150 m surge band of the mapped shoreline (Pirita tee, Reidi tee, Uus-Sadama all have band vertices) — Tallinn's tide is centimetres, surge is the hazard; honestly labelled, never a flood map or passability forecast. flood_prone=yes rejected (12 forest tracks, zero streets).",
  },
  {
    param: 336,
    name: "Avalanche or mudslide buffer",
    kind: "proxy",
    reason:
      "Shipped as slidebuf: nearness to 261 mapped natural=cliff lines (named pangad: Leetse, Kakumäe, Lasnamäe/Maarjamäe, Toompea) + earth_bank — avalanches do not occur in Estonia, the mappable half is klint-collapse buffer; honestly labelled, never a geotechnical ruling.",
  },
  {
    param: 371,
    name: "Burn scar mudslide risk",
    kind: "no-map",
    reason:
      "Needs burn perimeters; natural=burnt has zero features in the snapshot and no fire-scar survey exists there — flat Estonia with small rare fires has no post-fire mudslide mechanism to map.",
  },
  {
    param: 372,
    name: "FEMA buyout history",
    kind: "no-map",
    reason:
      "FEMA buyouts are US-only; the Estonian equivalent (flood-compensation payouts / kindlustus claim history) has no public register in the snapshot — the 11 office=insurance objects are sales points, not payout history, and using them would be fake precision.",
  },
];

/** Batch-C params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP08C_NO_MAP_PARAMS: number[] = G08C_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP08C_HOOK =
  "G08C-HOOK (#169): surgeroad + slidebuf wired into layers/overlays/snapshot; p371/p372 verdicts + dims only.";
