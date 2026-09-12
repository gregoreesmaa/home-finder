// Group 15 education + Group 11 leftover layers (parameters3.md §§5.15/5.11,
// issue #116): p130, p314, p338, p442, p462. Self-contained on purpose: it
// mirrors the shapes in lib/layers.ts (LayerDef, decay specs, Overpass
// TAGS, walk-raster wire doc) WITHOUT importing that file, so this batch
// lands and tests green on its own. Wiring it into the map is a marked
// hook (see HOOKS below) owned by the central integrator merging all
// parameter batches at once.
//
// HONESTY (load-bearing): EHIS lottery/redistricting internals, aquatic
// weed-management activity and the festival calendar are NOT in the
// 2026-09-12 snapshot, so every title/legend/source says "proksi"
// (proxy) and names the OSM tags measured — NEVER official lottery odds,
// measured dBA/flow/crime-style claims, or a weed-free guarantee.
// p130/p314 are OSM school-density proxies; p442/p462 state their green/
// red direction explicitly (green = far/calm, red = near/disruption).
// Unknown stays null/255 (renders red, never a faked score).
//
// HOOKS (exact, for the reviewer merging this PR onto a tree with
// lib/layers.ts + lib/server/snapshot.ts + lib/distanceField.ts):
//   layers.ts LayerId union: add Group15LayerId ("schoolchoice" |
//     "redistrict" | "weedwater" | "festival" | "stadium").
//   layers.ts TAG_ALLOWLIST: add "tourism" (festival tags).
//   layers.ts LAYERS: spread ...GROUP15_LAYERS.
//   layers.ts TAGS: spread ...GROUP15_TAGS.
//   layers.ts DECAY_KM: spread ...GROUP15_DECAY_KM.
//   layers.ts BonusSpec union: add { kind: "quiet"; halfM: number } —
//     SHARED with Group 9 (#104, identical 100·d/(d+halfM) semantics,
//     keep one) — and { kind: "shore"; halfM: number } (green-near
//     distance: 100·halfM/(d+halfM), weedwater only).
//   layers.ts bonusSpecFor: add `if (layer in GROUP15_BONUS) return
//     group15BonusSpec(layer as Group15LayerId);`
//   snapshot.ts RASTER_FILE: add ...GROUP15_RASTER_FILE (metro
//     intentionally absent — see GROUP15_NO_METRO).
//   snapshot.ts matchesContract: accept kinds "quiet"/"shore" via
//     group15MatchesContract (halfM + sigma), "area" via half + sigma.
//   distanceField.ts buildScoredField fall-through: route "quiet"/"shore"
//     to group15ScoreAt (nearest-point distance; area layers use the
//     existing "area" branch unchanged).
// No other shared file needs edits: the window route, fetchWindow and
// the layers page are all generic over the registry.

export type Group15LayerId =
  | "schoolchoice"
  | "redistrict"
  | "weedwater"
  | "festival"
  | "stadium";

export interface Group15BBox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

export interface Group15Point {
  lat: number;
  lon: number;
  tags?: Record<string, string>;
}

export interface Group15LayerDef {
  id: Group15LayerId;
  /** parameters3.md parameter numbers this layer implements. */
  paramIds: number[];
  title: string;
  /** Legend text: what green means. */
  goodLabel: string;
  /** Legend text: what red means. */
  badLabel: string;
  /** Provenance shown next to the map. */
  source: string;
  /** Honestly-labeled demo points used only when live fetch fails. */
  fallbackPoints: Group15Point[];
}

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP15_LAYERS: Group15LayerDef[] = [
  {
    id: "schoolchoice",
    paramIds: [130],
    title: "Koolivalik (koolitiheduse proksi)",
    goodLabel: "roheline = palju kaardistatud koole lähedal (proksi)",
    badLabel: "punane = koole vähe või pole (proksi, MITTE ametlik loosiinfo)",
    source: `${SNAP} (OSM amenity=school 342; EHIS loosiandmed hetktõmmises pole)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam (tihe koolivalik)
      { lat: 59.4278, lon: 24.7611 }, // Viru (tihe koolivalik)
    ],
  },
  {
    id: "redistrict",
    paramIds: [314],
    title: "Koolipiiride muutuste haavatavus (proksi)",
    goodLabel: "roheline = stabiilne, palju koole lähedal (proksi)",
    badLabel: "punane = haavatav, vähe koole / piiritsoon (proksi)",
    source: `${SNAP} (OSM amenity=school 2 km tihedus; piirijooned hetktõmmises pole)`,
    fallbackPoints: [
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (vähe koole, haavatav)
      { lat: 59.51, lon: 24.83 }, // Viimsi (hõre koolivalik)
    ],
  },
  {
    id: "weedwater",
    paramIds: [338],
    title: "Veekogude lähedus (veeproksi)",
    goodLabel: "roheline = veekogu lähedal (proksi)",
    badLabel: "punane = veekogu kaugel (proksi, MITTE mõõdetud hooldus)",
    source: `${SNAP} (OSM natural=water + water=pond/lake/reservoir/basin/river; hooldusprogrammid hetktõmmises pole)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti (Snelli tiik lähedal)
      { lat: 59.4711, lon: 24.8153 }, // Pirita (jõgi/meri)
    ],
  },
  {
    id: "festival",
    paramIds: [442],
    title: "Festivali- ja ürituspaikade mõju (proksi)",
    goodLabel: "roheline = ürituspaigad kaugel, rahulik (proksi)",
    badLabel: "punane = ürituspaik lähedal, müra/rahvahulgad (proksi)",
    source: `${SNAP} (OSM amenity=events_venue/marketplace + tourism=attraction 177; ürituskalender hetktõmmises pole)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (üritused lähedal)
      { lat: 59.4449, lon: 24.799 }, // Lauluväljak (laulupeod)
    ],
  },
  {
    id: "stadium",
    paramIds: [462],
    title: "Staadioniliiklus (proksi)",
    goodLabel: "roheline = staadion kaugel, rahulik (proksi)",
    badLabel: "punane = staadion lähedal, ürituste liiklus (proksi)",
    source: `${SNAP} (OSM leisure=stadium 55; piletitulu/külastajate arv hetktõmmises pole)`,
    fallbackPoints: [
      { lat: 59.4278, lon: 24.7611 }, // Viru (Kalevi staadion lähedal)
      { lat: 59.412, lon: 24.655 }, // Õismäe (staadionikaugus)
    ],
  },
];

/**
 * Overpass QL fragments per Group 15 layer (document the source tags; the
 * snapshot builder consumes them offline — no live fetch in code/tests).
 * theatre/museum/gallery stay p89 culture, community_centre/townhall stay
 * p87 community (batch B1, #98) — this layer claims no sibling tag.
 * leisure=pitch is deliberately excluded: pitches do not draw event
 * traffic, and 2723 of them would paint the county red.
 */
export const GROUP15_TAGS: Record<Group15LayerId, string> = {
  schoolchoice: 'n["amenity"="school"];',
  redistrict: 'n["amenity"="school"];',
  weedwater: 'n["natural"="water"];',
  festival: 'n["amenity"~"events_venue|marketplace"];n["tourism"="attraction"];',
  stadium: 'n["leisure"="stadium"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const GROUP15_RASTER_FILE: Record<Group15LayerId, string> = {
  schoolchoice: "schoolchoice-walk-raster.json",
  redistrict: "redistrict-walk-raster.json",
  weedwater: "weedwater-walk-raster.json",
  festival: "festival-walk-raster.json",
  stadium: "stadium-walk-raster.json",
};

/**
 * NO metro masters (documented): a count/distance-decay proxy is smooth
 * at the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for these layers.
 */
export const GROUP15_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same scale
 * story as the raster sigma): steep enough that hubs beat suburbs.
 */
export const GROUP15_DECAY_KM: Record<Group15LayerId, number> = {
  schoolchoice: 0.5,
  redistrict: 0.8,
  weedwater: 0.5,
  festival: 0.5,
  stadium: 0.8,
};

export function group15RadiusKmFor(layer: Group15LayerId): number {
  return GROUP15_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * services/scoring/dims_group15.py constants and
 * scripts/build/batch_g15_edu.py G15_CAL exactly — a pytest parses this
 * file and fails on drift).
 */
export const GROUP15_CAL = {
  schoolchoice: { sigma: 0.5, radiusM: 1500, half: 6 },
  redistrict: { sigma: 0.8, radiusM: 2000, half: 2 },
  weedwater: { halfM: 600, sigma: 0.5 },
  festival: { halfM: 500, sigma: 0.5 },
  stadium: { halfM: 800, sigma: 0.8 },
} as const;

export type Group15BonusSpec =
  | { kind: "area"; half: number }
  | { kind: "quiet"; halfM: number }
  | { kind: "shore"; halfM: number };

export const GROUP15_BONUS: Record<Group15LayerId, Group15BonusSpec> = {
  schoolchoice: { kind: "area", half: 6 },
  redistrict: { kind: "area", half: 2 },
  weedwater: { kind: "shore", halfM: 600 },
  festival: { kind: "quiet", halfM: 500 },
  stadium: { kind: "quiet", halfM: 800 },
};

export function group15BonusSpec(layer: Group15LayerId): Group15BonusSpec {
  return GROUP15_BONUS[layer];
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group15HavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Unweighted count 0..100: 100·S/(S+half); 0 stays 0 (evidence). */
export function group15Saturate(count: number, half: number): number {
  return Math.round((100 * count) / (count + half));
}

/** Nearest-source quietness 0..100: 0 on the source, 50 at halfM. */
export function group15QuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return Math.round((100 * dM) / (dM + halfM));
}

/** Nearest-water amenity 0..100: 100 at the shore, 50 at halfM. */
export function group15ShoreFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 0;
  return Math.round((100 * halfM) / (dM + halfM));
}

/**
 * Euclidean fallback score 0..100 (raster missing). Null when there is
 * nothing to score — never a faked zero. Area layers count points within
 * the calibration radius; distance layers use nearest-point distance.
 */
export function group15ScoreAt(
  layer: Group15LayerId,
  lat: number,
  lon: number,
  points: Group15Point[],
): number | null {
  if (points.length === 0) return null;
  const spec = group15BonusSpec(layer);
  if (spec.kind === "area") {
    const radiusM =
      layer === "schoolchoice"
        ? GROUP15_CAL.schoolchoice.radiusM
        : GROUP15_CAL.redistrict.radiusM;
    let n = 0;
    for (const p of points) {
      if (group15HavKm(lon, lat, p.lon, p.lat) * 1000 <= radiusM) n++;
    }
    return group15Saturate(n, spec.half);
  }
  let best = Infinity;
  for (const p of points) {
    const d = group15HavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  const dM = best * 1000;
  if (spec.kind === "quiet") return group15QuietFromHalf(dM, spec.halfM);
  return group15ShoreFromHalf(dM, spec.halfM);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group15MatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: Group15LayerId,
): boolean {
  if (!doc) return false;
  const spec = group15BonusSpec(layer);
  if (doc.sigma !== GROUP15_DECAY_KM[layer]) return false;
  if (spec.kind === "area") return doc.half === spec.half;
  return doc.half === spec.halfM;
}
