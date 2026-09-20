// Flood-risk polygon overlay (KAUR/EFAS per-parcel join, issue #487).
//
// One layer ("floodzone", p112): the KAUR/EELIS WFS object register
// eelis:kr_yleujutusohuga_ala ("KKR Üleujutusohuga ala") as an honest
// per-parcel zone-MEMBERSHIP choropleth — inside a named polygon vs
// outside/unknown — never a gradient. Verdict: docs/overturn_flood.md
// (issue #239 hunt, 2026-09-13): exactly one open flood polygon layer
// (16 water-body objects nationally, ZERO in the Tallinn market window,
// no return-period/band attribute — every row carries the single
// constant tyyp "Suurte üleujutusaladega siseveekogu"); EFAS/GloFAS stay
// a dated negative (registration-gated CEMS app, no anonymous bulk).
//
// HONESTY (load-bearing): there is no hazard model here, so this layer
// MUST NOT paint a score field. It serves zero points and builds zero
// raster — the map paints basemap + polygon fills only, and outside
// every polygon stays NULL ("teadmata, mitte kuiv", OTA PR #131
// precedent). The refused near-misses are pinned by the verdict doc:
// water proximity as flood risk (p50 drainage re-skin), shore distance
// as sea-rise projection (p117 stays NULL), forecast presence as a zone
// (5 km model grids behind a login are not per-parcel zones), and
// nearest-object distance to a Saaremaa lake as a Tallinn flood fact
// (only containment scores — centre and edge of a polygon read alike).
// #807 AMENDMENT (2026-09-20, contract change for the reviewer):
// the containment verdict IS now painted as a membership band score
// (zones kernel, FLOOD_ZONE_SCORE) — still no model, no smoothing,
// no decay; outside stays NULL. Approve by merging, or reject by
// demanding fills-only back.
//
// POLYGONS-ONLY plumbing (documented divergence from every other
// layer): fallbackPoints is EMPTY (demo points would paint a fake
// gradient splat — the generic labels test carves polygon-only layers
// out, see layers.test.ts); FLOOD_DECAY and FLOOD_BONUS below are inert
// placeholders required by the Record<LayerId> tables (zero points and
// a null raster mean neither is ever evaluated — pinned by test);
// FLOOD_TAGS is a provenance note, NOT runnable Overpass QL (the only
// rebuild path is scripts/build/batch_flood_kaur.py off the cached GML).
// The points endpoint answers honestly-empty for this layer (polygons
// carry the data — see the FLOOD-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the sidecar via
// /api/layers/floodzone/areas (parks /areas precedent).
//
// Overlap (documented, p13/p15 ships-twice precedent): p112's OSM-side
// no-map verdict stands (layers_group08a.ts G08A_VERDICTS — the 2026-09-12
// snapshot has no polygon signal: flood_prone=yes sits on 8 LineString
// segments); this layer answers a second buyer question off a second
// source (named KAUR zone membership). The per-listing scorer dim lives
// in services/scoring/dims_overturn_flood.py (dim_floodzone_p112:
// FLOOD_ZONE_SCORE inside a joined polygon, Estonian EI OLE NULLs
// outside) — this module answers the map question only, and shares no
// POI kind with dims_p4_kaur.py's P4-015 insurability leg
// (flood_zone_overturn vs kaur_zone_p4, kind-collision pinned in
// test_dims_overturn_flood.py).
//
// This file owns ALL floodzone runtime data; shared files
// (lib/layers.ts, lib/overlays.ts, lib/outlines.ts,
// lib/server/snapshot.ts) touch it only through small marked
// `FLOOD-HOOK (#487)` blocks, so sibling batches stay disjoint. This
// module imports ./layers ONLY as types: no runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type FloodLayerId = "floodzone";

export const FLOOD_LAYER_IDS: FloodLayerId[] = ["floodzone"];

/**
 * parameters3.md number per flood layer. p112 is SHARED with the Group 8
 * batch-A verdict (same parameter, OSM-snapshot no-map verdict vs KAUR
 * polygon-join overlay — the p13 roadsafety/B5-safety and p15
 * transit/gtfsstops ships-twice precedent).
 */
export const FLOOD_PARAMS: Record<FloodLayerId, number> = {
  floodzone: 112,
};

export const FLOOD_DEFS: LayerDef[] = [
  {
    id: "floodzone",
    paramIds: [112],
    title: "Üleujutusohuga alad (tsooniliide)",
    goodLabel:
      "tsoonis = KAUR üleujutusohuga ala (hinnang, mitte mõõdetud risk)",
    badLabel:
      "väljaspool tsoone = teadmata, mitte kuiv (registris pole T-bände ega Tallinna polügoone)",
    source:
      "KAUR/EELIS WFS eelis:kr_yleujutusohuga_ala (16 siseveekogu-objekti üleriigiliselt, Tallinna aknas 0; tagasituleku-perioodi pole — EFAS/GloFAS tellimuse taga, seisuga 2026-09-13, korduskontroll hiljemalt 2027-03-13)",
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): floodzone serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the polygons-only test.
 */
export const FLOOD_DECAY: Record<FloodLayerId, number> = {
  floodzone: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the KAUR flood
 * register lives behind a WFS GetFeature call, and snapshot-only serving
 * never queries live either way. The only rebuild path is
 * scripts/build/batch_flood_kaur.py off the cached GML snapshot.
 */
export const FLOOD_TAGS: Record<FloodLayerId, string> = {
  floodzone: "KAUR-WFS eelis:kr_yleujutusohuga_ala (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const FLOOD_RASTER_FILE: Record<FloodLayerId, string> = {
  floodzone: "floodzone-walk-raster.json",
};

/** NO metro master (documented): polygons-only, windows serve county. */
export const FLOOD_NO_METRO = true;

/**
 * Inside-zone score (issue #807): KAUR flood zones bite at the parcel
 * (tariff + illiquidity flag) — parity with the EELIS P4-015
 * FLOOD_SCORE 35 in services/scoring/dims_p4_eelis.py (same buyer
 * meaning; dims_flood_harju.py is verdict-only, no direct score leg).
 * Outside every zone stays unknown (no T-bands, no Tallinn polygons).
 */
export const FLOOD_ZONE_SCORE = 35;

/**
 * Bonus spec. Membership zones (issue #807): polygons carry the
 * verdict — inside reads FLOOD_ZONE_SCORE (see zones807.ts), outside
 * stays unknown. Zero points, null raster (still polygons-only).
 */
export const FLOOD_BONUS: Record<FloodLayerId, BonusSpec> = {
  floodzone: { kind: "zones" },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isFloodLayerId(layer: string): layer is FloodLayerId {
  return (FLOOD_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygons-only layers: no points, no raster, no gradient — the overlay
 * sidecar carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isPolygonOnlyLayer(layer: string): boolean {
  return isFloodLayerId(layer);
}

/**
 * Flood-zone bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForFlood(layer: string): BonusSpec | undefined {
  return (FLOOD_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * One KAUR flood-zone polygon for the map sidecar. Rings are GeoJSON
 * [lon, lat] (the GML snapshot stores WFS 2.0 lat/lon axis order — the
 * builder flips on write, pinned by test_batch_flood_kaur.py); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box (ParkOutline precedent).
 */
export interface FloodArea {
  zone_id: string;
  nimi: string;
  veekogu: string;
  tyyp: string;
  b: [number, number, number, number];
  r: number[][][];
}

function isFloodArea(v: unknown): v is FloodArea {
  const p = v as Partial<FloodArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.nimi === "string" &&
    typeof p?.veekogu === "string" &&
    typeof p?.tyyp === "string" &&
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
 * KAUR flood-zone polygons for painting fills on the floodzone layer.
 * Null on any failure: polygons are a visual aid, never load-bearing —
 * the per-parcel join lives in the scorer
 * (services/scoring/dims_overturn_flood.py).
 */
export async function fetchFloodAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<FloodArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/floodzone/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isFloodArea).map((p) => {
      const o = p as FloodArea;
      return { zone_id: o.zone_id, nimi: o.nimi, veekogu: o.veekogu, tyyp: o.tyyp, b: o.b, r: o.r };
    });
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const FLOOD_HOOK =
  "FLOOD-HOOK (#487): floodzone wired into layers/overlays/outlines/snapshot; p112 KAUR zone-membership choropleth, polygons only, outside stays unknown.";
