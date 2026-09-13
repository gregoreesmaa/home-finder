// Group 7 environmental-health layers, batch D (parameters3.md §5.7,
// issue #143): p409 proximity to active agriculture, p450 wildlife
// migration corridors. This file owns ALL G07D runtime data; shared
// files (lib/layers.ts, lib/server/snapshot.ts,
// lib/distanceField.ts, lib/overlays.ts) touch it only through small
// marked `G07D-HOOK (#143)` blocks, so sibling batches stay disjoint
// (issues #140/#141 own layers_group07.ts(b).ts / G07-HOOK / G07B-HOOK
// — different files, different ids, different params).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): no PRIA spray map, no harvest-activity log,
// no wildlife-corridor (rohevorgustik) register, no pipe-material
// registry and no radon-mitigation survey exist in the 2026-09-12
// snapshot, so both layers are honestly-labelled OSM PROXIMITY
// proxies. Titles, legends and sources say "proksi (hinnang)" (proxy,
// estimate) — NEVER spray doses, corridor ids, pipe counts or radon
// classes. Green = far/clean (hinnang), red = near/exposed (hinnang).
// Unknown stays null/255 (renders red, never a faked score).
//
// Per-param verdicts (see also services/scoring/dims_group07d.py):
//   p409 -> agrifield: honest (hinnang) OSM proxy (this file).
//   p450 -> wildcorr: honest (hinnang) OSM encounter proxy (this file).
//   p448 harvest dust/traffic -> DOCUMENTED NO-MAP: harvest TIMING is
//     not in the snapshot, and a spatial layer would duplicate the
//     agrifield map while claiming seasonal meaning (fake precision).
//     Scorer dim stays NULL.
//   p471 lead water service lines -> DOCUMENTED NO-MAP: 509656 mapped
//     buildings, only 644 = 0.13% carry any age tag and ZERO carry
//     pipe-material tags — an age proxy would be noise presented as
//     plumbing. Scorer dim stays NULL.
//   p499 radon-mitigation aesthetic -> DOCUMENTED NO-MAP: a
//     facade-aesthetics judgment with no data at all (even radon
//     LEVELS p66 are already no-mapped by #140). Scorer dim stays NULL.
//
// Tag verification (2026-09-12, local snapshot — no network):
//   PBF harjumaa-260911.osm.pbf via osmium tags-filter + export:
//   agrifield: farmland 1545 + farmyard 284 + meadow 1549 + orchard 9
//     + greenhouse_horticulture 42 MultiPolygon areas (closed-way
//     LineString twins + forest/residential/cemetery member objects
//     dropped by the reader).
//   wildcorr: natural=wood 3642 (+1 lone-tree point, kept —
//     negligible, documented) + natural=wetland 606 + leisure/boundary
//     nature_reserve 26 MultiPolygon areas (twins + coastline/water/
//     grassland/scrub member objects dropped by the reader).
//
// Overlap note (for the reviewer): agrifield DELIBERATELY overlaps
// #141 agriland (p227) spatially — the params themselves overlap
// (agricultural boundaries vs proximity to active agriculture). The
// footprints differ on purpose: agriland keeps farmland+farmyard only
// (spray-relevant subset); agrifield keeps the full active-ag
// footprint (hay/pasture manure and mowing, orchards, greenhouses are
// active agriculture). Same 800 m half, different question.
//
// Calibration (judgment calls, documented for the reviewer): both
// layers are nearest-source distance fields, quiet-kind cleanliness
// (100·d/(d+halfM)), the same kind the #140/#141 batches add —
// identical semantics (0 on the source, 50 at halfM), shared on
// purpose. agrifield halves at 800 m (drift/odour carry, same scale
// as #141 agriland); wildcorr halves at 500 m (parcel scale —
// habitat is dense in Harjumaa and 800 m would wash the county red
// without corridor meaning). Measured Tallinn-window medians/max
// (known cells, 2026-09-12 build): agrifield 56/88, wildcorr 49/91 —
// mid-ramp, streets discriminate. Sigmas equal the Euclidean fallback
// decay (DECAY hook) and the raster contract (matchesContract).
// Halves live in G07D_CAL below and in
// scripts/build/batch_g07d_envhealth.py G07D_CAL (kept in sync by
// test).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type G07DLayerId = "agrifield" | "wildcorr";

export const G07D_LAYER_IDS: G07DLayerId[] = ["agrifield", "wildcorr"];

/** parameters3.md parameter numbers per layer. */
export const G07D_PARAM_IDS: Record<G07DLayerId, number[]> = {
  agrifield: [409],
  wildcorr: [450],
};

/**
 * parameters3.md Group 7 params with DOCUMENTED NO-MAP verdicts (OTA
 * PR #131 precedent): no registry data exists in the snapshot, so no
 * layer ships; scorer dims in services/scoring/dims_group07d.py stay
 * NULL, never faked.
 */
export const G07D_NO_MAP: { param: number; reason: string }[] = [
  {
    param: 448,
    reason:
      "lõikusaja tolm/liiklus: hooaja ajastus hetktõmmises puudub; ruumiline proksi dubleeriks p409 kaarti hooajalise tähendusega (libe täpsus, hinnangut kaardil pole)",
  },
  {
    param: 471,
    reason:
      "pliitorud: 509656 hoonest vaid 644-l (0.13%) vanusemärge, torumaterjali märgetel null — vanuseproksi oleks müra torustikuna (hinnangut kaardil pole)",
  },
  {
    param: 499,
    reason:
      "radoonitõrje esteetika: fassaadihinnang, mille kohta andmed puuduvad (ka radoonitasemed p66 on #140 otsusega kaardita, hinnangut kaardil pole)",
  },
];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const G07D_LAYERS: LayerDef[] = [
  {
    id: "agrifield",
    paramIds: [409],
    title: "Põllumajanduslähedus (proksi, hinnang)",
    goodLabel: "roheline = haritavast maast kaugel (triivi/lõhna proksi, hinnang)",
    badLabel: "punane = põllu/karjamaa/kasvuhoone lähedal (proksi, hinnang)",
    source: `${SNAP} (kaardistatud põllud 1545 + õued 284 + heinamaad 1549 + aiad 9 + kasvuhooned 42; PROKSI-hinnang, mitte PRIA pritsikaart; laiem ala kui p227 triivikiht)`,
    fallbackPoints: [
      { lat: 59.4407, lon: 24.8041 }, // Lasnamäe-tagune heinamaa (proksi)
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (haritavast maast kaugel)
    ],
  },
  {
    id: "wildcorr",
    paramIds: [450],
    title: "Metsloomakoridorid (elupaiga proksi, hinnang)",
    goodLabel: "roheline = suurest elupaigast kaugel (vähem kohtumisi, proksi-hinnang)",
    badLabel: "punane = metsa/märgalu/kaitseala lähedal (liikumisala proksi, hinnang)",
    source: `${SNAP} (kaardistatud metsad 3642 + märgalad 606 + kaitsealad 26; PROKSI-hinnang: elupaiga lähedus, mitte rändekoridoride register)`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7489 }, // Kesklinna-rohe (proksi)
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (suurtest elupaikadest kaugemal)
    ],
  },
];

/**
 * Overpass QL fragments per G07D layer (document the source tags; the
 * snapshot builder consumes them offline — no live fetch in code/tests).
 * nwr/ everywhere areas carry the feature (PR #118: node-only would
 * drop way-mapped fields, woods and wetlands).
 */
export const G07D_TAGS: Record<G07DLayerId, string> = {
  agrifield: 'nwr["landuse"~"farmland|farmyard|meadow|orchard|greenhouse_horticulture"];',
  wildcorr: 'nwr["natural"~"wood|wetland"];nwr["leisure"="nature_reserve"];nwr["boundary"="nature_reserve"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const G07D_RASTER_FILE: Record<G07DLayerId, string> = {
  agrifield: "agrifield-walk-raster.json",
  wildcorr: "wildcorr-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay proxy is smooth at
 * the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for these layers.
 */
export const G07D_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same
 * scale story as the raster sigma): steep enough that source
 * pockets beat background.
 */
export const G07D_DECAY_KM: Record<G07DLayerId, number> = {
  agrifield: 0.8,
  wildcorr: 0.5,
};

export function g07dRadiusKmFor(layer: G07DLayerId): number {
  return G07D_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g07d_envhealth.py G07D_CAL exactly — a pytest
 * parses this file and fails on drift).
 */
export const G07D_CAL = {
  agrifield: { halfM: 800, sigma: 0.8 },
  wildcorr: { halfM: 500, sigma: 0.5 },
} as const;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isG07DLayerId(layer: LayerId): layer is G07DLayerId {
  return (G07D_LAYER_IDS as string[]).includes(layer);
}

/** Bonus spec for one G07D layer (called from the bonusSpecFor hook). */
export function g07dBonusSpecFor(layer: G07DLayerId): BonusSpec {
  return { kind: "quiet", halfM: G07D_CAL[layer].halfM };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function g07dHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source cleanliness 0..100: 0 on the source, 50 at halfM. */
export function g07dCleanFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface G07DPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback cleanliness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Nearest-point
 * distance against the layer half (mirrors the Python builder).
 */
export function g07dCleanlinessAt(
  layer: G07DLayerId,
  lat: number,
  lon: number,
  points: G07DPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = g07dHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(g07dCleanFromHalf(best * 1000, G07D_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function g07dMatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: G07DLayerId,
): boolean {
  if (!doc) return false;
  if (doc.sigma !== G07D_DECAY_KM[layer]) return false;
  return doc.half === G07D_CAL[layer].halfM;
}
