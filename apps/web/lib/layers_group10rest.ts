// Group 10 utilities-rest layer (parameters3.md §5.10, issue #171):
// p215 ships as an honest open-sky hinnang ("skyview"); p491 is a
// documented no-map with a scorer dim (see G10R_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = open (green = clear dish line-of-sight likely, red =
// obstructed — check on site); the whole county field is stamped
// (open land is genuinely open sky, no 255 desert). This file owns
// ALL G10R runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts) touch it only through
// small marked `G10R-HOOK (#171)` blocks, so the sibling batches
// stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the TTJA Lairiba katvuskaart, OpenCellID /
// CellMapper measurements and any dish line-of-sight survey are NOT
// in the 2026-09-12 snapshot (zero satellite-dish and zero
// indoor-signal keys — verified with osmium tags-count), so the
// shipped layer is NOT measured coverage:
// * skyview is a mapped-obstruction *hinnang* — nearness to
//   OSM-mapped tall buildings (5+ storeys) + mapped forest canopy,
//   never a coverage ruling. 1-4 storey houses are OUT (a family
//   house does not block the dish cone); level-less buildings are
//   OUT (guessing height would fake precision); tree rows and lone
//   trees are OUT (a row is not a canopy).
// * The field is radial while real dish obstruction is directional
//   (the south-sky cone): red means "check with the Starlink app
//   obstruction tool", never "no satellite here". Unmapped forest
//   clearings read falsely low — a rural house in an unmapped
//   clearing still needs the on-site check (documented, not hidden).
//
// NO-MAP VERDICT (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p491 indoor dead zones: a per-ROOM RF measurement (carrier,
//   floor, indoor walls). The snapshot carries zero indoor-signal
//   keys, and building:material (5131 uses, ~2% of buildings) is the
//   wrong shape — own-wall material, not an area gradient. Scorer
//   dim stays NULL with an on-site-measurement reason
//   (dims_group10rest.dim_deadzone).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/building:levels nwr/natural=wood nwr/landuse=forest
//   50423 features; the keep_sky predicate (tall = levels >= 5;
//   forest = natural wood / landuse forest) keeps 21532 county-wide
//   (5604 tall + 15928 forest incl. multipolygon member ways, ~8.7k
//   true polygons; 9596 in the Tallinn window: Lasnamäe/Õismäe/
//   Mustamäe panel districts + Nõmme-Mustamäe/Pirita/Viimsi woods).
//   28891 drop out (1-4 storey houses, level-less buildings, tree
//   rows, untagged members). Zero satellite-dish and zero
//   indoor-signal keys anywhere in the PBF.
//   Probe (built master, high = calm): Lasnamäe/Õismäe/Viru 0
//   (tower-adjacent), Balti/Kadriorg/Ulemiste 33, Kohtuotsa 63,
//   Pirita 66, Paljassaare 80 (open peninsula). Rural (24.5,59.2)
//   reads 0 — inside mapped forest (inside IS the obstruction).
//
// Calibration (judgment call, documented for the reviewer): skyview
// is a nearest-obstruction distance field, quiet-kind calmness
// (100·d/(d+halfM)), the same kind the G05C/G07/G08 batches add —
// identical semantics (0 on the obstruction, 50 at halfM), shared on
// purpose. halfM halves at 150 m (dish obstruction is local: a
// 15-30 m obstacle blocks the sky cone within tens of metres, so
// open courtyards read calm while tower-adjacent and forest parcels
// read honestly low). Sigma equals the Euclidean fallback decay
// (DECAY hook) and the raster contract (matchesContract). Half
// lives in G10R_CAL below and in scripts/build/batch_g10_rest.py
// G10R_CAL (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group10RestLayerId = "skyview";

export const GROUP10REST_LAYER_IDS: Group10RestLayerId[] = ["skyview"];

/** parameters3.md number per Group-10-rest layer (no-map params have no layer). */
export const GROUP10REST_PARAM_IDS: Record<Group10RestLayerId, number> = {
  skyview: 215,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP10REST_ALL_PARAMS = [215, 491] as const;

export type Group10RestParam = (typeof GROUP10REST_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP10REST_LAYERS: LayerDef[] = [
  {
    id: "skyview",
    paramIds: [215],
    title: "Avatud taevas satelliit-internetile (hinnang)",
    goodLabel: "roheline = lage taevas, antennile tõenäoliselt vaba vaade (hinnang)",
    badLabel:
      "punane = kõrged takistused lähedal — kontrolli antenni vaatevälja Starlink rakendusega (hinnang)",
    source: `${SNAP} (kaardistatud 5604 kõrghoonet 5+ korrust + 15928 metsaobjekti = 21532 takistust, sh Tallinnas 9596; PROKSI-hinnang kauguse järgi — see EI OLE mõõdetud levi ega TTJA katvuskaart; suunatakistus (lõunataevas) kaardil pole)`,
    fallbackPoints: [
      { lat: 59.44, lon: 24.82 }, // Lasnamäe paneelmaja hoov (takistuste seas, proksi 0)
      { lat: 59.466, lon: 24.698 }, // Paljassaare poolsaar (lage, takistustest kaugel, proksi 80)
    ],
  },
];

/**
 * Overpass QL fragment for the Group 10 rest layer (documents the
 * source tags; the app serves the frozen snapshot, never live
 * Overpass). n/ shape: the shared overpassQueryFor() rewrites n[ to
 * nwr/ (PR #118: node-only silently drops way-mapped buildings and
 * forest polygons). The builder consumes the same predicate offline
 * (see keep_sky); the 5-storey cutoff and the canopy check live in
 * the scorer mapping (kinds_from_tags), so the fragment stays a
 * plain source-tags query like sibling batches.
 */
export const GROUP10REST_TAGS: Record<Group10RestLayerId, string> = {
  skyview: 'n["building"]["building:levels"];n["natural"="wood"];n["landuse"="forest"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP10REST_DECAY: Record<Group10RestLayerId, number> = {
  skyview: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g10_rest.py G10R_CAL exactly — a pytest
 * parses this file and fails on drift). skyview carries the
 * quiet-kind halfM (metres).
 */
export const G10R_CAL = {
  skyview: { halfM: 150, sigma: 0.3 },
} as const;

/**
 * skyview: nearest-obstruction calmness 100·d/(d+halfM)
 * (quiet-kind, G05C/G07/G08 precedent).
 */
export const GROUP10REST_BONUS: Record<Group10RestLayerId, BonusSpec> = {
  skyview: { kind: "quiet", halfM: 150 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup10RestLayerId(layer: string): layer is Group10RestLayerId {
  return (GROUP10REST_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-10-rest bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup10Rest(layer: string): BonusSpec | undefined {
  return (GROUP10REST_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master file for the Group 10 rest layer (built by batch_g10_rest.py). */
export const G10R_RASTER_FILE: Record<Group10RestLayerId, string> = {
  skyview: "skyview-walk-raster.json",
};

/**
 * NO metro master (documented): a smooth distance-decay field at
 * 9.375 m cells would be fake precision. The window route serves
 * county everywhere for this layer (metro slot stays empty, like
 * G07B/G03D/G08B/G05C).
 */
export const G10R_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group10restHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-obstruction calmness 0..100: 0 on the obstruction, 50 at halfM. */
export function group10restQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group10RestPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM).
 */
export function group10restQuietnessAt(
  layer: "skyview",
  lat: number,
  lon: number,
  points: Group10RestPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group10restHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group10restQuietFromHalf(best * 1000, G10R_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group10restMatchesContract(
  layer: Group10RestLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G10R_CAL[layer].halfM && doc.sigma === G10R_CAL[layer].sigma;
}

export type Group10RestVerdictKind = "proxy" | "real" | "no-map";

export interface Group10RestVerdict {
  param: Group10RestParam;
  name: string;
  kind: Group10RestVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 10 rest (the no-map row is the docs
 * evidence; the scorer dim lives in services/scoring/dims_group10rest.py).
 */
export const G10R_VERDICTS: Group10RestVerdict[] = [
  {
    param: 215,
    name: "Satellite internet line-of-sight",
    kind: "proxy",
    reason:
      "Shipped as skyview: distance to 5604 mapped 5+ storey buildings + 15928 mapped forest features (9596 in Tallinn) as open-sky hinnang — honestly labelled, never measured coverage and never the TTJA katvuskaart; the field is radial while real obstruction is directional, so red means check on site.",
  },
  {
    param: 491,
    name: "Indoor dead zones",
    kind: "no-map",
    reason:
      "A per-room RF measurement (carrier, floor, indoor walls); the snapshot carries zero indoor-signal keys, and building:material (5131 uses, ~2% of buildings) is the wrong shape — own-wall material, not an area gradient. Scorer dim stays NULL with an on-site-measurement reason.",
  },
];

/** Batch params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP10REST_NO_MAP_PARAMS: number[] = G10R_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP10REST_HOOK =
  "G10R-HOOK (#171): skyview wired into layers/overlays/snapshot; p491 verdict + dim only.";
