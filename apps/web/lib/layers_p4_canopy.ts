// Canopy-height character tint overlay (issue #620): CHM class tint,
// taste-only, never a score field.
//
// Canopy height is taste, not good/bad: shade/shelter vs light/view is
// a buyer tradeoff, so a good/bad gradient would be fake precision.
// This layer paints the publisher's own CHM classes (Maa- ja Ruumiamet
// CHM2022_suvi WMS, CC BY 4.0 — see scripts/build/batch_canopy.py +
// docs/p4_canopy.md) with a taste-only legend ("maitse, mitte
// hinne"). No score field is painted anywhere; the scorer has NO
// canopy legs in this issue (tint first, capped taste legs second —
// legs arrive with the buyer-taste selection they need, never
// unlabeled).
//
// Serving: the county class grid (1000x570, reprojected 3301 -> 4326
// in batch) ships in ONE sidecar (canopy/canopy-tint.json, ~0.8 MB)
// via /api/layers/canopy/areas — fetched once per selection, painted
// as a canvas PNG image overlay (see applyCanopyTint in ./outlines).
// The grid renderer below (renderCanopyTint) is pure and unit-tested;
// the DOM glue (canvas -> data URL) is the only untested seam,
// guarded to a no-op without a document.

import type { BBoxLike, BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type CanopyLayerId = "canopy";
export const CANOPY_LAYER_IDS: CanopyLayerId[] = ["canopy"];

/** Publisher attribution (CC BY 4.0 — stamped in sidecar stats). */
export const CANOPY_ATTRIBUTION = "Maa- ja Ruumiamet CHM (CC BY 4.0, CHM2022_suvi)";

/** #807 NO-SCORE DECISION (2026-09-20): tree-cover shade is buyer
 * taste, not quality — the tint stays unscored (INERT). */
/** Publisher height classes (index 0 = <1 m / missing). */
export const CANOPY_CLASSES = [
  "<1m/puudub",
  "1-4m",
  "4-10m",
  "10-20m",
  "20-30m",
  ">30m",
] as const;

export const CANOPY_DEFS: LayerDef[] = [
  {
    id: "canopy",
    paramIds: [],
    paramLabel: "P4-võra",
    title: "Võrastiku toon (maitsekaart, hinnanguta)",
    goodLabel:
      "kõrgem toon = puistu iseloom (vari, varjulisus — maitse, mitte hinne)",
    badLabel:
      "madalam toon = lage maa (lehekoormus ja varjutus teadmata — toon ei hinda; väljaspool katvust = teadmata)",
    source:
      `${CANOPY_ATTRIBUTION}: Harju aken 1000x570 klassivõrk (lend 2022-suvi; 244k/570k võrakannet, 10-20 m levinuim; <1 m = läbipaistev, mitte lühike võra)`,
    // Tint-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // taste-only layers out of its fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): canopy serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the taste-only test.
 */
export const CANOPY_DECAY: Record<CanopyLayerId, number> = {
  canopy: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: canopy lives in
 * the CHM WMS harvest, and grid-only serving never queries anything
 * else. The only data path is app/api/layers/canopy/areas.
 */
export const CANOPY_TAGS: Record<CanopyLayerId, string> = {
  canopy: "CHM-WMS CHM2022_suvi Harjumaa viewport (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented taste-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const CANOPY_RASTER_FILE: Record<CanopyLayerId, string> = {
  canopy: "canopy-walk-raster.json",
};

/** NO raster master (documented): tint-only, windows serve county. */
export const CANOPY_NO_RASTER = true;

/** NO metro master (documented): tint-only, windows serve county. */
export const CANOPY_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the taste-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const CANOPY_BONUS: Record<CanopyLayerId, BonusSpec> = {
  canopy: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isCanopyLayerId(layer: string): layer is CanopyLayerId {
  return (CANOPY_LAYER_IDS as string[]).includes(layer);
}

/**
 * Taste-only layers: no points, no raster, no gradient, no score —
 * the tint grid carries the data. The /layers page and the points
 * endpoint branch on this (never on an id literal, so the contract
 * stays greppable).
 */
export function isCanopyTasteOnlyLayer(layer: string): boolean {
  return isCanopyLayerId(layer);
}

/**
 * Canopy bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForCanopy(layer: string): BonusSpec | undefined {
  return (CANOPY_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const CANOPY_HOOK =
  "CANOPY-HOOK (#620): canopy tint wired into layers/overlays/outlines/snapshot; CHM class character tint, taste-only, outside stays unknown (never scored).";

/** Decoded tint grid (class 0-5 per cell; 0 = transparent/missing). */
export interface CanopyTintGrid {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  vintage: string | null;
  classes: number[];
}

export function isCanopyTintGrid(v: unknown): v is CanopyTintGrid {
  const p = v as Partial<CanopyTintGrid>;
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
    Array.isArray(p.classes) &&
    p.classes.length === p.cols * p.rows &&
    p.classes.every((c) => typeof c === "number" && Number.isInteger(c) && c >= 0 && c <= 5) &&
    (p.vintage === null || p.vintage === undefined || typeof p.vintage === "string")
  );
}

/**
 * Decode the sidecar doc (base64 uint8 classes) into a grid.
 * Null on any malformation: a corrupt grid renders honestly-empty,
 * never a shifted tint.
 */
export function decodeCanopyGrid(doc: unknown): CanopyTintGrid | null {
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
  if (d.encoding !== "base64-uint8" || typeof d.data !== "string") return null;
  let raw: Uint8Array;
  try {
    const bin = atob(d.data as string);
    raw = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) raw[i] = bin.charCodeAt(i);
  } catch {
    return null;
  }
  if (raw.length !== cols * rows) return null;
  const classes: number[] = Array.from(raw);
  if (classes.some((c) => c < 0 || c > 5)) return null;
  const vintage = typeof d.vintage === "string" ? (d.vintage as string) : null;
  const grid: CanopyTintGrid = { cols, rows, bbox: bbox as BBoxLike, vintage, classes };
  return isCanopyTintGrid(grid) ? grid : null;
}

/**
 * Publisher class colors [r, g, b] (legend-exact, NOT recolored: the
 * tint shows the source's own classes; the taste-only framing lives in
 * the legend, not in a re-tint). Alpha is constant.
 */
export const CANOPY_LUT: ReadonlyArray<readonly [number, number, number]> = [
  [0, 0, 0], // 0 = transparent (unused)
  [0x25, 0x51, 0x0F], // 1-4 m
  [0x35, 0x69, 0x0D], // 4-10 m
  [0x6b, 0x86, 0x0a], // 10-20 m
  [0xdf, 0x7f, 0x03], // 20-30 m
  [0xe0, 0x1f, 0x1f], // >30 m
];

/** Tint opacity (0-255): the basemap stays readable through the tint. */
export const CANOPY_ALPHA = 150;

/**
 * Render the tint grid to RGBA bytes (row-major, top row first — the
 * sidecar's row 0 is maxlat). Pure: the DOM glue (canvas -> PNG data
 * URL in outlines.ts) consumes this; unit tests pin classes + missing.
 */
export function renderCanopyTint(grid: CanopyTintGrid): {
  cols: number;
  rows: number;
  rgba: Uint8ClampedArray<ArrayBuffer>;
} {
  // Plain ArrayBuffer (not shared): DOM ImageData requires it.
  const rgba = new Uint8ClampedArray(new ArrayBuffer(grid.cols * grid.rows * 4));
  for (let i = 0; i < grid.cols * grid.rows; i++) {
    const cls = grid.classes[i];
    if (cls <= 0 || cls >= CANOPY_LUT.length) {
      rgba[i * 4 + 3] = 0;
      continue;
    }
    const c = CANOPY_LUT[cls];
    rgba[i * 4] = c[0];
    rgba[i * 4 + 1] = c[1];
    rgba[i * 4 + 2] = c[2];
    rgba[i * 4 + 3] = CANOPY_ALPHA;
  }
  return { cols: grid.cols, rows: grid.rows, rgba };
}

/**
 * Canopy tint grid for painting the character tint on the canopy
 * layer. Null on any failure: the tint is a visual aid, never
 * load-bearing — and this layer has no scorer legs (taste-only).
 */
export async function fetchCanopyTint(
  fetchImpl: typeof fetch = fetch,
): Promise<CanopyTintGrid | null> {
  try {
    const res = await fetchImpl("/api/layers/canopy/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !("grid" in body)) return null;
    return decodeCanopyGrid((body as { grid: unknown }).grid);
  } catch {
    return null;
  }
}
