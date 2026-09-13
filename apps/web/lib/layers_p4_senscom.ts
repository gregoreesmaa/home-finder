// P4-031 sensor.community DIY-air overlay (parameters4.md P4-031 slice,
// issue #484, Group A POSITIVE verdict docs/p4_senscom.md): sensor points
// + hard-radius witness-count band kernel for /layers. This file owns ALL
// senscom overlay runtime data; shared files (lib/layers.ts,
// lib/distanceField.ts, lib/overlays.ts, lib/server/snapshot.ts,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `P4-031-HOOK (#484)` blocks, so sibling batches
// stay disjoint (sibling Layer issues #479-#483/#485-#495 own different
// files, different ids, different params).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): uncalibrated citizen sensors say which blocks
// have local witnesses, never what a balcony measures — and they say
// nothing about heating truth (EHR kütte liik stays unjoined). The map
// kernel is the EXACT scorer band function from
// services/scoring/dims_p4_senscom.py (1 witness <=500 m -> 60, 2-3 ->
// 70, 4+ -> 80 cap 80), so map colors and scored reasons agree by
// construction. The cutoff is HARD (haversine <= 500 m, no Gaussian
// smoothing — a DIY sensor 2 km away says nothing about the backyard,
// so smoothing would fake a gradient between watched balconies). Zero
// witnesses in radius stays null/255 (renders red, never a faked
// score) — the scorer reads the same gap as NULL with an Estonian
// reason (hinnang + EI OLE, pinned by test_dims_p4_senscom.py; scored
// reasons say hinnang and never EI OLE, same invariant).
//
// Points come from the sensor.community Tallinn extract
// (sensor-community-tallinn.json: {fetched, bbox, sensors, n_sensors},
// built by the dims_p4_senscom operator step, served by
// lib/server/senscom.ts) — NEVER from the 2026-09-12 OSM snapshot
// (DIY sensors are not OSM features) and never live (no network in the
// map path). No raster master exists BY DOCUMENTED DECISION (see
// SENSCOM_NO_RASTER): the network is thin (1 Tallinn location on
// 2026-09-13) and the points-splat band kernel IS the field.
//
// Per-slice verdicts (see also services/scoring/dims_p4_senscom.py):
//   P4-031 DIY density slice -> senscom overlay (this file, SCORES).
//   P4-031 Harku city baseline -> dims_p4_ilm (documented NULL).
//   P4-031 EHR heating truth -> dims_p4_ehr (kütte-liik echo, no map).
//   P4-031 LiDAR frost screen -> dims_p4_maa_lidar (no map here).
//   P4-031 KAUR met/wind density -> dims_p4_kaur (reference stations).
//
// Calibration (judgment calls, documented for the reviewer): the radius
// (500 m) and the bands (60/70/80) are byte-parity copies of
// SENSCOM_RADIUS_M / _band_density in dims_p4_senscom.py — changing the
// scorer without changing SENSCOM_BANDS (or vice versa) is a drift bug,
// pinned by the parity test in layers_p4_senscom.test.ts. One location
// id = one witness (dedup happens in parse_senscom_dump, the server
// serves extract rows as-is).
//
// The layer carries NO parameters3.md id: parameters3 p31 is
// "Structural integrity" (inspection group, documented no-map) and
// must NOT gain a map by accident. paramIds stays [] and paramLabel
// carries the buyer-param slice ("P4-031") for the layer button.

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type SenscomLayerId = "senscom";

export const SENSCOM_LAYER_IDS: SenscomLayerId[] = ["senscom"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const SENSCOM_PARAM_LABEL = "P4-031";

/**
 * Hard join radius in metres — byte parity with SENSCOM_RADIUS_M in
 * services/scoring/dims_p4_senscom.py (frost pockets are sub-block
 * facts; tighter than KAUR's 2 km on purpose).
 */
export const SENSCOM_RADIUS_M = 500;

/**
 * Witness-count bands — byte parity with _band_density in
 * services/scoring/dims_p4_senscom.py (capped: DIY proxy never earns
 * 100; thin network is unknown, never good).
 */
export const SENSCOM_BANDS = { one: 60, twoThree: 70, fourPlus: 80 } as const;

const EXTRACT = "sensor.community Tallinna väljavõte (DIY-välisandurid)";

export const SENSCOM_LAYERS: LayerDef[] = [
  {
    id: "senscom",
    paramIds: [],
    paramLabel: SENSCOM_PARAM_LABEL,
    title: "Hooviõhk (DIY-andurid, hinnang)",
    goodLabel: "roheline = mitu naabrusseire andurit lähedal (jälgitud kvartal, hinnang)",
    badLabel: "punane = DIY-välisandur 500 m raadiuses puudu (tundmatu, hinnangut pole)",
    source: `${EXTRACT} (kalibreerimata rahvaandurite tihedushinnang, mitte hoovi mõõtmine; Harku linnabaas, EHR kütte liik ja DEM-külmanõo sõel pole selles kihis)`,
    fallbackPoints: [
      // 2026-09-13 observed Tallinn location, DEMO fallback only (real
      // extract rows are served from the extract, never committed).
      { lat: 59.38, lon: 24.642 }, // Õismäe DIY-välisandur (demo)
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (anduriteta demo-taust)
    ],
  },
];

/**
 * Overpass QL fragment (documents the source vocabulary; the extract —
 * not Overpass — serves this layer, so the map path never fetches live.
 * overpassQueryFor("senscom") is never called in production).
 */
export const SENSCOM_TAGS: Record<SenscomLayerId, string> = {
  senscom: "sensor.community static/v2/data.json Tallinna väljavõte (DIY-välisandurid; serveeritakse vahemälu väljavõttest, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see SENSCOM_NO_RASTER). */
export const SENSCOM_RASTER_FILE: Record<SenscomLayerId, string> = {
  senscom: "senscom-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat band kernel IS the
 * field. A 75 m county stamp of a one-sensor network would be one
 * honest disc plus county-wide unknown — the splat already renders
 * exactly that from the extract rows, so a master would add build
 * machinery without meaning. The window route serves 500 for this
 * layer and the client falls back to the splat (designed path).
 */
export const SENSCOM_NO_RASTER = true;

/**
 * Euclidean fallback decay (same scale story as the 500 m join radius):
 * only feeds sigmaKm where a sigma is required; the band kernel itself
 * counts inside the hard radius (see the "bands" branch).
 */
export const SENSCOM_DECAY_KM: Record<SenscomLayerId, number> = {
  senscom: 0.5,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isSenscomLayerId(layer: LayerId): layer is SenscomLayerId {
  return (SENSCOM_LAYER_IDS as string[]).includes(layer);
}

/** Band spec for the senscom layer (called from the bonusSpecFor hook). */
export function senscomBonusSpecFor(layer: SenscomLayerId): BonusSpec {
  void layer;
  return {
    kind: "bands",
    radiusM: SENSCOM_RADIUS_M,
    one: SENSCOM_BANDS.one,
    twoThree: SENSCOM_BANDS.twoThree,
    fourPlus: SENSCOM_BANDS.fourPlus,
  };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function senscomHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface SenscomPoint {
  lat: number;
  lon: number;
}

/**
 * Band for a witness count — byte parity with _band_density in
 * services/scoring/dims_p4_senscom.py. Null when nothing watches the
 * backyard: unknown, never zero, never good.
 */
export function senscomBandForCount(n: number): number | null {
  if (!Number.isFinite(n) || n <= 0) return null;
  if (n <= 1) return SENSCOM_BANDS.one;
  if (n <= 3) return SENSCOM_BANDS.twoThree;
  return SENSCOM_BANDS.fourPlus;
}

/**
 * DIY witnesses within the hard backyard radius, nearest first (pure).
 * No averaging, no smoothing — mirrors _nearby in
 * services/scoring/dims_p4_senscom.py (same hard cutoff, same order).
 */
export function senscomNearby(
  lat: number,
  lon: number,
  points: SenscomPoint[],
  radiusM: number = SENSCOM_RADIUS_M,
): { point: SenscomPoint; distM: number }[] {
  const out: { point: SenscomPoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = senscomHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Band hinnang 60/70/80 at one address, null where no DIY witness
 * watches the backyard (the scorer reads the same gap as NULL with
 * hinnang + EI OLE + buyer-side check — never a faked score).
 */
export function senscomBandAt(
  lat: number,
  lon: number,
  points: SenscomPoint[],
  radiusM: number = SENSCOM_RADIUS_M,
): number | null {
  return senscomBandForCount(senscomNearby(lat, lon, points, radiusM).length);
}
