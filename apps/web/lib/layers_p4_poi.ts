// Maa- ja Ruumiamet huvipunktid long-tail overlays (issue #612,
// P4 POI register legs; Group-Y verify-first POSITIVE verdict
// docs/p4_poi_register.md §6 "Licence-day addendum #612").
// This file owns ALL poi overlay runtime tables; shared files
// (lib/layers.ts, lib/distanceField.ts, lib/overlays.ts,
// lib/server/snapshot.ts, app/api/layers/[layer]/route.ts,
// app/layers/page.tsx) touch it only through small marked
// `POI-HOOK (#612)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// FEED VERDICT (2026-09-16, polite harvest, custom UA
// `home-finder-612-poi-wfs/1.0`, 2 s pacing, HTTP 429 as stop, raw
// XML in /tmp/hf-612-poi only — never committed): the keyless
// huvipunktid WFS serves the three long-tail types with no dedicated
// issue (raamatukogu 124 / post 536 / tervisekaubad 187 Harjumaa
// features, CQL mk='Harju maakond', all plotted, zero dropped).
// Licence gate OPENED on the GetCapabilities ServiceIdentification
// Abstract (Maa- ja Ruumiamet avatud ruumiandmete litsents, no
// per-layer override; Fees/AccessConstraints "puudub") — stamped on
// the sidecar + every scorer reason (dims_p4_poi.py LICENCE_OK).
//
// TRANSFORM (labeled, reviewable): none needed — features carry WGS84
// pikkus/laius directly (L-EST97 point rides alongside; magnitudes
// checked). Names/addresses never leave the builder (TAG_ALLOWLIST
// precedent — the wire carries lat/lon/slice only). Post INCLUDES
// pakiautomaat (521/536: post-flip judgment, #612 title — lockers
// are the dominant postal access; offices-only would fake scarcity;
// the subgroup split rides the sidecar stats + the source note).
//
// HONESTY (load-bearing): the kernel is the EXACT scorer band table
// (_score_dist: ≤300 m -> 85, ≤600 m -> 70, ≤1000 m -> 55,
// NULL-beyond — dbands reuse, zero changes). No POI within 1000 m
// stays null/255 (renders red, never a faked "no amenity" score).
// Monthly vahekiht over source registers of varying vintage — every
// reason and source note says so (staleness table in
// docs/p4_poi_register.md §6).
//
// The layers carry NO parameters3.md id: the POI dims are
// parameters4 buyer params (tervise #494 precedent). paramIds stays []
// and paramLabel carries the slice ("P4-poi raamatukogu" / "P4-poi
// post" / "P4-poi apteek") for the layer button.

import type { BBoxLike, BonusSpec, LayerDef, LayerId } from "./layers";

export type PoiLayerId = "poi_library" | "poi_post" | "poi_pharmacy";

export const POI_LAYER_IDS: PoiLayerId[] = ["poi_library", "poi_post", "poi_pharmacy"];

/** Slice tag carried by sidecar points (lat/lon/slice only on the wire). */
export type PoiSlice = "library" | "post" | "pharmacy";

/**
 * Dated harvest these layers rest on (see header). The Python builder
 * (scripts/build/batch_poi.py) and its pytest pin the same numbers,
 * so the two sides cannot silently disagree.
 */
export const POI_PROBE = {
  date: "2026-09-16",
  licence: "Maa- ja Ruumiamet avatud ruumiandmete litsents",
  libraryFeatures: 124,
  postFeatures: 536,
  pharmacyFeatures: 187,
  droppedNoCoord: 0,
} as const;

/** Vintage label stamped on the sidecar build (monthly feed, 30 d TTL). */
export const POI_VINTAGE = "2026-09-16";

/**
 * Proximity bands in metres — the scorer _score_dist restated
 * (≤300 -> 85, ≤600 -> 70, ≤1000 -> 55, NULL-beyond): changing
 * services/scoring/dims_p4_poi.py without changing this (or vice
 * versa) is a drift bug, pinned by test on both sides.
 */
export const POI_EDGES_M: ReadonlyArray<readonly [number, number]> = [
  [300, 85],
  [600, 70],
  [1000, 55],
];

/**
 * Hard join radius in metres — the outer band edge (see header
 * calibration note). Most of the county renders unknown by honesty.
 */
export const POI_RADIUS_M = 1000;

export interface PoiPoint {
  lat: number;
  lon: number;
  slice: PoiSlice;
}

const POI_SLICE_TITLE: Record<PoiSlice, string> = {
  library: "Raamatukogud lähedal (register, hinnang)",
  post: "Post (kontor + pakiautomaat, register, hinnang)",
  pharmacy: "Apteegid lähedal (register, hinnang)",
};

const POI_SLICE_GOOD: Record<PoiSlice, string> = {
  library: "roheline = raamatukogu lähedal (huvipunktide-hinnang linnulennult, mitte kogu)",
  post: "roheline = postkontor/punkt/pakiautomaat lähedal (huvipunktide-hinnang linnulennult)",
  pharmacy: "roheline = apteek lähedal (Ravimiameti-hinnang linnulennult, mitte nõuanne)",
};

const POI_SLICE_DEMO: Record<PoiSlice, { lat: number; lon: number }> = {
  // Real register rows, DEMO fallback only (live points are served
  // from the snapshot sidecar, never committed twice).
  library: { lat: 59.438322, lon: 24.746638 },
  post: { lat: 59.426851, lon: 24.651591 },
  pharmacy: { lat: 59.441912, lon: 24.849979 },
};

/** Buyer-param slice labels (NOT parameters3 ids). */
export const POI_PARAM_LABELS: Record<PoiSlice, string> = {
  library: "P4-poi raamatukogu",
  post: "P4-poi post",
  pharmacy: "P4-poi apteek",
};

export const POI_LAYERS: LayerDef[] = (
  Object.keys(POI_SLICE_TITLE) as PoiSlice[]
).map((slice) => ({
  id: `poi_${slice}` as PoiLayerId,
  paramIds: [],
  paramLabel: POI_PARAM_LABELS[slice],
  title: POI_SLICE_TITLE[slice],
  goodLabel: POI_SLICE_GOOD[slice],
  badLabel:
    "punane = 1000 m raadiuses registris puudub (teadmata, mitte teenuseta — kaardistus võib olla lünklik)",
  source:
    "Maa- ja Ruumiamet huvipunktid (vahekiht, avatud ruumiandmete litsents, seis 2026-09-16; allikas: " +
    (slice === "library"
      ? "Eesti Rahvusraamatukogu 124"
      : slice === "post"
        ? "Omniva/DPD/SmartPOST/Maa-amet 536 (sh 521 pakiautomaati)"
        : "Ravimiamet 187 apteeki") +
    "; igakuine vahekiht lähteregistrite kohal)",
  fallbackPoints: [POI_SLICE_DEMO[slice]],
}));

/**
 * Source-vocabulary note (NOT an Overpass fragment — huvipunktid data
 * is not OSM data; inventing amenity=* plumbing would be dishonest,
 * paaste #493 precedent). overpassQueryFor("poi_*") is never called
 * in production; the string only satisfies the registry shape.
 */
export const POI_TAGS: Record<PoiLayerId, string> = {
  poi_library:
    "Maa- ja Ruumiamet huvipunktid raamatukogu (serveeritakse snapshot-sidecarist, mitte Overpassist)",
  poi_post:
    "Maa- ja Ruumiamet huvipunktid post (serveeritakse snapshot-sidecarist, mitte Overpassist)",
  poi_pharmacy:
    "Maa- ja Ruumiamet huvipunktid tervisekaubad (serveeritakse snapshot-sidecarist, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see POI_NO_RASTER). */
export const POI_RASTER_FILE: Record<PoiLayerId, string> = {
  poi_library: "poi-library-walk-raster.json",
  poi_post: "poi-post-walk-raster.json",
  poi_pharmacy: "poi-pharmacy-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat distance kernel IS
 * the field. A 75 m county stamp of 847 walk-scale points would be
 * honest discs plus county-wide unknown — the splat already renders
 * exactly that from the sidecar, so a master would add build
 * machinery without meaning. The window route serves 500 for these
 * layers and the client falls back to the splat (designed path,
 * ehis precedent).
 */
export const POI_NO_RASTER = true;

/**
 * Euclidean fallback decay in km (== the 1 km join radius: the scale
 * story is the walkable-amenity window, same as the kernel).
 */
export const POI_DECAY: Record<PoiLayerId, number> = {
  poi_library: 1.0,
  poi_post: 1.0,
  poi_pharmacy: 1.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isPoiLayerId(layer: LayerId): layer is PoiLayerId {
  return (POI_LAYER_IDS as string[]).includes(layer);
}

/** Slice tag for a poi layer id (pure). */
export function poiSliceFor(layer: PoiLayerId): PoiSlice {
  return layer.replace("poi_", "") as PoiSlice;
}

/** Distance-band spec for the poi layers (called from the bonusSpecFor hook). */
export function poiBonusSpecFor(layer: PoiLayerId): BonusSpec {
  void layer;
  return {
    kind: "dbands",
    radiusM: POI_RADIUS_M,
    edges: POI_EDGES_M.map(([m, b]) => [m, b] as [number, number]),
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function poiHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/**
 * Band for a distance in metres under the scorer table (pure) — the
 * map twin of dims_p4_poi._score_dist. Beyond the outer edge reads
 * null (never zero).
 */
export function poiBandAt(distM: number): number | null {
  for (const [edgeM, band] of POI_EDGES_M) {
    if (distM <= edgeM) return band;
  }
  return null;
}

/**
 * Nearest sliced POI within the hard radius, nearest first (pure).
 * No averaging, no smoothing — mirrors the dbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function poiNearby(
  lat: number,
  lon: number,
  points: PoiPoint[],
  slice: PoiSlice,
  radiusM: number = POI_RADIUS_M,
): { point: PoiPoint; distM: number }[] {
  const out: { point: PoiPoint; distM: number }[] = [];
  for (const p of points) {
    if (p.slice !== slice) continue;
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = poiHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Points of one slice inside a bbox (pure) — the route serves these
 * from the snapshot sidecar (never the OSM snapshot, never live).
 */
export function poiPointsIn(
  points: PoiPoint[],
  slice: PoiSlice,
  bbox: BBoxLike,
): { lat: number; lon: number }[] {
  return points
    .filter(
      (p) =>
        p.slice === slice &&
        p.lon >= bbox.minlon &&
        p.lon <= bbox.maxlon &&
        p.lat >= bbox.minlat &&
        p.lat <= bbox.maxlat,
    )
    .map((p) => ({ lat: p.lat, lon: p.lon }));
}
