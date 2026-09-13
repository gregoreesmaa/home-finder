// Group 3 cadastre-A layers (parameters3.md §5.3, issue #151): p50 ships
// as a real snapshot layer; p29/p68/p71/p75 are documented no-map with
// scorer dims (see NO-MAP VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0-100; unknown stays 255 (renders red). This file owns ALL G03 runtime
// data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts, lib/distanceField.ts) touch it only through small
// marked `G03-HOOK (#151)` blocks, so the sibling batches stay disjoint.
//
// HONESTY (load-bearing): the Maa-amet LiDAR DEM / EELIS hydrological
// flow grids are NOT in the snapshot, so p50 MUST NOT be presented as
// measured elevation, flow or flood zoning. It is an open-water
// proximity drainage *hinnang* — the title, legend and source say
// "drenaažiproksi (hinnang)", and the test below pins those markers.
// Green = far from mapped open water (good-drainage assumption),
// red = on/near water (high-water-table / check-drainage hint).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p29 lot size: per-parcel Maa-amet WFS fact (m² per cadastre unit).
//   OSM carries no parcel boundaries, so no area heatmap can show it.
//   Scorer dim p29_lot_size uses the listing's own lot area vs the
//   Tallinn median band (dims_group03.dim_lot_size).
// * p68 soil stability: needs the Maa-amet/ESDAC soil DB (clay, peat,
//   fill). Nothing soil-like exists in the snapshot at this branch —
//   a water-proximity re-skin would PUNISH dry parcels and REWARD wet
//   ones on a soil question, i.e. mislead. Scorer dim stays NULL with
//   a buyer-check reason (dims_group03.dim_soil_stability).
// * p71 easements/rights-of-way: KKIS per-parcel legal facts (a parcel
//   either carries a registered servitude or not). An HV-corridor proxy
//   would red-pen parcels that are legally clean and green-light parcels
//   with a driveway easement — unfair both ways. Scorer dim stays NULL
//   with a title-check reason (dims_group03.dim_easements).
// * p75 property-line clarity: pure per-parcel survey fact (boundary
//   markers, disputes). Zero area signal exists by construction.
//   Scorer dim stays NULL with a survey-check reason
//   (dims_group03.dim_boundary_clarity).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/natural=coastline nwr/natural=water nwr/natural=wetland
//     nwr/waterway=river nwr/waterway=stream nwr/waterway=canal
//     nwr/waterway=ditch nwr/waterway=drain -o /tmp/hf-g03-hydro.pbf
//   620 natural=coastline / 3684 natural=water / 606 natural=wetland /
//   1022 waterway=river / 1593 waterway=stream objects; export keeps
//   21843 features, predicate (see scripts/build/batch_g03_cadastre.py
//   keep_hydro) keeps sea shore + open inland water + wetlands +
//   flowing lines: coast 885, inland 7986, waterway 11539.
//   derived-water.geojson alone is INSUFFICIENT (verified: no sea, no
//   rivers — Kalamaja read 916 m from mapped water while the shore sits
//   ~300 m north), so the builder consumes the PBF extract, not it.
//
// Calibration (judgment call, documented for the reviewer): nearest-water
// quietness 100·d/(d+300), sigma 0.3 km (== halfM/1000, nuisance parity
// with batch G09). Measured county-raster reads (2026-09-12 full build,
// --probe): Kadriorg 0 (probe point on pond water), Pirita 20, Balti
// 33, airport 38, Kopli 46, Viru 52, Lasnamäe 52, Kalamaja 55, Viimsi
// 61, Nõmme 64, Õismäe 64, rural 70. The city spreads mid-ramp.

import type { BonusSpec, LayerDef } from "./layers";

export type Group03LayerId = "drainage";

export const GROUP03_LAYER_IDS: Group03LayerId[] = ["drainage"];

/** parameters3.md number per Group-3 layer (no-map params have no layer). */
export const GROUP03_PARAM_IDS: Record<Group03LayerId, number> = {
  drainage: 50,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP03_ALL_PARAMS = [29, 50, 68, 71, 75] as const;

export const GROUP03_LAYERS: LayerDef[] = [
  {
    id: "drainage",
    paramIds: [50],
    title: "Drenaaž ja pinnavesi (drenaažiproksi, hinnang)",
    goodLabel: "roheline = avaveest kaugel, hea drenaaži eeldus (hinnang)",
    badLabel: "punane = veekogu ääres või peal — kontrolli drenaaži (hinnang)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM rannajoon + veekogud + märgalad + vooluveed; kauguse-hinnang, EI OLE mõõdetud reljeef/vooluhulk/üleujutustsoon)",
    fallbackPoints: [
      { lat: 59.47, lon: 24.82 }, // Pirita jõe kallas (vee ääres)
      { lat: 59.39, lon: 24.68 }, // Nõmme kõrgustik (veest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 3 layer (documents the source tags; the
 * app serves the frozen snapshot, never live Overpass). nwr/ everywhere:
 * the sea shore, rivers and lake polygons are ways/relations (PR #118:
 * node-only silently drops them); the builder consumes the same
 * predicate offline (see keep_hydro).
 */
export const GROUP03_TAGS: Record<Group03LayerId, string> = {
  drainage:
    'nwr["natural"="coastline"];nwr["natural"="water"];nwr["natural"="wetland"];nwr["waterway"~"river|stream|canal|ditch|drain"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP03_DECAY: Record<Group03LayerId, number> = {
  drainage: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g03_cadastre.py G03_CAL exactly — a pytest parses
 * this file and fails on drift).
 */
export const G03_CAL = {
  drainage: { halfM: 300, sigma: 0.3 },
} as const;

/** Nearest-water drainage goodness: { kind: "quiet" } (see layers.ts). */
export const GROUP03_BONUS: Record<Group03LayerId, BonusSpec> = {
  drainage: { kind: "quiet", halfM: 300 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup03LayerId(layer: string): layer is Group03LayerId {
  return (GROUP03_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-3 bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup03(layer: string): BonusSpec | undefined {
  return (GROUP03_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 3 layer (built by batch_g03_cadastre.py). */
export const G03_RASTER_FILE: Record<Group03LayerId, string> = {
  drainage: "drainage-walk-raster.json",
};

/**
 * NO metro masters (documented): a smooth distance-decay proxy at
 * 9.375 m cells would be fake precision. The window route serves county
 * everywhere for these layers (metro slot stays empty, like GENV/B10C).
 */
export const G03_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group03HavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-water drainage goodness 0..100: 0 on the water, 50 at halfM. */
export function group03QuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group03Point {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback drainage goodness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the Python
 * builder's score_distance exactly (same halfM).
 */
export function group03QuietnessAt(
  lat: number,
  lon: number,
  points: Group03Point[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group03HavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group03QuietFromHalf(best * 1000, G03_CAL.drainage.halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group03MatchesContract(
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G03_CAL.drainage.halfM && doc.sigma === G03_CAL.drainage.sigma;
}
