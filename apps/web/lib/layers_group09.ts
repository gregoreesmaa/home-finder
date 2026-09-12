// Group 9 noise-proxy layers (parameters3.md §5.9): p16, p138, p162,
// p301, p493. Self-contained on purpose: it mirrors the shapes in
// lib/layers.ts (LayerDef, decay specs, Overpass TAGS, walk-raster wire
// doc) WITHOUT importing that file, so this batch lands and tests green
// on its own. Wiring it into the map is a marked hook (see HOOKS below)
// owned by whoever merges the base layers.ts first.
//
// HONESTY (load-bearing): Transpordiamet CNOSSOS-EU noise rasters are not
// in the 2026-09-12 snapshot, so every title/legend/source says
// "müraproksi" (noise proxy) — NEVER dBA. Green = quiet/far, red =
// loud/near. Unknown stays null/255 (renders red, never a faked score).
//
// HOOKS (exact, for the reviewer merging this PR onto a tree with
// lib/layers.ts + lib/server/snapshot.ts):
//   layers.ts LayerId union: add Group09LayerId ("trafficnoise" |
//     "quietnature" | "nuisance" | "lowfreq" | "braking").
//   layers.ts LAYERS: spread ...GROUP09_LAYERS.
//   layers.ts TAGS: spread ...GROUP09_TAGS.
//   layers.ts DECAY_KM: spread ...GROUP09_DECAY_KM.
//   layers.ts bonusSpecFor: add `if (layer in GROUP09_BONUS) return
//     group09BonusSpec(layer as Group09LayerId);`
//   layers.ts BonusSpec union: add { kind: "quiet"; halfM: number }
//     (distance layers) — density layers reuse { kind: "area"; half }.
//   snapshot.ts RASTER_FILE / METRO_PREFIX: add trafficnoise/quietnature/
//     nuisance/lowfreq/braking filenames (see GROUP09_RASTER_FILE; metro
//     intentionally absent — see NO_METRO below).
//   snapshot.ts matchesContract: accept kind "quiet" via matching halfM
//     + sigma, and kind "area" for trafficnoise/braking via half + sigma.
//   snapshot.ts loadSnapshotPoints: nuisance/lowfreq/braking read their
//     own derived-<layer>.json (written by the batch_g09_noise builder,
//     no join); trafficnoise/quietnature are raster-only (road points
//     would be ~35k JSON — the raster is the path, demo fallbackPoints
//     cover the degraded case honestly).
// No other shared file needs edits: the window route, fetchWindow and
// the layers page are all generic over the registry.

export type Group09LayerId =
  | "trafficnoise"
  | "quietnature"
  | "nuisance"
  | "lowfreq"
  | "braking";

export interface Group09BBox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

export interface Group09Point {
  lat: number;
  lon: number;
  /** Kernel weight (density layers); absent means unit weight. */
  a?: number;
  tags?: Record<string, string>;
}

export interface Group09LayerDef {
  id: Group09LayerId;
  /** parameters3.md parameter numbers this layer implements. */
  paramIds: number[];
  title: string;
  goodLabel: string;
  badLabel: string;
  source: string;
  fallbackPoints: Group09Point[];
}

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP09_LAYERS: Group09LayerDef[] = [
  {
    id: "trafficnoise",
    paramIds: [16],
    title: "Liiklusmüra (müraproksi)",
    goodLabel: "roheline = vaikne, suur tee/raudtee kaugel (proksi)",
    badLabel: "punane = lähedal tihe liiklus või raudtee (proksi)",
    source: `${SNAP} (teedevõrgu tihedus + raudtee kaugus; PROKSI, mitte Transpordiameti müratsoonid)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam (raudtee + tihe liiklus)
      { lat: 59.41646, lon: 24.79659 }, // Lennujaam / Ülemiste
    ],
  },
  {
    id: "quietnature",
    paramIds: [138],
    title: "Loodusheli ja vaikus (müraproksi)",
    goodLabel: "roheline = vaikne ja kaardistatud loodus lähedal (proksi)",
    badLabel: "punane = liiklus lähedal, loodus kaugel (proksi)",
    source: `${SNAP} (liiklusvaikus + haljasalade lähedus; PROKSI, mitte mõõdetud helimaastik)`,
    fallbackPoints: [
      { lat: 59.4386, lon: 24.7912 }, // Kadriorg (park + vaiksem)
      { lat: 59.4711, lon: 24.8153 }, // Pirita mets (vaikne loodus)
    ],
  },
  {
    id: "nuisance",
    paramIds: [162],
    title: "Häiringuallikad: ööelu ja tööstus (müraproksi)",
    goodLabel: "roheline = ööelu/tööstus kaugel (proksi)",
    badLabel: "punane = baar/klubi/tööstus lähedal (proksi)",
    source: `${SNAP} (ööelu 265 + tööstusalad 54; PROKSI, mitte määruse tekst)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe ööelu)
      { lat: 59.412, lon: 24.655 }, // Õismäe (rahulikum)
    ],
  },
  {
    id: "lowfreq",
    paramIds: [301],
    title: "Madalsageduslik müra: raudtee ja tööstus (müraproksi)",
    goodLabel: "roheline = raudtee/tööstus kaugel (proksi)",
    badLabel: "punane = raudtee/tööstus lähedal (proksi)",
    source: `${SNAP} (raudtee 1291 joont + tööstusalad; PROKSI, mitte mõõdetud infrasound)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaam (raudtee)
      { lat: 59.51, lon: 24.83 }, // Viimsi (raudteest kaugel)
    ],
  },
  {
    id: "braking",
    paramIds: [493],
    title: "Pidurdus- ja kiirendusmüra (müraproksi)",
    goodLabel: "roheline = ristmikud/peatused kaugel (proksi)",
    badLabel: "punane = ristmike/peatuste tihedus lähedal (proksi)",
    source: `${SNAP} (ristmike + peatuste + ülekäikude tihedus; PROKSI, mitte mõõdetud pidurdusmüra)`,
    fallbackPoints: [
      { lat: 59.4278, lon: 24.7611 }, // Viru (tihe ristmike ala)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hõre võrk)
    ],
  },
];

/**
 * Overpass QL fragments per Group 9 layer (document the source tags; the
 * snapshot builder consumes them offline — no live fetch in code/tests).
 * Major-road classes only (residential/service are local access, low
 * noise); cinema excluded from nightlife (seated culture, not nuisance).
 */
export const GROUP09_TAGS: Record<Group09LayerId, string> = {
  trafficnoise:
    'w["highway"~"motorway|trunk|primary|secondary|tertiary"];w["railway"~"rail|tram|narrow_gauge|light_rail"];',
  quietnature:
    'w["highway"~"motorway|trunk|primary|secondary|tertiary"];w["railway"~"rail|tram|narrow_gauge|light_rail"];',
  nuisance: 'n["amenity"~"bar|pub|nightclub|casino"];n["landuse"="industrial"];',
  lowfreq: 'w["railway"~"rail|tram|narrow_gauge|light_rail"];n["landuse"="industrial"];',
  braking:
    'n["highway"="traffic_signals"];n["railway"~"level_crossing|tram_level_crossing|tram_crossing|crossing"];n["highway"="bus_stop"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const GROUP09_RASTER_FILE: Record<Group09LayerId, string> = {
  trafficnoise: "trafficnoise-walk-raster.json",
  quietnature: "quietnature-walk-raster.json",
  nuisance: "nuisance-walk-raster.json",
  lowfreq: "lowfreq-walk-raster.json",
  braking: "braking-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay / density proxy is
 * smooth at the 75 m county step; 9.375 m cells would be fake precision.
 * The window route serves county everywhere for these layers.
 */
export const GROUP09_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same scale
 * story as the raster sigma): steep enough that corridors beat suburbs.
 */
export const GROUP09_DECAY_KM: Record<Group09LayerId, number> = {
  trafficnoise: 0.3,
  quietnature: 0.3,
  nuisance: 0.3,
  lowfreq: 0.5,
  braking: 0.3,
};

export function group09RadiusKmFor(layer: Group09LayerId): number {
  return GROUP09_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g09_noise.py G09_CAL exactly — a pytest parses this
 * file and fails on drift).
 */
export const GROUP09_CAL = {
  trafficnoise: { sigma: 0.3, roadHalf: 400, railSigma: 0.3 },
  quietnature: { sigma: 0.3, roadHalf: 400, railSigma: 0.3, natureBonus: 10, natureRangeM: 600 },
  nuisance: { halfM: 300, sigma: 0.3 },
  lowfreq: { halfM: 500, sigma: 0.5 },
  braking: { sigma: 0.3, half: 120 },
} as const;

export type Group09BonusSpec =
  | { kind: "area"; half: number }
  | { kind: "quiet"; halfM: number };

export function group09BonusSpec(layer: Group09LayerId): Group09BonusSpec {
  switch (layer) {
    case "trafficnoise":
      return { kind: "area", half: 400 };
    case "quietnature":
      return { kind: "area", half: 400 };
    case "braking":
      return { kind: "area", half: 120 };
    case "nuisance":
      return { kind: "quiet", halfM: 300 };
    case "lowfreq":
      return { kind: "quiet", halfM: 500 };
  }
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group09HavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Gaussian kernel (density layers, mirrors the Python builder). */
export function group09Kernel(d: number, sigma: number): number {
  return Math.exp((-d * d) / (2 * sigma * sigma));
}

/** Nearest-source quietness 0..100: 0 on the source, 50 at halfM. */
export function group09QuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

/**
 * Euclidean fallback quietness 0..100 (raster missing). Null when there is
 * nothing to score — never a faked zero. Density layers need weighted
 * points (a); distance layers use nearest-point distance. Nature bonus for
 * quietnature needs caller-supplied nature distance (null = unmapped, no
 * bonus — never a punishment).
 */
export function group09QuietnessAt(
  layer: Group09LayerId,
  lat: number,
  lon: number,
  points: Group09Point[],
  natureDM: number | null = null,
): number | null {
  if (points.length === 0) return null;
  const sigma = GROUP09_DECAY_KM[layer];
  switch (layer) {
    case "trafficnoise":
    case "braking": {
      const spec = group09BonusSpec(layer);
      if (spec.kind !== "area") return null;
      let s = 0;
      for (const p of points) {
        const w = typeof p.a === "number" && p.a > 0 ? p.a : 1;
        const d = group09HavKm(lon, lat, p.lon, p.lat);
        if (d > 4 * sigma) continue;
        s += w * group09Kernel(d, sigma);
      }
      if (s <= 0) return 100;
      return Math.round((100 * spec.half) / (s + spec.half));
    }
    case "quietnature": {
      const spec = group09BonusSpec(layer);
      if (spec.kind !== "area") return null;
      let s = 0;
      for (const p of points) {
        const w = typeof p.a === "number" && p.a > 0 ? p.a : 1;
        const d = group09HavKm(lon, lat, p.lon, p.lat);
        if (d > 4 * sigma) continue;
        s += w * group09Kernel(d, sigma);
      }
      let q = s <= 0 ? 100 : (100 * spec.half) / (s + spec.half);
      const { natureBonus, natureRangeM } = GROUP09_CAL.quietnature;
      if (typeof natureDM === "number" && natureDM <= natureRangeM) {
        q += natureBonus * (1 - natureDM / natureRangeM);
      }
      return Math.round(Math.min(100, q));
    }
    case "nuisance":
    case "lowfreq": {
      const spec = group09BonusSpec(layer);
      if (spec.kind !== "quiet") return null;
      let best = Infinity;
      for (const p of points) {
        const d = group09HavKm(lon, lat, p.lon, p.lat);
        if (d < best) best = d;
      }
      return Math.round(group09QuietFromHalf(best * 1000, spec.halfM));
    }
  }
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group09MatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: Group09LayerId,
): boolean {
  if (!doc) return false;
  const spec = group09BonusSpec(layer);
  if (doc.sigma !== GROUP09_DECAY_KM[layer]) return false;
  if (spec.kind === "area") return doc.half === spec.half;
  return doc.half === spec.halfM;
}
