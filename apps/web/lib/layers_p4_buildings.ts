// Building-height character tint overlay (issue #621): LoD1 height tint,
// taste-only, never a score field.
//
// Building height is taste, not good/bad: view vs shade, openness vs
// shelter is a buyer tradeoff, so a good/bad gradient would be fake
// precision. This layer paints OUR bins over the publisher's
// bldg:measuredHeight (Maa- ja Ruumiamet 3D hoonete LoD1 CityGML,
// CC BY 4.0 — see scripts/build/batch_buildings.py +
// docs/p4_buildings.md) with a taste-only legend ("maitse, mitte
// hinne"). No score field is painted anywhere; the scorer has NO
// building legs in this issue (tint first, capped taste legs second —
// legs arrive with the buyer-taste selection they need, never
// unlabeled).
//
// Serving: the county class grid (1000x570, union-envelope window —
// DELIBERATELY wider than the relief/canopy window, which clips Loksa;
// see the builder) ships in ONE sidecar
// (buildings/buildings-tint.json, ~0.8 MB) via
// /api/layers/buildings/areas — fetched once per selection, painted
// as a canvas PNG image overlay (see applyBuildingsTint in
// ./outlines). The grid renderer below (renderBuildingsTint) is pure
// and unit-tested; the DOM glue (canvas -> data URL) is the only
// untested seam, guarded to a no-op without a document.

import type { BBoxLike, BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type BuildingsLayerId = "buildings";
export const BUILDINGS_LAYER_IDS: BuildingsLayerId[] = ["buildings"];

/** Publisher attribution (CC BY 4.0 — stamped in sidecar stats). */
export const BUILDINGS_ATTRIBUTION = "Maa- ja Ruumiamet 3D hoonete LoD1 (CC BY 4.0)";

/** #807 NO-SCORE DECISION (2026-09-20): building-height character is
 * buyer taste, not quality — the tint stays unscored (INERT). */
/** Our height bins (index 0 = missing/negative). Stated as ours, never publisher classes. */
export const BUILDINGS_CLASSES = [
  "<3m/puudub",
  "0-3m",
  "3-6m",
  "6-12m",
  "12-25m",
  ">25m",
] as const;

export const BUILDINGS_DEFS: LayerDef[] = [
  {
    id: "buildings",
    paramIds: [],
    paramLabel: "P4-hooned",
    title: "Hoonete kõrguse toon (maitsekaart, hinnanguta)",
    goodLabel:
      "kõrgem toon = kõrgem hoonestus (vari, varjulisus — maitse, mitte hinne)",
    badLabel:
      "madalam toon = madal hoonestus (varjutus teadmata — toon ei hinda; väljaspool katvust = teadmata)",
    source:
      `${BUILDINGS_ATTRIBUTION}: Harju aken 1000x570 klassivõrk (LoD1 mõõdetud kõrgus, lend 2025; 199k/199k hoonet, 6-12 m levinuim; meie klassid, mitte avaldaja omad)`,
    // Tint-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // taste-only layers out of its fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): buildings serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the taste-only test.
 */
export const BUILDINGS_DECAY: Record<BuildingsLayerId, number> = {
  buildings: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: buildings live in
 * the LoD1 CityGML harvest, and grid-only serving never queries anything
 * else. The only data path is app/api/layers/buildings/areas.
 */
export const BUILDINGS_TAGS: Record<BuildingsLayerId, string> = {
  buildings: "LOD1-CityGML Harjumaa county window (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented taste-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const BUILDINGS_RASTER_FILE: Record<BuildingsLayerId, string> = {
  buildings: "buildings-walk-raster.json",
};

/** NO raster master (documented): tint-only, windows serve county. */
export const BUILDINGS_NO_RASTER = true;

/** NO metro master (documented): tint-only, windows serve county. */
export const BUILDINGS_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the taste-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const BUILDINGS_BONUS: Record<BuildingsLayerId, BonusSpec> = {
  buildings: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isBuildingsLayerId(layer: string): layer is BuildingsLayerId {
  return (BUILDINGS_LAYER_IDS as string[]).includes(layer);
}

/**
 * Taste-only layers: no points, no raster, no gradient, no score —
 * the tint grid carries the data. The /layers page and the points
 * endpoint branch on this (never on an id literal, so the contract
 * stays greppable).
 */
export function isBuildingsTasteOnlyLayer(layer: string): boolean {
  return isBuildingsLayerId(layer);
}

/**
 * Buildings bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForBuildings(layer: string): BonusSpec | undefined {
  return (BUILDINGS_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const BUILDINGS_HOOK =
  "BUILDINGS-HOOK (#621): buildings tint wired into layers/overlays/outlines/snapshot; LoD1 height character tint, taste-only, outside stays unknown (never scored).";

/** Decoded tint grid (class 0-5 per cell; 0 = missing/outside). */
export interface BuildingsTintGrid {
  cols: number;
  rows: number;
  bbox: BBoxLike;
  vintage: string | null;
  classes: number[];
}

export function isBuildingsTintGrid(v: unknown): v is BuildingsTintGrid {
  const p = v as Partial<BuildingsTintGrid>;
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
 * never a shifted tint. The sidecar stamps vintage as a per-year
 * object ({2025: n}); the grid carries the majority year as its
 * vintage string (or null when absent).
 */
export function decodeBuildingsGrid(doc: unknown): BuildingsTintGrid | null {
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
  let vintage: string | null = null;
  if (typeof d.vintage === "string") {
    vintage = d.vintage as string;
  } else if (d.vintage && typeof d.vintage === "object") {
    const years = Object.entries(d.vintage as Record<string, unknown>)
      .filter(([, n]) => typeof n === "number")
      .sort((a, b) => (b[1] as number) - (a[1] as number));
    if (years.length > 0) vintage = years[0][0];
  }
  const grid: BuildingsTintGrid = { cols, rows, bbox: bbox as BBoxLike, vintage, classes };
  return isBuildingsTintGrid(grid) ? grid : null;
}

/**
 * Height-tint colors [r, g, b]: pale stone -> deep indigo (deliberately
 * NOT green/red — never a score). Class 0 renders transparent.
 * Alpha is constant.
 */
export const BUILDINGS_LUT: ReadonlyArray<readonly [number, number, number]> = [
  [0, 0, 0], // 0 = transparent (unused)
  [0xd9, 0xd4, 0xc7], // 0-3 m
  [0xbc, 0xb6, 0xa4], // 3-6 m
  [0x9a, 0x93, 0xa3], // 6-12 m
  [0x6e, 0x63, 0x90], // 12-25 m
  [0x45, 0x3a, 0x6e], // >25 m
];

/** Tint opacity (0-255): the basemap stays readable through the tint. */
export const BUILDINGS_ALPHA = 150;

/**
 * Render the tint grid to RGBA bytes (row-major, top row first — the
 * sidecar's row 0 is maxlat). Pure: the DOM glue (canvas -> PNG data
 * URL in outlines.ts) consumes this; unit tests pin classes + missing.
 */
export function renderBuildingsTint(grid: BuildingsTintGrid): {
  cols: number;
  rows: number;
  rgba: Uint8ClampedArray<ArrayBuffer>;
} {
  // Plain ArrayBuffer (not shared): DOM ImageData requires it.
  const rgba = new Uint8ClampedArray(new ArrayBuffer(grid.cols * grid.rows * 4));
  for (let i = 0; i < grid.cols * grid.rows; i++) {
    const cls = grid.classes[i];
    if (cls <= 0 || cls >= BUILDINGS_LUT.length) {
      rgba[i * 4 + 3] = 0;
      continue;
    }
    const c = BUILDINGS_LUT[cls];
    rgba[i * 4] = c[0];
    rgba[i * 4 + 1] = c[1];
    rgba[i * 4 + 2] = c[2];
    rgba[i * 4 + 3] = BUILDINGS_ALPHA;
  }
  return { cols: grid.cols, rows: grid.rows, rgba };
}

/**
 * Buildings tint grid for painting the character tint on the buildings
 * layer. Null on any failure: the tint is a visual aid, never
 * load-bearing — and this layer has no scorer legs (taste-only).
 */
export async function fetchBuildingsTint(
  fetchImpl: typeof fetch = fetch,
): Promise<BuildingsTintGrid | null> {
  try {
    const res = await fetchImpl("/api/layers/buildings/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !("grid" in body)) return null;
    return decodeBuildingsGrid((body as { grid: unknown }).grid);
  } catch {
    return null;
  }
}
