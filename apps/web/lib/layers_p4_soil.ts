// Soil/garden-ground polygon overlay (Maa-amet mullastiku kaart, issue
// #617).
//
// One layer ("soil"): INSPIRE SO.SoilBody polygons
// (inspire.geoportaal.ee/geoserver/SO_pinnas, Harjumaa window, verified
// 2026-09-16) as an honest per-parcel ground-MEMBERSHIP choropleth —
// inside a named soil contour vs outside/unknown — never a gradient.
// The full Harjumaa harvest is ~600 MB of 1:10 000 rings, so there is
// NO committed sidecar and NO page-load fetch: the layer is
// viewport-driven (see fetchSoilAreas + app/api/layers/soil/areas,
// grid-snapped server cache, over-wide viewports refused with a zoom-in
// note). Rings are served UNMODIFIED (verbatim WFS coordinates).
//
// Source: Maa- ja Ruumiamet (Land and Spatial Administration),
// INSPIRE mullastiku kaart (SO.SoilBody), licence CC BY 4.0
// (attribution below). Memoir: mullakaardi seletuskiri (Tallinn 2001),
// §V Tabel 1 (pdf lk 9) + legend lisa 3 (pdf lk 46). The per-parcel
// scorer dims live in services/scoring/dims_soil_map.py (8
// suitability bands, harvest-decoded family join, urban joins NULL);
// this module answers the map question only and shares the band
// vocabulary with it (byte parity on family names + scores, see
// SOIL_CLASS_SCORE).
//
// HONESTY (load-bearing): this layer MUST NOT paint a score field. It
// serves zero points and builds zero rasters — the map paints basemap +
// family fills only, and outside every polygon stays NULL ("teadmata,
// mitte ...-vaba": unmapped ground is not good ground). Urban polygons
// (centroid inside the Tallinn city bbox) are DROPPED server-side and
// render no-data (city soil is disturbed fill; 1:10 000 precision
// breaks at parcel edges — scorer parity, stated in the legend).
// #807 AMENDMENT (2026-09-20, contract change for the reviewer):
// membership band scores ARE now painted (zones kernel) — exact class
// fills as numbers, still no kernels/smoothing/decay (centre and edge
// read alike), outside stays NULL. Approve by merging, or reject by
// demanding fills-only back.
// Water/settlement/undetermined contours ("Veeala, asustus või
// määramata") and undecoded prefixes (v⁰-…) are dropped, counted, and
// reported — never guessed into a band. Gleyic qualifiers (label LkG /
// Go on a liiv contour) do NOT move the family: the qualifier rides
// along on the row for the tooltip, the band stays the §V texture
// (guessing qualifier adjustments would fake legend knowledge).
// Every title says "hinnang"; the source names the licence + what is
// NOT in the join with EI OLE. No faked precision: no kernels, no
// smoothing, no distance decay.
//
// POLYGONS-ONLY plumbing (seveso #613 precedent): fallbackPoints is
// EMPTY (demo points would paint a fake gradient splat — the generic
// labels test carves polygon-only layers out, see layers.test.ts);
// SOIL_DECAY and SOIL_BONUS below are inert placeholders required by
// the Record<LayerId> tables (zero points and a null raster mean
// neither is ever evaluated — pinned by test); SOIL_TAGS is a
// provenance note, NOT runnable Overpass QL (the only data path is the
// viewport WFS proxy). The points endpoint answers honestly-empty for
// this layer (polygons carry the data — see the SOIL-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the viewport via
// /api/layers/soil/areas?bbox=… (parks /areas precedent, bbox added).
//
// This file owns ALL soil runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/soil.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `SOIL-HOOK (#617)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type SoilLayerId = "soil";

export const SOIL_LAYER_IDS: SoilLayerId[] = ["soil"];

/** Memoir families incl. the rähkne modifier group (see decodeSoilFamily). */
export type SoilFamily =
  | "saviliiv"
  | "liiv"
  | "liivsavi"
  | "leede"
  | "paepealne"
  | "rähkne"
  | "savi"
  | "glei"
  | "turvas";

/** Map classes: the 8 scorer bands (rähkne folds into paepealne 50). */
export type SoilClass =
  | "saviliiv"
  | "liiv"
  | "liivsavi"
  | "leede"
  | "paepealne"
  | "savi"
  | "glei"
  | "turvas";

export const SOIL_CLASSES: SoilClass[] = [
  "saviliiv",
  "liiv",
  "liivsavi",
  "leede",
  "paepealne",
  "savi",
  "glei",
  "turvas",
];

/**
 * Inside-polygon scores by class (scorer parity with
 * services/scoring/dims_soil_map.py SOIL_BANDS — byte-for-byte, pinned
 * by test). Map-side reference only: the map paints class fills, never
 * numbers.
 */
export const SOIL_CLASS_SCORE: Record<SoilClass, number> = {
  saviliiv: 85,
  liiv: 70,
  liivsavi: 65,
  leede: 55,
  paepealne: 50,
  savi: 40,
  glei: 30,
  turvas: 25,
};

/** Publisher attribution carried on every build (CC BY 4.0). */
export const SOIL_ATTRIBUTION =
  "Maa- ja Ruumiamet (Land and Spatial Administration), INSPIRE mullastiku kaart (SO.SoilBody), licence CC BY 4.0";

export const SOIL_DEFS: LayerDef[] = [
  {
    id: "soil",
    paramIds: [],
    paramLabel: "P4-muld",
    title: "Mullastik (tsooniliide, hinnang)",
    goodLabel:
      "tsoonis = kaardistatud mullakontuur (saviliiv parim alus/aed, turvas vajab vaiu — hinnang, mitte mõõdetud kandevõime)",
    badLabel:
      "väljaspool kontuure = teadmata, mitte hea pinnas (linnades, veekogudel ja kaardistamata aladel EI OLE hinnangut)",
    source:
      `${SOIL_ATTRIBUTION}: mullakaardi seletuskiri §V Tabel 1 + lisa 3 ` +
      `(Harjumaa aken, vaatepõhine WFS; linna/vee/määramata kontuurid EI MAALI; gleikvalifikaatorid ei muuda perekonda)`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): soil serves zero points and builds no raster, so no field is
 * ever computed from this — pinned by the polygons-only test.
 */
export const SOIL_DECAY: Record<SoilLayerId, number> = {
  soil: 0.5,
};

/**
 * Source note for rebuilds. NOT runnable Overpass QL: the soil map lives
 * behind WFS GetFeature calls, and viewport-only serving never queries
 * anything else. The only data path is app/api/layers/soil/areas.
 */
export const SOIL_TAGS: Record<SoilLayerId, string> = {
  soil: "Maaamet-WFS SO_pinnas:SO.SoilBody viewport proxy (Overpass-uta)",
};

/** Raster master filename next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the name resolves to
 * an absent file so windows serve honestly-empty, never a gradient. */
export const SOIL_RASTER_FILE: Record<SoilLayerId, string> = {
  soil: "soil-walk-raster.json",
};

/** NO raster master (documented): polygons-only, windows serve county. */
export const SOIL_NO_RASTER = true;

/** NO metro master (documented): polygons-only, windows serve county. */
export const SOIL_NO_METRO = true;

/**
 * Bonus spec. Membership zones (issue #807): polygons carry the
 * verdict — inside reads the leaf band table (see zones807.ts), outside
 * stays unknown. Zero points, null raster (still polygons-only).
 */
export const SOIL_BONUS: Record<SoilLayerId, BonusSpec> = {
  soil: { kind: "zones" },
};

/**
 * Map-class fill colors (internal to the choropleth painter in
 * outlines.ts — NOT marker colors, so the distinct-color registry does
 * not apply). Earth tones by drainage: free-draining sands read light,
 * waterlogged glei reads blue, peat reads near-black brown.
 */
export const SOIL_CLASS_FILL: Record<SoilClass, string> = {
  saviliiv: "#84cc16",
  liiv: "#eab308",
  liivsavi: "#ca8a04",
  leede: "#a16207",
  paepealne: "#78716c",
  savi: "#b45309",
  glei: "#0ea5e9",
  turvas: "#422006",
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isSoilLayerId(layer: string): layer is SoilLayerId {
  return (SOIL_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygon-only layers: no points, no raster, no gradient — the viewport
 * proxy carries the data. The /layers page and the points endpoint
 * branch on this (never on an id literal, so the contract stays
 * greppable).
 */
export function isSoilPolygonOnlyLayer(layer: string): boolean {
  return isSoilLayerId(layer);
}

/**
 * Soil bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForSoil(layer: string): BonusSpec | undefined {
  return (SOIL_BONUS as Record<string, BonusSpec>)[layer];
}

/** Unicode subscript/superscript digits -> ASCII (šifrid use ls₂, v⁰…). */
const SUB_DIGITS: Record<string, string> = {
  "₀": "0",
  "₁": "1",
  "₂": "2",
  "₃": "3",
  "₄": "4",
  "₅": "5",
  "₆": "6",
  "₇": "7",
  "₈": "8",
  "₉": "9",
  "⁰": "0",
  "¹": "1",
  "²": "2",
  "³": "3",
  "⁴": "4",
  "⁵": "5",
  "⁶": "6",
  "⁷": "7",
  "⁸": "8",
  "⁹": "9",
};

function asciiDigits(s: string): string {
  return s.replace(/[₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹]/g, (c) => SUB_DIGITS[c] ?? c);
}

/**
 * Decode the memoir family from a soil contour code (šifr). Reads the
 * LEADING texture token of gml_name (the §V Tabel 1 classification:
 * l/sl/ls/s + rähkne-r / turvas-t modifiers + Kh/Kr/G/L diagnostics
 * per lisa 1 + lisa 3) — never the soilbodylabel qualifier column.
 * Case-sensitive where the memoir is (L leede vs l liiv). Returns null
 * for water/settlement/undetermined contours and undecoded prefixes:
 * unknown stays NULL, never guessed.
 */
export function decodeSoilFamily(
  name: string | null | undefined,
  label: string | null | undefined,
): SoilFamily | null {
  if (typeof name !== "string") return null;
  if (/veeala/i.test(name) || (typeof label === "string" && /veeala/i.test(label))) return null;
  const head = asciiDigits(name).trim().split(/[;/\s+]/)[0] ?? "";
  if (!head) return null;
  const lo = head.toLowerCase();
  if (lo.startsWith("sl")) return "saviliiv";
  if (lo.startsWith("ls")) return "liivsavi";
  if (lo.startsWith("pl") || lo.startsWith("tl")) return "liiv";
  if (lo.startsWith("kh")) return "paepealne";
  if (lo.startsWith("kr")) return "rähkne";
  const c = head[0];
  if (c === "r") return "rähkne";
  if (c === "l") return "liiv";
  if (c === "L") return "leede";
  if (c === "s" || c === "S") return "savi";
  if (c === "g" || c === "G") return "glei";
  if (c === "t" || c === "T") return "turvas";
  return null;
}

/**
 * Family -> map class. Rähkne folds into the paepealne 50 band (scorer
 * parity: one hinnang for thin/gravelly ground); the decoded family
 * rides along on the row so the tooltip stays exact.
 */
export function soilClassForFamily(family: SoilFamily): SoilClass {
  return family === "rähkne" ? "paepealne" : family;
}

/**
 * One soil contour for the map viewport. Rings are GeoJSON [lon, lat]
 * VERBATIM from the WFS (EPSG:4326, unmodified — holes ignored
 * fail-safe towards over-coverage, sibling precedent); b is the
 * [minlon, minlat, maxlon, maxlat] prefilter box (ParkOutline
 * precedent); family is the decoded memoir family (tooltip-exact),
 * cls/score the scorer-parity band, code the raw šifr (tooltip).
 */
export interface SoilArea {
  zone_id: string;
  family: string;
  cls: SoilClass;
  score: number;
  code: string;
  b: [number, number, number, number];
  r: number[][][];
}

export function isSoilArea(v: unknown): v is SoilArea {
  const p = v as Partial<SoilArea>;
  return (
    typeof p?.zone_id === "string" &&
    typeof p?.family === "string" &&
    p.family.length > 0 &&
    typeof p?.cls === "string" &&
    (SOIL_CLASSES as string[]).includes(p.cls) &&
    typeof p?.score === "number" &&
    Number.isFinite(p.score) &&
    p.score >= 0 &&
    p.score <= 100 &&
    typeof p?.code === "string" &&
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

/** Viewport bbox for the soil areas endpoint (lon/lat degrees). */
export interface SoilBbox {
  minlon: number;
  minlat: number;
  maxlon: number;
  maxlat: number;
}

/**
 * Soil contours for the current viewport (+ the server's honesty note:
 * zoom-in guidance for over-wide views, outage note when the WFS is
 * down — rendered, never hidden). Null on client-side transport
 * failure only: polygons are a visual aid, never load-bearing — the
 * per-parcel join lives in the scorer
 * (services/scoring/dims_soil_map.py).
 */
export async function fetchSoilAreas(
  bbox: SoilBbox,
  fetchImpl: typeof fetch = fetch,
): Promise<{ areas: SoilArea[]; note: string | null } | null> {
  try {
    const q = new URLSearchParams({
      bbox: [bbox.minlon, bbox.minlat, bbox.maxlon, bbox.maxlat].join(","),
    });
    const res = await fetchImpl(`/api/layers/soil/areas?${q.toString()}`);
    if (!res.ok) return null;
    const body = (await res.json()) as { areas?: unknown; note?: unknown };
    if (!body || typeof body !== "object" || !Array.isArray(body.areas)) {
      return null;
    }
    const areas = body.areas.filter(isSoilArea).map((p) => {
      const o = p as SoilArea;
      return {
        zone_id: o.zone_id,
        family: o.family,
        cls: o.cls,
        score: o.score,
        code: o.code,
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
export const SOIL_HOOK =
  "SOIL-HOOK (#617): soil wired into layers/overlays/outlines/server; Maa-amet mullastiku viewport class choropleth, polygons only, outside stays unknown (never good ground).";
