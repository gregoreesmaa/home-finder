// Group 3 cadastre-D layers (parameters3.md §5.3, issue #154): p332 ships
// as an honest marina/mooring-proximity hinnang ("moorage"), p340 ships
// as a real shoreline-distance layer ("shoredist"); p331/p337/p339 are
// documented no-map with scorer dims (see G03D_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100; unknown stays 255 (renders red). This file owns ALL G03D
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `G03D-HOOK (#154)`
// blocks, so the sibling batches stay disjoint.
//
// HONESTY (load-bearing): the Maa-amet cadastre WFS (parcels, permits),
// EELIS hydrological time series and hydrogeology grids are NOT in the
// snapshot, so NEITHER shipped layer is measured registry data:
// * moorage is a mapped-facility *hinnang* — nearness to OSM-mapped
//   marinas/moorings/harbours, never a dock-permit register. A permit
//   itself is a per-parcel legal fact; the layer scores mooring
//   OPPORTUNITY (existing facilities nearby), honestly labelled.
// * shoredist is distance to the MAPPED shoreline (OSM coastline +
//   standing-water polygons) — the param's own ST_Distance formula —
//   never a legal setback ruling. Green = far (outside restriction
//   zones, high development freedom), red = at/on the shore (check
//   ehituskeeluvöönd). Rivers/streams/wetlands are EXCLUDED by design:
//   they belong to p50 drainage (#151); the Pirita-river corridor is
//   where the two maps visibly disagree (mid on shoredist, low on p50).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p331 bulkhead/seawall structure: a per-structure ENGINEERING fact
//   (is the seawall sound?). OSM maps structure LOCATIONS (47
//   man_made=breakwater ways, 14 man_made=quay ways, 577 piers —
//   mostly private/cargo) with ZERO condition attributes, so a
//   proximity gradient cannot answer the question. Scorer dim stays
//   NULL with an inspection reason (dims_group03d.dim_seawall).
// * p337 lake water level fluctuation: needs gauge TIME SERIES
//   (Ülemiste etc.). The 28 man_made=monitoring_station objects carry
//   air_quality/weather/traffic tags; the only water_level mentions
//   say water_level=no. Zero signal by construction. Scorer dim stays
//   NULL with a register-check reason (dims_group03d.dim_lake_level).
// * p339 well water recharge rate: needs hydrogeology (ESDAC/KOV
//   table). Well/spring PRESENCE (28 wells + 35 springs, #152) says
//   nothing about recharge RATE, and p183 already scores indicator
//   proximity — a second gradient would duplicate it. Scorer dim stays
//   NULL with a KOV-table reason (dims_group03d.dim_recharge).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/leisure=marina nwr/seamark:type=mooring
//     nwr/seamark:type=harbour nwr/harbour=yes nwr/mooring=yes
//     nwr/man_made=pier nwr/man_made=breakwater nwr/man_made=quay
//   800 features; tight moorage predicate (see keep_moorage in
//   scripts/build/batch_g03d_cadastre.py) keeps 195 county-wide, 41 in
//   the Tallinn window (Kakumäe, Hundipea, Lennusadam/Noblessner,
//   Kalasadam, Vanasadam, Pirita, Kalevi). Bare man_made=pier (544,
//   incl. cargo/industrial + mooring=no) is OUT by design: a cargo quay
//   is not mooring opportunity. mooring=no is explicitly excluded.
//   Shore predicate reuses the G03 hydro extract (coastline 620 ways +
//   natural=water polygons); rivers/wetlands excluded (see above).
//
// Calibration (judgment calls, documented for the reviewer):
// * moorage (p332): Euclidean Gaussian count kernel (sigma 0.3 km),
//   area-kind saturating score 100·S/(S+half). Euclidean, not walk-
//   stamped, by design: marina centroids sit on water where the foot
//   graph has no vertices (verified: Pirita sadam read 255 under
//   stamp_sum). half=1 (not 2): mooring facilities are sparse (195
//   county vs 5023 high-rises), so ONE mapped marina already reads 50
//   on its own cell (mid-amber) instead of vanishing —
//   Pirita/Kalamaja/Kakumäe go green-amber, inland Nõmme/Lasnamäe read
//   honestly low.
// * shoredist (p340): exact grid Dijkstra distance, score 100·d/(d+100).
//   halfM=100 m tracks the legal zones (Veeseadus 50–100 m). Measured
//   county-raster reads (2026-09-12 full build, --probe): Pirita 0 and
//   Vanasadam 0 (probes on marina/harbour water), Kakumäe 43, Viru 77,
//   Kalamaja 78, Nõmme 84, Lasnamäe 91, rural 94. Most of Tallinn reads
//   high BY DESIGN — most of Tallinn IS outside the setback zones.
//   Mirrors scripts/build/batch_g03d_cadastre.py G03D_CAL exactly (a
//   pytest parses this file and fails on drift).

import type { BonusSpec, LayerDef } from "./layers";

export type Group03DLayerId = "moorage" | "shoredist";

export const GROUP03D_LAYER_IDS: Group03DLayerId[] = ["moorage", "shoredist"];

/** parameters3.md number per Group-3D layer (no-map params have no layer). */
export const GROUP03D_PARAM_IDS: Record<Group03DLayerId, number> = {
  moorage: 332,
  shoredist: 340,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP03D_ALL_PARAMS = [331, 332, 337, 339, 340] as const;

export type Group03DParam = (typeof GROUP03D_ALL_PARAMS)[number];

export const GROUP03D_LAYERS: LayerDef[] = [
  {
    id: "moorage",
    paramIds: [332],
    title: "Sadamad ja sildumiskohad (sildumisvõimaluse hinnang)",
    goodLabel: "roheline = sadam või sildumiskoht lähedal (hinnang)",
    badLabel: "punane = sildumiskohad kaugel või andmed puuduvad (hinnang)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM leisure=marina + seamark sildumine/sadam + harbour/mooring, 195 objekti — sildumisvõimaluse läheduse hinnang; luba ise on krundi-põhine fakt — see EI OLE lubade register)",
    fallbackPoints: [
      { lat: 59.468, lon: 24.821 }, // Pirita sadam (sildumiskoha ääres)
      { lat: 59.39, lon: 24.68 }, // Nõmme keskus (sisemaal, sildumiskohtadeta)
    ],
  },
  {
    id: "shoredist",
    paramIds: [340],
    title: "Kaugus rannajoonest (ehituskeeluvööndi hinnang)",
    goodLabel: "roheline = rannajoonest kaugel, keeluvööndist väljas (hinnang)",
    badLabel: "punane = rannajoone ääres või peal — kontrolli ehituspiiranguid (hinnang)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM rannajoon + järved/veekogud, jõed ja märgalad välja — ST_Distance kauguse-hinnang; see EI OLE õiguslik ehituskeeluotsus)",
    fallbackPoints: [
      { lat: 59.39, lon: 24.68 }, // Nõmme keskus (rannajoonest kaugel)
      { lat: 59.47, lon: 24.82 }, // Pirita rand (rannajoone ääres)
    ],
  },
];

/**
 * Overpass QL fragments per Group 3D layer (documents the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped marinas and the coastline). The builder
 * consumes the same predicate offline (see keep_moorage / keep_shore).
 * mooring=no never matches (not in the mooring value list).
 */
export const GROUP03D_TAGS: Record<Group03DLayerId, string> = {
  moorage:
    'n["leisure"="marina"];n["seamark:type"~"mooring|harbour"];n["harbour"="yes"];n["mooring"~"yes|yacht|private|declaration|commercial"];',
  shoredist: 'n["natural"="coastline"];n["natural"="water"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP03D_DECAY: Record<Group03DLayerId, number> = {
  moorage: 0.3,
  shoredist: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g03d_cadastre.py G03D_CAL exactly — a pytest
 * parses this file and fails on drift). moorage carries the area-kind
 * half (saturating count), shoredist the quiet-kind halfM (metres).
 */
export const G03D_CAL = {
  moorage: { half: 1, sigma: 0.3 },
  shoredist: { halfM: 100, sigma: 0.3 },
} as const;

/**
 * moorage: nearby-facility count 100·S/(S+half) (area-kind, G02B
 * liftproxy precedent). shoredist: nearest-shore goodness 100·d/(d+halfM)
 * (quiet-kind, G03 drainage precedent).
 */
export const GROUP03D_BONUS: Record<Group03DLayerId, BonusSpec> = {
  moorage: { kind: "area", half: 1 },
  shoredist: { kind: "quiet", halfM: 100 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup03DLayerId(layer: string): layer is Group03DLayerId {
  return (GROUP03D_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-3D bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup03D(layer: string): BonusSpec | undefined {
  return (GROUP03D_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 3D layer (built by batch_g03d_cadastre.py). */
export const G03D_RASTER_FILE: Record<Group03DLayerId, string> = {
  moorage: "moorage-walk-raster.json",
  shoredist: "shoredist-walk-raster.json",
};

/**
 * NO metro masters (documented): a sparse count kernel (moorage) and a
 * smooth distance-decay proxy (shoredist) at 9.375 m cells would be fake
 * precision. The window route serves county everywhere for these layers
 * (metro slot stays empty, like G02B/G03).
 */
export const G03D_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group03dHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-shore setback goodness 0..100: 0 at the shore, 50 at halfM. */
export function group03dQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group03DPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback shoredist goodness 0..100 (raster missing). Null
 * when there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM).
 */
export function group03dQuietnessAt(
  lat: number,
  lon: number,
  points: Group03DPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group03dHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group03dQuietFromHalf(best * 1000, G03D_CAL.shoredist.halfM));
}

/** Area-kind saturating score 100·S/(S+half) (mirrors walk_raster.saturate). */
export function group03dAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group03dMatchesContract(
  layer: Group03DLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  if (layer === "shoredist")
    return doc.half === G03D_CAL.shoredist.halfM && doc.sigma === G03D_CAL.shoredist.sigma;
  return doc.half === G03D_CAL.moorage.half && doc.sigma === G03D_CAL.moorage.sigma;
}

export type Group03DVerdictKind = "proxy" | "real" | "no-map";

export interface Group03DVerdict {
  param: Group03DParam;
  name: string;
  kind: Group03DVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 3 batch D (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group03d.py).
 */
export const G03D_VERDICTS: Group03DVerdict[] = [
  {
    param: 331,
    name: "Bulkhead/seawall structure",
    kind: "no-map",
    reason:
      "Per-structure engineering fact (is the seawall sound?); OSM maps locations only (47 breakwater + 14 quay ways, zero condition attributes), so proximity cannot answer the question — no honest gradient exists.",
  },
  {
    param: 332,
    name: "Dock and mooring permits",
    kind: "proxy",
    reason:
      "Shipped as moorage: nearness to 195 mapped marinas/moorings/harbours as mooring-opportunity hinnang — honestly labelled, never a permit register (the permit itself stays a per-parcel fact).",
  },
  {
    param: 337,
    name: "Lake water level fluctuation",
    kind: "no-map",
    reason:
      "Needs gauge time series; the 28 monitoring_station objects carry air_quality/weather/traffic tags and the only water_level mentions say no — zero signal by construction.",
  },
  {
    param: 339,
    name: "Well water recharge rate",
    kind: "no-map",
    reason:
      "Needs hydrogeology (ESDAC/KOV table); well/spring presence says nothing about recharge rate, and p183 already scores indicator proximity — a second gradient would duplicate it.",
  },
  {
    param: 340,
    name: "Shoreline setback buffer",
    kind: "real",
    reason:
      "Shipped as shoredist: distance to the mapped shoreline (coastline + standing water) is the param's own ST_Distance formula — rivers/wetlands excluded so it never re-skins p50 drainage.",
  },
];

/** Batch-D params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP03D_NO_MAP_PARAMS: number[] = G03D_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP03D_HOOK =
  "G03D-HOOK (#154): moorage + shoredist wired into layers/overlays/snapshot; p331/p337/p339 verdicts + dims only.";
