// Group 11 leftover-A layers (parameters3.md §5.11, issue #134):
// p88 school-bus access, p101 specialized recreation, p124 specialized
// medical, p169 philosophical/religious proximity, p190 foraging.
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100; unknown stays 255 (renders red). This file owns ALL G11C
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `G11C-HOOK (#134)`
// blocks, so the sibling batches stay disjoint.
//
// HONESTY (load-bearing): real school-bus ROUTES are not mapped
// (route=school_bus has ~2 uses globally), so schoolbus is an honestly-
// labeled PROXY: amenity=school gated on a transit stop within 500 m
// (the exact dim_school_bus scorer logic). Its title/legend/source say
// "hinnang" (estimate), never a claimed route. recspecial/medspecial/
// worship/forage stamp mapped OSM features directly (real snapshot
// layers): specialized leisure, hospitals/dentists, places of worship,
// forest/scrub/heath units. Forage stamps one point per mapped polygon
// (centroid-density, NOT hectares -- a big forest counts like several
// small ones only via its mapped parts, never via measured yield).
//
// Tag verification (2026-09-12, local snapshot -- no network):
//   harju-amenities.geojson sweep (147295 features):
//   amenity=school 342 (337 within 500 m of a stop -- gated: 5 rural
//     schools read red, honestly stop-less); leisure=sports_centre|
//     sports_hall|stadium|swimming_pool|water_park|ice_rink|golf_course|
//     fitness_centre 523; amenity=hospital 41 + amenity=dentist 79;
//     amenity=place_of_worship|monastery 241.
//   harjumaa-260911.osm.pbf (the sweep drops forest polygons -- only 12
//   wood + 4 scrub -- so a one-time osmium export feeds forage):
//   landuse=forest + natural=wood|scrub|heath: 10483 polygons + 104
//   nodes -> 19473 deduped source points (see read_forest_points in
//   scripts/build/batch_g11c_amenity.py).
//
// Calibration (judgment calls, documented for the reviewer): all five
// are unweighted count kernels, area-kind saturating scores
// (100·S/(S+half)), mirroring the grocery/healthcare/B1 path.
// Destination trips (recspecial/medspecial/worship) read at the
// healthcare scale (0.8); neighbourhood access (schoolbus/forage) at a
// tighter 0.5. Halves histogram-locked 2026-09-12 (Tallinn-window
// known-cell medians 24-30, maxes 74-96 -- streets discriminate instead
// of blobbing; recspecial/medspecial/forage needed larger halves than
// their first guesses after the probe). Locked with LAYER_DEFAULTS in
// scripts/build/batch_g11c_amenity.py -- the raster wire doc carries
// these numbers and the server rejects mismatches.

import type { BonusSpec, LayerDef } from "./layers";

export type Group11CLayerId = "schoolbus" | "recspecial" | "medspecial" | "worship" | "forage";

export const G11C_LAYER_IDS: Group11CLayerId[] = [
  "schoolbus",
  "recspecial",
  "medspecial",
  "worship",
  "forage",
];

/** parameters3.md number per G11C layer. */
export const G11C_PARAMS: Record<Group11CLayerId, number> = {
  schoolbus: 88,
  recspecial: 101,
  medspecial: 124,
  worship: 169,
  forage: 190,
};

/**
 * Per-param verdict for the map (mirrored in services/scoring/
 * dims_group11c.py G11C_VERDICTS -- keep the two in sync).
 * "proxy" = honestly-labeled hinnang; "real" = mapped features directly.
 */
export const G11C_VERDICTS: Record<Group11CLayerId, "proxy" | "real"> = {
  schoolbus: "proxy",
  recspecial: "real",
  medspecial: "real",
  worship: "real",
  forage: "real",
};

export const G11C_DEFS: LayerDef[] = [
  {
    id: "schoolbus",
    paramIds: [88],
    title: "Koolibuss (peatusega kooli hinnang)",
    goodLabel: "roheline = peatusega kool jalutuskäigu kaugusel (hinnang)",
    badLabel: "punane = kool kaugel või peatuseta (hinnang, MITTE tegelik bussiliin)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM amenity=school 500 m peatuseulatuses, 337/342; tegelikud koolibussiliinid kaardil pole)",
    fallbackPoints: [
      { lat: 59.4383, lon: 24.749 }, // kool kesklinnas (hetktõmmis)
      { lat: 59.4353, lon: 24.7664 }, // kool kesklinnas (hetktõmmis)
      { lat: 59.4278, lon: 24.7418 }, // kool kesklinnas (hetktõmmis)
      { lat: 58.9352, lon: 23.541 }, // maakool (hetktõmmis)
    ],
  },
  {
    id: "recspecial",
    paramIds: [101],
    title: "Erisport (staadion, ujula, hall)",
    goodLabel: "roheline = erispordipaik (staadion/ujula/hall) lähedal",
    badLabel: "punane = erispordipaika lähedal pole",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM leisure sporditasand: 523 kaardistatud paika; tavalised mänguväljakud loeb pargikiht)",
    fallbackPoints: [
      { lat: 59.4372, lon: 24.7512 }, // fitness (hetktõmmis)
      { lat: 59.4376, lon: 24.756 }, // spordikeskus (hetktõmmis)
      { lat: 59.4364, lon: 24.7567 }, // spordikeskus (hetktõmmis)
    ],
  },
  {
    id: "medspecial",
    paramIds: [124],
    title: "Eriarstiabi (haigla, hambaarst)",
    goodLabel: "roheline = haigla või hambaarst lähedal",
    badLabel: "punane = eriarstiabi kaugel",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM haigla 41 + hambaarst 79; perearst/apteek loeb tervishoiukiht)",
    fallbackPoints: [
      { lat: 59.4384, lon: 24.751 }, // hambaarst (hetktõmmis)
      { lat: 59.4388, lon: 24.7498 }, // hambaarst (hetktõmmis)
      { lat: 59.4398, lon: 24.7559 }, // hambaarst (hetktõmmis)
    ],
  },
  {
    id: "worship",
    paramIds: [169],
    title: "Pühakojad ja kloostrid",
    goodLabel: "roheline = pühakoda lähedal",
    badLabel: "punane = pühakoda kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (OSM place_of_worship/monastery: 241 kaardistatud paika)",
    fallbackPoints: [
      { lat: 59.4379, lon: 24.7532 }, // pühakoda (hetktõmmis)
      { lat: 59.438, lon: 24.7529 }, // pühakoda (hetktõmmis)
      { lat: 59.4377, lon: 24.7488 }, // pühakoda (hetktõmmis)
    ],
  },
  {
    id: "forage",
    paramIds: [190],
    title: "Korjealad (mets, võsa, nõmm)",
    goodLabel: "roheline = mets/võsa lähedal (marja- ja seenemaa)",
    badLabel: "punane = korjemaad kaugel",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM landuse=forest + natural=wood/scrub/heath: ~19 tuhat kaardistatud üksust; saagikust kaardil pole)",
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7489 }, // salumets (hetktõmmis)
      { lat: 59.429, lon: 24.7602 }, // mets (hetktõmmis)
      { lat: 59.4457, lon: 24.7464 }, // võsa (hetktõmmis)
      { lat: 58.8491, lon: 23.5067 }, // maamets (hetktõmmis)
    ],
  },
];

/** Influence radii in km (== walk-kernel sigma == Euclidean fallback decay). */
export const G11C_DECAY: Record<Group11CLayerId, number> = {
  schoolbus: 0.5,
  recspecial: 0.8,
  medspecial: 0.8,
  worship: 0.8,
  forage: 0.5,
};

/**
 * Overpass QL fragments for the layer inside the bbox. Snapshot-only
 * serving never queries live; these document the source tags. The p88
 * stop gate (500 m) is applied at build time -- Overpass cannot express
 * that join in one fragment, so the fragment over-selects and the
 * builder keeps stop-served schools.
 */
export const G11C_TAGS: Record<Group11CLayerId, string> = {
  schoolbus: 'nwr["amenity"="school"];nwr["highway"="bus_stop"];nwr["public_transport"~"platform|stop_position|station"];',
  recspecial:
    'nwr["leisure"~"sports_centre|sports_hall|stadium|swimming_pool|water_park|ice_rink|golf_course|fitness_centre"];',
  medspecial: 'nwr["amenity"~"hospital|dentist"];',
  worship: 'nwr["amenity"~"place_of_worship|monastery"];',
  forage: 'nwr["landuse"="forest"];nwr["natural"~"wood|scrub|heath"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const G11C_RASTER_FILE: Record<Group11CLayerId, string> = {
  schoolbus: "schoolbus-walk-raster.json",
  recspecial: "recspecial-walk-raster.json",
  medspecial: "medspecial-walk-raster.json",
  worship: "worship-walk-raster.json",
  forage: "forage-walk-raster.json",
};

/**
 * Metro prefixes (county-only layers: no metro masters are built -- a
 * smooth count kernel needs no 9 m cells -- so these name the files the
 * window route would read; absent files fall back to county cleanly,
 * B5 precedent).
 */
export const G11C_METRO_PREFIX: Record<Group11CLayerId, string> = {
  schoolbus: "schoolbus-metro",
  recspecial: "recspecial-metro",
  medspecial: "medspecial-metro",
  worship: "worship-metro",
  forage: "forage-metro",
};

/**
 * Bonus specs (the single source of halves -- locked with LAYER_DEFAULTS
 * in scripts/build/batch_g11c_amenity.py; the raster wire doc carries
 * them and the server rejects mismatches).
 */
export const G11C_BONUS: Record<Group11CLayerId, BonusSpec> = {
  schoolbus: { kind: "area", half: 4.0 },
  recspecial: { kind: "area", half: 8.0 },
  medspecial: { kind: "area", half: 5.0 },
  worship: { kind: "area", half: 2.5 },
  forage: { kind: "area", half: 12.0 },
};

/**
 * G11C bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for all other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup11C(layer: string): BonusSpec | undefined {
  return (G11C_BONUS as Record<string, BonusSpec>)[layer];
}
