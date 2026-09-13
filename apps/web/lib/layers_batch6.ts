// Batch 6 mobility/access layers (issue #133): leftover place-params
// from Group 12 (p11/p17), Group 13 (p220/p270) and Group 15 (p386).
//
// One shipped layer per mappable param, Harjumaa scope, local
// 2026-09-12 snapshot ONLY. Scores are absolute 0..100; unknown stays
// 255 (renders red). This file owns ALL Batch-6 runtime data; shared
// files (lib/layers.ts, lib/server/snapshot.ts, lib/overlays.ts) touch
// it only through small marked `B6-HOOK (#133)` blocks, so the sibling
// batches stay disjoint. That module imports layers only as types, so
// no runtime cycle.
//
// PER-PARAM VERDICTS (load-bearing, reviewed in PR #133):
// * p11 commute time (G12): DOCUMENTED NO-MAP (see BATCH6_NO_MAP).
//   Reaffirms the issue #126 delivery note ("scorer dims ONLY, no raster
//   masters"): p11 is a per-listing minutes estimate with no destination,
//   and a county kernel of GTFS frequency would duplicate the p15
//   transit layer under a new name. Scorer: dims_group12.py (untouched).
// * p17 family/friends proximity (G12): DOCUMENTED NO-MAP. Where YOUR
//   family lives is not a place attribute — no registry and no honest
//   OSM proxy exists. Scorer: services/scoring/dims_batch6.py (new,
//   buyer-supplied "family" POIs, this batch).
// * p220 drone delivery clearance (G13): REAL quiet layer ("droneclear",
//   inverted nearest aerodrome/helipad site). Disagrees with the #126
//   "no raster" note on the record: that note feared sparse point-kernel
//   spikes, but a quiet-kind DISTANCE field has no spikes — every
//   in-bbox cell reads its nearest-site distance (flightcorr/p445 proves
//   the shape for airspace-adjacent sources). Helipads included, no
//   runway axis lobes: that is the honest split from flightcorr, which
//   scores runway NOISE corridors and deliberately excludes helipads.
// * p270 drone delivery viability (G13): REAL layer ("droneviab"),
//   min(clearance leg, yard leg) per cell — a drone needs BOTH
//   likely-clear airspace AND somewhere to land, so min() is the honest
//   combiner (same combiner and bands as the dims_group13.py scorer).
//   The yard leg is raster-side + fallback-only for the wire contract
//   (flightcorr minor-tier precedent): the wire half carries the
//   clearance leg.
// * p386 university-town rental bleed (G15): REAL quiet layer
//   ("rentbleed", hinnang). Student-rental pressure proxied by inverted
//   nearest distance to mapped universities/colleges/dormitories. Red
//   near campus = high pressure (owner-occupier framing, documented
//   judgment call — the schools/p12 layer scores the same universities
//   as variety GREEN, and buyer weights resolve the two views). Never
//   euros: the rental registries are not in the snapshot.
//
// HONESTY (load-bearing): the EANS UTM DroneMap WFS, Maa-amet yard
// clearances and any rental registry are NOT in the snapshot (MANIFEST
// gaps), so every title/legend/source says "proksi (hinnang)" plus
// "mitte EANS DroneMap" where airspace is claimed. Green =
// clear/viable/calm (far), red = restricted/unviable/pressured (near).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-count ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     aeroway=aerodrome aeroway=helipad
//   10  aeroway=aerodrome (7 nodes + 3 ways, named: Tallinna lennujaam,
//   Ämari, Haapsalu, Paslepa, Lyckholm, Humala, Aespa, Rapla, Kose,
//   Jägala — dims_group13.py §; export carries node+way+multipolygon
//   twins, harmless: nearest-only fields are minimum-immune)
//   33  aeroway=helipad (26 nodes + 7 ways, incl. ~20-pad Ämari cluster
//   and hospital/city pads)
//   osmium tags-filter ... nwr/amenity=university nwr/amenity=college
//     nwr/amenity=dormitory nwr/building=dormitory (see
//     scripts/build/batch_b6_mobility.py docstring -> derived-campus.geojson)
//   12 amenity=university + 12 amenity=college + 16 building=dormitory
//   + 2 amenity=dormitory (TalTech, TLU, EKA, EMTA, EBS, Mainor,
//   Mereakadeemia...; outlines collapse to bbox-center reps, 32 untagged
//   member nodes dropped).
//
// Calibration (judgment calls, documented for the reviewer): all three
// are quiet-kind nearest-distance layers (100·d/(d+halfM)), mirroring
// the GENV path. Halves locked 2026-09-12 from county-master probes
// (Balti/Viru/Kadriorg/Õismäe/Lasnamäe/Viimsi/Nõmme/rural/airport/
// TalTech — witness table in PR #133):
// * droneclear halfM 1300: fits the scorer CLEARANCE_BANDS mid-range
//   (1000 m -> 43 vs 40, 2000 m -> 61 vs 60, 4000 m -> 75 vs 75);
//   Tallinn-window median 73 (most of the city IS clear airspace —
//   honestly mostly-green, airport + hospital pads read red).
// * droneviab clear leg 800: fits VIABILITY_CLEAR_BANDS mid-range
//   (1000 m -> 56 vs 55, 2000 m -> 71 vs 75); Tallinn-window median 40
//   (the yard leg binds in dense blocks by design).
// * rentbleed halfM 800: TalTech 16 / Balti 28 / Viru 40 / suburbs
//   ~55 / Viimsi 89 (pressure is localized by nature — mostly-green
//   with red campus pockets, like the safety lone-station cap).
// Sigmas equal the Euclidean fallback decay (DECAY_KM hook) and the
// raster contract (matchesContract): 0.3 km throughout (quiet family).
// Air layers use direct grid distance BY DESIGN (airspace zones are
// circles around sites — drones fly, they do not walk; walk-graph
// routing would speckle an airspace field with footpath barriers).

import type { BonusSpec, LayerDef } from "./layers";

export type Batch6LayerId = "droneclear" | "droneviab" | "rentbleed";

export const BATCH6_LAYER_IDS: Batch6LayerId[] = [
  "droneclear",
  "droneviab",
  "rentbleed",
];

/** parameters3.md number per shipped Batch-6 layer. */
export const BATCH6_PARAMS: Record<Batch6LayerId, number> = {
  droneclear: 220,
  droneviab: 270,
  rentbleed: 386,
};

/**
 * Documented no-map verdicts (OTA PR #131 precedent): params with no
 * honest snapshot layer. Pinned by test so the verdict stays reviewable.
 */
export const BATCH6_NO_MAP = [
  {
    param: 11,
    name: "Commute time",
    verdict: "no-map",
    reason:
      "Per-listing minutes estimate with no destination (reaffirms issue " +
      "#126: scorer dims ONLY); a county GTFS-frequency kernel would " +
      "duplicate the p15 transit layer under a new name.",
    scorer: "services/scoring/dims_group12.py",
  },
  {
    param: 17,
    name: "Proximity to family/friends",
    verdict: "no-map",
    reason:
      "Where YOUR family lives is not a place attribute — no registry " +
      "and no honest OSM proxy exists; scored per listing from " +
      "buyer-supplied coordinates, never mapped.",
    scorer: "services/scoring/dims_batch6.py",
  },
] as const;

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const BATCH6_DEFS: LayerDef[] = [
  {
    id: "droneclear",
    paramIds: [220],
    title: "Droonilendude õhuruum (proksi, hinnang)",
    goodLabel: "roheline = lennuväljadest kaugel, õhuruum tõenäoliselt vaba (proksi)",
    badLabel: "punane = lennuvälja/helikopteriväljaku lähedal (proksi)",
    source:
      `${SNAP} (lennuväljad + helikopteriväljakud OSM; PROKSI, mitte EANS DroneMap — tegelikku lennuluba ei näita)`,
    fallbackPoints: [
      { lat: 59.41646, lon: 24.79659 }, // Lennujaam (piiratud)
      { lat: 59.51, lon: 24.83 }, // Viimsi (vaba)
    ],
  },
  {
    id: "droneviab",
    paramIds: [270],
    title: "Droonitarne võimalikkus (proksi, hinnang)",
    goodLabel: "roheline = õhuruum vaba JA avatud maandumisala lähedal (proksi)",
    badLabel: "punane = piiratud õhuruum või maandumisala puudub (proksi)",
    source:
      `${SNAP} (lennuväljad + haljasalad OSM; PROKSI, mitte EANS DroneMap ega Maa-ameti õuealad)`,
    fallbackPoints: [
      { lat: 59.41646, lon: 24.79659 }, // Lennujaam (õhuruum piirab)
      { lat: 59.4386, lon: 24.7912 }, // Kadriorg (park + vaba õhuruum)
    ],
  },
  {
    id: "rentbleed",
    paramIds: [386],
    title: "Üliõpilasüürisurve (proksi, hinnang)",
    goodLabel: "roheline = ülikoolidest kaugel, rahulik elukeskkond (proksi)",
    badLabel: "punane = ülikooli/ühiselamu lähedal, tugev üürisurve (proksi)",
    source:
      `${SNAP} (ülikoolid + kolledžid + ühiselamud OSM; PROKSI, mitte üüriregister — eurosid ei mõõda)`,
    fallbackPoints: [
      { lat: 59.3947, lon: 24.6615 }, // TalTech (surve)
      { lat: 59.51, lon: 24.83 }, // Viimsi (rahulik)
    ],
  },
];

/** Influence radii in km (== walk-kernel sigma == Euclidean fallback decay). */
export const BATCH6_DECAY: Record<Batch6LayerId, number> = {
  droneclear: 0.3,
  droneviab: 0.3,
  rentbleed: 0.3,
};

/**
 * Overpass QL fragments for the layer inside the bbox. Snapshot-only
 * serving never queries live; these document the source tags. nwr/
 * everywhere ways/areas carry the feature (PR #118: node-only would
 * drop the 3 aerodrome + 7 helipad ways, including the Tallinna
 * lennujaam polygon, and every campus building outline).
 */
export const BATCH6_TAGS: Record<Batch6LayerId, string> = {
  droneclear: 'nwr["aeroway"~"aerodrome|helipad"];',
  droneviab: 'nwr["aeroway"~"aerodrome|helipad"];',
  rentbleed: 'nwr["amenity"~"university|college|dormitory"];nwr["building"="dormitory"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const BATCH6_RASTER_FILE: Record<Batch6LayerId, string> = {
  droneclear: "droneclear-walk-raster.json",
  droneviab: "droneviab-walk-raster.json",
  rentbleed: "rentbleed-walk-raster.json",
};

/**
 * NO metro masters (documented, GENV precedent): smooth proxy fields at
 * the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for these layers.
 */
export const BATCH6_NO_METRO = true;

/**
 * Calibration locked 2026-09-12 from county-master probes (mirrors
 * scripts/build/batch_b6_mobility.py B6_CAL exactly — test_batch_b6.py
 * parses this block and fails on drift). droneviab carries the
 * CLEARANCE leg half on the wire; the yard step bands live raster-side
 * + in b6YardScore below (flightcorr minor-tier precedent).
 */
export const B6_CAL = {
  droneclear: { halfM: 1300, sigma: 0.3 },
  droneviab: { clearHalfM: 800, sigma: 0.3 },
  rentbleed: { halfM: 800, sigma: 0.3 },
} as const;

/**
 * p270 yard leg bands: nearest open-landing proxy (== the
 * services/scoring/dims_group13.py YARD_BANDS scorer bands, pinned by
 * test on both sides).
 */
export const B6_YARD_BANDS: ReadonlyArray<readonly [number, number]> = [
  [100, 100],
  [300, 80],
  [500, 60],
  [1000, 40],
  [Infinity, 25],
];

export const BATCH6_BONUS: Record<Batch6LayerId, BonusSpec> = {
  droneclear: { kind: "quiet", halfM: 1300 },
  // Wire carries the clearance leg (see contract_of in the builder).
  droneviab: { kind: "quiet", halfM: 800 },
  rentbleed: { kind: "quiet", halfM: 800 },
};

/**
 * Batch-6 bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for every other layer (their specs handle them).
 */
export function bonusSpecForBatch6(layer: string): BonusSpec | undefined {
  return (BATCH6_BONUS as Record<string, BonusSpec>)[layer];
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function b6HavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function b6QuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

/** p270 yard leg score from park distance in metres (step bands). */
export function b6YardScore(dM: number): number {
  for (const [limit, pts] of B6_YARD_BANDS) {
    if (dM <= limit) return pts;
  }
  return 25;
}

export interface B6Point {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when there
 * is nothing to score — never a faked zero. droneviab takes the
 * caller-supplied park distance (null = unmapped yard leg, which binds
 * the min at 25 — dense blocks genuinely lack landing space, same as
 * the scorer's no-park fallback).
 */
export function b6QuietnessAt(
  layer: Batch6LayerId,
  lat: number,
  lon: number,
  points: B6Point[],
  yardDM: number | null = null,
): number | null {
  if (points.length === 0) return null;
  const spec = BATCH6_BONUS[layer];
  if (spec.kind !== "quiet") return null;
  let best = Infinity;
  for (const p of points) {
    const d = b6HavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  const clear = b6QuietFromHalf(best * 1000, spec.halfM);
  if (layer !== "droneviab") return Math.round(clear);
  const yard = yardDM === null ? 25 : b6YardScore(yardDM);
  return Math.round(Math.min(clear, yard));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function b6MatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: Batch6LayerId,
): boolean {
  if (!doc) return false;
  const spec = BATCH6_BONUS[layer];
  if (doc.sigma !== BATCH6_DECAY[layer]) return false;
  if (spec.kind !== "quiet") return false;
  return doc.half === spec.halfM;
}
