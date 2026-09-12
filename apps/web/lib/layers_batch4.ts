// Batch 4 parameter layers (parameters3.md groups 12-13): p125, p343,
// p141, p282, p342. Self-contained on purpose: it mirrors the shapes in
// lib/layers.ts (LayerDef, bonus specs, Overpass TAGS, walk-raster wire
// doc) WITHOUT importing that file, so this batch lands and tests green
// on its own. Wiring it into the map is a marked hook (see HOOKS below)
// owned by whoever merges the base layers.ts first.
//
// HOOKS (exact, for the reviewer merging this PR onto a tree with
// lib/layers.ts + lib/server/snapshot.ts):
//   layers.ts LayerId union: add "teens" | "airport" | "lockers"
//     | "securepickup" | "rideshare".
//   layers.ts LAYERS: spread ...BATCH4_LAYERS.
//   layers.ts TAGS: spread ...BATCH4_TAGS.
//   layers.ts DECAY_KM: spread ...BATCH4_DECAY_KM.
//   layers.ts bonusSpecFor: add `if (layer in BATCH4_BONUS) return
//     batch4BonusSpec(layer as Batch4LayerId);`
//   layers.ts BonusSpec union: add { kind: "wait"; waitMin: number;
//     waitMax: number } (rideshare only).
//   snapshot.ts RASTER_FILE / METRO_PREFIX: add teens/airport/lockers/
//     securepickup/rideshare filenames (see BATCH4_RASTER_FILE).
//   snapshot.ts matchesContract: accept kind "wait" via matching waitMin
//     + waitMax (sigma rule unchanged).
//   snapshot.ts loadSnapshotPoints: teens reuses derived-transit.json with
//     the weekend join (osm/transit-weekend-frequency.json, default 100);
//     airport reuses derived-transit.json with the airport join
//     (osm/transit-airport-frequency.json, default 0 -- unserved stops
//     contribute nothing); lockers/securepickup/rideshare read their own
//     derived-<layer>.json (written by the batch4 builders, no join).
// No other shared file needs edits: the window route, fetchWindow,
// fetchLayerPoints and /layers page are all generic over the registry.

export type Batch4LayerId = "teens" | "airport" | "lockers" | "securepickup" | "rideshare";

export interface Batch4BBox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

export interface Batch4Point {
  lat: number;
  lon: number;
  /** Departures weight (teens weekend / airport-route / rideshare wed). */
  t?: number;
  /** Area/count weight (lockers unit, securepickup weighted). */
  a?: number;
  tags?: Record<string, string>;
}

export interface Batch4LayerDef {
  id: Batch4LayerId;
  /** parameters3.md parameter numbers this layer implements. */
  paramIds: number[];
  title: string;
  goodLabel: string;
  badLabel: string;
  source: string;
  fallbackPoints: Batch4Point[];
}

export const BATCH4_LAYERS: Batch4LayerDef[] = [
  {
    id: "teens",
    paramIds: [125],
    title: "Noorte iseseisvus",
    goodLabel: "roheline = sagedane nädalavahetuse ühendus (noor saab ise liikuda)",
    badLabel: "punane = nädalavahetusel ühendus puudub või on harv",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + GTFS laupäeva/pühapäeva väljumised)",
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam
      { lat: 59.4278, lon: 24.7611 }, // Viru
    ],
  },
  {
    id: "airport",
    paramIds: [343],
    title: "Lennujaama ühistranspordiühendus",
    goodLabel: "roheline = otsene lennujaamaliin jalutuskäigu kaugusel",
    badLabel: "punane = lennujaama saab vaid ümberistumisega või üldse mitte",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + GTFS lennujaamaliinide väljumised)",
    fallbackPoints: [
      { lat: 59.41646, lon: 24.79659 }, // Lennujaam
      { lat: 59.4278, lon: 24.7611 }, // Viru (buss 2 / tramm T2/T4 koridor)
    ],
  },
  {
    id: "lockers",
    paramIds: [141],
    title: "Pakiautomaadid",
    goodLabel: "roheline = pakiautomaat jalutuskäigu kaugusel",
    badLabel: "punane = pakiautomaadid kaugel",
    source: "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + amenity=parcel_locker)",
    fallbackPoints: [
      { lat: 59.4278, lon: 24.7611 }, // Viru
      { lat: 59.44, lon: 24.82 }, // Lasnamäe
    ],
  },
  {
    id: "securepickup",
    paramIds: [282],
    title: "Turvaline pakikättesaamine",
    goodLabel: "roheline = pakiautomaat või postkontor lähedal",
    badLabel: "punane = turvalist kättesaamist pole lähedal",
    source:
      "kohalik hetktõmmis 2026-09-12 (kõndimisgraafik + parcel_locker ×1, postkontor ×2)",
    fallbackPoints: [
      { lat: 59.4278, lon: 24.7611 }, // Viru
      { lat: 59.412, lon: 24.655 }, // Õismäe
    ],
  },
  {
    id: "rideshare",
    paramIds: [342],
    title: "Sõidujagamise ooteaeg (proksi)",
    goodLabel: "roheline = lühike hinnanguline ooteaeg (~2 min)",
    badLabel: "punane = pikk hinnanguline ooteaeg (~15 min)",
    source:
      "kohalik hetktõmmis 2026-09-12 (GTFS sageduse + teetiheduse PROKSI, mitte mõõdetud Bolt ETA)",
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam
      { lat: 59.4278, lon: 24.7611 }, // Viru
    ],
  },
];

/**
 * Overpass QL fragments per batch-4 layer (document the source tags; the
 * snapshot builders consume them offline -- no live fetch in code/tests).
 * Teen/airport/rideshare ride on the transit stop tags (GTFS-joined).
 */
export const BATCH4_TAGS: Record<Batch4LayerId, string> = {
  teens: 'n["public_transport"~"stop_position|platform"];n["railway"~"tram_stop|station"];n["highway"="bus_stop"];',
  airport: 'n["public_transport"~"stop_position|platform"];n["railway"~"tram_stop|station"];n["highway"="bus_stop"];',
  lockers: 'n["amenity"="parcel_locker"];',
  securepickup: 'n["amenity"~"parcel_locker|post_office"];',
  rideshare: 'n["public_transport"~"stop_position|platform"];n["railway"~"tram_stop|station"];n["highway"="bus_stop"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const BATCH4_RASTER_FILE: Record<Batch4LayerId, string> = {
  teens: "teens-walk-raster.json",
  airport: "airport-walk-raster.json",
  lockers: "lockers-walk-raster.json",
  securepickup: "securepickup-walk-raster.json",
  rideshare: "rideshare-walk-raster.json",
};

/**
 * Distance (km) at which goodness decays to ~37% (Euclidean fallback path;
 * the walk rasters bake the same sigma). Same steep-corridor philosophy as
 * the base layers.
 */
export const BATCH4_DECAY_KM: Record<Batch4LayerId, number> = {
  teens: 0.2,
  airport: 0.3,
  lockers: 0.3,
  securepickup: 0.3,
  rideshare: 0.3,
};

export function batch4RadiusKmFor(layer: Batch4LayerId): number {
  return BATCH4_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot histograms (mirrors
 * scripts/build/batch_b4_common.py CAL exactly -- a pytest parses this
 * file and fails on drift).
 */
export const BATCH4_CAL = {
  teens: { sigma: 0.2, half: 800 },
  airport: { sigma: 0.3, half: 150 },
  lockers: { sigma: 0.3, half: 4 },
  securepickup: { sigma: 0.3, half: 6 },
  rideshare: { sigma: 0.3, transitHalf: 1500, roadHalf: 800, waitMin: 2, waitMax: 15 },
} as const;

export type Batch4BonusSpec =
  | { kind: "trips"; half: number }
  | { kind: "area"; half: number }
  | { kind: "wait"; waitMin: number; waitMax: number };

export function batch4BonusSpec(layer: Batch4LayerId): Batch4BonusSpec {
  switch (layer) {
    case "teens":
      return { kind: "trips", half: 800 };
    case "airport":
      return { kind: "trips", half: 150 };
    case "lockers":
      return { kind: "area", half: 4 };
    case "securepickup":
      return { kind: "area", half: 6 };
    case "rideshare":
      return { kind: "wait", waitMin: 2, waitMax: 15 };
  }
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function batch4HavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Saturating sum score 0..100 (mirrors the Python builders). */
export function batch4Saturate(s: number, half: number): number {
  return s > 0 ? (100 * s) / (s + half) : 0;
}

/**
 * Rideshare wait model (REAL minutes proxy, honestly labeled -- NOT
 * measured dispatch data). tn/rn are 0..1 supply norms (transit departures
 * nearby, drivable-street density nearby):
 *   wait = waitMin + (waitMax-waitMin) * (1 - 0.5*tn - 0.5*rn).
 */
export function batch4WaitMin(tn: number, rn: number): number {
  const { waitMin, waitMax } = BATCH4_CAL.rideshare;
  const w = waitMin + (waitMax - waitMin) * (1 - 0.5 * tn - 0.5 * rn);
  return Math.min(waitMax, Math.max(waitMin, w));
}

/** Absolute 0..100 score from wait minutes: linear, 2 min -> 100, 15 min -> 0. */
export function batch4ScoreFromWait(wait: number): number {
  const { waitMin, waitMax } = BATCH4_CAL.rideshare;
  return (100 * (waitMax - wait)) / (waitMax - waitMin);
}

function tripsNearby(lat: number, lon: number, points: Batch4Point[], sigma: number): number {
  let s = 0;
  for (const p of points) {
    if (typeof p.t !== "number" || p.t <= 0) continue;
    const d = batch4HavKm(lon, lat, p.lon, p.lat);
    if (d > 4 * sigma) continue;
    s += p.t * Math.exp((-d * d) / (2 * sigma * sigma));
  }
  return s;
}

function areaNearby(lat: number, lon: number, points: Batch4Point[], sigma: number): number {
  let s = 0;
  for (const p of points) {
    if (typeof p.a !== "number" || p.a <= 0) continue;
    const d = batch4HavKm(lon, lat, p.lon, p.lat);
    if (d > 4 * sigma) continue;
    s += p.a * Math.exp((-d * d) / (2 * sigma * sigma));
  }
  return s;
}

/**
 * Mean road-supply norm (0..1) used by the transit-only fallback: the
 * raster bakes real car-graph density per cell, but the Euclidean path
 * only sees GTFS stops, so it holds density at this documented mean.
 */
export const BATCH4_FALLBACK_ROAD_NORM = 0.4;

/**
 * Euclidean fallback goodness 0..100 (raster missing). Null when there is
 * nothing to score -- never a faked zero. Rideshare without a raster is a
 * transit-only estimate at mean road density, honestly documented in the
 * source string; the raster is the full two-signal map.
 */
export function batch4GoodnessAt(
  layer: Batch4LayerId,
  lat: number,
  lon: number,
  points: Batch4Point[],
): number | null {
  if (points.length === 0) return null;
  const sigma = BATCH4_DECAY_KM[layer];
  switch (layer) {
    case "teens":
    case "airport": {
      const spec = batch4BonusSpec(layer);
      if (spec.kind !== "trips") return null;
      const s = tripsNearby(lat, lon, points, sigma);
      if (s <= 0) return null;
      return Math.round(batch4Saturate(s, spec.half));
    }
    case "lockers":
    case "securepickup": {
      const spec = batch4BonusSpec(layer);
      if (spec.kind !== "area") return null;
      const s = areaNearby(lat, lon, points, sigma);
      if (s <= 0) return null;
      return Math.round(batch4Saturate(s, spec.half));
    }
    case "rideshare": {
      const { transitHalf } = BATCH4_CAL.rideshare;
      const s = tripsNearby(lat, lon, points, sigma);
      if (s <= 0) return null;
      const tn = s / (s + transitHalf);
      // Road density is raster-side; the fallback holds it at the mean.
      return Math.round(batch4ScoreFromWait(batch4WaitMin(tn, BATCH4_FALLBACK_ROAD_NORM)));
    }
  }
}
