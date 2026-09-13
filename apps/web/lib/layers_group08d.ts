// Group 8 flood/climate layers, batch D (parameters3.md §5.8,
// issue #170): p447 ships as an honest ephemeral-water hinnang
// ("vernalpool"); p377/p378/p429 are documented no-map with scorer
// dims (see G08D_VERDICTS below). This file owns ALL G08D runtime
// data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked
// `G08D-HOOK (#170)` blocks, so sibling batches stay disjoint
// (no earlier G8 batch file exists — this is the first Group 8
// layer file; the registry grows 46 -> 47).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Keskkonnaagentuur flood-hazard WFS
// (Üleujutusohuga alad 10/50/100/1000yr), EFAS/CMEMS reanalyses,
// Ilmateenistus archives, soil frost-susceptibility grids and
// well-salinity series are NOT in the 2026-09-12 snapshot
// (MANIFEST gaps: "registries ... flood ... not yet pulled"), so the
// one shipped layer is an honestly-labelled OSM PROXY. Title, legend
// and source say "proksi (hinnang)" (proxy, estimate) — NEVER flood
// zones, return periods, or water-table claims. Green = far/clean
// (hinnang), red = near/exposed (hinnang). Unknown stays null/255
// (renders red, never a faked score).
//
// Per-param verdicts (see also services/scoring/dims_group08d.py):
//   p447 -> vernalpool: honest (hinnang) OSM proxy (this file).
//   p377 frost heave -> DOCUMENTED NO-MAP: foundation damage needs
//     soil frost-susceptibility + groundwater data; OSM maps no soil
//     (no geology/soil tags in the snapshot) and a wetland-proximity
//     gradient would re-skin p50 drainage (#151). Scorer dim stays
//     NULL with a geotechnical-survey reason.
//   p378 saltwater intrusion -> DOCUMENTED NO-MAP: aquifer salinity
//     needs well time series; the 149 salt-tagged objects are ~all
//     salt=no freshwater confirmations (76 ponds, 24 lakes, 14
//     wetlands) with 2 salt=yes wetlands — zero aquifer signal — and
//     a shoreline-distance gradient would re-skin p340 shoredist
//     (#154). Scorer dim stays NULL with a well-testing reason.
//   p429 flood zone creep -> DOCUMENTED NO-MAP: zone CREEP needs
//     flood-zone TIME SERIES (Keskkonnaagentuur model syncs); the 12
//     flood_prone=yes tags are anecdotal points, not a zone, and a
//     water-proximity gradient would re-skin p50 drainage (#151).
//     Scorer dim stays NULL with a flood-map check reason.
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/intermittent=yes  ->  299 features, mostly drainage ditches
//     (167) + drains (44) + rivers (14) + streams (7): flow features
//     belong to p50 drainage and are EXCLUDED. Kept: natural=water +
//     water=pond/basin + intermittent=yes (33 features = 17 areas +
//     16 closed-way twins, 2 intermittent=no ponds correctly dropped)
//     = 17 unique ephemeral still-water bodies county-wide (8 ponds +
//     9 basins), 5 unique in the Tallinn window.
//     seasonal-tagged water/wetland: 0 (seasonal=* lives on tourism
//     features, not water).
//   nwr/seasonal -> 133 features, none water/wetland (73 bare
//     seasonal=yes tourism, 25 seasonal=no): no vernal signal.
//   nwr/natural=wetland -> 1306 features, zero intermittent/seasonal:
//     all-wetland proximity would re-skin p50 drainage (#151) and
//     p257 vectorhabitat (#142), so wetlands are EXCLUDED by design —
//     ONLY explicitly-ephemeral water ships.
//   nwr/flood_prone=yes -> 12 features: anecdotal, not a zone.
//   nwr/salt -> 149 features, ~all salt=no (see above).
//
// Calibration (judgment calls, documented for the reviewer): the one
// layer is a nearest-source distance field, quiet-kind cleanliness
// (100·d/(d+halfM)) — identical semantics to the G07-A/B/C batches
// (0 on the source, 50 at halfM), shared on purpose. halfM 300 m
// (parcel-scale still-water nuisance: soggy ground + mosquitoes,
// same half as #151 drainage and #142 vectorhabitat). Sigma equals
// the Euclidean fallback decay (DECAY hook) and the raster contract
// (matchesContract). Halves live in G08D_CAL below and in
// scripts/build/batch_g08d_flood.py G08D_CAL (kept in sync by test).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type G08DLayerId = "vernalpool";

export const G08D_LAYER_IDS: G08DLayerId[] = ["vernalpool"];

/** parameters3.md parameter numbers per layer. */
export const G08D_PARAM_IDS: Record<G08DLayerId, number[]> = {
  vernalpool: [447],
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const G08D_ALL_PARAMS = [377, 378, 429, 447] as const;

export type G08DParam = (typeof G08D_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const G08D_LAYERS: LayerDef[] = [
  {
    id: "vernalpool",
    paramIds: [447],
    title: "Ajutised veekogud (kevadlompide proksi, hinnang)",
    goodLabel: "roheline = ajutisest veekogust kaugel, kuiv (hinnang)",
    badLabel: "punane = ajutise veekogu ääres — kevadine liigniiskus (hinnang)",
    source: `${SNAP} (kaardistatud ajutised tiigid/vannid 17, intermittent=yes; PROKSI-hinnang, mitte üleujutuskaart ega veetaseme mõõtmine — kraavid/jõed/sood välja, need on p50 drenaaž)`,
    fallbackPoints: [
      { lat: 59.4425, lon: 24.7972 }, // Lasnamäe-äärne ajutine tiik (proksi)
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (lähim ajutine tiik 1,1 km)
    ],
  },
];

/**
 * Overpass QL fragment for the G08D layer (documents the source tags;
 * the snapshot builder consumes them offline — no live fetch in
 * code/tests). nwr/ because ponds/basins are mapped as ways (PR #118:
 * node-only would drop them). intermittent=yes ONLY: ditches, drains,
 * rivers and streams carry the tag too but belong to p50 drainage.
 */
export const G08D_TAGS: Record<G08DLayerId, string> = {
  vernalpool: 'nwr["natural"="water"]["water"~"pond|basin"]["intermittent"="yes"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const G08D_RASTER_FILE: Record<G08DLayerId, string> = {
  vernalpool: "vernalpool-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay proxy is smooth at
 * the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for this layer.
 */
export const G08D_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same
 * scale story as the raster sigma): steep enough that pond pockets
 * beat background.
 */
export const G08D_DECAY_KM: Record<G08DLayerId, number> = {
  vernalpool: 0.3,
};

export function g08dRadiusKmFor(layer: G08DLayerId): number {
  return G08D_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g08d_flood.py G08D_CAL exactly — a pytest
 * parses this file and fails on drift).
 */
export const G08D_CAL = {
  vernalpool: { halfM: 300, sigma: 0.3 },
} as const;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isG08DLayerId(layer: LayerId): layer is G08DLayerId {
  return (G08D_LAYER_IDS as string[]).includes(layer);
}

/** Bonus spec for one G08D layer (called from the bonusSpecFor hook). */
export function g08dBonusSpecFor(layer: G08DLayerId): BonusSpec {
  return { kind: "quiet", halfM: G08D_CAL[layer].halfM };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function g08dHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source cleanliness 0..100: 0 on the source, 50 at halfM. */
export function g08dCleanFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface G08DPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback cleanliness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Nearest-point
 * distance against the layer half (mirrors the Python builder).
 */
export function g08dCleanlinessAt(
  layer: G08DLayerId,
  lat: number,
  lon: number,
  points: G08DPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = g08dHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(g08dCleanFromHalf(best * 1000, G08D_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function g08dMatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: G08DLayerId,
): boolean {
  if (!doc) return false;
  if (doc.sigma !== G08D_DECAY_KM[layer]) return false;
  return doc.half === G08D_CAL[layer].halfM;
}

export type G08DVerdictKind = "proxy" | "real" | "no-map";

export interface G08DVerdict {
  param: G08DParam;
  name: string;
  kind: G08DVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 8 batch D (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group08d.py).
 */
export const G08D_VERDICTS: G08DVerdict[] = [
  {
    param: 377,
    name: "Frost heave foundation damage",
    kind: "no-map",
    reason:
      "Needs soil frost-susceptibility + groundwater data; OSM maps no soil and a wetland-proximity gradient would re-skin p50 drainage — no honest gradient exists.",
  },
  {
    param: 378,
    name: "Saltwater intrusion",
    kind: "no-map",
    reason:
      "Needs well-salinity time series; the 149 salt tags are ~all salt=no freshwater confirmations (2 salt=yes wetlands, zero aquifer signal) and shore distance would re-skin p340 shoredist.",
  },
  {
    param: 429,
    name: "Flood zone creep",
    kind: "no-map",
    reason:
      "Zone creep needs flood-zone time series (Keskkonnaagentuur model syncs); 12 flood_prone=yes tags are anecdotal points, not a zone, and water proximity would re-skin p50 drainage.",
  },
  {
    param: 447,
    name: "Vernal pools and seasonal swamps",
    kind: "proxy",
    reason:
      "Shipped as vernalpool: nearness to 17 mapped intermittent=yes ponds/basins as ephemeral-water hinnang — honestly labelled, never a flood zone; ditches/streams/wetlands stay p50's.",
  },
];

/** Batch-D params with no honest map (dims-only, OTA PR #131 precedent). */
export const G08D_NO_MAP_PARAMS: number[] = G08D_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const G08D_HOOK =
  "G08D-HOOK (#170): vernalpool wired into layers/overlays/snapshot; p377/p378/p429 verdicts + dims only.";
