// Group 5 plans-C layers (parameters3.md §5.5, issue #163): p223 ships
// as an honest commercial-zone proximity hinnang ("commbleed"), p224
// ships as an honest wind/solar-farm distance hinnang ("windsolar"),
// p225 ships as an honest viewpoint-count hinnang ("viewshed");
// p221/p222 are documented no-map with scorer dims (see G05C_VERDICTS
// below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = calm (green = sheltered/clean, red = exposed); unknown
// stays 255 (renders red). This file owns ALL G05C runtime data; shared
// files (lib/layers.ts, lib/server/snapshot.ts, lib/overlays.ts) touch
// it only through small marked `G05C-HOOK (#163)` blocks, so the sibling
// batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Rahandusministeerium PLANK register, the
// Tallinna Planeeringute Register, KOV sundvõõrandamine decisions, EANS
// route schedules and the Elering generation register are NOT in the
// 2026-09-12 snapshot, so NONE of the three shipped layers is registry
// data:
// * commbleed is a mapped-zone *hinnang* — nearness to OSM-mapped
//   commercial/retail landuse + malls, never a KOV zoning decision.
//   Plain supermarkets stay the grocery layer's (#98): malls and retail
//   parks are bleed PRESSURE (traffic/noise), not errand amenity.
// * windsolar is a mapped-farm *hinnang* — distance to OSM-mapped wind
//   turbines + ground/surface solar farms, the param's own ST_Distance
//   shape — never an Elering production ruling. Rooftop panels (1734)
//   are OUT by design: a rooftop panel is not a farm.
// * viewshed is a mapped-viewpoint *hinnang* — count of OSM-mapped
//   scenic viewpoints nearby (area-kind, moorage precedent), never a
//   KOV height-limit ruling. Green = near (view protection likely),
//   red = far (protection unknown).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p221 eminent domain risk: a per-parcel LEGAL fact (a single
//   sundvõõrandamine decision). PLANK/TPR hold plan geometries, not
//   expropriation decisions, and the snapshot carries zero
//   expropriation keys — a proximity gradient cannot discriminate a
//   rare parcel event. Scorer dim stays NULL with a KOV-register
//   reason (dims_group05c.dim_eminent).
// * p222 flight path re-routing: a SCHEDULE fact (EANS route changes),
//   not a spatial gradient — and runway proximity is already scored
//   TWICE (flightcorr p445 corridors + droneclear p220 aerodrome
//   distance). A third runway gradient would duplicate them. Scorer
//   dim stays NULL with an EANS reason (dims_group05c.dim_flightreroute).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/landuse=commercial nwr/landuse=retail nwr/shop=mall
//   1054 features; the keep_comm predicate (landuse commercial/retail
//   or shop=mall, see scripts/build/batch_g05c_plans.py) keeps 854
//   county-wide (670 in the Tallinn window: Ülemiste, Rocca al Mare,
//   Mustakivi retail parks). 200 untagged relation members drop out.
//   osmium tags-filter ... nwr/power=generator   (+ export)
//   2842 features; the keep_farm predicate (wind any location; solar
//   ONLY ground/surface/overground) keeps 155 county-wide (53 wind +
//   102 farm solar, 91 in the Tallinn window incl. a Nõmme turbine).
//   2687 rooftop/unknown-location panels drop out BY DESIGN (a panel
//   is not a farm); diesel/gas/biofuel/hydro are OUT (not wind/solar).
//   osmium tags-filter ... nwr/tourism=viewpoint   (+ export)
//   89 features; the keep_view predicate keeps 88 county-wide (44 in
//   the Tallinn window: Kohtuotsa/Patkuli/Piiskopi platforms, klint
//   edges). 1 untagged member drops out. Bog bird-towers dilute the
//   rural field by design (documented, not hidden).
//
// Calibration (judgment calls, documented for the reviewer): commbleed
// + windsolar are nearest-source distance fields, quiet-kind calmness
// (100·d/(d+halfM)), the same kind the G07/G08 batches add — identical
// semantics (0 on the source, 50 at halfM), shared on purpose.
// commbleed halves at 300 m (mall traffic/noise is block-scale);
// windsolar halves at 800 m (turbine visual/noise setbacks run
// 500–1000 m; solar glare is local, turbines dominate). viewshed is
// an area-kind count kernel (Gaussian sigma 0.3, score 100·S/(S+1),
// moorage precedent): ONE mapped viewpoint already reads 50 on its
// own cell instead of vanishing. Sigmas equal the Euclidean fallback
// decay (DECAY hook) and the raster contract (matchesContract).
// Halves live in G05C_CAL below and in scripts/build/batch_g05c_plans.py
// G05C_CAL (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group05CLayerId = "commbleed" | "windsolar" | "viewshed";

export const GROUP05C_LAYER_IDS: Group05CLayerId[] = ["commbleed", "windsolar", "viewshed"];

/** parameters3.md number per Group-5C layer (no-map params have no layer). */
export const GROUP05C_PARAM_IDS: Record<Group05CLayerId, number> = {
  commbleed: 223,
  windsolar: 224,
  viewshed: 225,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP05C_ALL_PARAMS = [221, 222, 223, 224, 225] as const;

export type Group05CParam = (typeof GROUP05C_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP05C_LAYERS: LayerDef[] = [
  {
    id: "commbleed",
    paramIds: [223],
    title: "Äri- ja kaubandustsoonide surve (hinnang)",
    goodLabel: "roheline = äritsoonidest kaugel, rahulik elamupiirkond (hinnang)",
    badLabel: "punane = äritsooni mõjualas — liiklus/müra, kontrolli planeeringut (hinnang)",
    source: `${SNAP} (kaardistatud ärimaa 463 + kaubandusmaa 296 + kaubanduskeskused 95 = 854 objekti, sh Tallinnas 670; PROKSI-hinnang läheduse järgi — see EI OLE KOV ärimaa-otsus)`,
    fallbackPoints: [
      { lat: 59.4229, lon: 24.7956 }, // Ülemiste keskus (äritsooni ääres)
      { lat: 59.3827, lon: 24.6616 }, // Nõmme keskus (elamupiirkond, äritsoonidest kaugel)
    ],
  },
  {
    id: "windsolar",
    paramIds: [224],
    title: "Tuule- ja päikeseparkide lähedus (hinnang)",
    goodLabel: "roheline = tuulikutest ja päikeseparkidest kaugel (hinnang)",
    badLabel: "punane = tuule-/päikesepargi lähedal — kontrolli müra ja varjutust (hinnang)",
    source: `${SNAP} (kaardistatud 53 tuulikut + 102 maapealset päikeseparki = 155 objekti, sh Tallinnas 91; 1734 katusepaneeli VÄLJA — katusepaneel ei ole park; PROKSI-hinnang — see EI OLE Eleringi tootmisregister)`,
    fallbackPoints: [
      { lat: 59.39614, lon: 24.67064 }, // Nõmme tuulik (pargi lähedal, proksi)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (parkidest kaugel)
    ],
  },
  {
    id: "viewshed",
    paramIds: [225],
    title: "Vaatekaitselised punktid (hinnang)",
    goodLabel: "roheline = vaatepunkti lähedal, vaade tõenäoliselt kaitstud (hinnang)",
    badLabel: "punane = vaatepunktidest kaugel, vaatekaitse teadmata (hinnang)",
    source: `${SNAP} (kaardistatud 88 vaatepunkti — Toompea platvormid, pangad, linnutornid — sh Tallinnas 44; lähedus-hinnang, küllastus 1 — see EI OLE KOV kõrguspiirangute register)`,
    fallbackPoints: [
      { lat: 59.4357, lon: 24.7399 }, // Kohtuotsa vaateplatvorm (vaate ääres)
      { lat: 59.36, lon: 24.66 }, // Nõmme (vaatepunktidest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 5C layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped retail parks and farm polygons). The builder
 * consumes the same predicate offline (see keep_comm / keep_farm /
 * keep_view); the rooftop exclusion and the ground/surface check live in
 * the scorer mapping (kinds_from_tags), so the fragment stays a plain
 * source-tags query like sibling batches.
 */
export const GROUP05C_TAGS: Record<Group05CLayerId, string> = {
  commbleed: 'n["landuse"~"commercial|retail"];n["shop"="mall"];',
  windsolar: 'n["power"="generator"];n["generator:source"~"wind|solar"];',
  viewshed: 'n["tourism"="viewpoint"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP05C_DECAY: Record<Group05CLayerId, number> = {
  commbleed: 0.3,
  windsolar: 0.3,
  viewshed: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g05c_plans.py G05C_CAL exactly — a pytest
 * parses this file and fails on drift). commbleed/windsolar carry the
 * quiet-kind halfM (metres); viewshed carries the area-kind half
 * (saturating count, moorage precedent).
 */
export const G05C_CAL = {
  commbleed: { halfM: 300, sigma: 0.3 },
  windsolar: { halfM: 800, sigma: 0.3 },
  viewshed: { half: 1, sigma: 0.3 },
} as const;

/**
 * commbleed + windsolar: nearest-source calmness 100·d/(d+halfM)
 * (quiet-kind, G07/G08 precedent). viewshed: nearby-viewpoint count
 * 100·S/(S+half) (area-kind, moorage precedent — green NEAR the amenity).
 */
export const GROUP05C_BONUS: Record<Group05CLayerId, BonusSpec> = {
  commbleed: { kind: "quiet", halfM: 300 },
  windsolar: { kind: "quiet", halfM: 800 },
  viewshed: { kind: "area", half: 1 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup05CLayerId(layer: string): layer is Group05CLayerId {
  return (GROUP05C_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-5C bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup05C(layer: string): BonusSpec | undefined {
  return (GROUP05C_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 5C layer (built by batch_g05c_plans.py). */
export const G05C_RASTER_FILE: Record<Group05CLayerId, string> = {
  commbleed: "commbleed-walk-raster.json",
  windsolar: "windsolar-walk-raster.json",
  viewshed: "viewshed-walk-raster.json",
};

/**
 * NO metro masters (documented): smooth distance-decay fields and a
 * sparse count kernel at 9.375 m cells would be fake precision. The
 * window route serves county everywhere for these layers (metro slot
 * stays empty, like G07B/G03D/G08B).
 */
export const G05C_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group05cHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function group05cQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group05CPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM per layer).
 */
export function group05cQuietnessAt(
  layer: "commbleed" | "windsolar",
  lat: number,
  lon: number,
  points: Group05CPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group05cHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group05cQuietFromHalf(best * 1000, G05C_CAL[layer].halfM));
}

/** Area-kind saturating score 100·S/(S+half) (mirrors walk_raster.saturate). */
export function group05cAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group05cMatchesContract(
  layer: Group05CLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  if (layer === "viewshed")
    return doc.half === G05C_CAL.viewshed.half && doc.sigma === G05C_CAL.viewshed.sigma;
  return doc.half === G05C_CAL[layer].halfM && doc.sigma === G05C_CAL[layer].sigma;
}

export type Group05CVerdictKind = "proxy" | "real" | "no-map";

export interface Group05CVerdict {
  param: Group05CParam;
  name: string;
  kind: Group05CVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 5 batch C (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group05c.py).
 */
export const G05C_VERDICTS: Group05CVerdict[] = [
  {
    param: 221,
    name: "Eminent domain risk",
    kind: "no-map",
    reason:
      "A per-parcel legal fact (a single sundvõõrandamine decision); PLANK/TPR hold plan geometries, never expropriation decisions, and the snapshot carries zero expropriation keys — a proximity gradient cannot discriminate a rare parcel event.",
  },
  {
    param: 222,
    name: "Flight path re-routing",
    kind: "no-map",
    reason:
      "A schedule fact (EANS route changes), not a spatial gradient — and runway proximity is already scored twice (flightcorr p445 corridors + droneclear p220 aerodrome distance), so a third runway gradient would duplicate them.",
  },
  {
    param: 223,
    name: "Commercial zoning bleed",
    kind: "proxy",
    reason:
      "Shipped as commbleed: nearness to 854 mapped commercial/retail zones + malls (670 in Tallinn) as bleed-pressure hinnang — honestly labelled, never a KOV zoning decision, and never a re-skin of the grocery errand layer.",
  },
  {
    param: 224,
    name: "Wind/Solar farm proximity",
    kind: "proxy",
    reason:
      "Shipped as windsolar: distance to 53 mapped turbines + 102 farm-scale solar parks is the param's own ST_Distance shape — but the inventory is OSM-mapped, never the Elering register, so it stays a proxy; 1734 rooftop panels are out (a panel is not a farm).",
  },
  {
    param: 225,
    name: "View shedding ordinances",
    kind: "proxy",
    reason:
      "Shipped as viewshed: count of 88 mapped scenic viewpoints nearby (44 in Tallinn — Toompea platforms, klint edges) as view-protection hinnang, area-kind like moorage — honestly labelled, never a KOV height-limit ruling.",
  },
];

/** Batch-C params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP05C_NO_MAP_PARAMS: number[] = G05C_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP05C_HOOK =
  "G05C-HOOK (#163): commbleed + windsolar + viewshed wired into layers/overlays/snapshot; p221/p222 verdicts + dims only.";
