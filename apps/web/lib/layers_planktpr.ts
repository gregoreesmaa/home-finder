// PLANK/TPR designated-use polygon overlay (issue #492): planktpr.
//
// ONE polygon layer (p47 designated use), Tallinn scope, harvested WFS
// snapshot ONLY. Polygons are drawn as vector fills colored by the
// per-parcel designated-use band (the map twin of dim_zoning_use in
// services/scoring/dims_overturn_planktpr.py — same bands, same decree
// stage, same cap, pinned by the parity test below). Everything outside
// a harvested kehtestatud polygon stays unknown (the heatmap field has
// no raster and no points — a missing join is unknown, never good).
//
// This file owns ALL planktpr runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/snapshot.ts,
// app/api/layers/planktpr/areas/route.ts, app/layers/page.tsx,
// components/ValueHeatMap.tsx) touch it only through small marked
// `PLANKTPR-HOOK (#492)` blocks, so sibling batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef):
// no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing — Group B verify-first, docs/overturn_planktpr.md
// p47/p74 joins + p274 ceiling partial):
// * PLANK WFS is GONE (re-verified 2026-09-13: GetCapabilities follows to
//   the E-ehitus SPA shell, zero WFS markers) and TPR serves no bulk
//   (Angular SPA, no wfs/bulk/api/download link in the shell) — so the
//   live harvest holds NO polygons and the layer renders honestly empty
//   (dated NULL with the re-verification date in the legend + source).
// * POLYGONS ONLY: no point splat, no kernel, no OSM landuse=* proxy —
//   OSM landuse is descriptive (what is BUILT), never the prescriptive
//   decree, so painting it as zoning would be fake precision (G05A
//   p47 no-map precedent, layers_group05a.ts). fallbackPoints is EMPTY
//   by decision: there are no honest demo polygons to fall back to.
// * Per-parcel join ONLY: a cell/address scores only inside a
//   kehtestatud polygon with a recognised use code (exact join — no
//   distance weighting, no interpolation across parcel boundaries).
//   Non-decree stages (menetluses/algatatud), unknown codes and missing
//   joins stay NULL/unknown.
// * p74 restriction decrees and the p274 ceiling proxy are SCORER-ONLY
//   (dims_overturn_planktpr.py): decree texts are not a parcel feed and
//   a ceiling number is not a polygon — neither gains a fill here (see
//   PLANKTPR_VERDICTS).
//
// Harvest (scripts/build/batch_planktpr_wfs.py, fixtures only): polite
// WFS GetCapabilities -> GetFeature pull (max 1 / 14 d, single GET,
// HTTP 429 is a stop signal) into the `plank/areas.json` sidecar served
// by lib/server/snapshot.ts. Network lives ONLY in the harvest script;
// the layer and its tests never touch it.

import type { BonusSpec, LayerDef } from "./layers";

export type PlanktprLayerId = "planktpr";

export const PLANKTPR_LAYER_IDS: PlanktprLayerId[] = ["planktpr"];

/** parameters3.md number for the planktpr layer (p47 designated use). */
export const PLANKTPR_PARAMS: Record<PlanktprLayerId, number> = {
  planktpr: 47,
};

/** Designated-use fit classes (map twin of the scorer's classify_use). */
export type PlanktprUseClass = "residential" | "mixed" | "commercial" | "restricted";

/**
 * Per-parcel fit bands — byte parity with USE_BANDS in
 * services/scoring/dims_overturn_planktpr.py (cap 80: plan conditions
 * beyond the use label are unknown from this table alone; first-cut,
 * MUST be recalibrated from a real snapshot on reopen).
 */
export const PLANKTPR_USE_BANDS: Record<PlanktprUseClass, number> = {
  residential: 80,
  mixed: 60,
  commercial: 35,
  restricted: 20,
};

/** Cap: a use label alone never earns 100 (scorer parity). */
export const PLANKTPR_CAP = 80;

/** Decree stage that scores — parity with DECREE_STAGE (scorer). */
export const PLANKTPR_DECREE_STAGE = "kehtestatud";

/** Tallinn kov spellings — parity with TALLINN_KOVS (scorer). */
export const PLANKTPR_TALLINN_KOVS: ReadonlySet<string> = new Set([
  "tallinn",
  "tallinna linn",
]);

/**
 * Use-code stems — parity with _RESIDENTIAL/_MIXED/_COMMERCIAL/
 * _RESTRICTED_STEMS (scorer). UNVERIFIED against any live codelist
 * (none is openly served) — MUST be checked on reopen.
 */
export const PLANKTPR_RESIDENTIAL_STEMS = ["elamu", "eluhoon", "elamupiirkond"] as const;
export const PLANKTPR_MIXED_STEMS = ["sega", "segafunktsioon"] as const;
export const PLANKTPR_COMMERCIAL_STEMS = ["ari", "buroo", "kaubandus", "teenindus"] as const;
export const PLANKTPR_RESTRICTED_STEMS = [
  "toostus",
  "tootmis",
  "maatulundus",
  "pollu",
  "transpordi",
  "eriotstarb",
  "kaitsev",
  "jaatme",
  "ladu",
  "logistika",
] as const;

/** Estonian diacritics folded to ASCII (scorer _fold parity). */
export function planktprFold(raw: unknown): string | null {
  if (typeof raw !== "string") return null;
  const folded = raw
    .toLowerCase()
    .replace(/ä/g, "a")
    .replace(/ö/g, "o")
    .replace(/ü/g, "u")
    .replace(/õ/g, "o")
    .replace(/ž/g, "z")
    .replace(/š/g, "s")
    .trim();
  return folded.length > 0 ? folded : null;
}

/**
 * Designated-use code -> fit class (scorer classify_use parity:
 * restricted wins over everything, mixed (housing+commerce) wins over
 * pure commercial, unknown codes return null — never assumed).
 */
export function planktprClassifyUse(use: unknown): PlanktprUseClass | null {
  const code = planktprFold(use);
  if (!code) return null;
  if (PLANKTPR_RESTRICTED_STEMS.some((s) => code.includes(s))) return "restricted";
  const hasHousing = PLANKTPR_RESIDENTIAL_STEMS.some((s) => code.includes(s));
  const hasCommerce = PLANKTPR_COMMERCIAL_STEMS.some((s) => code.includes(s));
  if (hasHousing && hasCommerce) return "mixed";
  if (PLANKTPR_MIXED_STEMS.some((s) => code.includes(s))) return "mixed";
  if (hasCommerce) return "commercial";
  if (hasHousing) return "residential";
  return null;
}

/** Band for a use code — null when the code is unrecognised (unknown). */
export function planktprBandForUse(use: unknown): number | null {
  const cls = planktprClassifyUse(use);
  return cls === null ? null : PLANKTPR_USE_BANDS[cls];
}

/**
 * Polygon fill colors by fit class (green = fits a residential buyer,
 * red = hostile — same direction as the bands, so fills and scores
 * agree by construction).
 */
export const PLANKTPR_USE_COLORS: Record<PlanktprUseClass, string> = {
  residential: "#16a34a", // green-600: elamumaa (80)
  mixed: "#a3a32b", // olive: segafunktsioon (60)
  commercial: "#ea580c", // orange-600: ärimaa (35)
  restricted: "#dc2626", // red-600: tootmis/piirang (20)
};

/** Fill color for a use code; null when the code is unrecognised. */
export function planktprColorForUse(use: unknown): string | null {
  const cls = planktprClassifyUse(use);
  return cls === null ? null : PLANKTPR_USE_COLORS[cls];
}

const SNAP = "kohalik hetktõmmis 2026-09-12";
const WFS_NEGATIVE =
  "PLANK-WFS-liides puudub (2026-09-13: GetCapabilities viib E-ehituse " +
  "platvormile, WFS-XML-i pole) ja TPR-il avaandmete liidest pole " +
  "(veebivaade) — elusaid polügoone hetkel EI OLE";

export const PLANKTPR_DEFS: LayerDef[] = [
  {
    id: "planktpr",
    paramIds: [47],
    title: "Sihtotstarve polügoonid (PLANK/TPR, hinnang)",
    goodLabel: "roheline polügoon = elamu-sihtotstarve (kehtestatud, hinnang)",
    badLabel: "punane polügoon = tootmis/piirangu-tsoon või andmed puuduvad (hinnang — EI OLE)",
    source:
      `${SNAP} + PLANK/TPR korje (kehtestatud sihtotstarbe-polügoonid, ` +
      `krundi-täpne liide: elamu 80 / sega 60 / äri 35 / piirang 20, lagi 80). ` +
      `${WFS_NEGATIVE}; väljaspool korjatud polügoone hinnangut EI OLE`,
    // EMPTY by decision (see header): no honest demo polygons exist —
    // the client renders the empty field, never faked fills.
    fallbackPoints: [],
  },
];

/**
 * WFS source note (documents the harvest vocabulary; the app serves the
 * frozen sidecar, never live WFS — overpassQueryFor("planktpr") is never
 * called in production, senscom precedent).
 */
export const PLANKTPR_TAGS: Record<PlanktprLayerId, string> = {
  planktpr:
    "PLANK WFS GetCapabilities (planeeringud.ee/geoserver/wfs, OGC WFS " +
    "2.0.0 — 2026-09-13 seisuga MAAS, E-ehituse SPA; korje ootel) + TPR " +
    "veebivaade (tpr.tallinn.ee, avaandmete liidest pole); serveeritakse " +
    "korje-vahemälu plank/areas.json külgfailist, mitte elusalt",
};

/**
 * Fallback kernel width in km (== wire sigma). The fills themselves are
 * exact joins with no kernel; this only sizes the Euclidean fallback
 * when points ever appear (mobile/"cover" precedent).
 */
export const PLANKTPR_DECAY: Record<PlanktprLayerId, number> = {
  planktpr: 0.5,
};

/**
 * Self-scaling cover spec (mobile precedent): measured footprints carry
 * their own value (the polygon bands ARE the calibration, no half);
 * sigma is the Euclidean fallback kernel width. Contract-checked
 * against the wire (half null, sigma 0.5) by loadLayerRaster. The live
 * path serves no points, so the splat degrades to honestly unknown —
 * the polygon fills ARE the field.
 */
export const PLANKTPR_BONUS: Record<PlanktprLayerId, BonusSpec> = {
  planktpr: { kind: "cover", sigma: 0.5 },
};

/** Raster master filename (intentionally never built — see below). */
export const PLANKTPR_RASTER_FILE: Record<PlanktprLayerId, string> = {
  planktpr: "planktpr-walk-raster.json",
};

/**
 * NO raster master (documented): the polygon fills ARE the field (parks-
 * outline precedent — outlines draw over the base field, no master).
 * A county stamp of an empty harvest would be county-wide unknown with
 * build machinery and no meaning. The window route serves 500 for this
 * layer and the client falls back to the empty field (designed path,
 * GTFS overlay-only precedent). NO metro master either (county-only
 * windows, G05C/G17A precedent).
 */
export const PLANKTPR_NO_RASTER = true;
export const PLANKTPR_NO_METRO = true;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isPlanktprLayerId(layer: string): layer is PlanktprLayerId {
  return (PLANKTPR_LAYER_IDS as string[]).includes(layer);
}

/**
 * Honest-empty status line (issue #785). Planktpr ships ZERO points
 * BY DECISION (PLANK WFS gone, TPR bulk absent — header verdict) and
 * always renders through the demo fallback — so the generic "live
 * ebaõnnestus" (live failed) label reads as breakage. This names the
 * dated verdict instead: EI OLE + source + buyer-side check, never a
 * count claim beyond the served points, never a failure. Pure
 * (pinned by test, silly #774 precedent).
 */
export function planktprDemoStatus(pointCount: number): string {
  return (
    "EI OLE elusaid polügoone (PLANK-WFS/TPR, 2026-09-13: WFS-liides " +
    `puudub, korje ootel) · ${pointCount} punkti — kehtestatud ` +
    "sihtotstarve selgub TPR veebivaatest"
  );
}

/**
 * Planktpr bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForPlanktpr(layer: string): BonusSpec | undefined {
  return (PLANKTPR_BONUS as Record<string, BonusSpec>)[layer];
}

/** One harvested designated-use polygon (plank/areas.json sidecar row). */
export interface PlanktprArea {
  plan_id: string;
  /** Raw designated-use code (band + color derive from it, never stored). */
  use: string;
  /** Plan stage; only kehtestatud rows score/draw. */
  stage: string;
  kov: string;
  /** Polygon outer rings as [lon, lat] pairs (GeoJSON order). */
  rings: number[][][];
}

/** Validator: malformed rows are skipped, never faked. */
export function isPlanktprArea(v: unknown): v is PlanktprArea {
  const p = v as Partial<PlanktprArea>;
  return (
    typeof p?.plan_id === "string" &&
    typeof p?.use === "string" &&
    typeof p?.stage === "string" &&
    typeof p?.kov === "string" &&
    Array.isArray(p?.rings) &&
    p.rings.length > 0 &&
    p.rings.every(
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
 * Designated-use polygons for drawing fills on the planktpr layer.
 * Null on any failure: polygons are a visual aid, never load-bearing —
 * a missing sidecar is honestly empty (the dated NULL), never an error.
 */
export async function fetchPlanktprAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<PlanktprArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/planktpr/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isPlanktprArea).map((p) => {
      const o = p as PlanktprArea;
      return { plan_id: o.plan_id, use: o.use, stage: o.stage, kov: o.kov, rings: o.rings };
    });
  } catch {
    return null;
  }
}

/** True when the row's kov is a recognised Tallinn spelling. */
export function planktprIsTallinn(kov: unknown): boolean {
  if (typeof kov !== "string") return false;
  return (PLANKTPR_TALLINN_KOVS as ReadonlySet<string>).has(kov.trim().toLowerCase());
}

/** Ray-cast point-in-ring ([lon, lat] GeoJSON order, pure). */
export function planktprPointInRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) {
      inside = !inside;
    }
  }
  return inside;
}

/**
 * Exact per-parcel join at one address: the band of the first
 * kehtestatud Tallinn polygon containing the point, null outside every
 * polygon / for non-decree stages / unknown codes. No distance
 * weighting, no interpolation — a missing join is unknown, never good.
 */
export function planktprScoreAt(
  lat: number,
  lon: number,
  areas: PlanktprArea[],
): number | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  for (const a of areas) {
    if (!a || !planktprIsTallinn(a.kov)) continue;
    if (planktprFold(a.stage) !== PLANKTPR_DECREE_STAGE) continue;
    const band = planktprBandForUse(a.use);
    if (band === null) continue;
    if (a.rings.some((ring) => planktprPointInRing(lon, lat, ring))) return band;
  }
  return null;
}

export type PlanktprVerdictKind = "polygons" | "scorer-only";

export interface PlanktprVerdict {
  param: number;
  name: string;
  kind: PlanktprVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for the PLANK/TPR layer (the scorer-only rows are
 * the docs evidence; scorer dims live in
 * services/scoring/dims_overturn_planktpr.py).
 */
export const PLANKTPR_VERDICTS: PlanktprVerdict[] = [
  {
    param: 47,
    name: "Zoning laws (designated use)",
    kind: "polygons",
    reason:
      "Shipped as planktpr: kehtestatud designated-use polygons as exact per-parcel fills (residential 80 / mixed 60 / commercial 35 / restricted 20, cap 80) — the polygons are the mapped decree, honestly labelled, never an OSM-landuse proxy. Live harvest holds no polygons (WFS gone, dated 2026-09-13), so the layer renders honestly empty until bulk reopens.",
  },
  {
    param: 74,
    name: "Rental restrictions (decree)",
    kind: "scorer-only",
    reason:
      "Per-parcel decree fact (KOV üüripiirangud, Riigi Teataja): decree texts are not a parcel feed and restriction zones are not designated-use polygons, so no fill here — scorer dim rentrestr_decree_overturn only (present 30 with ref / absent 80 measured-clear dated).",
  },
  {
    param: 274,
    name: "Air rights (ceiling partial)",
    kind: "scorer-only",
    reason:
      "A plan max-height ceiling is a number, not a polygon — and the deed verdict stays in the paid e-Kinnistusraamat register (group04 precedent). Scorer ceiling proxy only (soft caps 55/60/65, deed stays NULL).",
  },
];

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const PLANKTPR_HOOK =
  "PLANKTPR-HOOK (#492): planktpr wired into layers/overlays/outlines/snapshot/page; p47 polygons-only exact fills, p74/p274 scorer-only verdicts.";
