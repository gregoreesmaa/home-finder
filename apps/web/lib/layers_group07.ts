// Group 7 environmental-health layers (parameters3.md §5.7, issue #140):
// p61 industrial proximity + p62 odor sources. This file owns ALL G07
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/distanceField.ts, lib/overlays.ts) touch it only through small
// marked `G07-HOOK (#140)` blocks, so sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): Keskkonnaagentuur air-quality stations and
// any measured odor/pollen/radon survey are NOT in the 2026-09-12
// snapshot, so both layers are honestly-labelled OSM PROXIMITY
// proxies. Titles, legends and sources say "proksi (hinnang)"
// (proxy, estimate) — NEVER AQI, OU/m3, Bq/m3 or pollen grains/m3.
// Green = far/clean (hinnang), red = near/exposed (hinnang). Unknown
// stays null/255 (renders red, never a faked score).
//
// Per-param verdicts (see also services/scoring/dims_group07.py):
//   p61 -> industprox: honest (hinnang) OSM proxy (this file).
//   p62 -> odorsrc: honest (hinnang) OSM proxy (this file).
//   p66 radon -> DOCUMENTED NO-MAP: no geology/WFS in the snapshot.
//   p67 pests/wildlife -> DOCUMENTED NO-MAP: no survey in the snapshot.
//   p137 seasonal allergens -> DOCUMENTED NO-MAP: no pollen traps in
//     the snapshot, and mapped green would read INVERTED (parks emit
//     pollen). All three keep scorer dims (NULL, never faked).
//
// Tag verification (2026-09-12, local snapshot — no network):
//   harju-amenities.geojson: landuse=industrial x54 features = 27
//     areas + their 27 closed-way LineString twins (used once).
//   derived-odor.geojson (one-time PBF export, see
//     scripts/build/batch_g07_envhealth.py): man_made=wastewater_plant
//     ~36 areas + landuse=landfill ~24 areas (closed-way twins and
//     14 untagged member objects dropped by the reader).
//
// Calibration (judgment calls, documented for the reviewer): both
// layers are nearest-source distance fields, quiet-kind cleanliness
// (100·d/(d+halfM)), mirroring the GENV lowspec path at the same half
// (500 m — smell and industrial haze carry like low-frequency
// rumble). Measured Tallinn-window medians/max (known cells,
// 2026-09-12 build): industprox 87/95, odorsrc 91/96 — high medians
// ARE the truth for sparse sources (most of Tallinn is far from a
// plant); the rasters still span 0..95 with honest red pockets
// (Paljassaare odorsrc 13). Sigmas equal the Euclidean fallback
// decay (DECAY hook) and the raster contract (matchesContract).
// Halves live in G07_CAL below and in
// scripts/build/batch_g07_envhealth.py G07_CAL (kept in sync by test).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type G07LayerId = "industprox" | "odorsrc";

export const G07_LAYER_IDS: G07LayerId[] = ["industprox", "odorsrc"];

/** parameters3.md parameter numbers per layer. */
export const G07_PARAM_IDS: Record<G07LayerId, number[]> = {
  industprox: [61],
  odorsrc: [62],
};

/**
 * parameters3.md Group 7 params with DOCUMENTED NO-MAP verdicts (OTA
 * PR #131 precedent): no registry data exists in the snapshot, so no
 * layer ships; scorer dims in services/scoring/dims_group07.py stay
 * NULL, never faked.
 */
export const G07_NO_MAP: { param: number; reason: string }[] = [
  {
    param: 66,
    reason: "radoon: geoloogia/WFS-atlas hetktõmmises puudub (hinnangut kaardil pole)",
  },
  {
    param: 67,
    reason: "kahjurid/metsloomad: seiret hetktõmmises pole (hinnangut kaardil pole)",
  },
  {
    param: 137,
    reason:
      "allergeenid: õietolmujaamu hetktõmmises pole; haljas loeks VASTUPIDI (pargid eritavad õietolmu)",
  },
];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const G07_LAYERS: LayerDef[] = [
  {
    id: "industprox",
    paramIds: [61],
    title: "Tööstuslähedus (õhu proksi, hinnang)",
    goodLabel: "roheline = tööstusala kaugel (õhu proksi, hinnang)",
    badLabel: "punane = tööstusala lähedal (õhu proksi, hinnang)",
    source: `${SNAP} (kaardistatud tööstusalad 27; PROKSI-hinnang, mitte Keskkonnaagentuuri õhuseire)`,
    fallbackPoints: [
      { lat: 59.4483, lon: 24.7134 }, // Paljassaare tööstusala lähedal (proksi)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (tööstusest kaugel)
    ],
  },
  {
    id: "odorsrc",
    paramIds: [62],
    title: "Lõhnaallikad (proksi, hinnang)",
    goodLabel: "roheline = puhasti/prügila kaugel (lõhna proksi, hinnang)",
    badLabel: "punane = reoveepuhasti või prügila lähedal (lõhna proksi, hinnang)",
    source: `${SNAP} (kaardistatud reoveepuhastid ~36 + prügilad ~24; PROKSI-hinnang, mitte lõhna mõõtmine)`,
    fallbackPoints: [
      { lat: 59.466, lon: 24.698 }, // Paljassaare puhasti (proksi)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (allikatest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per G07 layer (document the source tags; the
 * snapshot builder consumes them offline — no live fetch in code/tests).
 * nwr/ everywhere areas carry the feature (PR #118: node-only would
 * drop way-mapped industrial areas, plants and landfills).
 */
export const G07_TAGS: Record<G07LayerId, string> = {
  industprox: 'nwr["landuse"="industrial"];',
  odorsrc: 'nwr["man_made"="wastewater_plant"];nwr["landuse"="landfill"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const G07_RASTER_FILE: Record<G07LayerId, string> = {
  industprox: "industprox-walk-raster.json",
  odorsrc: "odorsrc-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay proxy is smooth at
 * the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for these layers.
 */
export const G07_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same
 * scale story as the raster sigma): steep enough that source
 * pockets beat background.
 */
export const G07_DECAY_KM: Record<G07LayerId, number> = {
  industprox: 0.5,
  odorsrc: 0.5,
};

export function g07RadiusKmFor(layer: G07LayerId): number {
  return G07_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g07_envhealth.py G07_CAL exactly — a pytest
 * parses this file and fails on drift).
 */
export const G07_CAL = {
  industprox: { halfM: 500, sigma: 0.5 },
  odorsrc: { halfM: 500, sigma: 0.5 },
} as const;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isG07LayerId(layer: LayerId): layer is G07LayerId {
  return (G07_LAYER_IDS as string[]).includes(layer);
}

/** Bonus spec for one G07 layer (called from the bonusSpecFor hook). */
export function g07BonusSpecFor(layer: G07LayerId): BonusSpec {
  return { kind: "quiet", halfM: G07_CAL[layer].halfM };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function g07HavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source cleanliness 0..100: 0 on the source, 50 at halfM. */
export function g07CleanFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface G07Point {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback cleanliness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Nearest-point
 * distance against the layer half (mirrors the Python builder).
 */
export function g07CleanlinessAt(
  layer: G07LayerId,
  lat: number,
  lon: number,
  points: G07Point[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = g07HavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(g07CleanFromHalf(best * 1000, G07_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function g07MatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: G07LayerId,
): boolean {
  if (!doc) return false;
  if (doc.sigma !== G07_DECAY_KM[layer]) return false;
  return doc.half === G07_CAL[layer].halfM;
}
