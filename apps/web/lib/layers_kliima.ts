// Keskkonnaagentuur climate-normals microclimate cells (issue #611,
// P4 winter-mildness + wetness station legs; Group-Y verify-first
// POSITIVE verdict docs/p4_kliima_cells.md §"Layer verdict #611").
// This file owns ALL kliima overlay runtime data; shared files
// (lib/layers.ts, lib/distanceField.ts, lib/overlays.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `KLIIMA-HOOK (#611)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.
//
// FEED VERDICT (2026-09-16, polite annual harvest, custom UA
// `home-finder-611-kliima-normals/1.0`, 2 s pacing, HTTP 429 as stop,
// raw JSON in /tmp/hf-611-kliima only — never committed): the
// keyless kliimaandmestik PostgREST feed serves 1991-2020 normals for
// the three usable Harjumaa stations. Frost days come from f_kliima_paev
// daily DTAN rows (the monthly view carries aggregates only —
// frost-day counts are NOT derivable from it); precipitation comes
// from f_kliima_kuu monthly DPREC rows (paginated: the 1000-row cap
// truncates silently, so a single GET would rank a partial decade).
// Harvest tally (scripts/build/batch_kliima.py --cache-dir
// /tmp/hf-611-kliima):
//   frost: Harku 128.6 d (55) / Pakri 106.5 d (70) / Kuusiku 146.5 d (40)
//   wet:   Harku 699.9 mm (70) / Kuusiku 730.1 mm (40) / Pakri NULL
// Pakri's monthly DPREC has genuine feed gaps (null vaartus winter
// months 2004-2010 + 2020-07: 22/30 complete years < the 24-year
// minimum), so Pakri stays wet-NULL by the coverage rule — its cell
// renders unknown on the wet slice, never a faked middle (the scorer
// reads the same gap as NULL: Pakri-area listings score EI OLE).
//
// TRANSFORM (labeled, reviewable): none needed — the feed serves WGS84
// station coords directly (Harku 59.398122N 24.602870E, Pakri
// 59.3895N 24.0401E, Kuusiku 58.9732N 24.7340E, per the scorer's
// HARJUMAA_STATIONS). Bands mirror _rank_dim in
// services/scoring/dims_p4_kliima_stations.py byte-for-byte: 3 joined
// cells -> 70/55/40 dense rank (ties share the better band), 2 joined
// -> 70/40. The builder and its pytest pin the same numbers, so the
// two sides cannot silently disagree.
//
// HONESTY (load-bearing): cells are nearest-station polygons in
// spirit — between-station interpolation is FORBIDDEN (the kernel is
// the qbands nearest-wins, the map twin of kliimaBandAt below: each
// cell takes the NEAREST station's band inside the hard 70 km county
// radius, no smoothing, no street-level gradients, no forecasts).
// Beyond all three stations stays null/255 (renders red, never a
// faked score). The legend states the 3-cell thinness + the
// 1991-2020 normals vintage on every slice.
//
// The layers carry NO parameters3.md id: the station dims are
// parameters4 buyer params (tervise #494 precedent). paramIds stays []
// and paramLabel carries the slice ("P4-kliima talv" / "P4-kliima
// sademed") for the layer button.

import type { BBoxLike, BonusSpec, LayerDef, LayerId, LayerPoint } from "./layers";

export type KliimaLayerId = "kliima_frost" | "kliima_wet";

export const KLIIMA_LAYER_IDS: KliimaLayerId[] = ["kliima_frost", "kliima_wet"];

/** Slice key for per-slice band stamping (frost vs wetness legs). */
export type KliimaSlice = "frost" | "wet";

/**
 * Dated harvest this layer rests on (see header). The Python builder
 * (scripts/build/batch_kliima.py) and its pytest pin the same numbers,
 * so the two sides cannot silently disagree.
 */
export const KLIIMA_PROBE = {
  date: "2026-09-16",
  normalsWindow: "1991-2020",
  frostHarkuDays: 128.6,
  frostPakriDays: 106.5,
  frostKuusikuDays: 146.5,
  precipHarkuMm: 699.9,
  precipKuusikuMm: 730.1,
  precipPakriCompleteYears: 22,
} as const;

/** Vintage label stamped on the build (annual normals harvest). */
export const KLIIMA_VINTAGE = "2026-09-16";

/** Attribution (CC BY 4.0) — surfaced in the layer source note. */
export const KLIIMA_ATTRIBUTION = "Keskkonnaagentuur (kliimaandmestik), CC BY 4.0";

/**
 * Hard join radius in metres — county scale on purpose: the farthest
 * Harjumaa corner (Loksa) sits ~65 km from its nearest cell station
 * (Harku), so 70 km keeps every county cell inside some station's
 * territory while the sea beyond stays honestly unknown.
 */
export const KLIIMA_RADIUS_M = 70000;

export const KLIIMA_LAYERS: LayerDef[] = [
  {
    id: "kliima_frost",
    paramIds: [],
    paramLabel: "P4-kliima talv",
    title: "Talvine leebus (kliimajaama rakk, normatiiv)",
    goodLabel:
      "roheline = leebeim liitunud rakk 70 km raadiuses (1991-2020 külmapäevade järjestus, 3 jämedat jaamarakku — lähedus, mitte mõõtmine)",
    badLabel:
      "punane = karmim liitunud rakk 70 km raadiuses VÕI lähim jaam normatiivita (teadmata, mitte karm)",
    source:
      "Keskkonnaagentuur kliimaandmestik (f_kliima_paev DTAN 1991-2020, seis 2026-09-16, CC BY 4.0; Harku 128,6 / Pakri 106,5 / Kuusiku 146,5 külmapäeva aastas; interpolatsiooni vahepeal pole)",
    fallbackPoints: [
      // Harvested normals, DEMO fallback only (real cells are served
      // from KLIIMA_CELLS below, never committed twice).
      { lat: 59.398122, lon: 24.60287, q: 55 }, // Harku (demo)
      { lat: 59.3895, lon: 24.0401, q: 70 }, // Pakri (demo)
    ],
  },
  {
    id: "kliima_wet",
    paramIds: [],
    paramLabel: "P4-kliima sademed",
    title: "Kuivus (kliimajaama rakk, normatiiv)",
    goodLabel:
      "roheline = kuiveim liitunud rakk 70 km raadiuses (1991-2020 aastasademete järjestus, 2 järjestatud rakku — lähedus, mitte mõõtmine)",
    badLabel:
      "punane = niiskeim liitunud rakk 70 km raadiuses VÕI lähim jaam normatiivita (Pakri sademerida 22/30 aastat — teadmata, mitte niiske)",
    source:
      "Keskkonnaagentuur kliimaandmestik (f_kliima_kuu DPREC 1991-2020, seis 2026-09-16, CC BY 4.0; Harku 699,9 / Kuusiku 730,1 mm aastas; Pakri 22/30 täisaastat ehk normatiivita; interpolatsiooni vahepeal pole)",
    fallbackPoints: [
      // Harvested normals, DEMO fallback only (real cells are served
      // from KLIIMA_CELLS below, never committed twice).
      { lat: 59.398122, lon: 24.60287, q: 70 }, // Harku (demo)
      { lat: 58.9732, lon: 24.734, q: 40 }, // Kuusiku (demo)
    ],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — Keskkonnaagentuur
 * normals are not OSM data; inventing natural=* plumbing would be
 * dishonest, paaste #493 precedent). overpassQueryFor("kliima_*") is
 * never called in production; the string only satisfies the registry
 * shape.
 */
export const KLIIMA_TAGS: Record<KliimaLayerId, string> = {
  kliima_frost:
    "Keskkonnaagentuur kliimaandmestik (f_kliima_paev DTAN 1991-2020; serveeritakse harvested rakkudest, mitte Overpassist)",
  kliima_wet:
    "Keskkonnaagentuur kliimaandmestik (f_kliima_kuu DPREC 1991-2020; serveeritakse harvested rakkudest, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see KLIIMA_NO_RASTER). */
export const KLIIMA_RASTER_FILE: Record<KliimaLayerId, string> = {
  kliima_frost: "kliima-frost-cell-raster.json",
  kliima_wet: "kliima-wet-cell-raster.json",
};

/**
 * NO raster master (documented): the points-splat quality kernel IS the
 * field. A 75 m county stamp of 3 coarse cells would be honest slabs
 * plus county-wide unknown — the nearest-wins splat already renders
 * exactly that from KLIIMA_CELLS, so a master would add build
 * machinery without meaning. The window route serves 500 for these
 * layers and the client falls back to the splat (designed path,
 * tervise precedent).
 */
export const KLIIMA_NO_RASTER = true;

/**
 * Euclidean fallback decay in km (== the 70 km join radius: the scale
 * story is the county-wide coarse cell, same as the kernel).
 */
export const KLIIMA_DECAY: Record<KliimaLayerId, number> = {
  kliima_frost: 70.0,
  kliima_wet: 70.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isKliimaLayerId(layer: LayerId): layer is KliimaLayerId {
  return (KLIIMA_LAYER_IDS as string[]).includes(layer);
}

/** Slice key for a kliima layer id (frost vs wetness legs). */
export function kliimaSliceFor(layer: KliimaLayerId): KliimaSlice {
  return layer === "kliima_wet" ? "wet" : "frost";
}

/** Quality-band spec for the kliima layers (called from the bonusSpecFor hook). */
export function kliimaBonusSpecFor(layer: KliimaLayerId): BonusSpec {
  void layer;
  return { kind: "qbands", radiusM: KLIIMA_RADIUS_M };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function kliimaHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface KliimaCell {
  code: string;
  lat: number;
  lon: number;
  /** Mean annual frost days 1991-2020 (null = normals too thin). */
  frostDays: number | null;
  /** Mean annual precipitation mm 1991-2020 (null = normals too thin). */
  precipMm: number | null;
  /** Rank band 70/55/40 across joined cells (null = unranked). */
  frostBand: number | null;
  /** Rank band 70/40 across joined cells (null = unranked). */
  wetBand: number | null;
}

/**
 * Nearest station cell within the hard county radius, nearest first
 * (pure). No averaging, no smoothing — mirrors the qbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function kliimaNearby(
  lat: number,
  lon: number,
  cells: KliimaCell[],
  radiusM: number = KLIIMA_RADIUS_M,
): { cell: KliimaCell; distM: number }[] {
  const out: { cell: KliimaCell; distM: number }[] = [];
  for (const cell of cells) {
    if (!Number.isFinite(cell.lat) || !Number.isFinite(cell.lon)) continue;
    const distM = kliimaHavKm(lon, lat, cell.lon, cell.lat) * 1000;
    if (distM <= radiusM) out.push({ cell, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Normatiiv-hinnang at one address: the NEAREST cell's slice band,
 * null where no cell covers the address or the nearest cell's slice
 * band is NULL (unknown, never zero, never a faked score — the scorer
 * reads the same gap as NULL).
 */
export function kliimaBandAt(
  lat: number,
  lon: number,
  slice: KliimaSlice,
  cells: KliimaCell[],
  radiusM: number = KLIIMA_RADIUS_M,
): number | null {
  const near = kliimaNearby(lat, lon, cells, radiusM);
  if (near.length === 0) return null;
  const band = slice === "wet" ? near[0].cell.wetBand : near[0].cell.frostBand;
  return typeof band === "number" && Number.isFinite(band) ? band : null;
}

/**
 * Extract cells clipped to the view bbox, stamped with the slice band
 * as q (same LayerPoint contract as tervisePointsIn). Unranked cells
 * ride WITHOUT q: plotted for location, never scored (the qbands
 * kernel renders nearest-q-absent as unknown — byte parity with the
 * scorer's EI OLE on the same gap).
 */
export function kliimaPointsIn(
  cells: KliimaCell[],
  slice: KliimaSlice,
  bbox: BBoxLike,
): LayerPoint[] {
  return cells
    .filter(
      (c) =>
        c.lon >= bbox.minlon &&
        c.lon <= bbox.maxlon &&
        c.lat >= bbox.minlat &&
        c.lat <= bbox.maxlat,
    )
    .map((c): LayerPoint => {
      const band = slice === "wet" ? c.wetBand : c.frostBand;
      return typeof band === "number" && Number.isFinite(band)
        ? { lat: c.lat, lon: c.lon, q: band }
        : { lat: c.lat, lon: c.lon };
    });
}

// KLIIMA-CELLS-BEGIN (regenerate with scripts/build/batch_kliima.py, never hand-edit).
export const KLIIMA_CELLS: KliimaCell[] = [
  { code: "AJHARK01", lat: 59.398122, lon: 24.60287, frostDays: 128.6, precipMm: 699.9, frostBand: 55, wetBand: 70 },
  { code: "AJPAKR01", lat: 59.3895, lon: 24.0401, frostDays: 106.5, precipMm: null, frostBand: 70, wetBand: null },
  { code: "AJKUUS01", lat: 58.9732, lon: 24.734, frostDays: 146.5, precipMm: 730.1, frostBand: 40, wetBand: 40 },
];
// KLIIMA-CELLS-END
