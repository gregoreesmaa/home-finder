// Group 18 rest-B layers (parameters3.md §5.18, issue #173): p468 ships
// as an honest settled-junction proximity hinnang ("fishbowl"), p479
// ships as an honest mapped-forest distance hinnang ("mossrisk"), p405
// ships as an honest building-openness (inverted count) hinnang
// ("daylight"); p394 + p403 are documented no-map with scorer dims
// (see G18B_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = calm/safe/bright (green = private/dry/open, red =
// exposed); unknown stays 255 (renders red). This file owns ALL G18B
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts, lib/distanceField.ts) touch it only through small
// marked `G18B-HOOK (#173)` blocks, so the sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): Maa-amet LoD2 3D CityGML meshes, ALS LiDAR
// point clouds, PVLib/PVGIS solar models and any RF transmitter
// register are NOT in the 2026-09-12 snapshot, so NONE of the three
// shipped layers is a 3D-simulation result:
// * fishbowl is a settled-corner *hinnang* — nearness to ≥3-arm
//   foot-graph junctions near buildings (corner lots face streets on
//   ≥2 sides), never a cadastral corner-lot ruling. Trail-fork
//   junctions far from any building drop out by design (a fork in an
//   empty forest is not a corner lot).
// * mossrisk is a mapped-forest *hinnang* — distance to mapped forest
//   polygons (filled: inside the stand reads 0) + wood lines, never a
//   roof-moisture measurement. 43,522 mapped street/park trees are OUT
//   by design (a street tree is not a moss stand — a panel is not a
//   farm, G05C precedent).
// * daylight is a building-openness *hinnang* — INVERTED count of
//   mapped buildings nearby (open sky = circadian light access),
//   never a lux measurement. Green sits where buildings are SPARSE
//   (new BonusSpec kind "sparse": 100·half/(S+half)), the mirror image
//   of the area kind. Zero buildings in range reads 100 (measured
//   open, honestly known — NOT unknown like viewshed deserts).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p394 patio sun orientation: a per-building AZIMUTH fact (which way
//   the patio faces + what shades it). The snapshot carries building
//   CENTROIDS only — no footprints, no heights, no orientation — and a
//   cell-average azimuth cannot tell a buyer where THEIR patio sun
//   falls. Scorer dim stays NULL with a LoD2 reason
//   (dims_group18restb.dim_patiosun).
// * p403 natural EM shielding: a TERRAIN + transmitter fact (hills and
//   stands attenuate RF from known masts). The snapshot has no DEM
//   and no transmitter register; forest density alone cannot carry an
//   EM claim without fake precision. Scorer dim stays NULL with a
//   DTM/register reason (dims_group18restb.dim_emshield).
//
// Tag verification (2026-09-12, local snapshot files — no network):
//   harju-foot-graph.json: 721,873 nodes / 796,269 undirected edges;
//   degree≥3 junctions = 144,580 county-wide (74,932 in the Tallinn
//   window); the settled filter (junction within ~1 cell of a mapped
//   building on a 200 m grid — trail forks in empty forest drop out)
//   keeps 139,474 county-wide. Rural probe (24.5, 59.2) moves 98 m →
//   1064 m from the nearest settled junction (the filter working);
//   city probes are unchanged (Vanalinn 3 m, Balti 16 m).
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/natural=wood nwr/landuse=forest   (+ export)
//   17,113 features (8,683 forest polygons + 8,367 wood lines + 63
//   points); the keep_forest predicate (natural=wood or
//   landuse=forest, see scripts/build/batch_g18_restb.py) keeps all
//   17,113 county-wide. 43,522 natural=tree points drop out BY DESIGN
//   (a street tree is not a moss stand).
//   ~/hf-data/2026-09-12/osm/derived-buildings.json: 252,140 bare
//   building centroids, reused directly (no tags to verify).
//
// Calibration (judgment calls, documented for the reviewer): fishbowl
// + mossrisk are nearest-source distance fields, quiet-kind calmness
// (100·d/(d+halfM)), the same kind the G05C/G07/G08 batches add —
// identical semantics (0 on the source, 50 at halfM), shared on
// purpose. fishbowl halves at 150 m (corner exposure is
// sub-block-scale: dense-grid districts read honestly low, detached
// Nõmme reads 73, rural 87); mossrisk halves at 250 m (stand
// shade/spore range: Nõmme 11 / Viimsi 3 vs Paljassaare 80).
// daylight is an inverted count kernel (Gaussian sigma 0.3, score
// 100·half/(S+half) with half 150): Tallinn S spans 31 (Nõmme) → 476
// (Toompea), so half 150 parks the city median mid-ramp (Balti 26,
// Lasnamäe 62, Nõmme 83, rural 100). Sigmas equal the Euclidean
// fallback decay (DECAY hook) and the raster contract
// (matchesContract). Halves live in G18B_CAL below and in
// scripts/build/batch_g18_restb.py G18B_CAL (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group18BLayerId = "fishbowl" | "mossrisk" | "daylight";

export const GROUP18B_LAYER_IDS: Group18BLayerId[] = ["fishbowl", "mossrisk", "daylight"];

/** parameters3.md number per Group-18B layer (no-map params have no layer). */
export const GROUP18B_PARAM_IDS: Record<Group18BLayerId, number> = {
  fishbowl: 468,
  mossrisk: 479,
  daylight: 405,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP18B_ALL_PARAMS = [394, 403, 405, 468, 479] as const;

export type Group18BParam = (typeof GROUP18B_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP18B_LAYERS: LayerDef[] = [
  {
    id: "fishbowl",
    paramIds: [468],
    title: "Nurgakrundi “akvaariumi” efekt (hinnang)",
    goodLabel: "roheline = ristmikest kaugel, privaatne asukoht (hinnang)",
    badLabel: "punane = ristmiku ääres — kahelt poolt nähtav, kontrolli krundi asendit (hinnang)",
    source: `${SNAP} (139 474 asustatud ristmikku — ≥3-harulised kõnnigraafi sõlmed hoonete lähedal, sh Tallinnas 74 400; PROKSI-hinnang läheduse järgi — see EI OLE katastritunnistus nurgakrundi kohta)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe ristmike võrk, proksi)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (ristmikest kaugel)
    ],
  },
  {
    id: "mossrisk",
    paramIds: [479],
    title: "Katuse sambla- ja vetikarisk (hinnang)",
    goodLabel: "roheline = metsast kaugel, kuiv ja päikeseline katus (hinnang)",
    badLabel: "punane = metsa ääres — vari ja niiskus, kontrolli katuse suunda (hinnang)",
    source: `${SNAP} (kaardistatud 8683 metsapolügooni + 8367 puuderida + 63 punkti = 17 113 objekti, sh Tallinnas 4067; 43 522 tänavapuud VÄLJA — tänavapuu ei ole samblastik; PROKSI-hinnang — see EI OLE katuse niiskusmõõtmine)`,
    fallbackPoints: [
      { lat: 59.36, lon: 24.66 }, // Nõmme (metsa ääres, proksi)
      { lat: 59.466, lon: 24.698 }, // Paljassaare (metsast kaugel)
    ],
  },
  {
    id: "daylight",
    paramIds: [405],
    title: "Päevavalguse avarus (hinnang)",
    goodLabel: "roheline = hõre hoonestus, avatud taevas (hinnang)",
    badLabel: "punane = tihe hoonestus, varjutatud (hinnang)",
    source: `${SNAP} (252 140 kaardistatud hoonet, sh Tallinnas 69 608; PÖÖRATUD tihedus-hinnang — hõre = valgusküllane, see EI OLE luksimõõtmine)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam (tihe hoonestus, proksi)
      { lat: 59.468, lon: 24.821 }, // Pirita (hõre hoonestus, proksi)
    ],
  },
];

/**
 * Overpass QL fragments per Group 18B layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). Junctions are
 * ≥3-arm foot-graph NODES, not tag features — the fragment below documents
 * the street/foot network they derive from (n[ shape: the shared
 * overpassQueryFor() rewrites n[ to nwr/, PR #118). The builder consumes
 * the same predicates offline (see keep_forest; junctions + buildings
 * come from snapshot readers, not the PBF).
 */
export const GROUP18B_TAGS: Record<Group18BLayerId, string> = {
  fishbowl: 'w["highway"~"residential|living_street|footway|path"];',
  mossrisk: 'n["natural"="wood"];n["landuse"="forest"];',
  daylight: 'n["building"];w["building"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP18B_DECAY: Record<Group18BLayerId, number> = {
  fishbowl: 0.3,
  mossrisk: 0.3,
  daylight: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g18_restb.py G18B_CAL exactly — a pytest
 * parses this file and fails on drift). fishbowl/mossrisk carry the
 * quiet-kind halfM (metres); daylight carries the sparse-kind half
 * (inverted saturating count, new kind — green where SPARSE).
 */
export const G18B_CAL = {
  fishbowl: { halfM: 150, sigma: 0.3 },
  mossrisk: { halfM: 250, sigma: 0.3 },
  daylight: { half: 150, sigma: 0.3 },
} as const;

/**
 * fishbowl + mossrisk: nearest-source calmness 100·d/(d+halfM)
 * (quiet-kind, G05C/G07/G08 precedent). daylight: inverted nearby
 * building count 100·half/(S+half) (sparse-kind — the mirror image of
 * area: green AWAY from the mass, open sky instead of amenity).
 */
export const GROUP18B_BONUS: Record<Group18BLayerId, BonusSpec> = {
  fishbowl: { kind: "quiet", halfM: 150 },
  mossrisk: { kind: "quiet", halfM: 250 },
  daylight: { kind: "sparse", half: 150 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup18BLayerId(layer: string): layer is Group18BLayerId {
  return (GROUP18B_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-18B bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup18B(layer: string): BonusSpec | undefined {
  return (GROUP18B_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 18B layer (built by batch_g18_restb.py). */
export const G18B_RASTER_FILE: Record<Group18BLayerId, string> = {
  fishbowl: "fishbowl-walk-raster.json",
  mossrisk: "mossrisk-walk-raster.json",
  daylight: "daylight-walk-raster.json",
};

/**
 * NO metro masters (documented): smooth distance-decay fields and a
 * county-wide count kernel at 9.375 m cells would be fake precision. The
 * window route serves county everywhere for these layers (metro slot
 * stays empty, like G07B/G03D/G08B/G05C).
 */
export const G18B_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group18bHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function group18bQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

/** Inverted count score 0..100: 100 where open (S=0), 50 at S=half. */
export function group18bSparseScore(count: number, half: number): number {
  return (100 * half) / (count + half);
}

export interface Group18BPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM per layer).
 */
export function group18bQuietnessAt(
  layer: "fishbowl" | "mossrisk",
  lat: number,
  lon: number,
  points: Group18BPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group18bHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group18bQuietFromHalf(best * 1000, G18B_CAL[layer].halfM));
}

/**
 * Euclidean fallback openness 0..100 (raster missing): Gaussian count
 * (sigma 0.3, 4-sigma cutoff) over the loaded building points, then the
 * sparse reading 100·half/(S+half). Null on EMPTY input (no data loaded
 * is unknown — never a faked open 100); S=0 over a loaded set reads 100
 * (measured open, honestly known). Mirrors the Python builder's
 * score_sparse_cells exactly.
 */
export function group18bDaylightAt(
  lat: number,
  lon: number,
  points: Group18BPoint[],
): number | null {
  if (points.length === 0) return null;
  const sigma = G18B_CAL.daylight.sigma;
  const cutoff = 4 * sigma;
  let s = 0;
  for (const p of points) {
    const d = group18bHavKm(lon, lat, p.lon, p.lat);
    if (d > cutoff) continue;
    s += Math.exp(-(d * d) / (2 * sigma * sigma));
  }
  return Math.round(group18bSparseScore(s, G18B_CAL.daylight.half));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group18bMatchesContract(
  layer: Group18BLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  if (layer === "daylight")
    return doc.half === G18B_CAL.daylight.half && doc.sigma === G18B_CAL.daylight.sigma;
  return doc.half === G18B_CAL[layer].halfM && doc.sigma === G18B_CAL[layer].sigma;
}

export type Group18BVerdictKind = "proxy" | "real" | "no-map";

export interface Group18BVerdict {
  param: Group18BParam;
  name: string;
  kind: Group18BVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 18 rest batch B (the no-map rows are the
 * docs evidence; scorer dims live in services/scoring/dims_group18restb.py).
 */
export const G18B_VERDICTS: Group18BVerdict[] = [
  {
    param: 394,
    name: "Patio sun orientation",
    kind: "no-map",
    reason:
      "A per-building azimuth fact (which way the patio faces + what shades it); the snapshot carries building centroids only — no footprints, no heights, no orientation — and a cell-average azimuth cannot tell a buyer where their patio sun falls. Needs Maa-amet LoD2 + PVLib ray-tracing.",
  },
  {
    param: 403,
    name: "Natural electromagnetic shielding",
    kind: "no-map",
    reason:
      "A terrain + transmitter fact (hills and stands attenuate RF from known masts); the snapshot has no DEM and no transmitter register, and forest density alone cannot carry an EM claim without fake precision.",
  },
  {
    param: 405,
    name: "Circadian lighting potential",
    kind: "proxy",
    reason:
      "Shipped as daylight: inverted count of 252,140 mapped buildings nearby (half 150, sigma 0.3) as open-sky hinnang — honestly labelled, never a lux measurement; zero buildings in range reads 100 (measured open, not unknown).",
  },
  {
    param: 468,
    name: "Corner lot fishbowl effect",
    kind: "proxy",
    reason:
      "Shipped as fishbowl: nearness to 139,474 settled ≥3-arm foot-graph junctions (trail forks in empty forest drop out) as corner-exposure hinnang — honestly labelled, never a cadastral corner-lot ruling.",
  },
  {
    param: 479,
    name: "Roof moss and algae shading",
    kind: "proxy",
    reason:
      "Shipped as mossrisk: distance to 17,113 mapped forest stands (polygons filled — inside reads 0) as shade/moisture hinnang — honestly labelled, never a roof-moisture measurement; 43,522 street trees are out (a street tree is not a moss stand).",
  },
];

/** Batch-B params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP18B_NO_MAP_PARAMS: number[] = G18B_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP18B_HOOK =
  "G18B-HOOK (#173): fishbowl + mossrisk + daylight wired into layers/overlays/snapshot/distanceField; p394/p403 verdicts + dims only.";
