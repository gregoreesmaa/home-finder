// GENV environmental-exposure layers (parameters3.md §5.9 leftovers +
// §5.18 leftovers): p234, p408, p445, p63, p181. Self-contained on
// purpose: it mirrors the shapes in lib/layers.ts (LayerDef, decay
// specs, Overpass TAGS, walk-raster wire doc) WITHOUT importing that
// file, so this batch lands and tests green on its own. Wiring it into
// the map is a marked hook (see HOOKS below) owned by whoever merges
// the base layers.ts first.
//
// HONESTY (load-bearing): Transpordiamet CNOSSOS-EU rasters, VIIRS
// nighttime lights and Landsat thermal UHI are not in the 2026-09-12
// snapshot, so every title/legend/source says "proksi (hinnang)"
// (proxy, estimate) — NEVER dBA, magnitudes, Bortle classes, Celsius
// or seasonal schedules. Green = calm/dark/cool, red = exposed/lit/
// sealed. Unknown stays null/255 (renders red, never a faked score).
// p445 adds "hooajalisus teadmata": OSM has runways, not timetables.
//
// HOOKS (exact, for the reviewer merging this PR onto a tree with
// lib/layers.ts + lib/server/snapshot.ts):
//   layers.ts LayerId union: add GenvLayerId ("vibration" | "lowspec" |
//     "flightcorr" | "darksky" | "coolisland").
//   layers.ts LAYERS: spread ...GENV_LAYERS.
//   layers.ts TAGS: spread ...GENV_TAGS.
//   layers.ts DECAY_KM: spread ...GENV_DECAY_KM.
//   layers.ts bonusSpecFor: add `if (layer in GENV_BONUS) return
//     genvBonusSpec(layer as GenvLayerId);`
//   layers.ts BonusSpec union: add { kind: "quiet"; halfM: number }
//     (distance layers incl. flightcorr's major tier) — density layers
//     reuse { kind: "area"; half }.
//   snapshot.ts RASTER_FILE / METRO_PREFIX: add vibration/lowspec/
//     flightcorr/darksky/coolisland filenames (see GENV_RASTER_FILE;
//     metro intentionally absent — see GENV_NO_METRO).
//   snapshot.ts matchesContract: accept kind "quiet" via matching halfM
//     + sigma (flightcorr matches the MAJOR half), and kind "area" for
//     darksky/coolisland via half + sigma.
//   snapshot.ts loadSnapshotPoints: vibration/lowspec/flightcorr read
//     their own derived points (written by the batch_genv_exposure
//     builder, no join); darksky/coolisland are raster-only (lit +
//     building points would be ~300k JSON — the raster is the path,
//     demo fallbackPoints cover the degraded case honestly).
// No other shared file needs edits: the window route, fetchWindow and
// the layers page are all generic over the registry.

export type GenvLayerId =
  | "vibration"
  | "lowspec"
  | "flightcorr"
  | "darksky"
  | "coolisland";

export interface GenvBBox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

export interface GenvPoint {
  lat: number;
  lon: number;
  /** Kernel weight (density layers); absent means unit weight. */
  a?: number;
  tags?: Record<string, string>;
}

export interface GenvLayerDef {
  id: GenvLayerId;
  /** parameters3.md parameter numbers this layer implements. */
  paramIds: number[];
  title: string;
  goodLabel: string;
  badLabel: string;
  source: string;
  fallbackPoints: GenvPoint[];
}

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GENV_LAYERS: GenvLayerDef[] = [
  {
    id: "vibration",
    paramIds: [234],
    title: "Maavärin ja vibratsioon (proksi, hinnang)",
    goodLabel: "roheline = rahulik, raudtee/rasketee kaugel (proksi)",
    badLabel: "punane = raudtee või raskeliiklus lähedal (proksi)",
    source: `${SNAP} (raudtee 1291 + rasketeed 3320; PROKSI, mitte mõõdetud vibratsioon)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam (raudtee peal)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (rahulik)
    ],
  },
  {
    id: "lowspec",
    paramIds: [408],
    title: "Madalsageduslik müra (proksi, hinnang)",
    goodLabel: "roheline = raskeliiklus/raudtee/tööstus kaugel (proksi)",
    badLabel: "punane = raskeallikas lähedal (proksi)",
    source: `${SNAP} (rasketeed + raudtee + tööstusalad; PROKSI, mitte mõõdetud sagedusspekter)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam (raudtee + liiklus)
      { lat: 59.51, lon: 24.83 }, // Viimsi (raskeallikatest kaugel)
    ],
  },
  {
    id: "flightcorr",
    paramIds: [445],
    title: "Lennukoridor (proksi, hinnang, hooajalisus teadmata)",
    goodLabel: "roheline = väljaspool lennukoridori (proksi)",
    badLabel: "punane = raja/telje lähedal (proksi)",
    source: `${SNAP} (Tallinna 08/26 + Ämari teljed ±8 km, mururajad; PROKSI, mitte lennuplaanid)`,
    fallbackPoints: [
      { lat: 59.41646, lon: 24.79659, tags: { surface: "asphalt" } }, // Lennujaam (koridoris)
      { lat: 59.20485, lon: 24.61098, tags: { surface: "grass" } }, // Aespa mururada (väike)
    ],
  },
  {
    id: "darksky",
    paramIds: [63],
    title: "Valgusreostus / pime taevas (proksi, hinnang)",
    goodLabel: "roheline = pime, kaardistatud valgusallikas kaugel (proksi)",
    badLabel: "punane = valgusallikate tihedus lähedal (proksi)",
    source: `${SNAP} (lit=yes + tänavalambid 20 m lahtrites; PROKSI, mitte VIIRS-satelliit)`,
    fallbackPoints: [
      { lat: 59.4278, lon: 24.7611 }, // Viru (valgustatud kesklinn)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (pime)
    ],
  },
  {
    id: "coolisland",
    paramIds: [181],
    title: "Kuumasaar / jahedus (proksi, hinnang)",
    goodLabel: "roheline = jahe, hõre hoonestus + haljas lähedal (proksi)",
    badLabel: "punane = tihe hoonestus/teed, haljast kaugel (proksi)",
    source: `${SNAP} (252140 hoonet + teedevõrk, haljasboonus; PROKSI, mitte termokaart)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti (tihe, kuum)
      { lat: 59.4386, lon: 24.7912 }, // Kadriorg (park jahutab)
    ],
  },
];

/**
 * Overpass QL fragments per GENV layer (document the source tags; the
 * snapshot builder consumes them offline — no live fetch in code/tests).
 * nwr/ everywhere ways/areas carry the feature (PR #118: node-only
 * silently drops way-mapped carriageways, runways, lit areas and
 * buildings). Secondary/tertiary streets are local distributors, not
 * heavy corridors; helipads are sporadic rotorcraft, not corridors.
 */
export const GENV_TAGS: Record<GenvLayerId, string> = {
  vibration:
    'nwr["railway"~"rail|tram|narrow_gauge|light_rail"];nwr["highway"~"motorway|trunk|primary"];',
  lowspec:
    'nwr["highway"~"motorway|trunk|primary"];nwr["railway"~"rail|tram|narrow_gauge|light_rail"];nwr["landuse"="industrial"];',
  flightcorr: 'nwr["aeroway"~"runway|aerodrome"];',
  darksky: 'nwr["lit"="yes"];n["highway"="street_lamp"];',
  coolisland: 'nwr["building"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const GENV_RASTER_FILE: Record<GenvLayerId, string> = {
  vibration: "vibration-walk-raster.json",
  lowspec: "lowspec-walk-raster.json",
  flightcorr: "flightcorr-walk-raster.json",
  darksky: "darksky-walk-raster.json",
  coolisland: "coolisland-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay / density proxy is
 * smooth at the 75 m county step; 9.375 m cells would be fake precision.
 * The window route serves county everywhere for these layers.
 */
export const GENV_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same scale
 * story as the raster sigma).
 */
export const GENV_DECAY_KM: Record<GenvLayerId, number> = {
  vibration: 0.3,
  lowspec: 0.5,
  flightcorr: 0.3,
  darksky: 0.3,
  coolisland: 0.3,
};

export function genvRadiusKmFor(layer: GenvLayerId): number {
  return GENV_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_genv_exposure.py GENV_CAL exactly — a pytest
 * parses this file and fails on drift). Runway axis extensions (±8 km,
 * raster-side) have no fallback equivalent: the fallback scores the
 * nearest mapped runway honestly without lobes.
 */
export const GENV_CAL = {
  vibration: { halfM: 300, sigma: 0.3 },
  lowspec: { halfM: 500, sigma: 0.5 },
  flightcorr: { majorHalfM: 1500, minorHalfM: 400, sigma: 0.3 },
  darksky: { half: 120, sigma: 0.3 },
  coolisland: { half: 120, sigma: 0.3, greenBonus: 8, greenRangeM: 500 },
} as const;

export type GenvBonusSpec =
  | { kind: "area"; half: number }
  | { kind: "quiet"; halfM: number };

export function genvBonusSpec(layer: GenvLayerId): GenvBonusSpec {
  switch (layer) {
    case "vibration":
      return { kind: "quiet", halfM: 300 };
    case "lowspec":
      return { kind: "quiet", halfM: 500 };
    case "flightcorr":
      // Major tier on the wire; the minor (grass, 400 m) tier is
      // raster-side only — the fallback picks per-point halves below.
      return { kind: "quiet", halfM: 1500 };
    case "darksky":
      return { kind: "area", half: 120 };
    case "coolisland":
      return { kind: "area", half: 120 };
  }
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function genvHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Gaussian kernel (density layers, mirrors the Python builder). */
export function genvKernel(d: number, sigma: number): number {
  return Math.exp((-d * d) / (2 * sigma * sigma));
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function genvQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

/** True when a runway point is a paved major-tier source. */
export function genvIsMajorRunway(p: GenvPoint): boolean {
  const s = p.tags?.surface ?? "";
  return s === "asphalt" || s === "concrete" || s === "paved";
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when there is
 * nothing to score — never a faked zero. Distance layers use
 * nearest-point distance (flightcorr picks the per-point tier half:
 * 1500 m paved, 400 m grass/unmapped). Density layers need weighted
 * points (a); coolisland takes caller-supplied green distance (null =
 * unmapped, no bonus — never a punishment).
 */
export function genvQuietnessAt(
  layer: GenvLayerId,
  lat: number,
  lon: number,
  points: GenvPoint[],
  natureDM: number | null = null,
): number | null {
  if (points.length === 0) return null;
  const sigma = GENV_DECAY_KM[layer];
  switch (layer) {
    case "vibration":
    case "lowspec": {
      const spec = genvBonusSpec(layer);
      if (spec.kind !== "quiet") return null;
      let best = Infinity;
      for (const p of points) {
        const d = genvHavKm(lon, lat, p.lon, p.lat);
        if (d < best) best = d;
      }
      return Math.round(genvQuietFromHalf(best * 1000, spec.halfM));
    }
    case "flightcorr": {
      let best = Infinity;
      for (const p of points) {
        const d = genvHavKm(lon, lat, p.lon, p.lat) * 1000;
        const half = genvIsMajorRunway(p)
          ? GENV_CAL.flightcorr.majorHalfM
          : GENV_CAL.flightcorr.minorHalfM;
        const q = genvQuietFromHalf(d, half);
        if (q < best) best = q;
      }
      return Math.round(best);
    }
    case "darksky":
    case "coolisland": {
      const spec = genvBonusSpec(layer);
      if (spec.kind !== "area") return null;
      let s = 0;
      for (const p of points) {
        const w = typeof p.a === "number" && p.a > 0 ? p.a : 1;
        const d = genvHavKm(lon, lat, p.lon, p.lat);
        if (d > 4 * sigma) continue;
        s += w * genvKernel(d, sigma);
      }
      let q = s <= 0 ? 100 : (100 * spec.half) / (s + spec.half);
      if (layer === "coolisland") {
        const { greenBonus, greenRangeM } = GENV_CAL.coolisland;
        if (typeof natureDM === "number" && natureDM <= greenRangeM) {
          q += greenBonus * (1 - natureDM / greenRangeM);
        }
        q = Math.min(100, q);
      }
      return Math.round(q);
    }
  }
}

/** True when a raster doc's baked calibration matches the live spec. */
export function genvMatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: GenvLayerId,
): boolean {
  if (!doc) return false;
  const spec = genvBonusSpec(layer);
  if (doc.sigma !== GENV_DECAY_KM[layer]) return false;
  if (spec.kind === "area") return doc.half === spec.half;
  return doc.half === spec.halfM;
}
