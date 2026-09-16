// Seveso danger-area polygon overlay (Päästeamet register, issue #613).
//
// One layer ("seveso"): the national major-accident-hazard register's
// danger-area POLYGONs (ohtlikud_kaitised_ohualad.csv, 235 rows / 95 in
// Harju, verified 2026-09-16) as an honest per-parcel zone-MEMBERSHIP
// choropleth — inside a named danger polygon vs outside/unknown — never
// a gradient. Verdict + probe evidence: docs/p4_seveso.md (issue #527).
//
// Source: Rescue Board (Päästeamet) via opendata.smit.ee (weekly
// CSV pull, see services/scoring/dims_p4_seveso.py fetch_seveso_snapshot
// — cache-first, 7 d TTL, polite single pull). Licence CC BY-NC-ND 4.0:
// attribute Päästeamet, keep raw snapshots unmodified, NO
// re-interpolated raster (ND forbids derivatives — hence polygons ONLY,
// SEVESO_NO_RASTER below). The per-listing scorer dim lives in
// services/scoring/dims_p4_seveso.py (dim_seveso_zone: inside scores by
// danger type, outside NULLs); this module answers the map question
// only and shares the danger-class vocabulary with it (byte parity on
// class names + scores, see SEVESO_DANGER_SCORE).
//
// HONESTY (load-bearing): this layer MUST NOT paint a score field. It
// serves zero points and builds zero rasters — the map paints basemap +
// danger-polygon fills only, and outside every polygon stays NULL
// ("teadmata, mitte ohutu", OTA PR #131 precedent — absence of a
// registered polygon is not absence of risk). Every title says
// "hinnang"; the source names the licence + what is NOT in the join
// with EI OLE; scorer NULLs stay NULL (no snapshot, beyond polygons —
// unknown, never safe). No faked precision: no kernels, no smoothing,
// no distance decay (centre and edge of a polygon read alike — the
// scorer pins that the polygon LABEL scores, distance only gates the
// point fallback scorer-side).
//
// POLYGONS-ONLY plumbing (maaparcel #491 precedent): fallbackPoints is
// EMPTY (demo points would paint a fake gradient splat — the generic
// labels test carves polygon-only layers out, see layers.test.ts);
// SEVESO_DECAY and SEVESO_BONUS below are inert placeholders required
// by the Record<LayerId> tables (zero points and a null raster mean
// neither is ever evaluated — pinned by test); SEVESO_TAGS is a
// provenance note, NOT runnable Overpass QL (the only rebuild path is
// scripts/build/batch_seveso.py off the cached danger CSV). The points
// endpoint answers honestly-empty for this layer (polygons carry the
// data — see the SEVESO-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the sidecar via
// /api/layers/seveso/areas (parks /areas precedent).
//
// This file owns ALL seveso runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `SEVESO-HOOK (#613)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type SevesoLayerId = "seveso";

export const SEVESO_LAYER_IDS: SevesoLayerId[] = ["seveso"];

/** Danger classes (scorer parity: dims_p4_seveso.classify_danger keys). */
export type SevesoDanger = "toxic" | "heat" | "overpressure" | "combustion" | "unknown";

export const SEVESO_DANGERS: SevesoDanger[] = [
  "toxic",
  "heat",
  "overpressure",
  "combustion",
  "unknown",
];

/**
 * Inside-polygon scores by danger class (scorer parity with
 * services/scoring/dims_p4_seveso.py DANGER_SCORES — toxic 20,
 * heat/overpressure 35, combustion 50, unknown 30; worst polygon wins).
 * Map-side reference only: the map paints class fills, never numbers.
 */
export const SEVESO_DANGER_SCORE: Record<SevesoDanger, number> = {
  toxic: 20,
  heat: 35,
  overpressure: 35,
  combustion: 50,
  unknown: 30,
};

/** Päästeamet attribution carried on every sidecar row (CC BY-NC-ND). */
export const SEVESO_ATTRIBUTION =
  "Päästeameti ohtlike ettevõtete register (opendata.smit.ee, CC BY-NC-ND 4.0)";

export const SEVESO_DEFS: LayerDef[] = [
  {
    id: "seveso",
    paramIds: [],
    paramLabel: "P4-ohuala",
    title: "Seveso ohualad (tsooniliide, hinnang)",
    goodLabel:
      "tsoonis = registreeritud ohuala (oht klassi järgi: mürkpunane / kuumusoranž — hinnang, mitte mõõdetud risk)",
    badLabel:
      "väljaspool tsoone = teadmata, mitte ohutu (registreerimata oht pole välistatud; infovoldiku EI OLE asenda)",
    source:
      `${SEVESO_ATTRIBUTION}: ohtlikud_kaitised_ohualad.csv ` +
      `(235 ohuala üleriigiliselt, sh 95 Harjumaal; seis 2026-09-16, nädalane register). ` +
      `Toorandmeid EI OLE muudetud (polügoonid originaalkujul, ainult L-EST97→WGS84 koordinaatteisendus); ` +
      `tuletatud rastri EI OLE (ND-litsents keelab)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): seveso serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the polygons-only test.
 */
export const SEVESO_DECAY: Record<SevesoLayerId, number> = {
  seveso: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the Seveso
 * register lives behind weekly CSV pulls, and snapshot-only serving
 * never queries live either way. The only rebuild path is
 * scripts/build/batch_seveso.py off the cached danger CSV.
 */
export const SEVESO_TAGS: Record<SevesoLayerId, string> = {
  seveso: "Paasteamet-CSV ohtlikud_kaitised_ohualad (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented licence decision (CC BY-NC-ND forbids derivatives — see
 * header): the name resolves to an absent file so windows serve
 * honestly-empty, never a gradient. */
export const SEVESO_RASTER_FILE: Record<SevesoLayerId, string> = {
  seveso: "seveso-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const SEVESO_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const SEVESO_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the polygons-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const SEVESO_BONUS: Record<SevesoLayerId, BonusSpec> = {
  seveso: { kind: "area", half: 60 },
};

/**
 * Danger-class fill colors (internal to the choropleth painter in
 * outlines.ts — NOT marker colors, so the distinct-color registry does
 * not apply). Toxic reads worst red; heat/overpressure share the
 * scorer's 35-band orange family in two shades; combustion brown
 * (catalogue domain, unobserved); unknown neutral slate (hazard,
 * never neutral — but untyped, never worst).
 */
export const SEVESO_CLASS_FILL: Record<SevesoDanger, string> = {
  toxic: "#dc2626",
  heat: "#f97316",
  overpressure: "#fb923c",
  combustion: "#b45309",
  unknown: "#94a3b8",
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isSevesoLayerId(layer: string): layer is SevesoLayerId {
  return (SEVESO_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygon-only layers: no points, no raster, no gradient — the overlay
 * sidecar carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isSevesoPolygonOnlyLayer(layer: string): boolean {
  return isSevesoLayerId(layer);
}

/**
 * Seveso bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForSeveso(layer: string): BonusSpec | undefined {
  return (SEVESO_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * One Seveso danger polygon for the map sidecar. Rings are GeoJSON
 * [lon, lat] (the builder projects the register's L-EST97 WKT outer
 * rings once — holes ignored fail-safe towards over-coverage, scorer
 * parity); b is the [minlon, minlat, maxlon, maxlat] prefilter box
 * (ParkOutline precedent); danger is the scorer-parity class.
 */
export interface SevesoArea {
  zone_id: string;
  nimi: string;
  danger: SevesoDanger;
  danger_label: string;
  aadress: string;
  b: [number, number, number, number];
  r: number[][][];
}

export function isSevesoArea(v: unknown): v is SevesoArea {
  const p = v as Partial<SevesoArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.nimi === "string" &&
    typeof p?.danger === "string" &&
    (SEVESO_DANGERS as string[]).includes(p.danger) &&
    typeof p?.danger_label === "string" &&
    typeof p?.aadress === "string" &&
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
 * Seveso danger polygons for painting class fills on the seveso layer.
 * Null on any failure: polygons are a visual aid, never load-bearing —
 * the per-parcel join lives in the scorer
 * (services/scoring/dims_p4_seveso.py).
 */
export async function fetchSevesoAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<SevesoArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/seveso/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isSevesoArea).map((p) => {
      const o = p as SevesoArea;
      return {
        zone_id: o.zone_id,
        nimi: o.nimi,
        danger: o.danger,
        danger_label: o.danger_label,
        aadress: o.aadress,
        b: o.b,
        r: o.r,
      };
    });
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const SEVESO_HOOK =
  "SEVESO-HOOK (#613): seveso wired into layers/overlays/outlines/snapshot; Päästeamet ohuala danger-class choropleth, polygons only, outside stays unknown (never safe).";
