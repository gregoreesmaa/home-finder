// Density 1 km character choropleth (issue #622): INSPIRE PD squares,
// taste-only, never a score field.
//
// Population density is taste, not good/bad: urban buzz vs space and
// quiet is a buyer tradeoff, so a good/bad gradient would be fake
// precision. This layer paints OUR bins over the publisher's
// inhabitants count (Maa- ja Ruumiamet INSPIRE PD 1x1 km, CC0,
// Statistikaamet — see scripts/build/batch_density.py +
// docs/p4_density.md) with a taste-only legend ("maitse, mitte
// hinne"). No score field is painted anywhere; the scorer has NO
// density legs in this issue (tint first, capped taste legs second —
// legs arrive with the buyer-taste selection they need, never
// unlabeled).
//
// Serving: the county square set (8210 inhabited 1 km squares, 2024
// vintage) ships in ONE sidecar (density/density-areas.json) via
// /api/layers/density/areas — fetched once per selection, painted as
// class fills (see applyDensityPolygons in ./outlines), KOV-choropleth
// precedent (MARU #486), coarse grain, honestly labeled. Squares are
// painted EXACTLY (1 km cells are the field — never interpolated).
// Outside every square is NULL (never rural); masked (<4) squares read
// 0 and paint class 0 (tühi/varjatud — never "empty").

import type { BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type DensityLayerId = "density";
export const DENSITY_LAYER_IDS: DensityLayerId[] = ["density"];

/** Publisher attribution (CC0 — still attributed; stamped in sidecar). */
export const DENSITY_ATTRIBUTION = "Maa- ja Ruumiamet INSPIRE PD 1x1 km (CC0, Statistikaamet)";

/** #807 NO-SCORE DECISION (2026-09-20): density character (city buzz
 * vs quiet) is buyer taste, not quality — the squares stay unscored
 * (INERT). A dense cell is services-near AND noise-near; collapsing
 * that to one number would fake a verdict. */
/** Our inhabitant bins (0 = empty OR privacy-masked <4, never "empty"). */
export const DENSITY_CLASSES = [
  "0 (tühi/varjatud)",
  "1-9",
  "10-99",
  "100-999",
  "1000-4999",
  "5000+",
] as const;

export const DENSITY_DEFS: LayerDef[] = [
  {
    id: "density",
    paramIds: [],
    paramLabel: "P4-asustus",
    title: "Asustuse toon (maitsekaart, hinnanguta)",
    goodLabel:
      "tihedam toon = linnakarakter (melu, teenused lähedal — maitse, mitte hinne)",
    badLabel:
      "hõredam toon = vaikusekarakter (ruumi, teadmata — toon ei hinda; väljaspool ruute = teadmata)",
    source:
      `${DENSITY_ATTRIBUTION}: Harju 8210 ruutu 1x1 km (2024; 0 = tühi või varjatud <4; meie klassid, mitte avaldaja omad)`,
    // Choropleth-only: no demo points, ever — a demo point would paint
    // a fake gradient splat (see header). The generic labels test
    // carves taste-only layers out of its fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): density serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the taste-only test.
 */
export const DENSITY_DECAY: Record<DensityLayerId, number> = {
  density: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: density lives in
 * the INSPIRE PD WFS harvest, and square-only serving never queries
 * anything else. The only data path is app/api/layers/density/areas.
 */
export const DENSITY_TAGS: Record<DensityLayerId, string> = {
  density: "INSPIRE-PD 1x1km Harjumaa squares (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented taste-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const DENSITY_RASTER_FILE: Record<DensityLayerId, string> = {
  density: "density-walk-raster.json",
};

/** NO raster master (documented): choropleth-only, windows serve county. */
export const DENSITY_NO_RASTER = true;

/** NO metro master (documented): choropleth-only, windows serve county. */
export const DENSITY_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the taste-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const DENSITY_BONUS: Record<DensityLayerId, BonusSpec> = {
  density: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isDensityLayerId(layer: string): layer is DensityLayerId {
  return (DENSITY_LAYER_IDS as string[]).includes(layer);
}

/**
 * Taste-only layers: no points, no raster, no gradient, no score —
 * the square fills carry the data. The /layers page and the points
 * endpoint branch on this (never on an id literal, so the contract
 * stays greppable).
 */
export function isDensityTasteOnlyLayer(layer: string): boolean {
  return isDensityLayerId(layer);
}

/**
 * Density bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForDensity(layer: string): BonusSpec | undefined {
  return (DENSITY_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const DENSITY_HOOK =
  "DENSITY-HOOK (#622): density squares wired into layers/overlays/outlines/snapshot; 1 km character choropleth, taste-only, outside stays unknown (never scored).";

/**
 * One density square for the map sidecar. Rings are GeoJSON [lon, lat]
 * (the builder keeps the WFS 4326 quad verbatim, rounded); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box; cls is our
 * inhabitants bin (never a score); value is inhabitants (2024).
 */
export interface DensityArea {
  zone_id: string;
  value: number;
  cls: number;
  b: [number, number, number, number];
  r: number[][][];
}

export function isDensityArea(v: unknown): v is DensityArea {
  const p = v as Partial<DensityArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.value === "number" &&
    Number.isFinite(p.value) &&
    typeof p?.cls === "number" &&
    Number.isInteger(p.cls) &&
    p.cls >= 0 &&
    p.cls <= 5 &&
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
 * Density squares for painting class fills on the density layer.
 * Null on any failure: fills are a visual aid, never load-bearing —
 * this layer has no scorer legs (taste-only).
 */
export async function fetchDensityAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<DensityArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/density/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    const areas = (body as { areas: unknown[] }).areas.filter(isDensityArea).map((p) => {
      const o = p as DensityArea;
      return {
        zone_id: o.zone_id,
        value: o.value,
        cls: o.cls,
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
 * Square fill colors by class (bone -> deep plum, deliberately NOT
 * green/red — never a score). Class 0 (empty/masked) is near-paper so
 * inhabited land reads first. Shared by the map painter
 * (applyDensityPolygons) and unit-tested here.
 */
export const DENSITY_CLASS_FILL: Record<string, string> = {
  "0": "#e7e2d6",
  "1": "#cfc3e4",
  "2": "#ac9bd2",
  "3": "#7e68b5",
  "4": "#523d8f",
  "5": "#312157",
  unknown: "#e7e2d6",
};

/** Fill color for one class (unknown class degrades to class 0, never a guess). */
export function densityFillColor(cls: number): string {
  const key = String(cls);
  return key in DENSITY_CLASS_FILL ? DENSITY_CLASS_FILL[key] : DENSITY_CLASS_FILL.unknown;
}
