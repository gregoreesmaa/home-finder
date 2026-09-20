// EELIS nature-polygons overlay (issue #488): kaitsealad + niidud +
// kaadamisalad as honest per-parcel zone-MEMBERSHIP choropleths.
//
// Source: the public Keskkonnaagentuur WFS snapshot behind
// services/scoring/dims_p4_eelis.py (fetch_eelis_snapshot, 5 tables,
// annual pull, verified 2026-09-13: kr_kaitseala 33 + niidud 44 +
// kaadamisalad 1 rows in the Tallinn window). The scorer joins those
// rows by nearest labelled centroid within its windows (P4-015 <=500 m
// kaitse, P4-024 <=500 m habitat, P4-030 <=500 m felling); the map
// paints the same named polygons as fills so inside-a-named-polygon vs
// outside/unknown reads at a glance. Verdict: docs/p4_eelis.md.
//
// HONESTY (load-bearing): these layers MUST NOT paint a score field.
// They serve zero points and build zero rasters — the map paints
// basemap + polygon fills only, and outside every polygon stays NULL
// ("teadmata, mitte puhas/vaba", OTA PR #131 precedent). Every title
// says "hinnang"/"proksi"; every source names what is NOT in the join
// with EI OLE; scorer NULLs stay NULL (no snapshot, no rows, beyond
// window — unknown, never clear). No faked precision: no kernels, no
// smoothing, no distance decay (centre and edge of a polygon read
// alike — the scorer pins that its LABEL scores, distance only gates).
//
// POLYGONS-ONLY plumbing (documented divergence from every other
// layer, FLOOD #487 precedent): fallbackPoints is EMPTY (demo points
// would paint a fake gradient splat — the generic labels test carves
// polygon-only layers out, see layers.test.ts); EELIS_DECAY and
// EELIS_BONUS below are inert placeholders required by the
// Record<LayerId> tables (zero points and a null raster mean neither
// is ever evaluated — pinned by test); EELIS_TAGS are provenance
// notes, NOT runnable Overpass QL (the only rebuild path is
// scripts/build/batch_eelis_poly.py off cached WFS GeoJSON). The
// points endpoint answers honestly-empty for these layers (polygons
// carry the data — see the EELIS-HOOK branch in
// app/api/layers/[layer]/route.ts), and /layers paints the sidecar via
// /api/layers/eelis/areas (parks /areas precedent).
//
// REFUSED (documented, reviewable):
// * Flood table (kr_yleujutusohuga_ala): owned by the #487 floodzone
//   overlay (docs/overturn_flood.md) — one layer per source, no ships
//   twice here (this module's sidecar builder skips flood rows).
// * Emitter register (kr_puhasti + kr_jaakreostus, P4-053 sector dim):
//   point locations, not zone polygons — there is no honest polygon to
//   paint, and a point splat would re-skin the scorer's sector join as
//   a circle buffer the dim explicitly refuses ("never a circle
//   buffer"). The sector dim stays scorer-side (pinned NULL-shape by
//   test_dims_p4_eelis.py).
// * Cat I/II species + habitats: withheld from the public WFS by
//   design (see docs/p4_eelis.md) — niidud stays a coarse proxy and
//   every hit-level string says "mitte liigiväide".
//
// This file owns ALL eelis runtime data; shared files (lib/layers.ts,
// lib/overlays.ts, lib/outlines.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `EELIS-HOOK (#488)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.

import type { BonusSpec, LayerDef } from "./layers";

export type EelisLayerId = "eeliskaitse" | "eelisniit" | "eelisraie";

export const EELIS_LAYER_IDS: EelisLayerId[] = [
  "eeliskaitse",
  "eelisniit",
  "eelisraie",
];

/** WFS layer behind each map layer (verified Tallinn counts 2026-09-13). */
export const EELIS_WFS_LAYER: Record<EelisLayerId, string> = {
  eeliskaitse: "eelis:kr_kaitseala", // 33 in Tallinn
  eelisniit: "eelis:niidud", // 44 in Tallinn
  eelisraie: "eelis:kaadamisalad", // 1 in Tallinn
};

/** Sidecar kind per map layer (filters the shared eelis-areas.json). */
export const EELIS_KIND: Record<EelisLayerId, "kaitse" | "niit" | "raie"> = {
  eeliskaitse: "kaitse",
  eelisniit: "niit",
  eelisraie: "raie",
};

/** Buyer-param slice each overlay visualizes (NOT a parameters3 id). */
export const EELIS_PARAM_LABELS: Record<EelisLayerId, string> = {
  eeliskaitse: "P4-015",
  eelisniit: "P4-024",
  eelisraie: "P4-030",
};

const SNAP = "kohalik väljavõte 2026-09-12";
const WFS = "Keskkonnaagentuuri EELIS WFS (võtmeta, loetud 2026-09-13)";

export const EELIS_DEFS: LayerDef[] = [
  {
    id: "eeliskaitse",
    paramIds: [],
    paramLabel: "P4-015",
    title: "Kaitsealad (P4-015 proksi-hinnang)",
    goodLabel:
      "tsoonis = kaitseala piiranguala (hinnang, mitte ehitusloa otsus)",
    badLabel:
      "väljaspool tsoone = teadmata, mitte piirangutevaba (tõmmises on kaitsealasid mujal)",
    source:
      `${WFS}: eelis:kr_kaitseala (33 kirjet Tallinna aknas; ${SNAP}). ` +
      `I/II kategooria liigi- + elupaigaandmeid EI OLE avalikus ` +
      `teenuses — piirangu jalga EI FEIGITA, kaugus ainult värav, ` +
      `hinde annab SILT`,
    // Polygons-only: no demo points, ever — a demo point would paint a
    // fake gradient splat (see header). The generic labels test carves
    // polygon-only layers out of the fallbackPoints assertion.
    fallbackPoints: [],
  },
  {
    id: "eelisniit",
    paramIds: [],
    paramLabel: "P4-024",
    title: "Niiduelupaigad (P4-024 proksi-hinnang)",
    goodLabel:
      "tsoonis = niidu-elupaiga rakk (jäme proksi-hinnang, mitte liigiväide)",
    badLabel:
      "väljaspool rakke = teadmata, mitte puugivaba (tõmmises on rakke mujal)",
    source:
      `${WFS}: eelis:niidud (44 kirjet Tallinna aknas; ${SNAP}). ` +
      `Masinloetavat rohevõrgustikku EI OLE — niit on jäme ` +
      `puugi-elupaiga proksi (rakud, mitte liigiväide)`,
    fallbackPoints: [],
  },
  {
    id: "eelisraie",
    paramIds: [],
    paramLabel: "P4-030",
    title: "Raiealad (P4-030 muutuslipp, hinnang)",
    goodLabel:
      "tsoonis = registreeritud raieala (jäme muutuslipp, mitte satelliidimõõt)",
    badLabel:
      "väljaspool = teadmata, mitte muutumatu (tõmmises on raieid mujal; raieloa/satelliidi jalga EI OLE)",
    source:
      `${WFS}: eelis:kaadamisalad (1 kirje Tallinna aknas; ${SNAP}). ` +
      `NDVI/satelliidi/muutusekaardi jalga EI OLE — lipp, mitte delta`,
    fallbackPoints: [],
  },
];

/**
 * Influence radius in km. INERT placeholder (Record<LayerId> requires an
 * entry): eelis layers serve zero points and build no raster, so no
 * field is ever computed from this — pinned by the polygons-only test.
 */
export const EELIS_DECAY: Record<EelisLayerId, number> = {
  eeliskaitse: 0.5,
  eelisniit: 0.5,
  eelisraie: 0.5,
};

/**
 * Source notes for rebuilds. NOT runnable Overpass QL: the EELIS zones
 * live behind WFS GetFeature calls, and snapshot-only serving never
 * queries live either way. The only rebuild path is
 * scripts/build/batch_eelis_poly.py off cached WFS GeoJSON.
 */
export const EELIS_TAGS: Record<EelisLayerId, string> = {
  eeliskaitse: "EELIS-WFS eelis:kr_kaitseala (Overpass-uta)",
  eelisniit: "EELIS-WFS eelis:niidud (Overpass-uta)",
  eelisraie: "EELIS-WFS eelis:kaadamisalad (Overpass-uta)",
};

/** Raster master filenames next to the base masters. NEVER BUILT by
 * documented polygons-only decision (see header): the names resolve to
 * absent files so windows serve honestly-empty, never a gradient. */
export const EELIS_RASTER_FILE: Record<EelisLayerId, string> = {
  eeliskaitse: "eeliskaitse-walk-raster.json",
  eelisniit: "eelisniit-walk-raster.json",
  eelisraie: "eelisraie-walk-raster.json",
};

/** NO metro masters (documented): polygons-only, windows serve county. */
export const EELIS_NO_METRO = true;

/**
 * Bonus specs. INERT placeholders (never evaluated: zero points, null
 * raster — pinned by the polygons-only test). Shape mirrors the area
 * kind so the type contract holds without inventing a calibration.
 */
export const EELIS_BONUS: Record<EelisLayerId, BonusSpec> = {
  eeliskaitse: { kind: "area", half: 60 },
  eelisniit: { kind: "area", half: 60 },
  eelisraie: { kind: "area", half: 60 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isEelisLayerId(layer: string): layer is EelisLayerId {
  return (EELIS_LAYER_IDS as string[]).includes(layer);
}

/**
 * Polygons-only layers: no points, no raster, no gradient — the overlay
 * sidecar carries the data. The /layers page and the points endpoint
 * branch on this (never on id literals, so the contract stays
 * greppable).
 */
export function isEelisPolygonOnlyLayer(layer: string): boolean {
  return isEelisLayerId(layer);
}

/**
 * Eelis bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForEelis(layer: string): BonusSpec | undefined {
  return (EELIS_BONUS as Record<string, BonusSpec>)[layer];
}

/**
 * One EELIS nature polygon for the map sidecar. Rings are GeoJSON
 * [lon, lat] (WFS serves EPSG:4326 GeoJSON in lon/lat order — the
 * builder keeps the order, pinned by test_batch_eelis_poly.py); b is
 * the [minlon, minlat, maxlon, maxlat] prefilter box (ParkOutline
 * precedent); kiht filters the shared sidecar per map layer.
 */
export interface EelisArea {
  kiht: "kaitse" | "niit" | "raie";
  zone_id: string;
  nimi: string;
  lisa: string;
  b: [number, number, number, number];
  r: number[][][];
}

function isEelisArea(v: unknown): v is EelisArea {
  const p = v as Partial<EelisArea>;
  return (
    (p?.kiht === "kaitse" || p?.kiht === "niit" || p?.kiht === "raie") &&
    typeof p?.zone_id === "string" &&
    typeof p?.nimi === "string" &&
    typeof p?.lisa === "string" &&
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
 * EELIS nature polygons for painting fills on the eelis layers.
 * Null on any failure: polygons are a visual aid, never load-bearing —
 * the per-parcel join lives in the scorer
 * (services/scoring/dims_p4_eelis.py).
 */
export async function fetchEelisAreas(
  fetchImpl: typeof fetch = fetch,
): Promise<EelisArea[] | null> {
  try {
    const res = await fetchImpl("/api/layers/eelis/areas");
    if (!res.ok) return null;
    const body: unknown = await res.json();
    if (!body || typeof body !== "object" || !Array.isArray((body as { areas: unknown }).areas)) {
      return null;
    }
    return (body as { areas: unknown[] }).areas.filter(isEelisArea).map((p) => {
      const o = p as EelisArea;
      return { kiht: o.kiht, zone_id: o.zone_id, nimi: o.nimi, lisa: o.lisa, b: o.b, r: o.r };
    });
  } catch {
    return null;
  }
}

/**
 * Offshore-stray verdict (issue #788, dated 2026-09-20): the single
 * `eelis:kaadamisalad` row in the Tallinn window (zone_id "546732811",
 * nimi "Paljassaare", "Kaadamisala (pinnas)", staatus "Töötav") plots
 * ENTIRELY offshore — the live WFS re-pull on 2026-09-20 returns the
 * same 1 row with the same ring (bbox lon 24.647–24.664, lat
 * 59.474–59.486, centroid lon 24.654 / lat 59.479), while the OSM
 * coastline puts the northernmost land in that corridor (the
 * Paljassaare tip) at lat 59.47086, ~330 m south of the ring's
 * southern vertex, with no coastline segment crossing any ring edge.
 * A felling polygon with zero land overlap is not a clearcut the map
 * may paint, so the stray is filtered from the painted overlay here
 * and the status names this verdict (eelisRaieOffshoreStatus) instead
 * of "1 polügooni". Pinned by test. Re-verify on the annual EELIS
 * re-pull (docs/p4_eelis.md checklist): rows with any other zone_id
 * paint normally.
 */
export const EELIS_RAIE_OFFSHORE_ZONE_ID = "546732811";

/** True for the documented offshore kaadamisalad stray (pure). */
export function isEelisOffshoreStray(area: EelisArea): boolean {
  return area?.kiht === "raie" && area?.zone_id === EELIS_RAIE_OFFSHORE_ZONE_ID;
}

/**
 * Honest-empty status for eelisraie when the sidecar holds the
 * documented offshore stray and no other raie row (pure, pinned by
 * test): names the dated verdict instead of a polygon count. Null
 * when a paintable raie row exists (normal "N polügooni" path) or the
 * sidecar holds no raie rows at all.
 */
export function eelisRaieOffshoreStatus(
  areas: EelisArea[] | null | undefined,
): string | null {
  if (!areas) return null;
  const raie = areas.filter((a) => a && a.kiht === "raie");
  if (raie.length === 0 || raie.some((a) => !isEelisOffshoreStray(a))) return null;
  return (
    "EELIS raiealad · 0 polügooni (registri kirje Paljassaare on meres — " +
    "merd ei värvita; kontrollitud 2026-09-20, elus-WFS + rannajoon)"
  );
}

/**
 * Sidecar rows for one map layer (pure): the shared sidecar carries all
 * three kinds; each layer paints only its own. The documented offshore
 * kaadamisalad stray (#788) never paints — painting it would put a
 * "felling polygon" in Tallinn Bay.
 */
export function eelisAreasForKind(
  areas: EelisArea[] | null | undefined,
  kiht: "kaitse" | "niit" | "raie",
): EelisArea[] {
  if (!areas) return [];
  return areas.filter((a) => a && a.kiht === kiht && !isEelisOffshoreStray(a));
}

/** Sidecar kind painted by a map layer (null for other layers). */
export function eelisKindForLayer(layer: string): "kaitse" | "niit" | "raie" | null {
  if (!isEelisLayerId(layer)) return null;
  return EELIS_KIND[layer];
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const EELIS_HOOK =
  "EELIS-HOOK (#488): eeliskaitse + eelisniit + eelisraie wired into " +
  "layers/overlays/outlines/snapshot; kr_kaitseala/niidud/kaadamisalad " +
  "zone-membership choropleths, polygons only, outside stays unknown " +
  "(flood owned by #487, emitters refused: point register, no polygons).";
