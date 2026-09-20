// Relief character tint overlay (issue #619): DTM hypsometric tint,
// taste-only, never a score field.
//
// Relief is scenery, not good/bad: flatness is taste-dependent (a
// cyclist's green is a view-seeker's red), so a good/bad gradient
// would be fake precision. This layer paints a hypsometric CHARACTER
// tint from the committed county grid (Maa-amet DTM dtm-10, CC BY 4.0
// — see scripts/build/batch_relief.py + docs/p4_relief.md) with a
// taste-only legend ("maitse, mitte hinne"). No score field is painted
// anywhere; the scorer has NO relief legs in this issue (tint first,
// capped taste legs second — legs arrive with the buyer-taste
// selection they need, never unlabeled).
// #807 NO-SCORE DECISION (2026-09-20): taste tints cannot score —
// flat vs high is buyer taste, not quality. Spec stays INERT.
//
// Serving: the whole-county grid (1000x570, ~130x240 m cells) ships in
// ONE sidecar (relief/relief-tint.json, ~1.5 MB) via
// /api/layers/relief/areas — fetched once per selection, painted as a
// canvas PNG image overlay (see applyReliefTint in ./outlines). The
// grid renderer below (renderReliefTint) is pure and unit-tested; the
// DOM glue (canvas -> data URL) is the only untested seam, guarded to
// a no-op without a document.

import type { BBoxLike, BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type ReliefLayerId = "relief";
export const RELIEF_LAYER_IDS: ReliefLayerId[] = ["relief"];

/** Publisher attribution (CC BY 4.0 — stamped in sidecar stats). */
export const RELIEF_ATTRIBUTION = "Maa-ameti DTM (CC BY 4.0, dtm-10)";

export const RELIEF_DEFS: LayerDef[] = [
  {
    id: "relief",
    paramIds: [],
    paramLabel: "P4-reljeef",
    title: "Reljeefi toon (maitsekaart, hinnanguta)",
    goodLabel:
      "kõrgem toon = vaate-iseloom (klint, nõlvad — maitse, mitte hinne)",
    badLabel:
      "madalam toon = tasane maa (niiskus- ja vaate-olemus teadmata — toon ei hinda; väljaspool katvust = teadmata)",
    source:
      `${RELIEF_ATTRIBUTION}: Harju aken 1000x570 toonvõrk (seis 2026-09-17; 0-112 m, p50 20 m; klint 41-45 / Nõmme 27-52 / Pirita 0-6 — toon ERISTAB, ei hinda)`,
    // Tint-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // taste-only layers out of its fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): relief serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the taste-only test.
 */
export const RELIEF_DECAY: Record<ReliefLayerId, number> = {
  relief: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: relief lives in
 * the DTM WCS harvest, and grid-only serving never queries anything
 * else. The only data path is app/api/layers/relief/areas.
 */
export const RELIEF_TAGS: Record<ReliefLayerId, string> = {
  relief: "DTM-WCS dtm-10 Harjumaa viewport (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented taste-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const RELIEF_RASTER_FILE: Record<ReliefLayerId, string> = {
  relief: "relief-walk-raster.json",
};

/** NO raster master (documented): tint-only, windows serve county. */
export const RELIEF_NO_RASTER = true;

/** NO metro master (documented): tint-only, windows serve county. */
export const RELIEF_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the taste-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const RELIEF_BONUS: Record<ReliefLayerId, BonusSpec> = {
  relief: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isReliefLayerId(layer: string): layer is ReliefLayerId {
  return (RELIEF_LAYER_IDS as string[]).includes(layer);
}

/**
 * Taste-only layers: no points, no raster, no gradient, no score —
 * the tint grid carries the data. The /layers page and the points
 * endpoint branch on this (never on an id literal, so the contract
 * stays greppable).
 */
export function isReliefTasteOnlyLayer(layer: string): boolean {
  return isReliefLayerId(layer);
}

/**
 * Relief bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForRelief(layer: string): BonusSpec | undefined {
  return (RELIEF_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const RELIEF_HOOK =
  "RELIEF-HOOK (#619): relief tint wired into layers/overlays/outlines/snapshot; DTM hypsometric character tint, taste-only, outside stays unknown (never scored).";

/** Decoded tint grid (heights in metres; NaN = missing/transparent). */
export interface ReliefTintGrid {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  vintage: string | null;
  heights: number[];
}

/** Missing-cell sentinel in the sidecar (int16 decimetres). */
export const RELIEF_MISSING = -32768;

export function isReliefTintGrid(v: unknown): v is ReliefTintGrid {
  const p = v as Partial<ReliefTintGrid>;
  return (
    !!p &&
    typeof p.cols === "number" &&
    Number.isInteger(p.cols) &&
    p.cols > 0 &&
    typeof p.rows === "number" &&
    Number.isInteger(p.rows) &&
    p.rows > 0 &&
    !!p.bbox &&
    typeof p.bbox.minlon === "number" &&
    typeof p.bbox.minlat === "number" &&
    typeof p.bbox.maxlon === "number" &&
    typeof p.bbox.maxlat === "number" &&
    Array.isArray(p.heights) &&
    p.heights.length === p.cols * p.rows &&
    p.heights.every((h) => typeof h === "number") &&
    (p.vintage === null || p.vintage === undefined || typeof p.vintage === "string")
  );
}

/**
 * Decode the sidecar doc (base64 int16 decimetres) into metres.
 * Null on any malformation: a corrupt grid renders honestly-empty,
 * never a shifted tint.
 */
export function decodeReliefGrid(doc: unknown): ReliefTintGrid | null {
  if (!doc || typeof doc !== "object") return null;
  const d = doc as Record<string, unknown>;
  const cols = d.cols;
  const rows = d.rows;
  const bbox = d.bbox as Partial<BBoxLike> | null;
  if (
    typeof cols !== "number" ||
    !Number.isInteger(cols) ||
    cols <= 0 ||
    typeof rows !== "number" ||
    !Number.isInteger(rows) ||
    rows <= 0 ||
    !bbox ||
    typeof bbox.minlon !== "number" ||
    typeof bbox.minlat !== "number" ||
    typeof bbox.maxlon !== "number" ||
    typeof bbox.maxlat !== "number"
  ) {
    return null;
  }
  if (d.encoding !== "base64-int16-le" || typeof d.data !== "string") return null;
  let raw: Uint8Array;
  try {
    const bin = atob(d.data as string);
    raw = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) raw[i] = bin.charCodeAt(i);
  } catch {
    return null;
  }
  if (raw.length !== cols * rows * 2) return null;
  const view = new DataView(raw.buffer);
  const heights: number[] = new Array(cols * rows);
  for (let i = 0; i < cols * rows; i++) {
    const dm = view.getInt16(i * 2, true);
    heights[i] = dm === RELIEF_MISSING ? NaN : dm / 10;
  }
  const vintage = typeof d.vintage === "string" ? (d.vintage as string) : null;
  const grid: ReliefTintGrid = { cols, rows, bbox: bbox as BBoxLike, vintage, heights };
  return isReliefTintGrid(grid) ? grid : null;
}

/**
 * Hypsometric tint stops [metres, r, g, b] (taste-only character ramp:
 * moss lowlands -> sand -> tan -> pale rock; deliberately NOT
 * green/red, so the tint never reads as good/bad). Alpha is constant.
 */
export const RELIEF_LUT: Array<readonly [number, number, number, number]> = [
  [0, 92, 138, 77],
  [15, 130, 158, 88],
  [30, 168, 172, 96],
  [50, 201, 180, 120],
  [75, 176, 125, 79],
  [100, 160, 120, 95],
  [130, 217, 210, 197],
];

/** Tint opacity (0-255): the basemap stays readable through the tint. */
export const RELIEF_ALPHA = 150;

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/** Tint color for one height (metres); null = transparent (missing). */
export function reliefColorFor(h: number): [number, number, number, number] | null {
  if (!Number.isFinite(h)) return null;
  const lut = RELIEF_LUT;
  if (h <= lut[0][0]) return [lut[0][1], lut[0][2], lut[0][3], RELIEF_ALPHA];
  for (let i = 1; i < lut.length; i++) {
    if (h <= lut[i][0]) {
      const t = (h - lut[i - 1][0]) / (lut[i][0] - lut[i - 1][0]);
      return [
        Math.round(lerp(lut[i - 1][1], lut[i][1], t)),
        Math.round(lerp(lut[i - 1][2], lut[i][2], t)),
        Math.round(lerp(lut[i - 1][3], lut[i][3], t)),
        RELIEF_ALPHA,
      ];
    }
  }
  const top = lut[lut.length - 1];
  return [top[1], top[2], top[3], RELIEF_ALPHA];
}

/**
 * Render the tint grid to RGBA bytes (row-major, top row first — the
 * sidecar's row 0 is maxlat). Pure: the DOM glue (canvas -> PNG data
 * URL in outlines.ts) consumes this; unit tests pin bands + missing.
 */
export function renderReliefTint(grid: ReliefTintGrid): {
  cols: number;
  rows: number;
  rgba: Uint8ClampedArray<ArrayBuffer>;
} {
  // Plain ArrayBuffer (not shared): DOM ImageData requires it.
  const rgba = new Uint8ClampedArray(new ArrayBuffer(grid.cols * grid.rows * 4));
  for (let i = 0; i < grid.cols * grid.rows; i++) {
    const c = reliefColorFor(grid.heights[i]);
    rgba[i * 4] = c ? c[0] : 0;
    rgba[i * 4 + 1] = c ? c[1] : 0;
    rgba[i * 4 + 2] = c ? c[2] : 0;
    rgba[i * 4 + 3] = c ? c[3] : 0;
  }
  return { cols: grid.cols, rows: grid.rows, rgba };
}

/**
 * Relief tint grid for painting the character tint on the relief
 * layer. Null on any failure: the tint is a visual aid, never
 * load-bearing — and this layer has no scorer legs (taste-only).
 */
export async function fetchReliefTint(
  fetchImpl: typeof fetch = fetch,
): Promise<ReliefTintGrid | null> {
  try {
    const res = await fetchImpl("/api/layers/relief/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !("grid" in body)) return null;
    return decodeReliefGrid((body as { grid: unknown }).grid);
  } catch {
    return null;
  }
}
