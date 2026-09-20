// Maa-amet kataster parcel overlay (p364 ships twice, issue #491).
//
// One layer ("maaparcel", p364): the kataster:ky_kehtiv parcel polygons
// as an honest omandivorm-CLASS choropleth — Eraomand vs
// Munitsipaalomand vs Riigiomand vs muu (Avalik-õiguslik omand + unknown
// folded, see CLASS_BY_OMVORM in scripts/build/batch_maaparcel_kataster.py)
// — never a suspicion score and never a gradient. Verdict:
// docs/overturn_maa.md (issue #235 hunt, 2026-09-13) + the #491 harvest
// addendum (100-parcel Kesklinn sample + 10-KKIS touch join, same day):
// the p364 scorer hint (dims_overturn_maa.py: Eraomand→70,
// Riigi/Munitsipaalomand→50 + hoonestus-check) answers the per-listing
// question; this module answers the map question off the same register
// (which lots are municipal/state land).
//
// HONESTY (load-bearing): the sidecar covers a harvested SAMPLE window
// only (Kesklinn 24.74–24.76 / 59.428–59.438, 100 parcels) — outside the
// window stays NULL ("teadmata, mitte tühi", OTA PR #131 precedent).
// Colors encode the register FACT (omvorm class); the lease-suspicion
// reading stays a capped scorer hint with the RIK-extract check named in
// the legend — painting suspicion itself would be the area heatmap of
// lease suspicion docs/overturn_maa.md already refuses. The KKIS
// touch-hit count (kkis, coarse puute-liide — see the builder) rides
// along per parcel for the status line, never as depth (reegel is None
// live, so rule text stays out). Maardlad are a harvest TALLY only
// (10 levialad in the market window, 0 in the parcel window) — deposit
// polygons as a buyer layer is a second question for a follow-up;
// p76/p229 scorer dims are untouched.
//
// POLYGONS-ONLY plumbing (documented divergence from every other
// layer, floodzone #487 precedent): fallbackPoints is EMPTY (demo points
// would paint a fake gradient splat — the generic labels test carves
// polygon-only layers out, see layers.test.ts); MAAPARCEL_DECAY and
// MAAPARCEL_BONUS below are inert placeholders required by the
// Record<LayerId> tables (zero points and a null raster mean neither is
// ever evaluated — pinned by test; #807 NO-SCORE DECISION (2026-09-20):
// parcel membership answers WHICH parcel (cadastre ID), not whether the
// place is good — scoring inside-a-parcel would rank listings by window
// coverage. Spec stays INERT); MAAPARCEL_TAGS is a provenance note,
// NOT runnable Overpass QL (the only rebuild path is
// scripts/build/batch_maaparcel_kataster.py off the cached GeoJSON).
// The points endpoint answers honestly-empty for this layer (polygons
// carry the data — see the MAAPARCEL-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the sidecar via
// /api/layers/maaparcel/areas (parks /areas precedent).
//
// Overlap (documented, p13/p15 ships-twice precedent): p364's scorer
// hint (dims_overturn_maa.py dim_ground_lease_p364) and P4-004's
// closing-block leg (dims_p4_maa_kataster.py, arest/keelumärge→notary)
// ask disjoint questions off the same source family — title-block vs
// use-form fabric. The final rebalance must weight only one per parcel.
//
// This file owns ALL maaparcel runtime data; shared files
// (lib/layers.ts, lib/overlays.ts, lib/outlines.ts,
// lib/server/snapshot.ts) touch it only through small marked
// `MAAPARCEL-HOOK (#491)` blocks, so sibling batches stay disjoint. This
// module imports ./layers ONLY as types: no runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type MaaParcelLayerId = "maaparcel";

export const MAAPARCEL_LAYER_IDS: MaaParcelLayerId[] = ["maaparcel"];

/**
 * Harvested sample window [minlon, minlat, maxlon, maxlat] (issue #789):
 * the Kesklinn 100-parcel window baked into the sidecar provenance by
 * scripts/build/batch_maaparcel_kataster.py (SAMPLE_BBOX). Exported so
 * the map can DRAW the boundary: outside this rect is teadmata, never
 * empty — and the rect on the map makes that unmistakable. Values must
 * stay in lockstep with the builder (pinned by test).
 */
export const MAAPARCEL_SAMPLE_BBOX: readonly [number, number, number, number] = [
  24.74, 59.428, 24.76, 59.438,
];

/** Harvest date of the sample window (sidecar provenance, pinned). */
export const MAAPARCEL_HARVEST_DATE = "2026-09-13";

/**
 * Map label for the drawn sample boundary (issue #789): names the
 * window + the outside-unknown rule so the rect reads as a coverage
 * limit, never as a parcel.
 */
export const MAAPARCEL_SAMPLE_LABEL =
  "Kesklinna proovivalimi piir (24.74–24.76 / 59.428–59.438): sees 100 katastritunnust, väljas = teadmata, mitte tühi";

/**
 * parameters3.md number for the parcel layer. p364 is SHARED with the
 * overturn scorer hint (same parameter, per-listing hint vs parcel-fabric
 * overlay — the p13 roadsafety/B5-safety and p15 transit/gtfsstops
 * ships-twice precedent).
 */
export const MAAPARCEL_PARAMS: Record<MaaParcelLayerId, number> = {
  maaparcel: 364,
};

export const MAAPARCEL_DEFS: LayerDef[] = [
  {
    id: "maaparcel",
    paramIds: [364],
    title: "Katastritunnused (omandivorm)",
    goodLabel:
      "eraomand = era (hinnang, mitte notariaalne tõend; RIK väljavõte jääb)",
    badLabel:
      "väljaspool proovivalimit = teadmata, mitte tühi (100 katastritunnust Kesklinna aknas)",
    source:
      "Maa-amet WFS kataster:ky_kehtiv proovivalim (Kesklinn 24.74–24.76/59.428–59.438, 100 katastritunnust, seisuga 2026-09-13, korduskontroll hiljemalt 2027-03-13; KKIS-puute arv jäme puute-liide 10 piirangu alalt; maardlaid aknas 0)",
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): maaparcel serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the polygons-only test.
 */
export const MAAPARCEL_DECAY: Record<MaaParcelLayerId, number> = {
  maaparcel: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the kataster
 * register lives behind a WFS GetFeature call, and snapshot-only serving
 * never queries live either way. The only rebuild path is
 * scripts/build/batch_maaparcel_kataster.py off the cached GeoJSON.
 */
export const MAAPARCEL_TAGS: Record<MaaParcelLayerId, string> = {
  maaparcel: "Maa-amet-WFS kataster:ky_kehtiv (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const MAAPARCEL_RASTER_FILE: Record<MaaParcelLayerId, string> = {
  maaparcel: "maaparcel-walk-raster.json",
};

/** NO metro master (documented): polygons-only, windows serve county. */
export const MAAPARCEL_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the polygons-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const MAAPARCEL_BONUS: Record<MaaParcelLayerId, BonusSpec> = {
  maaparcel: { kind: "area", half: 60 },
};

/** Paint classes (register facts, never scores — see header). */
export type MaaParcelClass = "era" | "muni" | "riik" | "muu";

/**
 * Class fill colors (internal to the choropleth painter in outlines.ts —
 * NOT marker colors, so the distinct-color registry does not apply).
 * Ordered dull ramp: era reads calmest; muni/riik warm (hoonestus-check
 * hint); muu neutral slate (unknown, never bad).
 */
export const MAAPARCEL_CLASS_FILL: Record<MaaParcelClass, string> = {
  era: "#22c55e",
  muni: "#fdba74",
  riik: "#fda4af",
  muu: "#94a3b8",
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isMaaParcelLayerId(layer: string): layer is MaaParcelLayerId {
  return (MAAPARCEL_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygon-only layers: no points, no raster, no gradient — the overlay
 * sidecar carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isPolygonOnlyMaaLayer(layer: string): boolean {
  return isMaaParcelLayerId(layer);
}

/**
 * Parcel bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForMaaParcel(layer: string): BonusSpec | undefined {
  return (MAAPARCEL_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * One Maa-amet kataster parcel for the map sidecar. Rings are GeoJSON
 * [lon, lat] (the WFS cache serves EPSG:4326 GeoJSON directly — no axis
 * flip needed, pinned by test_batch_maaparcel_kataster.py); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box (ParkOutline precedent).
 * kkis is the coarse KKIS touch-hit count (null = unknown, never zero).
 */
export interface MaaParcelArea {
  tunnus: string;
  cls: MaaParcelClass;
  omvorm: string;
  siht1: string;
  pindala: number | null;
  aadress: string;
  kkis: number | null;
  b: [number, number, number, number];
  r: number[][][];
}

const MAAPARCEL_CLASSES: ReadonlySet<string> = new Set(["era", "muni", "riik", "muu"]);

function isMaaParcelArea(v: unknown): v is MaaParcelArea {
  const p = v as Partial<MaaParcelArea>;
  return (
    typeof p?.tunnus === "string" &&
    typeof p?.cls === "string" &&
    MAAPARCEL_CLASSES.has(p.cls) &&
    typeof p?.omvorm === "string" &&
    typeof p?.siht1 === "string" &&
    (typeof p?.pindala === "number" || p?.pindala === null) &&
    typeof p?.aadress === "string" &&
    (typeof p?.kkis === "number" || p?.kkis === null) &&
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
 * Kataster parcel polygons for painting class fills on the maaparcel
 * layer. Null on any failure: polygons are a visual aid, never
 * load-bearing — the per-parcel join lives in the scorer
 * (services/scoring/dims_overturn_maa.py).
 */
export async function fetchMaaParcelAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<MaaParcelArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/maaparcel/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { parcels: unknown }).parcels)) {
      return null;
    }
    return (body as { parcels: unknown[] }).parcels.filter(isMaaParcelArea).map((p) => {
      const o = p as MaaParcelArea;
      return {
        tunnus: o.tunnus,
        cls: o.cls,
        omvorm: o.omvorm,
        siht1: o.siht1,
        pindala: o.pindala,
        aadress: o.aadress,
        kkis: o.kkis,
        b: o.b,
        r: o.r,
      };
    });
  } catch {
    return null;
  }
}

/** Coverage served with the parcel sidecar (issue #789). */
export interface MaaParcelCoverage {
  parcels: MaaParcelArea[];
  /** Sample window bbox, or null when the route served none. */
  bbox: [number, number, number, number] | null;
  harvest_date: string | null;
  count: number;
}

function isMaaParcelBbox(v: unknown): v is [number, number, number, number] {
  return (
    Array.isArray(v) &&
    v.length === 4 &&
    v.every((n) => typeof n === "number" && Number.isFinite(n))
  );
}

/**
 * Parcel polygons + sample-window coverage for the map sidecar route
 * (issue #789: the boundary rect is drawn from `bbox` so
 * outside-window unknown is unmistakable). Null on any failure: never
 * faked — callers fall back to MAAPARCEL_SAMPLE_BBOX.
 */
export async function fetchMaaParcelCoverage(
  fetchImpl: typeof fetch = fetch,
): Promise<MaaParcelCoverage | null> {
  try {
    const res = await fetchImpl("/api/layers/maaparcel/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object") return null;
    const raw = (body as { parcels?: unknown; bbox?: unknown; harvest_date?: unknown }).parcels;
    if (!Array.isArray(raw)) return null;
    const parcels = raw.filter(isMaaParcelArea).map((p) => {
      const o = p as MaaParcelArea;
      return {
        tunnus: o.tunnus,
        cls: o.cls,
        omvorm: o.omvorm,
        siht1: o.siht1,
        pindala: o.pindala,
        aadress: o.aadress,
        kkis: o.kkis,
        b: o.b,
        r: o.r,
      };
    });
    const b = (body as { bbox?: unknown }).bbox;
    const hd = (body as { harvest_date?: unknown }).harvest_date;
    return {
      parcels,
      bbox: isMaaParcelBbox(b) ? [b[0], b[1], b[2], b[3]] : null,
      harvest_date: typeof hd === "string" ? hd : null,
      count: parcels.length,
    };
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const MAAPARCEL_HOOK =
  "MAAPARCEL-HOOK (#491): maaparcel wired into layers/overlays/outlines/snapshot; p364 kataster omandivorm-class choropleth, polygons only, outside stays unknown.";
