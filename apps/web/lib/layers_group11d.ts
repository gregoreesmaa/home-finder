// G11D layers: Group 11 amenity leftovers B (issue #135,
// parameters3.md section 5.11). One layer per mappable param; p317
// (park maintenance/enforcement) is a documented no-map (see below).
//
// Snapshot counts 2026-09-12 (osmium over harjumaa-260911.osm.pbf,
// Harjumaa; Tallinn bbox 24.5-24.9/59.35-59.5 in brackets):
//   amenity=post_box 122 nodes [75] + amenity=letter_box 4 [1]
//   amenity=post_office 76n+5w [13] + amenity=parcel_locker 523n+3w [406]
//   service=alley 34 ways [51/59 exported features touch Tallinn]
//   highway=path 10746 ways (dense in Tallinn parks/forests)
// No live Overpass/network in this module; the app serves the frozen
// snapshot, never live data.
//
// Per-param verdicts:
// * p346 mailbox placement/security -> "mailbox": REAL snapshot layer
//   (post_box + letter_box count kernel). Hinnang label: OSM maps box
//   positions, never placement quality or security, so the legend says
//   proximity (hinnang), never safety.
// * p470 mail delivery location -> "postal": REAL snapshot layer
//   (post_office + parcel_locker count kernel, same merge precedent as
//   dim_postal in dims_group11b.py).
// * p419 alleyway access -> "alley": REAL snapshot layer (service=alley
//   way-km density, evac road-km precedent from layers_batch5.ts).
//   Sparse (34 ways) but real; absence reads red (unknown), honestly.
// * p466 public-trail privacy loss -> "trailprivacy": REAL snapshot
//   layer, INVERTED scale (highway=path way-km density through the
//   quiet transform: green = private, red = trail-dense). Only
//   highway=path counts -- urban footway/cycleway sidewalks are
//   deliberately excluded (same rule as dim_trail_privacy), otherwise
//   every city listing would read exposed.
// * p317 park maintenance/enforcement -> DOCUMENTED NO-MAP (OTA PR #131
//   precedent): no OSM tag encodes upkeep/enforcement quality, so any
//   gradient would be fake precision (AGENTS.md section 7.2). No
//   registry entry; the scorer stub in dims_group11.py stands and
//   dims_group11d.py re-exports it.
//
// Shared-file wiring (marked G11D-HOOK lines in lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts, lib/distanceField.ts) spreads
// these tables into the LayerId union, LAYERS registry, TAGS, DECAY_KM,
// bonusSpecFor (+ the shared "quiet" BonusSpec kind, first wired use --
// GENV designed it but is still unwired), RASTER_FILE and METRO_PREFIX
// with one line per table -- this file owns all G11D logic so the hooks
// stay trivial. Type-only imports from ./layers: no runtime cycle
// (layers.ts imports values from here).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type G11DLayerId = "mailbox" | "postal" | "alley" | "trailprivacy";

export const G11D_LAYER_IDS: G11DLayerId[] = ["mailbox", "postal", "alley", "trailprivacy"];

/** parameters3.md parameter numbers per layer (p317 is no-map, no entry). */
export const G11D_PARAM_IDS: Record<G11DLayerId, number[]> = {
  mailbox: [346],
  postal: [470],
  alley: [419],
  trailprivacy: [466],
};

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const G11D_LAYERS: LayerDef[] = [
  {
    id: "mailbox",
    paramIds: [346],
    title: "Postkastid (hinnang)",
    goodLabel: "roheline = postkast jalutuskäigu kaugusel (hinnang)",
    badLabel: "punane = kaardistatud postkasti läheduses pole",
    source: `${SNAP} (kõndimisgraafik + amenity=post_box/letter_box; PROKSI: asukoht, mitte turvalisus)`,
    // Real snapshot features (labeled demo only: shown iff the snapshot
    // cannot be read). Coordinates rounded from harju-amenities.geojson.
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7558 }, // post_box (snapshot, Kesklinn)
      { lat: 59.4363, lon: 24.8207 }, // post_box (snapshot, Lasnamäe)
      { lat: 59.4432, lon: 24.8725 }, // post_box (snapshot, Pirita)
    ],
  },
  {
    id: "postal",
    paramIds: [470],
    title: "Postiteenused",
    goodLabel: "roheline = postkontor/pakiautomaat jalutuskäigu kaugusel",
    badLabel: "punane = postiteenus kaugel",
    source: `${SNAP} (kõndimisgraafik + amenity=post_office/parcel_locker)`,
    fallbackPoints: [
      { lat: 59.4361, lon: 24.739 }, // post_office (snapshot, Kesklinn)
      { lat: 59.4265, lon: 24.7821 }, // parcel_locker (snapshot)
      { lat: 59.4406, lon: 24.8628 }, // post_office (snapshot, Lasnamäe)
    ],
  },
  {
    id: "alley",
    paramIds: [419],
    title: "Tagateed",
    goodLabel: "roheline = kaardistatud taga-tee lähedal",
    badLabel: "punane = taga-teid läheduses kaardistatud pole",
    source: `${SNAP} (kõndimisgraafik + service=alley teede km)`,
    fallbackPoints: [
      { lat: 59.4444, lon: 24.702 }, // alley (snapshot, Põhja-Tallinn)
      { lat: 59.4505, lon: 24.7137 }, // alley (snapshot, Põhja-Tallinn)
      { lat: 59.4202, lon: 24.5888 }, // alley (snapshot, Haabersti)
    ],
  },
  {
    id: "trailprivacy",
    paramIds: [466],
    title: "Rajaprivaatsus (hinnang)",
    goodLabel: "roheline = privaatne, matkarada kaugel (hinnang)",
    badLabel: "punane = tihe rajavõrk lähedal, privaatsust vähem",
    source: `${SNAP} (kõndimisgraafik + highway=path teede km, PÖÖRATUD skaala; PROKSI)`,
    fallbackPoints: [
      { lat: 59.3889, lon: 24.657 }, // path (snapshot, Nõmme mets)
      { lat: 59.4382, lon: 24.6834 }, // path (snapshot, Pelgulinn)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (radadest kaugel, privaatne)
    ],
  },
];

/**
 * Overpass QL per layer (documents the source tags for future use; the app
 * serves the frozen snapshot, never live Overpass). Mirrors the
 * scripts/build/batch_g11d_leftovers.py predicates exactly. nwr/
 * everywhere ways carry the feature (PR #118: node-only silently drops
 * way-mapped post offices, lockers, alleys and paths).
 */
export const G11D_TAGS: Record<G11DLayerId, string> = {
  mailbox: 'nwr["amenity"~"post_box|letter_box"];',
  postal: 'nwr["amenity"~"post_office|parcel_locker"];',
  alley: 'nwr["service"="alley"];',
  trailprivacy: 'nwr["highway"="path"];',
};

/**
 * Influence radii (km). Neighbourhood amenities (mailbox) and sparse
 * networks (alley, trailprivacy) read at the tighter 0.5; destination
 * trips (postal) at the healthcare scale (0.8). Way radii match the
 * 500 m privacy/access window of dims_group11b.py.
 */
export const G11D_DECAY: Record<G11DLayerId, number> = {
  mailbox: 0.5,
  postal: 0.8,
  alley: 0.5,
  trailprivacy: 0.5,
};

/**
 * Saturation midpoints, histogram-locked 2026-09-12 (Tallinn known-cell
 * medians mid-ramp; see the builder docstring for the probe numbers).
 * Locked with LAYER_DEFAULTS in scripts/build/batch_g11d_leftovers.py --
 * the raster wire doc carries these numbers and the server rejects
 * mismatches. trailprivacy is a quiet-kind layer: halfM is metres of
 * trail-km saturation (score = 100*half/(S+half), 90 where the walk
 * network reaches but no trail does).
 */
export const G11D_BONUS: Record<G11DLayerId, { kind: "area"; half: number } | { kind: "quiet"; halfM: number }> = {
  mailbox: { kind: "area", half: 2.5 },
  postal: { kind: "area", half: 12.0 },
  alley: { kind: "area", half: 0.3 },
  trailprivacy: { kind: "quiet", halfM: 1500 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isG11DLayerId(layer: LayerId): layer is G11DLayerId {
  return (G11D_LAYER_IDS as string[]).includes(layer);
}

/** Bonus spec for one G11D layer (called from the bonusSpecFor hook). */
export function g11dBonusSpecFor(layer: G11DLayerId): BonusSpec {
  return G11D_BONUS[layer];
}

/** Raster master files per G11D layer (built by batch_g11d_leftovers.py). */
export const G11D_RASTER_FILES: Record<G11DLayerId, string> = {
  mailbox: "mailbox-walk-raster.json",
  postal: "postal-walk-raster.json",
  alley: "alley-walk-raster.json",
  trailprivacy: "trailprivacy-walk-raster.json",
};

/**
 * NO metro masters (documented): county-only falls back cleanly (B5/GENV
 * precedent) -- sparse count kernels and the smooth privacy field gain
 * no honest precision from 9.375 m cells. The METRO_PREFIX hook still
 * lists per-layer names (Record type); the window route treats the
 * missing files as county-only.
 */
export const G11D_METRO_PREFIXES: Record<G11DLayerId, string> = {
  mailbox: "mailbox-metro",
  postal: "postal-metro",
  alley: "alley-metro",
  trailprivacy: "trailprivacy-metro",
};

/**
 * Inverted trail-privacy score 0..100 from accumulated trail-km S:
 * 100*half/(S+half), so dense trail networks read exposed (low) and
 * trail-free walk-network cells read private (high). Mirrors
 * quiet_score() in scripts/build/batch_g11d_leftovers.py -- a pytest
 * parses neither file, so the vitest suite below locks the shared
 * numbers (FAR_SCORE 90 matches dim_trail_privacy's unmapped fallback).
 */
export const G11D_TRAIL_FAR_SCORE = 90;

export function g11dQuietScore(trailKm: number, halfKm: number): number {
  if (!(trailKm > 0)) return G11D_TRAIL_FAR_SCORE;
  return (100 * halfKm) / (trailKm + halfKm);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function g11dQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}
