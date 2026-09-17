// Forest-change detected-change overlay (issue #624): metsamuutused
// polygons, scored bands, NULL-empty outside.
//
// A detected canopy change near a listing is scored (fresh + near
// dominates: <=3y<=500m->30, <=3y<=1500m->55, <=10y<=500m->60, else
// 70 — services/scoring/dims_p4_forestchange.py, licence flipped by
// the #624 verdict). The overlay paints the DETECTION polygons so the
// warning reads at a glance; the per-listing distance bands are the
// scorer's job (distance is per-listing, never per-polygon). Outside
// every polygon is NULL — never "safe forest" (absence of detected
// change is not protection; the publisher's caveat rides every label:
// automatic CHM-difference processing, errors expected).
//
// Serving: the Harju+2 km keep set (5288 polygons, 2024 vintage)
// ships in ONE sidecar (forest/forest-areas.json) via
// /api/layers/forest/areas — fetched once per selection, painted as
// class fills (see applyForestPolygons in ./outlines), seveso
// polygons-only precedent. Rings are Douglas-Peucker simplified at
// 5 m (stated); the scorer reads the same rings, consistently.

import type { BonusSpec, LayerDef } from "./layers";

/** Layer id (parameters4 namespace, no parameters3 number). */
export type ForestLayerId = "forest";
export const FOREST_LAYER_IDS: ForestLayerId[] = ["forest"];

/** Publisher attribution (ETAK open-data licence, stamped in sidecar). */
export const FOREST_ATTRIBUTION = "Maa- ja Ruumiamet metsamuutused 2024 (ETAK avaandmete litsents)";

/** Detection-age classes (mirror the scorer's age brackets). */
export const FOREST_CLASSES = ["", ">10a", "3-10a", "2024 värske"] as const;

export const FOREST_DEFS: LayerDef[] = [
  {
    id: "forest",
    paramIds: [],
    paramLabel: "P4-mets",
    title: "Tuvastatud võramuutis (2024 lend)",
    goodLabel:
      "muutisaknas muutust pole (mitte 'turvaline mets' — tuvastamata jätmine ei kaitse)",
    badLabel:
      "pruun = 2024 tuvastatud muutus lähedal (värske + lähedal loeb kõige rohkem)",
    source:
      `${FOREST_ATTRIBUTION}: Harju+2 km 5288 polügooni (2024 kevad/suvi; tuvastatud muutus, mitte ametlik raiestatistika — automaat-töötlus, vead võimalikud)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygons-only layers out of its fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): forest serves zero points and builds no raster; the scorer's
 * distances read off the sidecar polygons, never a field — pinned by test.
 */
export const FOREST_DECAY: Record<ForestLayerId, number> = {
  forest: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: forest lives in
 * the metsamuutused SHP harvest, and polygon-only serving never
 * queries anything else. The only data path is
 * app/api/layers/forest/areas.
 */
export const FOREST_TAGS: Record<ForestLayerId, string> = {
  forest: "metsamuutused-2024 SHP Harjumaa+2km keep (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const FOREST_RASTER_FILE: Record<ForestLayerId, string> = {
  forest: "forest-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const FOREST_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const FOREST_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by test). The live scorer leg is
 * services/scoring/dims_p4_forestchange.py (registry entry point, not
 * this bonus). Shape mirrors the area kind so the type contract holds
 * without inventing a calibration.
 */
export const FOREST_BONUS: Record<ForestLayerId, BonusSpec> = {
  forest: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isForestLayerId(layer: string): layer is ForestLayerId {
  return (FOREST_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygons-only layers: no points, no raster — the sidecar polygons
 * carry the data (scored, unlike taste-only tints). The /layers page
 * branches on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isForestPolygonOnlyLayer(layer: string): boolean {
  return isForestLayerId(layer);
}

/**
 * Forest bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForForest(layer: string): BonusSpec | undefined {
  return (FOREST_BONUS as Record<string, BonusSpec>)[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const FOREST_HOOK =
  "FOREST-HOOK (#624): forest polygons wired into layers/overlays/outlines/snapshot; detected-change bands, NULL-empty outside (never safe forest).";

/**
 * One detected change for the map sidecar. Rings are GeoJSON [lon, lat]
 * (Douglas-Peucker 5 m in 3301, then LCC-projected); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box; cls is the detection
 * age class (never a score — distance bands are per-listing).
 */
export interface ForestArea {
  change_id: string;
  season: string;
  first: string | null;
  second: string | null;
  area_ha: number;
  cls: number;
  b: [number, number, number, number];
  r: number[][][];
}

export function isForestArea(v: unknown): v is ForestArea {
  const p = v as Partial<ForestArea>;
  return (
    typeof p?.change_id === "string" &&
    typeof p?.season === "string" &&
    (p?.first === null || p?.first === undefined || typeof p.first === "string") &&
    (p?.second === null || p?.second === undefined || typeof p.second === "string") &&
    typeof p?.area_ha === "number" &&
    Number.isFinite(p.area_ha) &&
    typeof p?.cls === "number" &&
    Number.isInteger(p.cls) &&
    p.cls >= 1 &&
    p.cls <= 3 &&
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
 * Forest polygons for painting class fills on the forest layer.
 * Null on any failure: fills are a visual aid, never load-bearing —
 * the scorer reads the same sidecar independently.
 */
export async function fetchForestAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<ForestArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/forest/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    const areas = (body as { areas: unknown[] }).areas.filter(isForestArea).map((p) => {
      const o = p as ForestArea;
      return {
        change_id: o.change_id,
        season: o.season,
        first: o.first ?? null,
        second: o.second ?? null,
        area_ha: o.area_ha,
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
 * Detection fill colors by class (soil umbers — fresh change darkest,
 * mirroring the scorer's age brackets; deliberately NOT green/red —
 * the overlay warns, never grades). Shared by the map painter
 * (applyForestPolygons) and unit-tested here.
 */
export const FOREST_CLASS_FILL: Record<string, string> = {
  "1": "#dcc9a8",
  "2": "#c08a4d",
  "3": "#92400e",
  unknown: "#dcc9a8",
};

/** Fill color for one class (unknown class degrades oldest, never a guess). */
export function forestFillColor(cls: number): string {
  const key = String(cls);
  return key in FOREST_CLASS_FILL ? FOREST_CLASS_FILL[key] : FOREST_CLASS_FILL.unknown;
}
