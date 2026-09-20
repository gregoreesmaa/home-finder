// Strategic-noise measured overlay (issue #625): myrakaart 2022
// Lden/Lnight bands, NULL-empty outside.
//
// Modelled (not measured) road/tram/rail/air/industry noise for
// Tallinn + Tartu + main roads (2020–2021 input data). Bands score
// per listing in services/scoring/dims_p4_noisemap.py (Lden ≤45→85,
// ≤55→65, ≤65→40, >65→20; Lnight shifted 5 dB down; binding/minimum
// leg wins). The overlay paints the BAND polygons so loud vs quiet
// reads at a glance; outside every polygon is NULL — never "quiet"
// (unmapped is unmeasured, not silent; the legend says so, always).
//
// Serving: the Harju+2 km keep set ships in ONE sidecar
// (noise/noise-areas.json, both legs) via /api/layers/noise/areas —
// fetched once per selection, painted as band fills (see
// applyNoisePolygons in ./outlines), forest polygons-only precedent.
// Rings are Douglas-Peucker simplified at 5 m (stated); the scorer
// reads the same rings, consistently.

import type { BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type NoiseLayerId = "noise";
export const NOISE_LAYER_IDS: NoiseLayerId[] = ["noise"];

/** Publisher attribution (service: Fees none + AccessConstraints NONE). */
export const NOISE_ATTRIBUTION = "Maa- ja Ruumiamet strateegilised mürakaardid 2022 (WFS myrakaart)";

/** Sidecar legs (binding/minimum wins in the scorer, never on the map). */
export const NOISE_LEGS = ["Lden", "Lnight"] as const;

export const NOISE_DEFS: LayerDef[] = [
  {
    id: "noise",
    paramIds: [],
    paramLabel: "P4-müra",
    title: "Strateegiline müra (2022 mudel)",
    goodLabel:
      "vööndis müra pole (mitte 'vaikne' — kaardistamata on mõõtmata, mitte vaikne)",
    badLabel:
      "punane = vali (Lden >65 või Lnight >60 dB lähedal — siduv jalg loeb)",
    source:
      `${NOISE_ATTRIBUTION}: Harju+2 km vööndipolügoonid (Lden + Lnight 5 dB samm; MUDEL, mitte mõõtmine)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygons-only layers out of its fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): noise serves zero points and builds no raster; the scorer's
 * bands read off the sidecar polygons, never a field — pinned by test.
 */
export const NOISE_DECAY: Record<NoiseLayerId, number> = {
  noise: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: noise lives in
 * the myrakaart WFS harvest, and polygon-only serving never
 * queries anything else. The only data path is
 * app/api/layers/noise/areas.
 */
export const NOISE_TAGS: Record<NoiseLayerId, string> = {
  noise: "myrakaart-2022 WFS Harjumaa+2km keep (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const NOISE_RASTER_FILE: Record<NoiseLayerId, string> = {
  noise: "noise-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const NOISE_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const NOISE_NO_METRO = true;

/**
/**
 * Strategic-noise band tables (issue #807) — byte parity with
 * LDEN_BANDS / LNIGHT_BANDS / LDEN_LOUD / LNIGHT_LOUD in
 * services/scoring/dims_p4_noisemap.py. band_db IS the contour upper
 * bound (MYRAKLASS steps 45/50/55…), so the scorer's _band_score
 * applies verbatim; min-wins across legs happens in zones807.
 */
export const NOISE_LDEN_BANDS: Array<[number, number]> = [
  [45, 85],
  [55, 65],
  [65, 40],
];
export const NOISE_LDEN_LOUD = 20;
export const NOISE_LNIGHT_BANDS: Array<[number, number]> = [
  [40, 85],
  [50, 65],
  [60, 40],
];
export const NOISE_LNIGHT_LOUD = 20;

/** Band score for one sidecar polygon (null when the leg is unknown). */
export function noiseScoreForArea(leg: string, bandDb: number): number | null {
  const bands = leg === "Lden" ? NOISE_LDEN_BANDS : leg === "Lnight" ? NOISE_LNIGHT_BANDS : null;
  if (!bands || !Number.isFinite(bandDb)) return null;
  for (const [limit, pts] of bands) {
    if (bandDb <= limit) return pts;
  }
  return leg === "Lden" ? NOISE_LDEN_LOUD : NOISE_LNIGHT_LOUD;
}

/**
 * Bonus spec. Membership zones (issue #807): polygons carry the
 * verdict — inside reads noiseScoreForArea (see zones807.ts), outside
 * stays unknown (unmapped is unmeasured, never quiet). Zero points,
 * null raster (still polygons-only). The live scorer leg is
 * services/scoring/dims_p4_noisemap.py.
 */
export const NOISE_BONUS: Record<NoiseLayerId, BonusSpec> = {
  noise: { kind: "zones" },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isNoiseLayerId(layer: string): layer is NoiseLayerId {
  return (NOISE_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygons-only layers: no points, no raster — the sidecar polygons
 * carry the data (scored, unlike taste-only tints). The /layers page
 * branches on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isNoisePolygonOnlyLayer(layer: string): boolean {
  return isNoiseLayerId(layer);
}

/**
 * Noise bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForNoise(layer: string): BonusSpec | undefined {
  return (NOISE_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const NOISE_HOOK =
  "NOISE-HOOK (#625): noise bands wired into layers/overlays/outlines/snapshot; Lden+Lnight fills, NULL-empty outside (never quiet).";

/**
 * One noise band polygon for the map sidecar. Rings are GeoJSON
 * [lon, lat] (Douglas-Peucker 5 m in 3301, then LCC-projected); b is
 * the [minlon, minlat, maxlon, maxlat] prefilter box; leg is
 * Lden|Lnight; band_db is the 5 dB LOWER bound (45 = 45–49.9 dB).
 */
export interface NoiseArea {
  noise_id: string;
  leg: string;
  band_db: number;
  b: [number, number, number, number];
  r: number[][][];
}

export function isNoiseArea(v: unknown): v is NoiseArea {
  const p = v as Partial<NoiseArea>;
  return (
    typeof p?.noise_id === "string" &&
    typeof p?.leg === "string" &&
    (p.leg === "Lden" || p.leg === "Lnight") &&
    typeof p?.band_db === "number" &&
    Number.isFinite(p.band_db) &&
    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    Array.isArray(p?.r) &&
    p.r.length > 0 &&
    p.r.every(
      (ring) =>
        Array.isArray(ring) &&
        ring.length >= 3 &&
        ring.every(
          (pt) =>
            Array.isArray(pt) &&
            pt.length === 2 &&
            pt.every((n) => typeof n === "number" && Number.isFinite(n)),
        ),
    )
  );
}

/**
 * Noise polygons for painting band fills on the noise layer.
 * Null on any failure: fills are a visual aid, never load-bearing —
 * the scorer reads the same sidecar independently.
 */
export async function fetchNoiseAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<NoiseArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/noise/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    const areas = (body as { areas: unknown[] }).areas.filter(isNoiseArea).map((p) => {
      const o = p as NoiseArea;
      return {
        noise_id: o.noise_id,
        leg: o.leg,
        band_db: o.band_db,
        b: o.b,
        r: o.r,
      };
    });
    return areas;
  } catch {
    return null;
  }
}

/**
 * Band fill colors by 5 dB lower bound (green = quiet, red = loud —
 * the overlay grades audibility, per docs/layers.md; Lnight paints
 * the same ramp, binding leg wins in the scorer, never on the map).
 * Shared by the map painter (applyNoisePolygons) and unit-tested here.
 */
export const NOISE_BAND_FILL: Record<string, string> = {
  "45": "#22c55e",
  "50": "#a3e635",
  "55": "#facc15",
  "60": "#fb923c",
  "65": "#ef4444",
  "70": "#991b1b",
  unknown: "#d1d5db",
};

/** Fill color for one band (unknown band degrades gray, never a guess). */
export function noiseFillColor(bandDb: number): string {
  const key = String(bandDb);
  if (key in NOISE_BAND_FILL) return NOISE_BAND_FILL[key];
  // Above the top labelled band reads loudest; below reads quietest.
  if (Number.isFinite(bandDb)) {
    if (bandDb > 70) return NOISE_BAND_FILL["70"];
    if (bandDb < 45) return NOISE_BAND_FILL["45"];
  }
  return NOISE_BAND_FILL.unknown;
}
