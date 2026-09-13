// Group 7 environmental-health layers, batch B (parameters3.md §5.7,
// issue #141): p189 soil history/toxicity, p202 buried oil tanks,
// p227 agricultural boundaries. This file owns ALL G07B runtime data;
// shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/distanceField.ts, lib/overlays.ts) touch it only through small
// marked `G07B-HOOK (#141)` blocks, so sibling batches stay disjoint
// (issue #140 owns layers_group07.ts / G07-HOOK — different file,
// different ids, different params).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): no soil-toxicity survey, no buried-tank
// register and no PRIA spray map exist in the 2026-09-12 snapshot, so
// all three layers are honestly-labelled OSM PROXIMITY proxies.
// Titles, legends and sources say "proksi (hinnang)" (proxy,
// estimate) — NEVER mg/kg, tank counts, or spray-dose claims.
// Green = far/clean (hinnang), red = near/exposed (hinnang). Unknown
// stays null/255 (renders red, never a faked score).
//
// Per-param verdicts (see also services/scoring/dims_group07b.py):
//   p189 -> brownsoil: honest (hinnang) OSM proxy (this file).
//   p202 -> oiltank: honest (hinnang) OSM proxy (this file).
//   p227 -> agriland: honest (hinnang) OSM proxy (this file).
//   p204 hazardous materials -> DOCUMENTED NO-MAP: no Seveso/hazard
//     registry in the snapshot (man_made=works is generic plant stock
//     overlapping p61 industry, industrial=chemical/oil/gas refines to
//     ~8 areas — neither is hazardous-specific). Scorer dim stays NULL.
//   p252 invasive plants -> DOCUMENTED NO-MAP: no invasive-species
//     survey in the snapshot; reusing mapped trees/green would be
//     meaningless (most mapped trees are native/planted). Scorer dim
//     stays NULL.
//
// Tag verification (2026-09-12, local snapshot — no network):
//   PBF harjumaa-260911.osm.pbf via osmium tags-filter + export:
//   landuse=brownfield: 53 features = 24 MultiPolygon areas + their 22
//     closed-way LineString twins + 2 named twins + 5 untagged member
//     objects (reader keeps tagged MultiPolygons once; twins/untagged
//     dropped).
//   man_made=storage_tank: 825 features = 402 MultiPolygon areas (+24
//     Points) + closed-way twins. Content split: fuel 110, oil 1,
//     slurry 23, manure 3, water 5, wheat/wastewater 1 each, untagged
//     258. OSM does NOT distinguish buried vs above-ground tanks, so
//     the whole mapped stock is the proxy (documented in the source
//     string); water/wheat/wastewater/slurry/manure tanks are kept on
//     purpose — a content allowlist would fake precision about which
//     yards hold legacy buried oil tanks.
//   landuse=farmland/farmyard: 1829 areas (farmland 1545 + farmyard
//     284) + closed-way twins. landuse=meadow (~1549 areas, mostly
//     hay/pasture with low spray relevance) and landuse=orchard (18
//     features, negligible) are DELIBERATELY excluded: including
//     meadow would wash the county in red without health meaning.
//
// Calibration (judgment calls, documented for the reviewer): all three
// layers are nearest-source distance fields, quiet-kind cleanliness
// (100·d/(d+halfM)), the same kind the G07-A batch (#140) adds —
// identical semantics (0 on the source, 50 at halfM), shared on
// purpose. brownsoil/oiltank halve at 500 m (parcel-scale hazards,
// same carry as #140 odor/industrial proximity); agriland halves at
// 800 m (spray/dust drift carries further — destination-scale sigma
// 0.8, mirroring the B1 healthcare scale). Sigmas equal the Euclidean
// fallback decay (DECAY hook) and the raster contract
// (matchesContract). Halves live in G07B_CAL below and in
// scripts/build/batch_g07b_envhealth.py G07B_CAL (kept in sync by
// test).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type G07BLayerId = "brownsoil" | "oiltank" | "agriland";

export const G07B_LAYER_IDS: G07BLayerId[] = ["brownsoil", "oiltank", "agriland"];

/** parameters3.md parameter numbers per layer. */
export const G07B_PARAM_IDS: Record<G07BLayerId, number[]> = {
  brownsoil: [189],
  oiltank: [202],
  agriland: [227],
};

/**
 * parameters3.md Group 7 params with DOCUMENTED NO-MAP verdicts (OTA
 * PR #131 precedent): no registry data exists in the snapshot, so no
 * layer ships; scorer dims in services/scoring/dims_group07b.py stay
 * NULL, never faked.
 */
export const G07B_NO_MAP: { param: number; reason: string }[] = [
  {
    param: 204,
    reason:
      "ohtlikud ained: Seveso-/ohuregister hetktõmmises puudub (tehased kattuks p61 tööstusega, hinnangut kaardil pole)",
  },
  {
    param: 252,
    reason: "invasiivtaimed: liigiseiret hetktõmmises pole (haljas/puud loeks mõttetult, hinnangut kaardil pole)",
  },
];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const G07B_LAYERS: LayerDef[] = [
  {
    id: "brownsoil",
    paramIds: [189],
    title: "Endised tööstusalad (mulla proksi, hinnang)",
    goodLabel: "roheline = pruunväljast kaugel (mulla proksi, hinnang)",
    badLabel: "punane = endise tööstusala lähedal (mulla proksi, hinnang)",
    source: `${SNAP} (kaardistatud pruunväljad 24; PROKSI-hinnang, mitte pinnase mõõtmine)`,
    fallbackPoints: [
      { lat: 59.4513, lon: 24.7222 }, // Kopli pruunväli (proksi)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (pruunväljadest kaugel)
    ],
  },
  {
    id: "oiltank",
    paramIds: [202],
    title: "Mahutid (õlimahutite proksi, hinnang)",
    goodLabel: "roheline = mahutitest kaugel (proksi, hinnang)",
    badLabel: "punane = mahuti lähedal (proksi, hinnang)",
    source: `${SNAP} (kaardistatud mahutid ~426, sh kütus 110; PROKSI-hinnang, mitte maa-aluste mahutite register — OSM ei erista maa-aluseid)`,
    fallbackPoints: [
      { lat: 59.4983, lon: 24.937 }, // Muuga kütusehoidla (proksi)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (mahutitest kaugel)
    ],
  },
  {
    id: "agriland",
    paramIds: [227],
    title: "Põllumajandusmaa (triivi proksi, hinnang)",
    goodLabel: "roheline = põllust kaugel (triivi proksi, hinnang)",
    badLabel: "punane = haritava põllu lähedal (triivi proksi, hinnang)",
    source: `${SNAP} (kaardistatud põllud 1545 + õued 284; PROKSI-hinnang, mitte PRIA pritsikaart; heina-/karjamaad välja arvatud)`,
    fallbackPoints: [
      { lat: 59.44, lon: 24.9261 }, // Lasnamäe-tagune põld (proksi)
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (põldudest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per G07B layer (document the source tags; the
 * snapshot builder consumes them offline — no live fetch in code/tests).
 * nwr/ everywhere areas carry the feature (PR #118: node-only would
 * drop way-mapped brownfields, tanks and fields).
 */
export const G07B_TAGS: Record<G07BLayerId, string> = {
  brownsoil: 'nwr["landuse"="brownfield"];',
  oiltank: 'nwr["man_made"="storage_tank"];',
  agriland: 'nwr["landuse"~"farmland|farmyard"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const G07B_RASTER_FILE: Record<G07BLayerId, string> = {
  brownsoil: "brownsoil-walk-raster.json",
  oiltank: "oiltank-walk-raster.json",
  agriland: "agriland-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay proxy is smooth at
 * the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for these layers.
 */
export const G07B_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same
 * scale story as the raster sigma): steep enough that source
 * pockets beat background.
 */
export const G07B_DECAY_KM: Record<G07BLayerId, number> = {
  brownsoil: 0.5,
  oiltank: 0.5,
  agriland: 0.8,
};

export function g07bRadiusKmFor(layer: G07BLayerId): number {
  return G07B_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g07b_envhealth.py G07B_CAL exactly — a pytest
 * parses this file and fails on drift).
 */
export const G07B_CAL = {
  brownsoil: { halfM: 500, sigma: 0.5 },
  oiltank: { halfM: 500, sigma: 0.5 },
  agriland: { halfM: 800, sigma: 0.8 },
} as const;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isG07BLayerId(layer: LayerId): layer is G07BLayerId {
  return (G07B_LAYER_IDS as string[]).includes(layer);
}

/** Bonus spec for one G07B layer (called from the bonusSpecFor hook). */
export function g07bBonusSpecFor(layer: G07BLayerId): BonusSpec {
  return { kind: "quiet", halfM: G07B_CAL[layer].halfM };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function g07bHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source cleanliness 0..100: 0 on the source, 50 at halfM. */
export function g07bCleanFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface G07BPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback cleanliness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Nearest-point
 * distance against the layer half (mirrors the Python builder).
 */
export function g07bCleanlinessAt(
  layer: G07BLayerId,
  lat: number,
  lon: number,
  points: G07BPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = g07bHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(g07bCleanFromHalf(best * 1000, G07B_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function g07bMatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: G07BLayerId,
): boolean {
  if (!doc) return false;
  if (doc.sigma !== G07B_DECAY_KM[layer]) return false;
  return doc.half === G07B_CAL[layer].halfM;
}
