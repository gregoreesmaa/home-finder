// Drainage-network wetness + outflow overlay (maaparandus GIS, issue #616).
//
// One layer ("maaparandus"): regulating-network areas (pta:msr_vork) +
// invalid systems (pta:kehtetu_maaparandussysteem) + outflow
// centerlines (pta:msr_eesvool) from the Kliimaministeerium WFS harvest
// (Harju window, verified 2026-09-17) as an honest per-parcel
// zone-MEMBERSHIP choropleth — inside a named network/invalid area vs
// outside/unknown — never a gradient. Verdict:
// docs/p4_maaparandus.md (issue #551).
//
// Source: Kliimaministeerium / Maa- ja Ruumiamet maaparanduse GIS,
// licence CC BY 4.0 (attribution below). The per-listing scorer dims
// live in services/scoring/dims_p4_maaparandus.py (inside_network ->
// capped wetness hinnang 55; inside_kehtetu -> risk flag 40;
// near_outflow <= 100 m -> dampness flag 45; duty -> always NULL;
// outside NULLs); this module answers the map question only and shares
// the class vocabulary with it (byte parity on class names + scores,
// see MAAPARANDUS_CLASS_SCORE).
//
// HONESTY (load-bearing): this layer MUST NOT paint a score field. It
// serves zero points and builds zero rasters — the map paints basemap +
// network/invalid fills + outflow centerlines only, and outside every
// shape stays NULL ("teadmata, mitte kuiv", OTA PR #131 precedent —
// absence of a registered network is not absence of wetness). Status
// is UNPROVEN on every network row (the register carries no
// condition attributes — maintained reads neutral-to-good, derelict
// reads risk, but the map asserts neither; the legend says the MSR
// check decides). Outflow lines paint as centerlines (width 2, no
// fill, no buffer — the <= 100 m band stays scorer-side, the legend
// says so). Duty (kraavihooldus) is refused everywhere (no duty
// attributes exist — scorer parity). Every title says "hinnang"; the
// source names the licence + what is NOT in the join with EI OLE.
// No faked precision: no kernels, no smoothing, no distance decay.
//
// POLYGONS-ONLY plumbing (seveso #613 precedent): fallbackPoints is
// EMPTY (demo points would paint a fake gradient splat — the generic
// labels test carves polygon-only layers out, see layers.test.ts);
// MAAPARANDUS_DECAY and MAAPARANDUS_BONUS below are inert placeholders
// required by the Record<LayerId> tables (zero points and a null raster
// mean neither is ever evaluated — pinned by test); MAAPARANDUS_TAGS is a
// provenance note, NOT runnable Overpass QL (the only rebuild path is
// scripts/build/batch_maaparandus.py off the cached WFS GeoJSON). The
// points endpoint answers honestly-empty for this layer (polygons carry
// the data — see the DRAINAGE-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the sidecar via
// /api/layers/maaparandus/areas (parks /areas precedent).
//
// This file owns ALL maaparandus runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `DRAINAGE-HOOK (#616)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type MaaparandusLayerId = "maaparandus";

export const MAAPARANDUS_LAYER_IDS: MaaparandusLayerId[] = ["maaparandus"];

/** Map classes (scorer parity: network / invalid / outflow). */
export type MaaparandusClass = "network" | "invalid" | "outflow";

export const MAAPARANDUS_CLASSES: MaaparandusClass[] = ["network", "invalid", "outflow"];

/**
 * Inside-shape scores by class (scorer parity with
 * services/scoring/dims_p4_maaparandus.py — network 55 capped hinnang,
 * invalid 40 risk flag, outflow-near 45 dampness flag). Map-side
 * reference only: the map paints class fills + centerlines, never
 * numbers.
 */
export const MAAPARANDUS_CLASS_SCORE: Record<MaaparandusClass, number> = {
  network: 55,
  invalid: 40,
  outflow: 45,
};

/** Publisher attribution carried on every build (CC BY 4.0). */
export const MAAPARANDUS_ATTRIBUTION =
  "Allikas: Kliimaministeerium / Maa- ja Ruumiamet, maaparanduse GIS (CC BY 4.0)";

export const MAAPARANDUS_DEFS: LayerDef[] = [
  {
    id: "maaparandus",
    paramIds: [],
    paramLabel: "P4-kuivendus",
    title: "Kuivendusvõrk ja eesvoolud (tsooniliide, hinnang)",
    goodLabel:
      "tsoonis = reguleeriv võrk (sinine, seisukord teadmata — kontrolli MSR-registrist) või eesvool (joon, lähedus ≤100 m hindab skoorija — hinnang, mitte mõõdetud niiskus)",
    badLabel:
      "kehtetu süsteem (pruun, mõõdetud lagunemisrisk) või väljaspool tsoone = teadmata, mitte kuiv (registreerimata võrk pole välistatud; hoolduskohustust EI OLE — registris puuduvad tööülesanded)",
    source:
      `${MAAPARANDUS_ATTRIBUTION}: pta:msr_vork + ` +
      `pta:kehtetu_maaparandussysteem + pta:msr_eesvool (Harju aken, seis 2026-09-17; 1916 võrguala + 785 kehtetut + 1595 eesvoolu; seisundi-atribuute EI OLE — hooldatud/lagunenud hinnangut EI ANTA; kraavihooldus-kohustust EI OLE)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): maaparandus serves zero points and builds no raster, so no field
 * is ever computed from this — pinned by the polygons-only test.
 */
export const MAAPARANDUS_DECAY: Record<MaaparandusLayerId, number> = {
  maaparandus: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the maaparandus
 * register lives behind WFS GetFeature calls, and snapshot-only serving
 * never queries live either way. The only rebuild path is
 * scripts/build/batch_maaparandus.py off the cached WFS GeoJSON.
 */
export const MAAPARANDUS_TAGS: Record<MaaparandusLayerId, string> = {
  maaparandus: "Kliimamin-WFS pta:msr_vork + pta:kehtetu_maaparandussysteem + pta:msr_eesvool (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const MAAPARANDUS_RASTER_FILE: Record<MaaparandusLayerId, string> = {
  maaparandus: "maaparandus-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const MAAPARANDUS_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const MAAPARANDUS_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the polygons-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const MAAPARANDUS_BONUS: Record<MaaparandusLayerId, BonusSpec> = {
  maaparandus: { kind: "area", half: 60 },
};

/**
 * Map-class paint colors (internal to the choropleth painter in
 * outlines.ts — NOT marker colors, so the distinct-color registry does
 * not apply). Network reads honest wetness-blue (condition unproven —
 * mid blue, never guarantee-teal); invalid reads derelict brown
 * (measured derelict proxy); outflow reads ditch-line blue (thin
 * centerlines, never a band).
 */
export const MAAPARANDUS_CLASS_FILL: Record<MaaparandusClass, string> = {
  network: "#2563eb",
  invalid: "#92400e",
  outflow: "#38bdf8",
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isMaaparandusLayerId(layer: string): layer is MaaparandusLayerId {
  return (MAAPARANDUS_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygon-only layers: no points, no raster, no gradient — the overlay
 * sidecar carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isMaaparandusPolygonOnlyLayer(layer: string): boolean {
  return isMaaparandusLayerId(layer);
}

/**
 * Drainage bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForMaaparandus(layer: string): BonusSpec | undefined {
  return (MAAPARANDUS_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * One maaparandus shape for the map sidecar. Polygon rows (network /
 * invalid) carry r (GeoJSON [lon, lat] exterior rings); outflow rows
 * carry l (centerline [lon, lat] strings). The builder projects nothing
 * (service cache is EPSG:4326 already — no axis flip, pinned by
 * test_batch_maaparandus.py); holes ignored fail-safe towards
 * over-coverage, scorer parity. b is the [minlon, minlat, maxlon,
 * maxlat] prefilter box (ParkOutline precedent); ms_kood + ms_url name
 * the MSR check (duty/status live there, never here).
 */
export interface MaaparandusArea {
  zone_id: string;
  nimi: string;
  cls: MaaparandusClass;
  ms_kood: string;
  ms_url: string;
  b: [number, number, number, number];
  r?: number[][][];
  l?: number[][][];
}

function isLonLat(pt: unknown): pt is [number, number] {
  return (
    Array.isArray(pt) &&
    pt.length === 2 &&
    pt.every((n) => typeof n === "number" && Number.isFinite(n))
  );
}

export function isMaaparandusArea(v: unknown): v is MaaparandusArea {
  const p = v as Partial<MaaparandusArea>;
  if (
    typeof p?.zone_id !== "string" ||
    typeof p?.nimi !== "string" ||
    typeof p?.cls !== "string" ||
    !(MAAPARANDUS_CLASSES as string[]).includes(p.cls) ||
    typeof p?.ms_kood !== "string" ||
    typeof p?.ms_url !== "string" ||
    !Array.isArray(p?.b) ||
    p.b.length !== 4 ||
    !p.b.every((n) => typeof n === "number" && Number.isFinite(n))
  ) {
    return false;
  }
  if (p.cls === "outflow") {
    return (
      Array.isArray(p.l) &&
      p.l.length > 0 &&
      p.l.every((ln) => Array.isArray(ln) && ln.length >= 2 && ln.every(isLonLat))
    );
  }
  return (
    Array.isArray(p?.r) &&
    p.r.length > 0 &&
    p.r.every((ring) => Array.isArray(ring) && ring.length >= 3 && ring.every(isLonLat))
  );
}

/**
 * Drainage shapes for painting class fills + outflow centerlines on
 * the maaparandus layer. Null on any failure: shapes are a visual aid,
 * never load-bearing — the per-parcel join lives in the scorer
 * (services/scoring/dims_p4_maaparandus.py).
 */
export async function fetchMaaparandusAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<MaaparandusArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/maaparandus/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isMaaparandusArea).map((p) => {
      const o = p as MaaparandusArea;
      const base = {
        zone_id: o.zone_id,
        nimi: o.nimi,
        cls: o.cls,
        ms_kood: o.ms_kood,
        ms_url: o.ms_url,
        b: o.b,
      };
      return o.cls === "outflow" ? { ...base, l: o.l } : { ...base, r: o.r };
    });
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const MAAPARANDUS_HOOK =
  "DRAINAGE-HOOK (#616): drainage wired into layers/overlays/outlines/snapshot; maaparandus network/invalid/outflow class choropleth, polygons only, outside stays unknown (never dry).";
