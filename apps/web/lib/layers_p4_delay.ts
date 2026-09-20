// Typical-delay corridor bands overlay (issue #629): harvested GPS
// bus-track factors as corridor strips.
//
// One layer per hour band + a worst-of-peaks rollup (5 layers, approved
// design): delay-morning (hommikune tipp 7-9), delay-midday (keskpäev
// 10-15), delay-evening (õhtune tipp 16-18), delay-offpeak (muu — the
// free-flow ANCHOR, factor 1.0 where measured), delay-worst (max over
// the three peaks, muu excluded).
//
// HONESTY (load-bearing): typical, NEVER live — every def carries
// "tavaline, mitte reaalajas"; bands are ±150 m ribbons around GTFS
// trip-shape polylines (road-following by construction, #667 —
// equirectangular approx, never surveyed road polygons); thin/missing
// cells paint slate "mõõtmata" (never dropped, never free-flow
// green). The per-listing legs are the scorer's job
// (services/scoring/dims_p4_typical_delay.py).
//
// This file owns ALL delay runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/snapshot.ts,
// app/layers/page.tsx) touch it only through small marked
// `DELAY-HOOK (#629)` blocks.

import type { BonusSpec, LayerDef } from "./layers";

export type DelayLayerId =
  | "delay-morning"
  | "delay-midday"
  | "delay-evening"
  | "delay-offpeak"
  | "delay-worst";

export const DELAY_LAYER_IDS: DelayLayerId[] = [
  "delay-morning",
  "delay-midday",
  "delay-evening",
  "delay-offpeak",
  "delay-worst",
];

/** Hour band painted per layer (worst = max over the three peaks). */
export const DELAY_LAYER_BAND: Record<DelayLayerId, string> = {
  "delay-morning": "hommikune tipp",
  "delay-midday": "keskpäev",
  "delay-evening": "õhtune tipp",
  "delay-offpeak": "muu",
  "delay-worst": "worst",
};

/** Scorer parity: services/scoring DELAY_BANDS (factor -> score). */
export type DelayBand = "free" | "steady" | "slow" | "jammed" | "unknown";

export const DELAY_BANDS: DelayBand[] = [
  "free",
  "steady",
  "slow",
  "jammed",
  "unknown",
];

/**
 * Factor -> band (mirrors the scorer thresholds: <=1.1 free,
 * <=1.3 steady, <=1.6 slow, else jammed; null/NaN/<1 -> unknown).
 */
export function delayBandForFactor(factor: unknown): DelayBand {
  if (typeof factor !== "number" || !Number.isFinite(factor) || factor < 1) {
    return "unknown";
  }
  if (factor <= 1.1) return "free";
  if (factor <= 1.3) return "steady";
  if (factor <= 1.6) return "slow";
  return "jammed";
}

/** Scores behind the bands (scorer parity, map reference only). */
export const DELAY_BAND_SCORE: Record<DelayBand, number> = {
  free: 75,
  steady: 60,
  slow: 45,
  jammed: 30,
  unknown: 30,
};

export const DELAY_ATTRIBUTION =
  "Tallinna Linnavalitsus GPS (keyless gps.txt, typical tables) + TLT GTFS-vints (schedules, corridor validation)";

/**
 * Band fills: traffic greens -> red (score semantics, never a score
 * field); unknown slate for thin/missing cells (mõõtmata, never
 * dropped, never free-flow green).
 */
export const DELAY_BAND_FILL: Record<DelayBand, string> = {
  free: "#16a34a",
  steady: "#4d7c0f",
  slow: "#eab308",
  jammed: "#dc2626",
  unknown: "#64748b",
};

export const DELAY_DEFS: LayerDef[] = [
  {
    id: "delay-morning",
    paramIds: [],
    paramLabel: "P4-viivitus",
    title: "Tavaviivitus hommikul (koridorid, hinnang)",
    goodLabel:
      "roheline = tavaliselt voolab (tegur ≤1,1 hommikusel tipul 7–9)",
    badLabel:
      "punane = tavaliselt ummikus (tegur >1,6); hall = mõõtmata, mitte vaba tee (tavaline, mitte reaalajas)",
    source: `${DELAY_ATTRIBUTION}: busside GPS-jäljed koridoritunnis (tegur = vaba/tavaline kiirus; <20 proovi = mõõtmata)`,
    fallbackPoints: [],
  },
  {
    id: "delay-midday",
    paramIds: [],
    paramLabel: "P4-viivitus",
    title: "Tavaviivitus keskpäeval (koridorid, hinnang)",
    goodLabel:
      "roheline = tavaliselt voolab (tegur ≤1,1 keskpäeval 10–15)",
    badLabel:
      "punane = tavaliselt ummikus (tegur >1,6); hall = mõõtmata, mitte vaba tee (tavaline, mitte reaalajas)",
    source: `${DELAY_ATTRIBUTION}: busside GPS-jäljed koridoritunnis (tegur = vaba/tavaline kiirus; <20 proovi = mõõtmata)`,
    fallbackPoints: [],
  },
  {
    id: "delay-evening",
    paramIds: [],
    paramLabel: "P4-viivitus",
    title: "Tavaviivitus õhtul (koridorid, hinnang)",
    goodLabel:
      "roheline = tavaliselt voolab (tegur ≤1,1 õhtusel tipul 16–18)",
    badLabel:
      "punane = tavaliselt ummikus (tegur >1,6); hall = mõõtmata, mitte vaba tee (tavaline, mitte reaalajas)",
    source: `${DELAY_ATTRIBUTION}: busside GPS-jäljed koridoritunnis (tegur = vaba/tavaline kiirus; <20 proovi = mõõtmata)`,
    fallbackPoints: [],
  },
  {
    id: "delay-offpeak",
    paramIds: [],
    paramLabel: "P4-viivitus",
    title: "Tavaviivitus tipuvälisel ajal (koridorid, tugitase)",
    goodLabel:
      "roheline = mõõdetud vaba liiklus (tegur 1,0 — tipuväline tugitase, mitte hinnang)",
    badLabel:
      "hall = tugitase mõõtmata, mitte vaba tee (tavaline, mitte reaalajas)",
    source: `${DELAY_ATTRIBUTION}: tipuväline mediaankirus koridori kohta (vaba voo tugi; <20 proovi = mõõtmata)`,
    fallbackPoints: [],
  },
  {
    id: "delay-worst",
    paramIds: [],
    paramLabel: "P4-viivitus",
    title: "Tavaviivitus halvimal tipul (koridorid, hinnang)",
    goodLabel:
      "roheline = voolab ka halvimal tipul (tegur ≤1,1)",
    badLabel:
      "punane = halvimal tipul tavaliselt ummikus (tegur >1,6); hall = mõõtmata, mitte vaba tee (tavaline, mitte reaalajas)",
    source: `${DELAY_ATTRIBUTION}: tippude (hommik/keskpäev/õhtu) maksimumtegur koridori kohta; tipuväline tugitase välja arvatud`,
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): delay serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the polygons-only test.
 */
export const DELAY_DECAY: Record<DelayLayerId, number> = {
  "delay-morning": 0.5,
  "delay-midday": 0.5,
  "delay-evening": 0.5,
  "delay-offpeak": 0.5,
  "delay-worst": 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the delay table
 * is harvested from keyless gps.txt pulls, and snapshot-only serving
 * never queries live either way. The only rebuild path is
 * scripts/build/batch_delay_sampler.py --pull/--build.
 */
export const DELAY_TAGS: Record<DelayLayerId, string> = {
  "delay-morning": "gps.txt vehicle-track harvest (Overpass-uta)",
  "delay-midday": "gps.txt vehicle-track harvest (Overpass-uta)",
  "delay-evening": "gps.txt vehicle-track harvest (Overpass-uta)",
  "delay-offpeak": "gps.txt vehicle-track harvest (Overpass-uta)",
  "delay-worst": "gps.txt vehicle-track harvest (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * decision (typical tables are corridor bands, not a raster): the
 * name resolves to an absent file so windows serve honestly-empty,
 * never a gradient. */
export const DELAY_RASTER_FILE: Record<DelayLayerId, string> = {
  "delay-morning": "delay-walk-raster.json",
  "delay-midday": "delay-walk-raster.json",
  "delay-evening": "delay-walk-raster.json",
  "delay-offpeak": "delay-walk-raster.json",
  "delay-worst": "delay-walk-raster.json",
};

export const DELAY_NO_RASTER = true;
export const DELAY_NO_METRO = true;

/**
 * Membership-zone specs (issue #807): corridor ribbons carry the
 * verdict — inside reads DELAY_BAND_SCORE for the layer's hour band
 * (see zones807.ts); thin/missing cells emit no zone (the scorer reads
 * the same gap as NULL, never free-flow). Zero points, null raster
 * (still polygons-only).
 */
export const DELAY_BONUS: Record<DelayLayerId, BonusSpec> = {
  "delay-morning": { kind: "zones" },
  "delay-midday": { kind: "zones" },
  "delay-evening": { kind: "zones" },
  "delay-offpeak": { kind: "zones" },
  "delay-worst": { kind: "zones" },
};

export function isDelayLayerId(layer: string): layer is DelayLayerId {
  return (DELAY_LAYER_IDS as string[]).includes(layer);
}

export function isDelayPolygonOnlyLayer(layer: string): boolean {
  return isDelayLayerId(layer);
}

export function bonusSpecForDelay(layer: string): BonusSpec | undefined {
  if (isDelayLayerId(layer)) return DELAY_BONUS[layer];
  return undefined;
}

/**
 * One delay corridor band row for the map sidecar. factors/ns carry
 * the four hour bands plus worst (null/0 = thin or missing ->
 * unknown slate, never dropped). rep is the polyline middle vertex;
 * b is the polyline bbox prefilter; r holds the ±150 m road ribbon
 * (equirectangular approx, documented).
 */
export interface DelayArea {
  corridor: string;
  factors: Record<string, number | null>;
  ns: Record<string, number>;
  rep: { lon: number; lat: number } | null;
  b: [number, number, number, number];
  r: number[][][];
}

function isFinitePair(pt: unknown): pt is [number, number] {
  return (
    Array.isArray(pt) &&
    pt.length === 2 &&
    pt.every((n) => typeof n === "number" && Number.isFinite(n))
  );
}

export function isDelayArea(v: unknown): v is DelayArea {
  const p = v as Partial<DelayArea>;
  return (
    typeof p?.corridor === "string" &&
    !!p.corridor &&
    typeof p?.factors === "object" &&
    p.factors !== null &&
    typeof p?.ns === "object" &&
    p.ns !== null &&
    (p.rep === null ||
      (typeof p.rep === "object" &&
        typeof (p.rep as { lon: unknown }).lon === "number" &&
        typeof (p.rep as { lat: unknown }).lat === "number")) &&
    Array.isArray(p?.b) &&
    p.b.length === 4 &&
    p.b.every((n) => typeof n === "number" && Number.isFinite(n)) &&
    Array.isArray(p?.r) &&
    p.r.length > 0 &&
    p.r.every(
      (ring) =>
        Array.isArray(ring) &&
        ring.length >= 3 &&
        ring.every(isFinitePair),
    )
  );
}

/**
 * Delay corridor bands for painting factor fills on a delay layer.
 * Null on any failure: bands are a visual aid, never load-bearing —
 * the per-parcel join lives in the scorer
 * (services/scoring/dims_p4_typical_delay.py).
 */
export async function fetchDelayAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<DelayArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/delay/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (
      !body ||
      typeof body !== "object" ||
      !Array.isArray((body as { areas: unknown }).areas)
    ) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isDelayArea).map((p) => {
      const o = p as DelayArea;
      return {
        corridor: o.corridor,
        factors: o.factors,
        ns: o.ns,
        rep: o.rep,
        b: o.b,
        r: o.r,
      };
    });
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const DELAY_HOOK =
  "DELAY-HOOK (#629): delay wired into layers/overlays/outlines/snapshot; keyless gps.txt typical-delay corridor bands (4 bands + worst), polygons only, thin stays unknown slate (never free-flow green).";
