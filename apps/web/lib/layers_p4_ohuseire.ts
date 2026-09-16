// Keskkonnaagentuur official air-station dots overlay (issue #610;
// P4-031 official-register slice from
// services/scoring/dims_p4_ohuseire.py). This file owns ALL ohuseire
// runtime data; shared files (lib/layers.ts, lib/overlays.ts,
// lib/server/snapshot.ts, app/api/layers/[layer]/route.ts,
// app/layers/page.tsx) touch it only through small marked
// `OHUSEIRE-HOOK (#610)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// FEED VERDICT (2026-09-16, polite one-off round, custom UA
// `home-finder-research/0.1`, single GETs, no retries; aggregates only,
// raw bodies never committed — full evidence in docs/p4_ohuseire.md):
// keskkonnaandmed.envir.ee is a keyless PostgREST 12.0.1 endpoint;
// the air-programme slice (sr_programm_nimi ilike *õhu* — the õ is
// load-bearing: plain *ohu* also matches "ohustatud" plant
// communities, 360 wrong rows, caught live and never shipped) returns
// 90 rows, 42 with coords. Harvest scripts/build/batch_ohuseire.py
// (weekly TTL, paced, 429 = stop) keeps Kasutusel rows whose own
// admin label names Tallinn and whose converted coords fall in the
// Tallinn bbox: 3 stations — Tallinn Rahu (59.44729, 24.71513),
// Tallinn Liivalaia (59.43107, 24.76032), Tallinn Õismäe (59.41413,
// 24.64922); 39 skipped + 48 coordless, all counted. Station coords
// are L-EST97 metres projected offline (PROJ-agreement <0.01 m per the
// scorer docs, labelled `teisendatud`).
//
// THINNESS (load-bearing, maintainer decision): 3 stations for the
// whole county — the layer ships thin as-is. NO interpolation (a
// reference inlet 5 km away says nothing about the balcony), NO
// raster master (see OHUSEIRE_NO_RASTER), NO metro master. The map
// kernel is the FLAT district band below: nearest station within
// 2 km -> 60, beyond NULL. DIVERGENCE (documented, never hidden): the
// scorer refines 2+ stations in radius to 70 (dims _band_density);
// the map renders 60 for any in-radius witness — with 3 county
// stations the 2-in-2km case is rare, and the legend states that the
// 70 lives scorer-side only. DIY sensor.community stations stay
// untouched (dims_p4_senscom.py is never re-scored here; reasons
// cross-reference the DIY leg).
//
// HONESTY: reference stations interpolate across districts, so this
// is a coarse 2 km district-coverage hinnang (never a calibrated
// measurement, never a doorstep value, never heating truth —
// courtyard air stays the buyer check). Points come from the snapshot
// sidecar (ohuseire/ohuseire-points.json: {vintage, counts, points},
// built by the harvester, served by loadOhuseirePoints in
// lib/server/snapshot.ts) — NEVER from the 2026-09-12 OSM snapshot
// and never live (no network in the map path).
//
// Overlap (documented): P4-031 is shared with the DIY senscom leg by
// scorer design — distinct slices (official_air_ohuseire vs DIY),
// distinct dim keys, no double-score of one signal.
//
// The layer carries NO parameters3.md id: P4-031 is a parameters4
// buyer param (sport #607 / ehis #608 / medre #609 precedent).
// paramIds stays [] and paramLabel carries the slice ("P4-031") for
// the layer button.

import type { BBoxLike, BonusSpec, LayerDef, LayerId } from "./layers";

export type OhuseireLayerId = "ohuseire";

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const OHUSEIRE_PARAM_LABEL = "P4-031";

/**
 * Dated harvest this layer rests on (see header). The Python builder
 * (scripts/build/batch_ohuseire.py) and the 2026-09-16 pull agree: 90
 * fetched rows -> 42 with coords -> 3 Tallinn stations (39 skipped).
 */
export const OHUSEIRE_PROBE = {
  date: "2026-09-16",
  fetchedRows: 90,
  stations: ["Tallinn Rahu", "Tallinn Liivalaia", "Tallinn Õismäe"],
} as const;

/** Vintage label stamped on the sidecar build (weekly feed, 7 d TTL). */
export const OHUSEIRE_VINTAGE = "2026-09-16";

/**
 * Flat district band in metres — the scorer's 1-station leg restated:
 * changing services/scoring/dims_p4_ohuseire.py without changing this
 * (or vice versa) is a drift bug, pinned by test on both sides. The
 * scorer's 2+ -> 70 refinement lives scorer-side only (see header).
 */
export const OHUSEIRE_EDGES_M: ReadonlyArray<readonly [number, number]> = [
  [2000, 60],
];

/**
 * Hard join radius in metres — the district window (reference inlets
 * interpolate, balconies do not). Most of the county renders unknown
 * by honesty.
 */
export const OHUSEIRE_RADIUS_M = 2000;

export interface OhuseirePoint {
  lat: number;
  lon: number;
  name: string;
}

export const OHUSEIRE_LAYERS: LayerDef[] = [
  {
    id: "ohuseire",
    paramIds: [],
    paramLabel: OHUSEIRE_PARAM_LABEL,
    title: "Õhuseire jaamad (ametlik, hinnang)",
    goodLabel:
      "roheline = ametlik seirejaam 2 km raadiuses (piirkonna-hinnang, mitte mõõtmine)",
    badLabel:
      "punane = jaam 2 km raadiuses puudu VÕI andmed teadmata (ainult 3 jaama Harjumaal)",
    source:
      "Keskkonnaagentuuri seirejaamade register (keskkonnaandmed avaandmed, võtmeta PostgREST, seis 2026-09-16; 90 õhuvalimi kirjet, 3 Tallinna jaama: Rahu / Liivalaia / Õismäe; L-EST97->WGS84 pooramine; kauguse-hinnang 2 km linnaosa aknas, mitte kalibreeritud mõõtmine ega küte-tõde)",
    fallbackPoints: [{ lat: 59.44729, lon: 24.71513 }],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — register data is
 * not OSM data; inventing man_made=monitoring_station plumbing would
 * be dishonest, paaste #493 precedent). overpassQueryFor("ohuseire")
 * is never called in production; the string only satisfies the
 * registry shape.
 */
export const OHUSEIRE_TAGS: Record<OhuseireLayerId, string> = {
  ohuseire:
    "Keskkonnaagentuuri päritolu märkus (välisõhu seireprogramm, Tallinna väljavõte 3 jaama), mitte Overpass-päring.",
};

/** Raster master filename (intentionally never built — see OHUSEIRE_NO_RASTER). */
export const OHUSEIRE_RASTER_FILE: Record<OhuseireLayerId, string> = {
  ohuseire: "ohuseire-walk-raster.json",
};

/**
 * NO raster master (documented): 3 county stations bake to three
 * discs plus county-wide unknown either way, and the points-splat
 * distance kernel IS the field. The window route serves 500 and the
 * client falls back to the splat (designed path, senscom precedent).
 */
export const OHUSEIRE_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the window route is
 * skipped by the generic dbands short-circuit and empty windows serve
 * county everywhere (sport #607 precedent).
 */
export const OHUSEIRE_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 2 km district window, same
 * as the kernel).
 */
export const OHUSEIRE_DECAY: Record<OhuseireLayerId, number> = {
  ohuseire: 2.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isOhuseireLayerId(layer: LayerId): layer is OhuseireLayerId {
  return layer === "ohuseire";
}

/**
 * Flat district-band spec (called from the bonusSpecFor hook).
 * Reuses the sport #607 dbands kernel — no new spec kind.
 */
export function ohuseireBonusSpecFor(_layer: OhuseireLayerId): BonusSpec {
  void _layer;
  return {
    kind: "dbands",
    radiusM: OHUSEIRE_RADIUS_M,
    edges: OHUSEIRE_EDGES_M.map(([m, b]) => [m, b] as [number, number]),
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function ohuseireHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/**
 * Band for a distance in metres (pure) — flat 60 in radius, null
 * beyond (never zero). The scorer's 2+ -> 70 lives scorer-side only.
 */
export function ohuseireBandAt(distM: number): number | null {
  for (const [edgeM, band] of OHUSEIRE_EDGES_M) {
    if (distM <= edgeM) return band;
  }
  return null;
}

/**
 * Nearest station within the hard radius, nearest first (pure). No
 * averaging, no smoothing — mirrors the dbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function ohuseireNearby(
  lat: number,
  lon: number,
  points: OhuseirePoint[],
  radiusM: number = OHUSEIRE_RADIUS_M,
): { point: OhuseirePoint; distM: number }[] {
  const out: { point: OhuseirePoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = ohuseireHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Stations inside a bbox (pure) — the route serves these from the
 * snapshot sidecar (never the OSM snapshot, never live).
 */
export function ohuseirePointsIn(
  points: OhuseirePoint[],
  bbox: BBoxLike,
): { lat: number; lon: number }[] {
  return points
    .filter(
      (p) =>
        p.lon >= bbox.minlon &&
        p.lon <= bbox.maxlon &&
        p.lat >= bbox.minlat &&
        p.lat <= bbox.maxlat,
    )
    .map((p) => ({ lat: p.lat, lon: p.lon }));
}
