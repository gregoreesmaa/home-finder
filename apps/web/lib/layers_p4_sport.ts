// Sport-venue amenity proximity overlays (issue #607; P4-048 family-buyer
// facility slice from services/scoring/dims_p4_sportreg.py). This file
// owns ALL sport runtime data; shared files (lib/layers.ts,
// lib/distanceField.ts, lib/overlays.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `SPORT-HOOK (#607)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.
//
// FEED VERDICT (2026-09-16, polite one-off round, custom UA
// `home-finder-research/0.1`, single GETs, no retries; aggregates only,
// raw bodies never committed — full evidence in docs/p4_sportreg.md):
// Spordiregister spordiehitised.json (HTTP 200, ~21 MB): 4157 venues,
// 1216 Harjumaa (`maakond` == "Harjumaa"), ALL with WGS84
// kaart_laius/kaart_pikkus (0 coord-less), ALL ehstaatus "Spordialases
// kasutuses", newest esitatudkuupaev 2026-09-15 — the feed is FRESH.
// vtiav ujulad.xml (HTTP 200, ~263 KB): 226 <ujula> rows, 219 with
// L-EST97 x/y (7 without, counted). Harvest
// scripts/build/batch_sport.py (yearly TTL, paced, 429 = stop) placed
// 1110 Harjumaa points: hall 335 / field 630 / pool 145 (37 register
// Siseujula-combos + plain Siseujula rows + 101 ujulad in the Harju
// window); dropped 239 unsliced kinds + 118 ujulad outside the county
// window + 7 coordless, all counted, never faked.
//
// TRANSFORM (labeled, reviewable): register coords ship as WGS84 and are
// used as-is; ujulad L-EST97 metres project offline via the labelled
// inverse-LCC in batch_sport.py (same math as batch_tervise.py,
// pyproj-agreement to 14 decimals pinned by test_batch_sport.py). The
// GRS80(ETRS89)~WGS84 datum gap drifts ~1 m — stated on the sidecar +
// here, never hidden. Slice matchers mirror dims_p4_sportreg.py
// venue_slices exactly (pool "siseujula", hall "voimla", six field
// markers; combos yield one point per slice), so map colors and scored
// reasons agree by construction (parity pinned by
// layers_p4_sport.test.ts on this side, test_dims_p4_sportreg.py on
// the scorer side).
//
// HONESTY (load-bearing): straight-line haversine proximity is NOT
// measured access — every reason says "hinnang (linnulennult, mitte
// marsruut)"; beyond 2 km stays NULL (never "no sport nearby" as a
// fact — timetables, prices, lane availability stay human-page buyer
// checks, p4_recre precedent). The kernel below is the EXACT scorer
// band table (PROX_BANDS: <=500 m -> 80, <=1 km -> 65, <=2 km -> 50).
// Hard cutoff, no smoothing — a hall 3 km away says nothing about the
// backyard. Points come from the snapshot sidecar
// (sport/sport-points.json: {vintage, counts, points}, built by the
// harvester, served by loadSportPoints in lib/server/snapshot.ts) —
// NEVER from the 2026-09-12 OSM snapshot (venues are not OSM features)
// and never live (no network in the map path). No raster master exists
// BY DOCUMENTED DECISION (see SPORT_NO_RASTER): sparse points bake to
// discs-plus-unknown either way, and the points-splat distance kernel
// IS the field. Names/addresses never leave the sidecar (the wire
// carries lat/lon/slice only).
//
// Calibration (judgment calls, documented for the reviewer): the
// nearest sliced venue wins (a second hall 200 m further adds no
// family-buyer value worth scoring); the 2 km outer edge mirrors the
// scorer exactly; ujulad rows place regardless of <tyyp> (a kooli pool
// near a listing is still a pool — dims precedent); Ujulad Harjumaa
// membership is the documented approximate county window in
// batch_sport.py (no county column exists — border rows may
// misclassify, counted, never hidden). EHIS huvikool/spordikool rows
// (#608) are SCHOOLS, these are VENUES: distinct keys, no double-score
// of one signal; OSM dim_rec_special stays the fallback cousin.
//
// The layers carry NO parameters3.md id: P4-048 is a parameters4 buyer
// param (tervise #494 / paaste #493 precedent). paramIds stays [] and
// paramLabel carries the slice ("P4-048") for the layer buttons.

import type { BBoxLike, BonusSpec, LayerDef, LayerId } from "./layers";

export type SportLayerId = "sport_hall" | "sport_field" | "sport_pool";

export const SPORT_LAYER_IDS: SportLayerId[] = [
  "sport_hall",
  "sport_field",
  "sport_pool",
];

/** Buyer-param slice these overlays visualize (NOT a parameters3 id). */
export const SPORT_PARAM_LABEL = "P4-048";

/**
 * Dated harvest these layers rest on (see header). The Python builder
 * (scripts/build/batch_sport.py) and the 2026-09-16 live pull agree:
 * 4157 register rows -> 1009 placed POIs + 239 unsliced + 0 coordless;
 * 226 ujulad rows -> 101 placed + 7 coordless + 118 outside county.
 */
export const SPORT_PROBE = {
  date: "2026-09-16",
  registerRows: 4157,
  harjuPlaced: 1009,
  ujuladRows: 226,
  ujuladPlaced: 101,
} as const;

/** Vintage label stamped on the sidecar build (annual feed, 365 d TTL). */
export const SPORT_VINTAGE = "2026-09-16";

/**
 * Proximity bands in metres — the scorer PROX_BANDS (km) restated:
 * changing services/scoring/dims_p4_sportreg.py without changing this
 * (or vice versa) is a drift bug, pinned by test on both sides.
 */
export const SPORT_EDGES_M: ReadonlyArray<readonly [number, number]> = [
  [500, 80],
  [1000, 65],
  [2000, 50],
];

/**
 * Hard join radius in metres — the outer band edge (see header
 * calibration note). Most of the county renders unknown by honesty.
 */
export const SPORT_RADIUS_M = 2000;

/** Slice tag carried by sidecar points (lat/lon/slice only on the wire). */
export type SportSlice = "hall" | "field" | "pool";

export interface SportPoint {
  lat: number;
  lon: number;
  slice: SportSlice;
}

const SPORT_SLICE_TITLE: Record<SportSlice, string> = {
  hall: "Spordisaalid ja võimlad (hinnang)",
  field: "Staadionid ja väliväljakud (hinnang)",
  pool: "Ujulate ligidus (hinnang)",
};

const SPORT_SLICE_GOOD: Record<SportSlice, string> = {
  hall: "roheline = võimla/spordisaal lähedal (hinnang linnulennult, mitte ligipääs)",
  field: "roheline = staadion/väliväljak lähedal (hinnang linnulennult, mitte ligipääs)",
  pool: "roheline = ujula lähedal (hinnang linnulennult, mitte ligipääs)",
};

export const SPORT_LAYERS: LayerDef[] = (
  Object.keys(SPORT_SLICE_TITLE) as SportSlice[]
).map((slice) => ({
  id: `sport_${slice}` as SportLayerId,
  paramIds: [],
  paramLabel: SPORT_PARAM_LABEL,
  title: SPORT_SLICE_TITLE[slice],
  goodLabel: SPORT_SLICE_GOOD[slice],
  badLabel:
    "punane = lähim koht kaugel (≤500 m → 80, ≤1 km → 65, ≤2 km → 50) VÕI andmed teadmata",
  source:
    "Spordiregister spordiehitised (Kultuuriministeerium, CC BY-SA 3.0, seis 2026-09-16; 4157 kirjet, Harjumaa väljavõte) + Terviseameti ujulate loend (vtiav avaandmed, CC BY-SA 3.0, 226 kirjet; L-EST97->WGS84 pooramine ~1 m tapsusega; lahtiolekuajad/hinnad ostja kontroll — kauguse-hinnang, mitte mõõdetud ligipääs)",
  fallbackPoints: [
    // Real register rows, DEMO fallback only (live points are served
    // from the snapshot sidecar, never committed twice).
    ...(slice === "hall"
      ? [{ lat: 59.41852, lon: 24.756669 }]
      : slice === "field"
        ? [{ lat: 59.419445, lon: 24.733486 }]
        : [{ lat: 59.430375, lon: 24.735809 }]),
  ],
}));

/**
 * Source-vocabulary note (NOT an Overpass fragment — register data is
 * not OSM data; inventing leisure=sports_centre plumbing would be
 * dishonest, paaste #493 precedent). overpassQueryFor("sport_*") is
 * never called in production; the string only satisfies the registry
 * shape.
 */
export const SPORT_TAGS: Record<SportLayerId, string> = {
  sport_hall:
    "Spordiregistri päritolu märkus (voimla-liik, Harjumaa väljavõte), mitte Overpass-päring.",
  sport_field:
    "Spordiregistri päritolu märkus (staadion/väljak-liigid, Harjumaa väljavõte), mitte Overpass-päring.",
  sport_pool:
    "Spordiregistri + ujulate päritolu märkus (Siseujula-liik + vtiav koordinaadid), mitte Overpass-päring.",
};

/** Raster master filenames (intentionally never built — see SPORT_NO_RASTER). */
export const SPORT_RASTER_FILE: Record<SportLayerId, string> = {
  sport_hall: "sport-hall-walk-raster.json",
  sport_field: "sport-field-walk-raster.json",
  sport_pool: "sport-pool-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat distance kernel IS
 * the field. A 75 m county stamp of sparse sliced points would be
 * honest discs plus county-wide unknown — the splat already renders
 * exactly that, so a master would add build machinery without meaning.
 * The window route serves 500 for these layers and the client falls
 * back to the splat (designed path, senscom/tervise precedent).
 */
export const SPORT_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the window route is
 * skipped by the generic dbands short-circuit and empty windows serve
 * county everywhere (tervise qbands precedent).
 */
export const SPORT_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 2 km join radius: the scale
 * story is the family-walk window, same as the kernel).
 */
export const SPORT_DECAY: Record<SportLayerId, number> = {
  sport_hall: 2.0,
  sport_field: 2.0,
  sport_pool: 2.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isSportLayerId(layer: LayerId): layer is SportLayerId {
  return (SPORT_LAYER_IDS as readonly string[]).includes(layer);
}

/** Distance-band spec for the sport layers (called from the bonusSpecFor hook). */
export function sportBonusSpecFor(_layer: SportLayerId): BonusSpec {
  void _layer;
  return {
    kind: "dbands",
    radiusM: SPORT_RADIUS_M,
    edges: SPORT_EDGES_M.map(([m, b]) => [m, b] as [number, number]),
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function sportHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/**
 * Band for a distance in metres under the scorer table (pure) — the map
 * twin of dims_p4_sportreg._band_score with km restated as m. Beyond
 * the outer edge reads null (never zero).
 */
export function sportBandAt(distM: number): number | null {
  for (const [edgeM, band] of SPORT_EDGES_M) {
    if (distM <= edgeM) return band;
  }
  return null;
}

/** Slice tag for a sport layer id (pure). */
export function sportSliceFor(layer: SportLayerId): SportSlice {
  return layer.replace("sport_", "") as SportSlice;
}

/**
 * Nearest sliced venue within the hard radius, nearest first (pure).
 * No averaging, no smoothing — mirrors the dbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function sportNearby(
  lat: number,
  lon: number,
  points: SportPoint[],
  slice: SportSlice,
  radiusM: number = SPORT_RADIUS_M,
): { point: SportPoint; distM: number }[] {
  const out: { point: SportPoint; distM: number }[] = [];
  for (const p of points) {
    if (p.slice !== slice) continue;
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = sportHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Points of one slice inside a bbox (pure) — the route serves these
 * from the snapshot sidecar (never the OSM snapshot, never live).
 */
export function sportPointsIn(
  points: SportPoint[],
  slice: SportSlice,
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
