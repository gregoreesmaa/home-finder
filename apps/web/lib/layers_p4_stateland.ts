// State-land adjacency + auction polygon overlay (KATRI + maaoksjon
// registers, issue #615).
//
// One layer ("stateland"): state parcels (katri:state_property_ownership)
// + active auction parcels (maaoksjon:auction, status Avaldatud with a
// parseable-future offer_deadline) from the Keskkonnaagentuur/Maa-amet
// GeoServer WFS harvest (Harju window, verified 2026-09-17) as an
// honest per-parcel zone-MEMBERSHIP choropleth — inside a named state /
// auction parcel vs outside/unknown — never a gradient. Verdict:
// docs/p4_riigimaa.md (issue #544).
//
// Source: Maa- ja Ruumiamet (Land and Spatial Administration), licence
// CC BY 4.0 (attribution below). The per-listing scorer dims live in
// services/scoring/dims_p4_riigimaa.py (state_land_adjacency: forest
// neighbour -> 70, other state land -> 60, capped hinnang;
// auction_warning: borders an ACTIVE auction parcel -> flat flag 40,
// dated; outside NULLs); this module answers the map question only and
// shares the class vocabulary with it (byte parity on class names,
// see STATELAND_CLASS_SCORE).
//
// HONESTY (load-bearing): this layer MUST NOT paint a score field. It
// serves zero points and builds zero rasters — the map paints basemap +
// state/auction-parcel fills only, and outside every polygon stays NULL
// ("teadmata, mitte riigimaavaba", OTA PR #131 precedent — absence of
// a registered parcel is not absence of state interest). Assurance is
// capped hinnang (state CAN sell — the auction leg exists precisely
// because of that; the legend says so). Auction flags EXPIRE: only
// Avaldatud rows with a parseable-future deadline join the sidecar
// (expired/unknown-expiry auctions never flag — scorer parity); the
// deadline rides every auction row (never stale silently). The
// scorer's forest/other split stays scorer-side: ZERO harvested rows
// carry a forest signal (no RMK manager, no mets in vara_liik/nimetus),
// so the map paints ONE state class and the legend says the forest leg
// is unobserved in this harvest. Adjacency (<= 50 m) is scorer-side
// only (no buffered fills — fake precision refused). Every title says
// "hinnang"; the source names the licence + what is NOT in the join
// with EI OLE. No faked precision: no kernels, no smoothing, no
// distance decay.
//
// POLYGONS-ONLY plumbing (seveso #613 precedent): fallbackPoints is
// EMPTY (demo points would paint a fake gradient splat — the generic
// labels test carves polygon-only layers out, see layers.test.ts);
// STATELAND_DECAY and STATELAND_BONUS below are inert placeholders
// required by the Record<LayerId> tables (zero points and a null raster
// mean neither is ever evaluated — pinned by test); STATELAND_TAGS is a
// provenance note, NOT runnable Overpass QL (the only rebuild path is
// scripts/build/batch_stateland.py off the cached WFS GeoJSON). The
// points endpoint answers honestly-empty for this layer (polygons carry
// the data — see the STATELAND-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the sidecar via
// /api/layers/stateland/areas (parks /areas precedent).
//
// This file owns ALL stateland runtime data; shared files
// (lib/layers.ts, lib/overlays.ts, lib/outlines.ts,
// lib/server/snapshot.ts, app/api/layers/[layer]/route.ts,
// app/layers/page.tsx) touch it only through small marked
// `STATELAND-HOOK (#615)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type StatelandLayerId = "stateland";

export const STATELAND_LAYER_IDS: StatelandLayerId[] = ["stateland"];

/** Map classes (scorer parity: state adjacency vs auction warning). */
export type StatelandClass = "state" | "auction";

export const STATELAND_CLASSES: StatelandClass[] = ["state", "auction"];

/**
 * Inside-polygon scores by class (scorer parity with
 * services/scoring/dims_p4_riigimaa.py — other state land 60 (forest
 * 70 unobserved in this harvest, scorer-side), auction warning flag
 * 40). Map-side reference only: the map paints class fills with
 * auction dates, never numbers.
 */
export const STATELAND_CLASS_SCORE: Record<StatelandClass, number> = {
  state: 60,
  auction: 40,
};

/** Publisher attribution carried on every build (CC BY 4.0). */
export const STATELAND_ATTRIBUTION =
  "Maa- ja Ruumiamet (Land and Spatial Administration), licence CC BY 4.0";

export const STATELAND_DEFS: LayerDef[] = [
  {
    id: "stateland",
    paramIds: [],
    paramLabel: "P4-riigimaa",
    title: "Riigimaa ja oksjonid (tsooniliide, hinnang)",
    goodLabel:
      "tsoonis = riigimaa (roheline, piiratud kinnitus — riik VÕIB müüa) või aktiivne oksjon (kollane, kuupäevaga hoiatuslipp — hinnang, mitte väärtushinnang)",
    badLabel:
      "väljaspool tsoone = teadmata, mitte riigimaavaba (registreerimata huvi pole välistatud; RMK raieplaane EI OLE — piir pole raielank)",
    source:
      `${STATELAND_ATTRIBUTION}: katri:state_property_ownership + ` +
      `maaoksjon:auction (Harju aken, seis 2026-09-17; 11068 riigiparselli + 15 aktiivset oksjonit; aegunud/tühistatud oksjoneid EI LIPUSTATA; metsasignaali EI OLE ühelgi real — metsa-jalg skoorija poolel)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): stateland serves zero points and builds no raster, so no
 * field is ever computed from this — pinned by the polygons-only test.
 */
export const STATELAND_DECAY: Record<StatelandLayerId, number> = {
  stateland: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the KATRI +
 * auction registers live behind WFS GetFeature calls, and
 * snapshot-only serving never queries live either way. The only
 * rebuild path is scripts/build/batch_stateland.py off the cached WFS
 * GeoJSON.
 */
export const STATELAND_TAGS: Record<StatelandLayerId, string> = {
  stateland: "KATRI-WFS katri:state_property_ownership + maaoksjon:auction (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const STATELAND_RASTER_FILE: Record<StatelandLayerId, string> = {
  stateland: "stateland-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const STATELAND_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const STATELAND_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the polygons-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const STATELAND_BONUS: Record<StatelandLayerId, BonusSpec> = {
  stateland: { kind: "area", half: 60 },
};

/**
 * Map-class fill colors (internal to the choropleth painter in
 * outlines.ts — NOT marker colors, so the distinct-color registry does
 * not apply). State reads calm assurance-olive (capped hinnang, never
 * guarantee-green); auction reads caution yellow (dated warning flag,
 * never penalty-red).
 */
export const STATELAND_CLASS_FILL: Record<StatelandClass, string> = {
  state: "#4d7c0f",
  auction: "#eab308",
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isStatelandLayerId(layer: string): layer is StatelandLayerId {
  return (STATELAND_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygon-only layers: no points, no raster, no gradient — the overlay
 * sidecar carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isStatelandPolygonOnlyLayer(layer: string): boolean {
  return isStatelandLayerId(layer);
}

/**
 * Stateland bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForStateland(layer: string): BonusSpec | undefined {
  return (STATELAND_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * One state/auction parcel for the map sidecar. Rings are GeoJSON
 * [lon, lat] (the service cache serves EPSG:4326 GeoJSON directly — no
 * axis flip needed, pinned by test_batch_stateland.py); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box (ParkOutline
 * precedent); cls is the scorer-parity class. State rows carry tunnus
 * + valitseja; auction rows carry deadline + purpose + url (flags
 * expire — dates ride along, never stale silently).
 */
export interface StatelandArea {
  zone_id: string;
  nimi: string;
  cls: StatelandClass;
  tunnus: string;
  valitseja: string;
  deadline: string;
  purpose: string;
  url: string;
  b: [number, number, number, number];
  r: number[][][];
}

export function isStatelandArea(v: unknown): v is StatelandArea {
  const p = v as Partial<StatelandArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.nimi === "string" &&
    typeof p?.cls === "string" &&
    (STATELAND_CLASSES as string[]).includes(p.cls) &&
    typeof p?.tunnus === "string" &&
    typeof p?.valitseja === "string" &&
    typeof p?.deadline === "string" &&
    typeof p?.purpose === "string" &&
    typeof p?.url === "string" &&
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
 * State/auction parcels for painting class fills on the stateland
 * layer. Null on any failure: polygons are a visual aid, never
 * load-bearing — the per-parcel join lives in the scorer
 * (services/scoring/dims_p4_riigimaa.py).
 */
export async function fetchStatelandAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<StatelandArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/stateland/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isStatelandArea).map((p) => {
      const o = p as StatelandArea;
      return {
        zone_id: o.zone_id,
        nimi: o.nimi,
        cls: o.cls,
        tunnus: o.tunnus,
        valitseja: o.valitseja,
        deadline: o.deadline,
        purpose: o.purpose,
        url: o.url,
        b: o.b,
        r: o.r,
      };
    });
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const STATELAND_HOOK =
  "STATELAND-HOOK (#615): stateland wired into layers/overlays/outlines/snapshot; KATRI state + dated auction-flag class choropleth, polygons only, outside stays unknown (never state-free).";
