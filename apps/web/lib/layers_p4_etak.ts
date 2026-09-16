// ETAK measured-polygon overlay (Eesti topograafia andmebaas, issue
// #618).
//
// One layer ("etak"): Maa-amet ETAK WFS polygons
// (gsavalik.envir.ee/geoserver/etak/wfs, Harjumaa window, verified
// 2026-09-16) as an honest measured-presence choropleth — inside a
// named contour vs outside/unknown — never a gradient. Themes:
// wetland (e_306_margala_a), standing water (e_202_seisuveekogu_a),
// flowing water polygons (e_203_vooluveekogu_a), yards
// (e_302_ou_a). The relief (pinnamood) leg stays OUT (licence unstated
// — scorer parity, stated in the legend).
// The four Harjumaa themes total ~52k polygons (~114 MB raw); there is
// NO committed sidecar and NO page-load fetch: the layer is
// viewport-driven (see fetchEtakAreas + app/api/layers/etak/areas,
// grid-snapped server cache, over-wide viewports refused with a
// zoom-in note). Rings are served UNMODIFIED (verbatim WFS
// coordinates, EPSG:4326).
//
// Source: Maa- ja Ruumiamet (Land and Spatial Administration), ETAK
// maakate/hüdrograafia, licence CC BY 4.0 (attribution below). The
// per-parcel scorer legs live in
// services/scoring/dims_group18etak.py (wetland/water/yard bands,
// vintage stated per reason, ETAK-wins-over-OSM); this module answers
// the map question only and shares the band vocabulary with it (parity
// on class names + scores, see ETAK_CLASS_SCORE).
//
// HONESTY (load-bearing): this layer MUST NOT paint a score field. It
// serves zero points and builds zero rasters — the map paints basemap +
// class fills only, and outside every polygon stays NULL ("teadmata,
// mitte ...-vaba": unmapped ground is not dry land). Water distance
// bands (≤30/100 m) stay scorer-side (no buffered fills — fake
// precision refused). Vintage varies by tile (muutmisaeg rides each
// row; unknown vintages still paint but say so in the tooltip source).
// Where ETAK contradicts OSM, ETAK wins (documented in the legend).
// Every title says "hinnang"; the source names the licence + what is
// NOT in the join with EI OLE. No faked precision: no kernels, no
// smoothing, no distance decay.
//
// POLYGONS-ONLY plumbing (soil #617 precedent): fallbackPoints is
// EMPTY (demo points would paint a fake gradient splat — the generic
// labels test carves polygon-only layers out, see layers.test.ts);
// ETAK_DECAY and ETAK_BONUS below are inert placeholders required by
// the Record<LayerId> tables (zero points and a null raster mean
// neither is ever evaluated — pinned by test); ETAK_TAGS is a
// provenance note, NOT runnable Overpass QL (the only data path is the
// viewport WFS proxy). The points endpoint answers honestly-empty for
// this layer (polygons carry the data — see the ETAK-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the viewport via
// /api/layers/etak/areas?bbox=… (soil /areas precedent, bbox added).
//
// This file owns ALL etak runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/etak.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `ETAK-HOOK (#618)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type EtakLayerId = "etak";

export const ETAK_LAYER_IDS: EtakLayerId[] = ["etak"];

/** Measured themes served by the viewport proxy (relief gated OUT). */
export type EtakTheme = "wetland" | "standing" | "flowing" | "yard";

/** Map classes: the scorer legs (water type never moves the edge). */
export type EtakClass =
  | "wet_wettest"
  | "wet_mid"
  | "wet_other"
  | "water"
  | "yard_impervious"
  | "yard_green"
  | "yard_other";

export const ETAK_CLASSES: EtakClass[] = [
  "wet_wettest",
  "wet_mid",
  "wet_other",
  "water",
  "yard_impervious",
  "yard_green",
  "yard_other",
];

/**
 * Inside-polygon scores by class (scorer parity with
 * services/scoring/dims_group18etak.py — pinned by test). Map-side
 * reference only: the map paints class fills, never numbers.
 */
export const ETAK_CLASS_SCORE: Record<EtakClass, number> = {
  wet_wettest: 25,
  wet_mid: 35,
  wet_other: 30,
  water: 30,
  yard_impervious: 45,
  yard_green: 70,
  yard_other: 60,
};

/** Publisher attribution carried on every build (CC BY 4.0). */
export const ETAK_ATTRIBUTION =
  "Maa- ja Ruumiamet (Land and Spatial Administration), ETAK maakate/hüdrograafia, licence CC BY 4.0";

export const ETAK_DEFS: LayerDef[] = [
  {
    id: "etak",
    paramIds: [],
    paramLabel: "P4-etak",
    title: "ETAK märgala/vesi/õu (tsooniliide, hinnang)",
    goodLabel:
      "tsoonis = mõõdetud ETAK kontuur (märgala niiskus, vesi äravool, õu katvus — hinnang, mitte mõõdetud kuivus)",
    badLabel:
      "väljaspool kontuure = teadmata, mitte kuiv maa (reljeef EI OLE hinnangus — pinnamood litsentsita; ETAK võidab OSMi vastuolu korral)",
    source:
      `${ETAK_ATTRIBUTION}: märgala (e_306) + seisuvesi (e_202) + ` +
      `vooluvesi (e_203) + õued (e_302), vaatepõhine WFS; vee kaugusvööndid ` +
      `ainult skoori (kaardil EI MAALI); reljeef (pinnamood) EI MAALI (litsentsita)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): etak serves zero points and builds no raster, so no field is
 * ever computed from this — pinned by the polygons-only test.
 */
export const ETAK_DECAY: Record<EtakLayerId, number> = {
  etak: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: ETAK lives
 * behind WFS GetFeature calls, and viewport-only serving never queries
 * anything else. The only data path is app/api/layers/etak/areas.
 */
export const ETAK_TAGS: Record<EtakLayerId, string> = {
  etak: "ETAK-WFS etak:e_306/e_202/e_203/e_302 viewport proxy (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const ETAK_RASTER_FILE: Record<EtakLayerId, string> = {
  etak: "etak-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const ETAK_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const ETAK_NO_METRO = true;

/**
 * Bonus spec. INERT placeholder (never evaluated: zero points, null
 * raster — pinned by the polygons-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const ETAK_BONUS: Record<EtakLayerId, BonusSpec> = {
  etak: { kind: "area", half: 60 },
};

/**
 * Map-class fill colors (internal to the choropleth painter in
 * outlines.ts — NOT marker colors, so the distinct-color registry does
 * not apply). Wet blues, water blue, yard stone/green.
 */
export const ETAK_CLASS_FILL: Record<EtakClass, string> = {
  wet_wettest: "#0c4a6e",
  wet_mid: "#0284c7",
  wet_other: "#7dd3fc",
  water: "#2563eb",
  yard_impervious: "#78716c",
  yard_green: "#4ade80",
  yard_other: "#a8a29e",
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isEtakLayerId(layer: string): layer is EtakLayerId {
  return (ETAK_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygon-only layers: no points, no raster, no gradient — the viewport
 * proxy carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isEtakPolygonOnlyLayer(layer: string): boolean {
  return isEtakLayerId(layer);
}

/**
 * Etak bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForEtak(layer: string): BonusSpec | undefined {
  return (ETAK_BONUS as Record<string, BonusSpec>)[layer];
}

function norm(s: string | null | undefined): string {
  return (s ?? "").toLowerCase();
}

function has(hay: string, ...needles: string[]): boolean {
  return needles.some((n) => hay.includes(n));
}

/**
 * Decode the map class from a theme + its class text (tyyp_tekst).
 * Scorer parity (dims_group18etak.py): madalsoo/raba wettest 25,
 * soovik/õõtsik 35, other/unknown wetland 30; water distance-only
 * (type carried, edge unmoved); era/tootmis yards impervious 45,
 * haljasala 70, other yards 60. Unknown themes (relief) -> null:
 * unlicensed stays unpainted, never guessed.
 */
export function decodeEtakClass(
  theme: string,
  tyyp: string | null | undefined,
  _name: string | null | undefined,
): EtakClass | null {
  // The name is carried by the caller (server/etak.ts keeps it on the
  // area) but never moves the class edge — water type, like the name,
  // must not shift the boundary. Voided, not removed: the 3-arg call
  // shape is the decoder contract (pinned by test).
  void _name;
  const t = norm(tyyp);
  if (theme === "wetland") {
    if (has(t, "madalsoo", "raba")) return "wet_wettest";
    if (has(t, "soovik", "õõtsik", "ootsik")) return "wet_mid";
    return "wet_other";
  }
  if (theme === "standing" || theme === "flowing") return "water";
  if (theme === "yard") {
    if (has(t, "eraõu", "eraued", "eraou", "tootmisõu", "tootmisoued", "tootmisou")) {
      return "yard_impervious";
    }
    if (has(t, "haljasala")) return "yard_green";
    return "yard_other";
  }
  return null;
}

/** Vintage date (YYYY-MM-DD) from a muutmisaeg timestamp, else null. */
export function etakVintage(muutmisaeg: unknown): string | null {
  if (typeof muutmisaeg !== "string") return null;
  const m = muutmisaeg.match(/^(\d{4}-\d{2}-\d{2})/);
  return m ? m[1] : null;
}

/**
 * One ETAK contour for the map viewport. Rings are GeoJSON [lon, lat]
 * VERBATIM from the WFS (EPSG:4326, unmodified — holes ignored
 * fail-safe towards over-coverage, sibling precedent); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box (ParkOutline
 * precedent); cls/score the scorer-parity leg, label the class text,
 * name the water nimetus (else null), vintage the tile muutmisaeg date
 * (tiles vary — never mixed silently).
 */
export interface EtakArea {
  zone_id: string;
  theme: EtakTheme;
  cls: EtakClass;
  score: number;
  label: string;
  name: string | null;
  vintage: string | null;
  b: [number, number, number, number];
  r: number[][][];
}

const ETAK_THEMES: string[] = ["wetland", "standing", "flowing", "yard"];

export function isEtakArea(v: unknown): v is EtakArea {
  const p = v as Partial<EtakArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.theme === "string" &&
    ETAK_THEMES.includes(p.theme) &&
    typeof p?.cls === "string" &&
    (ETAK_CLASSES as string[]).includes(p.cls) &&
    typeof p?.score === "number" &&
    Number.isFinite(p.score) &&
    p.score >= 0 &&
    p.score <= 100 &&
    typeof p?.label === "string" &&
    (p?.name === null || typeof p?.name === "string") &&
    (p?.vintage === null || typeof p?.vintage === "string") &&
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

/** Viewport bbox for the etak areas endpoint (lon/lat degrees). */
export interface EtakBbox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

/**
 * ETAK contours for the current viewport (+ the server's honesty note:
 * zoom-in guidance for over-wide views, outage note when the WFS is
 * down — rendered, never hidden). Null on client-side transport
 * failure only: polygons are a visual aid, never load-bearing — the
 * per-parcel join lives in the scorer
 * (services/scoring/dims_group18etak.py).
 */
export async function fetchEtakAreas(
  bbox: EtakBbox,
  fetchImpl: typeof fetch = fetch,
): Promise<{ areas: EtakArea[]; note: string | null } | null> {
  try {
    const q = new URLSearchParams({
      bbox: [bbox.minlon, bbox.minlat, bbox.maxlon, bbox.maxlat].join(","),
    });
    const res = await fetchImpl(`/api/layers/etak/areas?${q.toString()}`);
    if (!res.ok) return null;
    const body = (await res.json()) as { areas?: unknown; note?: unknown };
    if (!body || typeof body !== "object" || !Array.isArray(body.areas)) {
      return null;
    }
    const areas = body.areas.filter(isEtakArea).map((p) => {
      const o = p as EtakArea;
      return {
        zone_id: o.zone_id,
        theme: o.theme,
        cls: o.cls,
        score: o.score,
        label: o.label,
        name: o.name,
        vintage: o.vintage,
        b: o.b,
        r: o.r,
      };
    });
    return { areas, note: typeof body.note === "string" ? body.note : null };
  } catch {
    return null;
  }
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const ETAK_HOOK =
  "ETAK-HOOK (#618): etak wired into layers/overlays/outlines/server; ETAK wetland/water/yard viewport class choropleth, polygons only, outside stays unknown (never dry land).";
