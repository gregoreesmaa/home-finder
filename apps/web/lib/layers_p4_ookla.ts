// Ookla quarterly-tile overlay (P4-009 fallback slice, issue #489,
// Group B verify-first): fixed + mobile download-band hinnang layers
// from the Ookla Speedtest Open Data Tallinn extract. This file owns ALL
// ookla overlay runtime data; shared files (lib/layers.ts,
// lib/distanceField.ts, lib/server/snapshot.ts, lib/overlays.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `OOKLA-HOOK (#489)` blocks, so sibling batches
// stay disjoint (sibling Layer issues #479-#488/#490-#495 own different
// files, different ids, different params). This module imports
// ./layers ONLY as types (TilebandSpec, LayerDef, LayerId): no
// runtime cycle (layers.ts imports values from here).
//
// VERDICT (re-verified 2026-09-13, POSITIVE — keyless tile download
// works): 2 HEADs with a labelled one-off user-agent
// (`home-finder openness-check (one-off, no scrape)`):
//   fixed  Q1-2026 parquet -> HTTP 200, Content-Length 348853499,
//     Last-Modified Mon, 13 Apr 2026 (== docs/p4_ookla.md, unchanged)
//   mobile Q1-2026 parquet -> HTTP 200, Content-Length 175330099,
//     Last-Modified Mon, 13 Apr 2026 (unchanged)
// plus 2 bounded DuckDB range-reads (httpfs column chunks only, files
// never pulled whole) over the Tallinn bbox lon 24.3-25.1 / lat
// 59.3-59.6 with the scorer's own guards (tests >= 5, avg_d present):
//   fixed: 971 qualifying tiles / 21 598 tests, median 164 537 kbps
//   mobile: 555 qualifying tiles / 6 856 tests, median 261 748 kbps
// The qualifying-tile subset the scorer and this layer consume is
// therefore PROVEN live today — no dated-negative, no synthetic fill.
// (Full 9-request openness record stays in docs/p4_ookla.md.)
//
// HONESTY (load-bearing): a ~0.6 km quarterly tile says which speed
// band an address sits in, never what the flat's contract delivers —
// and it says nothing about power cuts (Elektrilevi SAIDI stays
// unpublished). The map kernel is the EXACT scorer band function from
// services/scoring/dims_p4_ookla.py (nearest qualifying tile <= 1 km
// -> 35/55/75/capped-85), so map colors and scored reasons agree by
// construction. Tiles are NOT averaged or smoothed — smoothing would
// fake a gradient between measured squares. No qualifying tile in
// radius stays null/255 (renders red, never a faked score) — the
// scorer reads the same gap as NULL with an Estonian reason (hinnang
// + EI OLE, pinned by test_dims_p4_ookla.py; scored reasons say
// hinnang and never EI OLE, same invariant).
//
// Points come from the Ookla Tallinn extract
// (ookla-tallinn-2026Q1.json: {quarter, fixed, mobile, n_fixed,
// n_mobile}, built by the dims_p4_ookla operator step, served by
// lib/server/ookla.ts) — NEVER from the 2026-09-12 OSM snapshot
// (Ookla tiles are not OSM features) and never live (no network in
// the map path). No raster master exists BY DOCUMENTED DECISION (see
// OOKLA_NO_RASTER): the extract is a sparse tile-centroid set and the
// points-splat tileband kernel IS the field — a county stamp would add
// build machinery without meaning. The window route serves 500 for
// these layers and the client falls back to the splat (designed path,
// GTFS/senscom precedent).
//
// The layers carry NO parameters3.md id: parameters3 p9 is an
// inspection-group fact (documented no-map) and must NOT gain a map by
// accident. paramIds stays [] and paramLabel carries the buyer-param
// slice ("P4-009") for the layer button (senscom P4-031 precedent).
// Fixed + mobile ship as TWO layers on one slice (fiber/mobile p51
// precedent in layers_batch10c.ts): different buyer questions
// (püsiühendus vs mobiilne), same quarter, same kernel.
//
// Calibration (judgment calls, documented for the reviewer): the band
// edges (30/100/300 Mbit/s -> 35/55/75/85) and the join guards
// (1000 m, >= 5 tests) are byte-parity copies of _SPEED_BANDS /
// OOKLA_RADIUS_M / OOKLA_MIN_TESTS in dims_p4_ookla.py — changing the
// scorer without changing OOKLA_BANDS (or vice versa) is a drift bug,
// pinned by the parity test in layers_p4_ookla.test.ts. Tile payload
// rides LayerPoint.tags as decimal strings (avg_d/tests) — the
// measured-coverage precedent (tags.ulatus_m, "cover" branch in
// distanceField.ts); cleanTags passes string tags through untouched.

import type { LayerDef, LayerId, TilebandSpec } from "./layers";

export type OoklaLayerId = "ookla_fixed" | "ookla_mobile";

export const OOKLA_LAYER_IDS: OoklaLayerId[] = ["ookla_fixed", "ookla_mobile"];

/** Buyer-param slice both overlays visualize (NOT a parameters3 id). */
export const OOKLA_PARAM_LABEL = "P4-009";

/**
 * Extract vintage both layers render (== OOKLA_LATEST_LABEL in
 * dims_p4_ookla.py; a new quarterly pull updates this constant with
 * the extract, same practice as SNAP date strings elsewhere).
 */
export const OOKLA_QUARTER = "2026-Q1";

/**
 * Nearest-tile join radius in metres — byte parity with
 * OOKLA_RADIUS_M in services/scoring/dims_p4_ookla.py (tile pitch is
 * ~0.6 km; 1 km reaches the neighbour square without inventing
 * coverage).
 */
export const OOKLA_RADIUS_M = 1000;

/**
 * Tiles with fewer quarterly tests are anecdotes, not bands — byte
 * parity with OOKLA_MIN_TESTS in dims_p4_ookla.py.
 */
export const OOKLA_MIN_TESTS = 5;

/**
 * Download-band edges in kbit/s — byte parity with _SPEED_BANDS in
 * dims_p4_ookla.py (EU broadband tiers: 30 = fast-broadband line,
 * 100 = ultrafast; checked against live Tallinn Q1-2026 quartiles).
 */
export const OOKLA_BAND_EDGES = [30000, 100000, 300000] as const;

/**
 * Download bands — byte parity with _band_d in
 * dims_p4_ookla.py (capped: a tile proxy never earns 100; thin
 * network is unknown, never good).
 */
export const OOKLA_BANDS = { weak: 35, mid: 55, strong: 75, top: 85 } as const;

/** LayerPoint.tags keys carrying one tile's measured payload. */
export const OOKLA_TAG_AVG_D = "avg_d";
export const OOKLA_TAG_TESTS = "tests";

const EXTRACT = "Ookla Speedtest Open Data 2026-Q1 Tallinna väljavõte";

export const OOKLA_LAYERS: LayerDef[] = [
  {
    id: "ookla_fixed",
    paramIds: [],
    paramLabel: OOKLA_PARAM_LABEL,
    title: "Fikseeritud netikiirus (P4-009 Ookla-hinnang)",
    goodLabel: "roheline = kiire fikseeritud kvartal (mõõdetud ruut lähedal, hinnang)",
    badLabel: "punane = aeglane kvartal või mõõdetud ruut 1 km raadiuses puudu (tundmatu, hinnang)",
    source:
      `${EXTRACT} (fikseeritud z16-kvartaliruudud ~0,6 km; kvartali keskmine allalaadimiskiirus — hinnang, ≥5 testi kvartalis; korteri lepingukiirus ja elektrikatkestused selles kihis pole — CC BY-NC-SA 4.0, lähemalt docs/p4_ookla.md)`,
    fallbackPoints: [
      // 2026-09-13 observed dense Kesklinn tile (24.7549, 59.4381:
      // 176 Mbit/s down, 151 tests — see docs/p4_ookla.md), DEMO
      // fallback only (real extract rows are served from the
      // extract, never committed).
      { lat: 59.4381, lon: 24.7549 }, // Kesklinn (tihe mõõtmine, demo)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (ruudust väljas, demo-taust)
    ],
  },
  {
    id: "ookla_mobile",
    paramIds: [],
    paramLabel: OOKLA_PARAM_LABEL,
    title: "Mobiilne netikiirus (P4-009 Ookla-hinnang)",
    goodLabel: "roheline = kiire mobiilne kvartal (mõõdetud ruut lähedal, hinnang)",
    badLabel: "punane = aeglane kvartal või mõõdetud ruut 1 km raadiuses puudu (tundmatu, hinnang)",
    source:
      `${EXTRACT} (mobiilsed z16-kvartaliruudud ~0,6 km; kvartali keskmine allalaadimiskiirus — hinnang, ≥5 testi kvartalis; operaatori levikaart ja elektrikatkestused selles kihis pole — CC BY-NC-SA 4.0, lähemalt docs/p4_ookla.md)`,
    fallbackPoints: [
      { lat: 59.4381, lon: 24.7549 }, // Kesklinn (tihe mõõtmine, demo)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (ruudust väljas, demo-taust)
    ],
  },
];

/**
 * Source-vocabulary note (documents the S3 layout; the extract — not
 * S3, not Overpass — serves these layers, so the map path never
 * fetches live. overpassQueryFor("ookla_*") is never called in
 * production).
 */
export const OOKLA_TAGS: Record<OoklaLayerId, string> = {
  ookla_fixed:
    "s3:ookla-open-data/parquet/performance/type=fixed/year=YYYY/quarter=Q (kvartaliruudud; serveeritakse Tallinna väljavõttest, mitte S3-st/Overpassist)",
  ookla_mobile:
    "s3:ookla-open-data/parquet/performance/type=mobile/year=YYYY/quarter=Q (kvartaliruudud; serveeritakse Tallinna väljavõttest, mitte S3-st/Overpassist)",
};

/** Raster master filenames (intentionally never built — see OOKLA_NO_RASTER). */
export const OOKLA_RASTER_FILE: Record<OoklaLayerId, string> = {
  ookla_fixed: "ookla-fixed-walk-raster.json",
  ookla_mobile: "ookla-mobile-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat tileband kernel IS
 * the field. A county stamp of a sparse tile-centroid set would add
 * build machinery without meaning — the splat already renders the
 * nearest-tile bands from the extract rows (senscom SENSCOM_NO_RASTER
 * precedent). The window route serves 500 for these layers and the
 * client falls back to the splat (designed path).
 */
export const OOKLA_NO_RASTER = true;

/**
 * Euclidean fallback decay (same scale story as the 1 km join
 * radius): only feeds sigmaKm where a sigma is required; the tileband
 * kernel itself joins the nearest qualifying tile in the hard radius
 * (see the "tileband" branch in distanceField.ts).
 */
export const OOKLA_DECAY_KM: Record<OoklaLayerId, number> = {
  ookla_fixed: 1.0,
  ookla_mobile: 1.0,
};

/** Type guard for the bonusSpecFor()/goodnessAt() hooks in ./layers. */
export function isOoklaLayerId(layer: LayerId): layer is OoklaLayerId {
  return (OOKLA_LAYER_IDS as string[]).includes(layer);
}

/** Band spec for the ookla layers (called from the bonusSpecFor hook). */
export function ooklaBonusSpecFor(layer: OoklaLayerId): TilebandSpec {
  void layer;
  return {
    kind: "tileband",
    radiusM: OOKLA_RADIUS_M,
    minTests: OOKLA_MIN_TESTS,
    weak: OOKLA_BANDS.weak,
    mid: OOKLA_BANDS.mid,
    strong: OOKLA_BANDS.strong,
    top: OOKLA_BANDS.top,
  };
}

function numTag(tags: Record<string, string> | undefined, key: string): number | null {
  if (!tags) return null;
  const raw = tags[key];
  if (typeof raw !== "string") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

/** Tile download average (kbit/s) off a served point, null when unmeasured. */
export function ooklaAvgDOf(tags: Record<string, string> | undefined): number | null {
  return numTag(tags, OOKLA_TAG_AVG_D);
}

/** Quarterly test count off a served point, null when unknown. */
export function ooklaTestsOf(tags: Record<string, string> | undefined): number | null {
  return numTag(tags, OOKLA_TAG_TESTS);
}

/**
 * Download band for one quarterly average — byte parity with _band_d
 * in services/scoring/dims_p4_ookla.py. Null when the average is not
 * a number (unmeasured tile, never a band).
 */
export function ooklaBandForSpeed(avgDkbps: number): number | null {
  if (!Number.isFinite(avgDkbps)) return null;
  if (avgDkbps < OOKLA_BAND_EDGES[0]) return OOKLA_BANDS.weak;
  if (avgDkbps < OOKLA_BAND_EDGES[1]) return OOKLA_BANDS.mid;
  if (avgDkbps < OOKLA_BAND_EDGES[2]) return OOKLA_BANDS.strong;
  return OOKLA_BANDS.top;
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function ooklaHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface OoklaPoint {
  lat: number;
  lon: number;
  tags?: Record<string, string>;
}

export interface OoklaJoin {
  /** Band 35/55/75/85 off the tile's download average. */
  band: number;
  /** Tile download average (kbit/s). */
  avgD: number;
  /** Tile quarterly test count. */
  tests: number;
  /** Distance to the tile centroid in metres. */
  distM: number;
}

/**
 * Nearest QUALIFYING tile within the hard radius, or null — byte
 * parity with _nearest_tile in services/scoring/dims_p4_ookla.py (no
 * averaging, no smoothing; thin or speed-less tiles never qualify).
 */
export function ooklaTileAt(
  lat: number,
  lon: number,
  points: OoklaPoint[],
  radiusM: number = OOKLA_RADIUS_M,
  minTests: number = OOKLA_MIN_TESTS,
): OoklaJoin | null {
  let best: OoklaJoin | null = null;
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const avgD = ooklaAvgDOf(p.tags);
    const tests = ooklaTestsOf(p.tags);
    if (avgD === null || tests === null || tests < minTests) continue;
    const distM = ooklaHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM > radiusM) continue;
    const band = ooklaBandForSpeed(avgD);
    if (band === null) continue;
    if (best === null || distM < best.distM) best = { band, avgD, tests, distM };
  }
  return best;
}

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const OOKLA_HOOK =
  "OOKLA-HOOK (#489): ookla_fixed/ookla_mobile wired into layers/overlays/snapshot/distanceField; P4-009 linkage in OOKLA_PARAM_LABEL, paramIds stays empty (parameters4 namespace).";
