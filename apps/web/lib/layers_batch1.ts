// Batch B1 layers: Group 11 OSM amenity-proximity scores (issue #98,
// parameters3.md section 5.11). Point-kernel layers in the
// grocery/healthcare style: unweighted nearby-feature counts, saturating
// (score = 100*S/(S+half)), absolute 0-100, Harjumaa scope, local
// 2026-09-12 snapshot only. Unknown stays 255 (renders red, honest).
//
// Every tag below was verified present in the snapshot before use
// (snapshot counts: pets 229, community 238, culture 259, nightlife 283,
// libraries 86). No live Overpass/network in this module.
//
// Shared-file wiring (marked B1-HOOK lines in lib/layers.ts and
// lib/server/snapshot.ts) spreads these tables into the LayerId union,
// LAYERS registry, TAGS, DECAY_KM, bonusSpecFor, RASTER_FILE and
// METRO_PREFIX with one line per table -- this file owns all B1 logic so
// the hooks stay trivial. Type-only imports from ./layers: no runtime
// cycle (layers.ts imports values from here).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type B1LayerId = "pets" | "community" | "culture" | "nightlife" | "libraries";

export const B1_LAYER_IDS: B1LayerId[] = ["pets", "community", "culture", "nightlife", "libraries"];

/** parameters3.md parameter numbers per layer. */
export const B1_PARAM_IDS: Record<B1LayerId, number[]> = {
  pets: [86],
  community: [87],
  culture: [89],
  nightlife: [108],
  libraries: [313],
};

export const B1_LAYERS: LayerDef[] = [
  {
    id: "pets",
    paramIds: [86],
    title: "Lemmikloomad",
    goodLabel: "roheline = koerapark või loomaarst jalutuskäigu kaugusel",
    badLabel: "punane = lemmikloomateenused kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + leisure/amenity/shop)",
    // Real snapshot features (labeled demo only: shown iff the snapshot
    // cannot be read). Coordinates rounded from derived-pets.json.
    fallbackPoints: [
      { lat: 59.381, lon: 24.6986 }, // vet (snapshot)
      { lat: 59.3887, lon: 24.6826 }, // vet (snapshot)
      { lat: 59.4276, lon: 24.5493 }, // dog park (snapshot)
    ],
  },
  {
    id: "community",
    paramIds: [87],
    title: "Kogukonnaruumid",
    goodLabel: "roheline = kogukonnakeskus lähedal",
    badLabel: "punane = kogukonnaruumid kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + amenity)",
    fallbackPoints: [
      { lat: 59.4372, lon: 24.7517 }, // townhall (snapshot)
      { lat: 59.4327, lon: 24.744 }, // townhall (snapshot)
      { lat: 59.454, lon: 24.8347 }, // social facility (snapshot)
    ],
  },
  {
    id: "culture",
    paramIds: [89],
    title: "Kultuur",
    goodLabel: "roheline = teater/muuseum jalutuskäigu kaugusel",
    badLabel: "punane = kultuur kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + amenity/tourism)",
    fallbackPoints: [
      { lat: 59.4382, lon: 24.7433 }, // theatre (snapshot)
      { lat: 59.4405, lon: 24.7476 }, // museum (snapshot)
      { lat: 59.4403, lon: 24.8316 }, // gallery (snapshot)
    ],
  },
  {
    id: "nightlife",
    paramIds: [108],
    title: "Ööelu",
    goodLabel: "roheline = baarid ja kino lähedal",
    badLabel: "punane = ööelu kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + amenity)",
    fallbackPoints: [
      { lat: 59.4303, lon: 24.7468 }, // nightclub (snapshot)
      { lat: 59.4383, lon: 24.7565 }, // cinema (snapshot)
      { lat: 59.4009, lon: 24.6972 }, // casino (snapshot)
    ],
  },
  {
    id: "libraries",
    paramIds: [313],
    title: "Raamatukogud",
    goodLabel: "roheline = raamatukogu jalutuskäigu kaugusel",
    badLabel: "punane = raamatukogu kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + amenity)",
    fallbackPoints: [
      { lat: 59.4336, lon: 24.7534 }, // library (snapshot)
      { lat: 59.4423, lon: 24.7489 }, // library (snapshot)
      { lat: 59.4304, lon: 24.7386 }, // library (snapshot)
    ],
  },
];

/**
 * Overpass QL per layer (documents the source tags for future use; the app
 * serves the frozen snapshot, never live Overpass). Mirrors the
 * scripts/build/batch_b1_group11.py predicates exactly, including the
 * Teachers' House rule (community excludes tourism=museum/gallery, which
 * culture claims) -- verified disjoint on the snapshot.
 */
export const B1_TAGS: Record<B1LayerId, string> = {
  pets: 'n["leisure"="dog_park"];n["amenity"="veterinary"];n["shop"="pet"];',
  community: 'n["amenity"~"community_centre|social_facility|townhall"];',
  culture: 'n["amenity"~"arts_centre|theatre|studio"];n["tourism"~"museum|gallery"];',
  nightlife: 'n["amenity"~"bar|pub|nightclub|cinema|casino"];',
  libraries: 'n["amenity"~"library|public_bookcase"];',
};

/**
 * Influence radii (km). Destination trips (culture/nightlife/libraries)
 * read at the healthcare scale (0.8); neighbourhood amenities
 * (pets/community) at a tighter 0.5.
 */
export const B1_DECAY: Record<B1LayerId, number> = {
  pets: 0.5,
  community: 0.5,
  culture: 0.8,
  nightlife: 0.8,
  libraries: 0.8,
};

/**
 * Saturation midpoints, histogram-locked 2026-09-12: Tallinn known-cell
 * median ~15-20, matching the built grocery (17) / healthcare (16) /
 * parks (17) / transit (15) rasters. Same unweighted-count semantics as
 * grocery (half=6): singletons read low-teens, clusters green. Locked with
 * LAYER_DEFAULTS in scripts/build/batch_b1_group11.py -- the raster wire
 * doc carries these numbers and the server rejects mismatches.
 */
export const B1_BONUS: Record<B1LayerId, { kind: "area"; half: number }> = {
  pets: { kind: "area", half: 5.7 },
  community: { kind: "area", half: 3.3 },
  culture: { kind: "area", half: 4.5 },
  nightlife: { kind: "area", half: 7.5 },
  libraries: { kind: "area", half: 3.0 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isB1LayerId(layer: LayerId): layer is B1LayerId {
  return (B1_LAYER_IDS as string[]).includes(layer);
}

/** Bonus spec for one B1 layer (called from the bonusSpecFor hook). */
export function b1BonusSpecFor(layer: B1LayerId): BonusSpec {
  return B1_BONUS[layer];
}

/** Raster master files per B1 layer (built by batch_b1_group11.py). */
export const B1_RASTER_FILES: Record<B1LayerId, string> = {
  pets: "pets-walk-raster.json",
  community: "community-walk-raster.json",
  culture: "culture-walk-raster.json",
  nightlife: "nightlife-walk-raster.json",
  libraries: "libraries-walk-raster.json",
};

/** Metro master file prefixes per B1 layer (meta JSON + raw .u8, 8x cells). */
export const B1_METRO_PREFIXES: Record<B1LayerId, string> = {
  pets: "pets-metro",
  community: "community-metro",
  culture: "culture-metro",
  nightlife: "nightlife-metro",
  libraries: "libraries-metro",
};
