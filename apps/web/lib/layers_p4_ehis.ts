// EHIS measured-schools overlay (issue #608; P4-011 family-buyer
// proximity slice from services/scoring/dims_p4_ehis_map.py). This file
// owns ALL ehis runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `EHIS-HOOK (#608)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.
//
// FEED VERDICT (2026-09-16, polite one-off round, custom UA
// `home-finder-research/0.1`, single GETs, no retries; aggregates only,
// raw bodies never committed — full evidence in docs/p4_ehis_map.md):
// EHIS hooned bulk (HTTP 200, 1 093 076 B): 2180 <hoone> rows, 738
// naming Harju maakond in <aadress>, 703 of them with
// <koordinaatX>/<koordinaatY> (L-EST97, x = northing, y = easting).
// EHIS oppeasutused bulk (HTTP 200, ~12.6 MB): 5689 institutions with
// <koolId>/<tyyp>/<staatus>. Harvest scripts/build/batch_ehis.py
// (quarterly TTL, paced, 429 = stop) joins buildings to slices via
// <oppeasutusId> and places 618 Harjumaa points: school 239 /
// kindergarten 369 / hobby 10; dropped 1179 other-county + 355
// closed/unsliced-institution + 28 coordless, all counted (zero
// closed-institution buildings in the Harju set — stated, not hidden).
// The hobby slice is thin (10 coord-carrying Harju buildings) —
// huvikool institutions without their own coord-carrying building
// place nowhere, and that thinness rides the legend, never a faked
// fill.
//
// TRANSFORM (labeled, reviewable): type map mirrors
// dims_p4_ehis_map.py TYPE_SLICES exactly (pohikool voi gumnaasium ->
// school; lasteaed/koolieelne lasteasutus/lastehoid -> kindergarten;
// huvikool -> hobby; only Registreeritud), and coords project offline
// via the labelled inverse-LCC in batch_ehis.py (same math as
// batch_tervise.py, pyproj-agreement pinned by test_batch_ehis.py).
// The GRS80(ETRS89)~WGS84 datum gap drifts ~1 m — stated on the
// sidecar + here, never hidden. NO language column exists anywhere in
// the 12.6 MB bulk — language slices are impossible, documented, never
// guessed. EHR/ADS joins are NOT needed: 95.1% of Harjumaa rows place
// as-is (the <ehrKood>/<adsAdrId> ride along only as future-join
// provenance, never onto the wire).
//
// HONESTY (load-bearing): straight-line haversine proximity is NOT
// measured access or school quality — every reason says "hinnang
// (linnulennult, mitte marsruut)"; beyond 2 km stays NULL (never "bad
// school", only distance; capacity/quality stays the buyer check).
// The kernel below is the EXACT scorer band table (PROX_BANDS:
// <=500 m -> 80, <=1 km -> 65, <=2 km -> 50). Hard cutoff, no
// smoothing — a school 3 km away says nothing about the backyard.
// Points come from the snapshot sidecar (ehis/ehis-points.json:
// {vintage, counts, points}, built by the harvester, served by
// loadEhisPoints in lib/server/snapshot.ts) — NEVER from the
// 2026-09-12 OSM snapshot (register schools are not OSM features;
// the OSM `schools` layer keeps its own tuning, GTFS-vs-transit
// precedent) and never live (no network in the map path). No raster
// master exists BY DOCUMENTED DECISION (see EHIS_NO_RASTER): sparse
// points bake to discs-plus-unknown either way, and the points-splat
// distance kernel IS the field (sport #607 dbands precedent — this
// module reuses that spec kind, no new kernel). Names/EHR/ADS codes
// never leave the sidecar (the wire carries lat/lon/slice only).
//
// Calibration (judgment calls, documented for the reviewer): the
// nearest sliced building wins; every building of a sliced
// institution counts (peahoone is NOT a filter — a kindergarten in a
// shared building is still the kindergarten, dims precedent); the 2 km
// outer edge mirrors the scorer exactly. Spordiregister venues (#607)
// are PHYSICAL VENUES, these are SCHOOLS: distinct sources, distinct
// keys, no double-score of one signal (huvikool/spordikool rows stay
// here, never in sport).
//
// The layers carry NO parameters3.md id: P4-011 is a parameters4 buyer
// param (sport #607 / tervise #494 precedent). paramIds stays [] and
// paramLabel carries the slice ("P4-011") for the layer buttons.

import type { BBoxLike, BonusSpec, LayerDef, LayerId } from "./layers";

export type EhisLayerId = "ehis_school" | "ehis_kindergarten" | "ehis_hobby";

export const EHIS_LAYER_IDS: EhisLayerId[] = [
  "ehis_school",
  "ehis_kindergarten",
  "ehis_hobby",
];

/** Buyer-param slice these overlays visualize (NOT a parameters3 id). */
export const EHIS_PARAM_LABEL = "P4-011";

/**
 * Dated harvest these layers rest on (see header). The Python builder
 * (scripts/build/batch_ehis.py) and the 2026-09-16 live pulls agree:
 * 2180 hoone rows -> 618 placed + 1179 other-county + 355
 * closed/unsliced + 28 coordless (sums to rows exactly).
 */
export const EHIS_PROBE = {
  date: "2026-09-16",
  hooneRows: 2180,
  harjuPlaced: 618,
  oppeasutusRows: 5689,
} as const;

/** Vintage label stamped on the sidecar build (quarterly feed, 90 d TTL). */
export const EHIS_VINTAGE = "2026-09-16";

/**
 * Proximity bands in metres — the scorer PROX_BANDS (km) restated:
 * changing services/scoring/dims_p4_ehis_map.py without changing this
 * (or vice versa) is a drift bug, pinned by test on both sides.
 */
export const EHIS_EDGES_M: ReadonlyArray<readonly [number, number]> = [
  [500, 80],
  [1000, 65],
  [2000, 50],
];

/**
 * Hard join radius in metres — the outer band edge (see header
 * calibration note). Most of the county renders unknown by honesty.
 */
export const EHIS_RADIUS_M = 2000;

/** Slice tag carried by sidecar points (lat/lon/slice only on the wire). */
export type EhisSlice = "school" | "kindergarten" | "hobby";

export interface EhisPoint {
  lat: number;
  lon: number;
  slice: EhisSlice;
}

const EHIS_SLICE_TITLE: Record<EhisSlice, string> = {
  school: "Koolid lähedal (mõõdetud, hinnang)",
  kindergarten: "Lasteaiad lähedal (mõõdetud, hinnang)",
  hobby: "Huvikoolid lähedal (mõõdetud, hinnang)",
};

const EHIS_SLICE_GOOD: Record<EhisSlice, string> = {
  school: "roheline = kool lähedal (EHIS-hinnang linnulennult, mitte kvaliteet)",
  kindergarten: "roheline = lasteaed lähedal (EHIS-hinnang linnulennult, mitte kvaliteet)",
  hobby: "roheline = huvikool lähedal (EHIS-hinnang linnulennult, õhuke valim)",
};

const EHIS_SLICE_DEMO: Record<EhisSlice, { lat: number; lon: number }> = {
  // Real register rows, DEMO fallback only (live points are served
  // from the snapshot sidecar, never committed twice).
  school: { lat: 59.442384, lon: 24.699436 },
  kindergarten: { lat: 59.442124, lon: 24.830605 },
  hobby: { lat: 59.427489, lon: 24.790014 },
};

export const EHIS_LAYERS: LayerDef[] = (
  Object.keys(EHIS_SLICE_TITLE) as EhisSlice[]
).map((slice) => ({
  id: `ehis_${slice}` as EhisLayerId,
  paramIds: [],
  paramLabel: EHIS_PARAM_LABEL,
  title: EHIS_SLICE_TITLE[slice],
  goodLabel: EHIS_SLICE_GOOD[slice],
  badLabel:
    "punane = lähim koht kaugel (≤500 m → 80, ≤1 km → 65, ≤2 km → 50) VÕI andmed teadmata",
  source:
    "EHIS avaandmed (Haridus- ja Teadusministeerium, CC BY-SA 3.0, seis 2026-09-16; hooned 2180 kirjet + oppeasutused 5689 kirjet, Harjumaa väljavõte 618 hoonet; L-EST97->WGS84 pooramine ~1 m tapsusega; keele veergu voog ei kanna — keelelisi viile pole; kauguse-hinnang, mitte kvaliteet)",
  fallbackPoints: [EHIS_SLICE_DEMO[slice]],
}));

/**
 * Source-vocabulary note (NOT an Overpass fragment — register data is
 * not OSM data; inventing amenity=school plumbing would be dishonest,
 * paaste #493 precedent). overpassQueryFor("ehis_*") is never called
 * in production; the string only satisfies the registry shape.
 */
export const EHIS_TAGS: Record<EhisLayerId, string> = {
  ehis_school:
    "EHISe päritolu märkus (pohikool/gümnaasium-liik, Harjumaa väljavõte), mitte Overpass-päring.",
  ehis_kindergarten:
    "EHISe päritolu märkus (lasteaed-liigid, Harjumaa väljavõte), mitte Overpass-päring.",
  ehis_hobby:
    "EHISe päritolu märkus (huvikool-liik, Harjumaa väljavõte, õhuke valim), mitte Overpass-päring.",
};

/** Raster master filenames (intentionally never built — see EHIS_NO_RASTER). */
export const EHIS_RASTER_FILE: Record<EhisLayerId, string> = {
  ehis_school: "ehis-school-walk-raster.json",
  ehis_kindergarten: "ehis-kindergarten-walk-raster.json",
  ehis_hobby: "ehis-hobby-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat distance kernel IS
 * the field (sport #607 dbands precedent). The window route serves 500
 * for these layers and the client falls back to the splat.
 */
export const EHIS_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the window route is
 * skipped by the generic dbands short-circuit and empty windows serve
 * county everywhere (sport #607 precedent).
 */
export const EHIS_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 2 km join radius: the scale
 * story is the family-walk window, same as the kernel).
 */
export const EHIS_DECAY: Record<EhisLayerId, number> = {
  ehis_school: 2.0,
  ehis_kindergarten: 2.0,
  ehis_hobby: 2.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isEhisLayerId(layer: LayerId): layer is EhisLayerId {
  return (EHIS_LAYER_IDS as readonly string[]).includes(layer);
}

/**
 * Distance-band spec for the ehis layers (called from the bonusSpecFor
 * hook). Reuses the sport #607 dbands kernel — same band table as the
 * scorer, no new spec kind.
 */
export function ehisBonusSpecFor(_layer: EhisLayerId): BonusSpec {
  void _layer;
  return {
    kind: "dbands",
    radiusM: EHIS_RADIUS_M,
    edges: EHIS_EDGES_M.map(([m, b]) => [m, b] as [number, number]),
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function ehisHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/**
 * Band for a distance in metres under the scorer table (pure) — the map
 * twin of dims_p4_ehis_map._band_score with km restated as m. Beyond
 * the outer edge reads null (never zero).
 */
export function ehisBandAt(distM: number): number | null {
  for (const [edgeM, band] of EHIS_EDGES_M) {
    if (distM <= edgeM) return band;
  }
  return null;
}

/** Slice tag for an ehis layer id (pure). */
export function ehisSliceFor(layer: EhisLayerId): EhisSlice {
  return layer.replace("ehis_", "") as EhisSlice;
}

/**
 * Nearest sliced building within the hard radius, nearest first
 * (pure). No averaging, no smoothing — mirrors the dbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function ehisNearby(
  lat: number,
  lon: number,
  points: EhisPoint[],
  slice: EhisSlice,
  radiusM: number = EHIS_RADIUS_M,
): { point: EhisPoint; distM: number }[] {
  const out: { point: EhisPoint; distM: number }[] = [];
  for (const p of points) {
    if (p.slice !== slice) continue;
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = ehisHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Points of one slice inside a bbox (pure) — the route serves these
 * from the snapshot sidecar (never the OSM snapshot, never live).
 */
export function ehisPointsIn(
  points: EhisPoint[],
  slice: EhisSlice,
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
