// Quarry extraction + exploration polygon overlay (Maa-amet register,
// issue #614).
//
// One layer ("quarry"): active extraction-permit polygons
// (ms:maeeraldis_aktiivne) + licensed exploration areas
// (ms:Aktiivne_uuringuala) from the Maa-amet MapServer WFS
// (teenus.maaamet.ee/ows/maardlad, Harjumaa L-EST97 window harvest,
// verified 2026-09-17) as an honest per-parcel zone-MEMBERSHIP
// choropleth — inside a named permit/watch polygon vs
// outside/unknown — never a gradient. Verdict: docs/p4_maavara_extract.md
// (issue #545).
//
// Source: Maa- ja Ruumiamet (Land and Spatial Administration), licence
// CC BY 4.0 (attribution below). The per-listing scorer dims live in
// services/scoring/dims_p4_maavara_extract.py (dim_extraction_proximity:
// inside -> 25, coarse near-band <= 2 km -> 45, outside NULL;
// dim_exploration_watch: inside -> dated watch-flag 55, outside NULL);
// this module answers the map question only and shares the class
// vocabulary with it (byte parity on class names + scores, see
// QUARRY_CLASS_SCORE).
//
// HONESTY (load-bearing): this layer MUST NOT paint a score field. It
// serves zero points and builds zero rasters — the map paints basemap +
// permit/watch-polygon fills only, and outside every polygon stays NULL
// ("teadmata, mitte kaevandusvaba", OTA PR #131 precedent — absence of
// a registered polygon is not absence of extraction). Only
// permit-ACTIVE extraction paints (ME_OLEK == "aktiivne" AND a
// parseable-future LOA_LOPP — expired/unknown permits never paint as
// active, scorer parity); exploration paints as a dated watch-flag
// (permit date carried, liveness stays scorer-side); the <= 2 km
// near-band is scorer-side only (a buffered fill would be fake
// precision — the legend says so). Every title says "hinnang"; the
// source names the licence + what is NOT in the join with EI OLE.
// No faked precision: no kernels, no smoothing, no distance decay.
//
// POLYGONS-ONLY plumbing (seveso #613 precedent): fallbackPoints is
// EMPTY (demo points would paint a fake gradient splat — the generic
// labels test carves polygon-only layers out, see layers.test.ts);
// QUARRY_DECAY and QUARRY_BONUS below are inert placeholders required
// by the Record<LayerId> tables (zero points and a null raster mean
// neither is ever evaluated — pinned by test); QUARRY_TAGS is a
// provenance note, NOT runnable Overpass QL (the only rebuild path is
// scripts/build/batch_quarry.py off the cached WFS GML). The points
// endpoint answers honestly-empty for this layer (polygons carry the
// data — see the QUARRY-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the sidecar via
// /api/layers/quarry/areas (parks /areas precedent).
//
// This file owns ALL quarry runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `QUARRY-HOOK (#614)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type QuarryLayerId = "quarry";

export const QUARRY_LAYER_IDS: QuarryLayerId[] = ["quarry"];

/** Map classes (scorer parity: active extraction vs exploration watch). */
export type QuarryClass = "active" | "exploration";

export const QUARRY_CLASSES: QuarryClass[] = ["active", "exploration"];

/**
 * Inside-polygon scores by class (scorer parity with
 * services/scoring/dims_p4_maavara_extract.py — active inside 25,
 * exploration watch-flag 55; the <= 2 km near-band 45 is scorer-side
 * only and has no map class). Map-side reference only: the map paints
 * class fills, never numbers.
 */
export const QUARRY_CLASS_SCORE: Record<QuarryClass, number> = {
  active: 25,
  exploration: 55,
};

/** Publisher attribution carried on every build (CC BY 4.0). */
export const QUARRY_ATTRIBUTION =
  "Maa- ja Ruumiamet (Land and Spatial Administration), licence CC BY 4.0";

export const QUARRY_DEFS: LayerDef[] = [
  {
    id: "quarry",
    paramIds: [],
    paramLabel: "P4-maavara",
    title: "Karjäärid ja uuringualad (tsooniliide, hinnang)",
    goodLabel:
      "tsoonis = registreeritud kaevandusluba (punane, vältimiskiht) või uuringuala (kollane, kuupäevaga valve-lipp — hinnang, mitte mõõdetud mõju)",
    badLabel:
      "väljaspool tsoone = teadmata, mitte kaevandusvaba (registreerimata kaevandamine pole välistatud; lõhketööde ajakava EI OLE)",
    source:
      `${QUARRY_ATTRIBUTION}: ms:maeeraldis_aktiivne + ` +
      `ms:Aktiivne_uuringuala (Harjumaa L-EST97 aken, seis 2026-09-17; 154 kehtiva loaga kaevanduslubade + 28 uuringuala polügooni; aegunud/tundmatu loaga load EI MAALI aktiivsena; taotletavaid lubasid EI OLE — taotlus pole luba)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): quarry serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the polygons-only test.
 */
export const QUARRY_DECAY: Record<QuarryLayerId, number> = {
  quarry: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the maardlad
 * register lives behind WFS GetFeature calls, and snapshot-only serving
 * never queries live either way. The only rebuild path is
 * scripts/build/batch_quarry.py off the cached GML harvest.
 */
export const QUARRY_TAGS: Record<QuarryLayerId, string> = {
  quarry: "Maaamet-WFS ms:maeeraldis_aktiivne + ms:Aktiivne_uuringuala (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const QUARRY_RASTER_FILE: Record<QuarryLayerId, string> = {
  quarry: "quarry-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const QUARRY_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const QUARRY_NO_METRO = true;

/**
 * Bonus spec. Membership zones (issue #807): polygons carry the
 * verdict — inside reads the leaf band table (see zones807.ts), outside
 * stays unknown. Zero points, null raster (still polygons-only).
 */
export const QUARRY_BONUS: Record<QuarryLayerId, BonusSpec> = {
  quarry: { kind: "zones" },
};

/**
 * Map-class fill colors (internal to the choropleth painter in
 * outlines.ts — NOT marker colors, so the distinct-color registry does
 * not apply). Active reads burnt avoidance-red; exploration reads
 * caution yellow (dated watch-flag, never a full penalty).
 */
export const QUARRY_CLASS_FILL: Record<QuarryClass, string> = {
  active: "#c2410c",
  exploration: "#eab308",
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isQuarryLayerId(layer: string): layer is QuarryLayerId {
  return (QUARRY_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygon-only layers: no points, no raster, no gradient — the overlay
 * sidecar carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isQuarryPolygonOnlyLayer(layer: string): boolean {
  return isQuarryLayerId(layer);
}

/**
 * Quarry bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForQuarry(layer: string): BonusSpec | undefined {
  return (QUARRY_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * One quarry permit/watch polygon for the map sidecar. Rings are
 * GeoJSON [lon, lat] (the builder projects the register's L-EST97
 * outer rings once — holes ignored fail-safe towards over-coverage,
 * scorer parity); b is the [minlon, minlat, maxlon, maxlat] prefilter
 * box (ParkOutline precedent); cls is the scorer-parity class; loa /
 * loa_lopp carry the dated permit (exploration watch-flag date).
 */
export interface QuarryArea {
  zone_id: string;
  nimi: string;
  cls: QuarryClass;
  loa: string;
  loa_lopp: string;
  operaator: string;
  b: [number, number, number, number];
  r: number[][][];
}

export function isQuarryArea(v: unknown): v is QuarryArea {
  const p = v as Partial<QuarryArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.nimi === "string" &&
    typeof p?.cls === "string" &&
    (QUARRY_CLASSES as string[]).includes(p.cls) &&
    typeof p?.loa === "string" &&
    typeof p?.loa_lopp === "string" &&
    typeof p?.operaator === "string" &&
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
 * Quarry permit/watch polygons for painting class fills on the quarry
 * layer. Null on any failure: polygons are a visual aid, never
 * load-bearing — the per-parcel join lives in the scorer
 * (services/scoring/dims_p4_maavara_extract.py).
 */
export async function fetchQuarryAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<QuarryArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/quarry/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isQuarryArea).map((p) => {
      const o = p as QuarryArea;
      return {
        zone_id: o.zone_id,
        nimi: o.nimi,
        cls: o.cls,
        loa: o.loa,
        loa_lopp: o.loa_lopp,
        operaator: o.operaator,
        b: o.b,
        r: o.r,
      };
    });
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const QUARRY_HOOK =
  "QUARRY-HOOK (#614): quarry wired into layers/overlays/outlines/snapshot; Maa-amet extraction+exploration class choropleth, polygons only, outside stays unknown (never quarry-free).";
