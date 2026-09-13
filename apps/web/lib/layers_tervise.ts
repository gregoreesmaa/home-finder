// Terviseamet bathing-water (suplusvesi) monitoring-point overlay
// (issue #494, P4-024 Terviseamet slice; Group B verify-first POSITIVE
// verdict docs/p4_tervise.md §"Layer re-check #494 (XML overturn)").
// This file owns ALL tervise overlay runtime data; shared files
// (lib/layers.ts, lib/distanceField.ts, lib/overlays.ts,
// lib/server/snapshot.ts, app/api/layers/[layer]/route.ts,
// app/layers/page.tsx) touch it only through small marked
// `TERVISE-HOOK (#494)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// FEED VERDICT CORRECTION (2026-09-14, polite harvest, custom UA
// `home-finder-494-tervise-xml/1.0`, paced single GETs, HTTP 429 as
// stop, raw XML in /tmp/hf-494-xml only — never committed): PR #510's
// "no machine feed" verdict is WRONG for the bathing-water slice. The
// vtiav.sm.ee "Avaandmed" JS tab serves bulk yearly XML + XSD + PDF per
// dataset. Harvest tally:
//   supluskohad.xml                 HTTP 200, 313862 B, 211 <supluskoht>
//   supluskoha_veeproovid_2026.xml  HTTP 200, 918975 B, 758 <proovivott>
//   supluskoha_veeproovid_2025.xml  HTTP 200, 931177 B, 793 <proovivott>
//   supluskohad.xsd                 HTTP 200, 5325 B (schema, no CRS tag)
// 211 sites -> 205 plotted, 6 dropped (no <x>/<y>), 37 quality-NULL.
// Pirita rand (119), Stroomi/Pelgurand (120) and Kakumae rand (118) all
// present. The P4-017 drinking-water slice stays human-only (per-veevark
// lookup UI, no bulk export) — its scorer dim stays NULL (OTA PR #131
// precedent, dims_p4_tervise.py untouched).
//
// TRANSFORM (labeled, reviewable): <x>/<y> are L-EST97 metres (EPSG:3301
// — x northing ~6.4-6.6M, y easting ~0.37-0.74M; magnitudes + the #490
// Transpordiamet family precedent; the XSD names no CRS). Projected by
// scripts/build/batch_tervise.py lest97_to_wgs84 (inverse Lambert
// Conformal Conic 2SP, Maa-amet/EPSG constants, stdlib only): the math
// is exact, the GRS80(ETRS89)~WGS84 datum gap drifts ~1 m, so every
// point below is honest to ~1 m. Verified 2026-09-14 two independent
// ways: (1) pyproj EPSG:3301->EPSG:4326 agrees to <1 mm on all 320 feed
// coordinates; (2) Pirita/Stroomi/Kakumae land on their beaches.
//
// HONESTY (load-bearing): per-point quality q is the coarse P4-024 band
// (80 vaga hea / 70 hea or passing latest sample / 60 piisav or unknown
// / 45 kesine / 30 halb or failing latest sample; cap 80 — amenity
// proximity is never 100). A fresh "ei vasta noutele" sample caps the
// band at 30 with its date (dated negative evidence beats an older
// class — e.g. Anne kanal 25.08.2026); a single passing sample never
// lifts a seasonal class (Laulasmaa keeps 2025-Halb 30 despite a passing
// 2026 sample — EU classes are multi-year). q absent = quality NULL
// (plotted for location, never scored as a middle). The kernel below is
// the NEAREST site's band inside a hard 1 km radius (no smoothing — a
// beach 2 km away says nothing about the backyard); no site in radius
// stays null/255 (renders red, never a faked score).
//
// Points come from the committed project below (built offline by
// scripts/build/batch_tervise.py from the /tmp harvest — NEVER from the
// 2026-09-12 OSM snapshot, bathing sites are not OSM features) and
// never live (no network in the map path). No raster master exists BY
// DOCUMENTED DECISION (see TERVISE_NO_RASTER): 205 sparse points bake
// to discs-plus-unknown either way, and the points-splat quality kernel
// IS the field. Names/addresses never leave the module (TAG_ALLOWLIST
// precedent — the wire carries lat/lon/q only).
//
// Calibration (judgment calls, documented for the reviewer): radius 1 km
// (walkable-to-the-beach scale; sparser than senscom's 500 m on purpose
// — 211 sites nationwide, ~10 in the Tallinn window, so most of the
// city honestly renders unknown) and the GRADE_BANDS parity with
// batch_tervise.py quality_band (changing the builder without changing
// TERVISE_POINTS, or vice versa, is a drift bug — pinned by the probe
// test in layers_tervise.test.ts).
//
// The layer carries NO parameters3.md id: P4-024 is a parameters4 buyer
// param (senscom #484 precedent). paramIds stays [] and paramLabel
// carries the slice ("P4-024") for the layer button.

import type { BBoxLike, BonusSpec, LayerDef, LayerId, LayerPoint } from "./layers";

export type TerviseLayerId = "tervise";

export const TERVISE_LAYER_IDS: TerviseLayerId[] = ["tervise"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const TERVISE_PARAM_LABEL = "P4-024";

/**
 * Dated harvest this layer rests on (see header). The Python builder
 * (scripts/build/batch_tervise.py) and its pytest pin the same numbers,
 * so the two sides cannot silently disagree.
 */
export const TERVISE_PROBE = {
  date: "2026-09-14",
  sitesXmlBytes: 313862,
  sites: 211,
  samples2026: 758,
  samples2025: 793,
  plotted: 205,
  droppedNoCoord: 6,
} as const;

/** Vintage label stamped on the build (yearly feed). */
export const TERVISE_VINTAGE = "2026-09-14";

/**
 * Hard join radius in metres — walkable-to-the-beach scale (see header
 * calibration note). Most of the city renders unknown by honesty.
 */
export const TERVISE_RADIUS_M = 1000;

export const TERVISE_LAYERS: LayerDef[] = [
  {
    id: "tervise",
    paramIds: [],
    paramLabel: TERVISE_PARAM_LABEL,
    title: "Suplusvee seirepunktid (mõõdetud, hinnang)",
    goodLabel:
      "roheline = väga hea suplusvesi 1 km raadiuses (seire-hinnang, lagi 80 — lähedus, mitte tervisetõde)",
    badLabel:
      "punane = hea supluskoht 1 km raadiuses puudu, vesi halb/kesine VÕI kvaliteet teadmata",
    source:
      "Terviseameti vtiav.sm.ee avaandmed (supluskohad.xml 211 kirjet + 2025/2026 veeproovid 1551 kirjet, seis 2026-09-14; L-EST97->WGS84 pooramine ~1 m tapsusega; 6 punkti koordinaatideta joonistamata, 37 punkti kvaliteet teadmata ehk hinnangut pole; joogivee seire (P4-017) masinloetava voona puudub)",
    fallbackPoints: [
      // Projected register rows, DEMO fallback only (real points are
      // served from TERVISE_POINTS below, never committed twice).
      { lat: 59.47215, lon: 24.830954, q: 80 }, // Pirita rand (demo)
      { lat: 59.442513, lon: 24.683935, q: 80 }, // Stroomi rand (demo)
    ],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — Terviseamet data is
 * not OSM data; inventing leisure=beach plumbing would be dishonest,
 * paaste #493 precedent). overpassQueryFor("tervise") is never called
 * in production; the string only satisfies the registry shape.
 */
export const TERVISE_TAGS: Record<TerviseLayerId, string> = {
  tervise:
    "Terviseamet vtiav.sm.ee avaandmed (supluskohad.xml + supluskoha_veeproovid_2025/2026.xml; serveeritakse projekteeritud valjavottest, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see TERVISE_NO_RASTER). */
export const TERVISE_RASTER_FILE: Record<TerviseLayerId, string> = {
  tervise: "tervise-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat quality kernel IS the
 * field. A 75 m county stamp of 205 sparse points would be honest
 * discs plus county-wide unknown — the splat already renders exactly
 * that from TERVISE_POINTS, so a master would add build machinery
 * without meaning. The window route serves 500 for this layer and the
 * client falls back to the splat (designed path, senscom precedent).
 */
export const TERVISE_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only, like the senscom bands
 * layer — the window route is skipped by the generic qbands
 * short-circuit and empty windows serve county everywhere.
 */
export const TERVISE_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 1 km join radius: the scale
 * story is the walkable-to-the-beach window, same as the kernel).
 */
export const TERVISE_DECAY: Record<TerviseLayerId, number> = {
  tervise: 1.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isTerviseLayerId(layer: LayerId): layer is TerviseLayerId {
  return (TERVISE_LAYER_IDS as string[]).includes(layer);
}

/** Quality-band spec for the tervise layer (called from the bonusSpecFor hook). */
export function terviseBonusSpecFor(layer: TerviseLayerId): BonusSpec {
  void layer;
  return { kind: "qbands", radiusM: TERVISE_RADIUS_M };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function terviseHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface TervisePoint {
  lat: number;
  lon: number;
  /** Coarse P4-024 band (absent = quality NULL, never a faked middle). */
  q?: number;
}

/**
 * Nearest monitored site within the hard beach radius, nearest first
 * (pure). No averaging, no smoothing — mirrors the qbands kernel in
 * distanceField.ts (same hard cutoff, same nearest rule).
 */
export function terviseNearby(
  lat: number,
  lon: number,
  points: TervisePoint[],
  radiusM: number = TERVISE_RADIUS_M,
): { point: TervisePoint; distM: number }[] {
  const out: { point: TervisePoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = terviseHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Quality hinnang at one address: the NEAREST site's band, null where
 * no site covers the address or the nearest site's quality is NULL
 * (unknown, never zero, never a faked score).
 */
export function terviseBandAt(
  lat: number,
  lon: number,
  points: TervisePoint[],
  radiusM: number = TERVISE_RADIUS_M,
): number | null {
  const near = terviseNearby(lat, lon, points, radiusM);
  if (near.length === 0) return null;
  const q = near[0].point.q;
  return typeof q === "number" && Number.isFinite(q) ? q : null;
}

/** Extract points clipped to the view bbox (same inBBox contract as senscom). */
export function tervisePointsIn(points: TervisePoint[], bbox: BBoxLike): LayerPoint[] {
  return points.filter(
    (p) =>
      p.lon >= bbox.minlon && p.lon <= bbox.maxlon && p.lat >= bbox.minlat && p.lat <= bbox.maxlat,
  );
}

/**
 * Measured bathing-site points in WGS84 (205 sites, vintage
 * 2026-09-14). Built offline by scripts/build/batch_tervise.py from the
 * /tmp harvest (labels + addresses never leave the builder — the wire
 * carries lat/lon/q only). Regenerate, never hand-edit.
 */
export const TERVISE_POINTS: LayerPoint[] = [
  { lat: 59.574424, lon: 25.527142, q: 80 },
  { lat: 58.943582, lon: 23.52377 },
  { lat: 59.437881, lon: 27.151374, q: 80 },
  { lat: 59.312967, lon: 27.04693, q: 80 },
  { lat: 58.741654, lon: 26.246799, q: 80 },
  { lat: 58.529208, lon: 26.947537, q: 80 },
  { lat: 59.006706, lon: 27.425509, q: 80 },
  { lat: 58.600289, lon: 27.133771, q: 80 },
  { lat: 59.243582, lon: 25.331185, q: 70 },
  { lat: 59.269835, lon: 23.762438, q: 80 },
  { lat: 59.498079, lon: 25.455739, q: 80 },
  { lat: 58.378265, lon: 26.740583, q: 30 },
  { lat: 59.069179, lon: 26.262034, q: 80 },
  { lat: 58.225239, lon: 26.416314, q: 80 },
  { lat: 59.206349, lon: 23.500495 },
  { lat: 58.694516, lon: 25.736632, q: 80 },
  { lat: 58.392277, lon: 26.711306, q: 70 },
  { lat: 58.394526, lon: 26.704559, q: 70 },
  { lat: 59.511561, lon: 24.814908, q: 80 },
  { lat: 59.414259, lon: 24.632634, q: 80 },
  { lat: 58.273325, lon: 25.691885, q: 80 },
  { lat: 59.494447, lon: 25.174703, q: 80 },
  { lat: 58.362977, lon: 26.762776 },
  { lat: 58.562681, lon: 23.08543, q: 80 },
  { lat: 59.444979, lon: 24.792305 },
  { lat: 59.331047, lon: 25.343108, q: 80 },
  { lat: 59.141909, lon: 24.932846 },
  { lat: 59.041022, lon: 25.876089, q: 80 },
  { lat: 58.599425, lon: 22.772516, q: 80 },
  { lat: 58.000994, lon: 26.398451 },
  { lat: 58.061916, lon: 26.528175, q: 80 },
  { lat: 59.506245, lon: 25.286583, q: 80 },
  { lat: 58.011768, lon: 24.446498, q: 80 },
  { lat: 59.448287, lon: 24.574426, q: 80 },
  { lat: 59.241295, lon: 25.680158, q: 80 },
  { lat: 58.667983, lon: 27.167141, q: 80 },
  { lat: 58.238752, lon: 26.704745, q: 80 },
  { lat: 57.909726, lon: 26.981899 },
  { lat: 59.190021, lon: 25.767203, q: 80 },
  { lat: 59.005858, lon: 22.758599, q: 80 },
  { lat: 59.006969, lon: 22.744837, q: 80 },
  { lat: 59.547597, lon: 26.414389, q: 60 },
  { lat: 59.041068, lon: 25.954106 },
  { lat: 59.002337, lon: 25.022496 },
  { lat: 59.009073, lon: 27.488502, q: 80 },
  { lat: 58.110809, lon: 25.546839 },
  { lat: 58.378244, lon: 22.229112, q: 80 },
  { lat: 58.517468, lon: 27.239479, q: 80 },
  { lat: 58.779167, lon: 22.825192, q: 80 },
  { lat: 58.98884, lon: 27.229665, q: 80 },
  { lat: 59.554124, lon: 24.838523 },
  { lat: 58.262685, lon: 26.331879, q: 80 },
  { lat: 58.136909, lon: 27.010833 },
  { lat: 57.68144, lon: 27.248103, q: 80 },
  { lat: 59.318284, lon: 24.242197, q: 80 },
  { lat: 59.346626, lon: 24.242915, q: 60 },
  { lat: 59.17041, lon: 24.755654 },
  { lat: 59.39885, lon: 27.268269, q: 80 },
  { lat: 58.52485, lon: 27.075275, q: 60 },
  { lat: 58.32739, lon: 25.311604, q: 80 },
  { lat: 58.420984, lon: 26.765233, q: 60 },
  { lat: 58.424329, lon: 26.768193, q: 30 },
  { lat: 57.81221, lon: 27.003143, q: 80 },
  { lat: 58.33345, lon: 26.597322, q: 80 },
  { lat: 59.520349, lon: 26.538077, q: 80 },
  { lat: 58.733361, lon: 26.533569, q: 80 },
  { lat: 58.317601, lon: 26.822838, q: 70 },
  { lat: 58.2453, lon: 22.4772, q: 80 },
  { lat: 57.722551, lon: 27.01072, q: 80 },
  { lat: 58.242221, lon: 26.819401, q: 80 },
  { lat: 57.859405, lon: 27.175208, q: 80 },
  { lat: 59.374024, lon: 24.235242, q: 30 },
  { lat: 59.367466, lon: 24.140478, q: 60 },
  { lat: 59.435742, lon: 26.988775, q: 80 },
  { lat: 58.709905, lon: 22.484579, q: 80 },
  { lat: 59.394693, lon: 24.214757, q: 70 },
  { lat: 59.579033, lon: 25.708118, q: 80 },
  { lat: 58.935027, lon: 22.388549, q: 80 },
  { lat: 58.355424, lon: 26.883143, q: 80 },
  { lat: 59.450619, lon: 24.994464, q: 80 },
  { lat: 57.893094, lon: 27.010484, q: 80 },
  { lat: 59.209423, lon: 24.580919, q: 80 },
  { lat: 58.366092, lon: 24.525706, q: 80 },
  { lat: 58.211467, lon: 22.321463, q: 80 },
  { lat: 59.034144, lon: 22.573811, q: 80 },
  { lat: 58.34903, lon: 25.465371 },
  { lat: 59.345052, lon: 24.709051 },
  { lat: 59.061175, lon: 25.51293, q: 80 },
  { lat: 58.327945, lon: 26.973392, q: 80 },
  { lat: 59.399857, lon: 24.250407 },
  { lat: 58.546993, lon: 27.094356, q: 80 },
  { lat: 57.615785, lon: 26.614311, q: 80 },
  { lat: 58.158217, lon: 27.185371, q: 80 },
  { lat: 59.372699, lon: 28.202506, q: 80 },
  { lat: 59.453853, lon: 28.024626, q: 70 },
  { lat: 59.463421, lon: 28.046488, q: 80 },
  { lat: 59.365301, lon: 28.16604, q: 80 },
  { lat: 59.273478, lon: 25.629484, q: 80 },
  { lat: 58.611102, lon: 27.199667, q: 70 },
  { lat: 59.244278, lon: 27.550457, q: 80 },
  { lat: 58.274255, lon: 26.52402, q: 80 },
  { lat: 58.1297, lon: 26.521479 },
  { lat: 58.148125, lon: 25.983238 },
  { lat: 58.203266, lon: 25.532536 },
  { lat: 57.888921, lon: 27.453443, q: 80 },
  { lat: 58.993349, lon: 23.50711 },
  { lat: 58.814796, lon: 26.540699, q: 30 },
  { lat: 58.371989, lon: 25.589121, q: 80 },
  { lat: 58.883287, lon: 25.582947, q: 70 },
  { lat: 58.704848, lon: 25.930463 },
  { lat: 58.497636, lon: 26.693021, q: 80 },
  { lat: 58.671585, lon: 27.022717, q: 80 },
  { lat: 59.357088, lon: 24.041912, q: 80 },
  { lat: 58.082962, lon: 26.913907, q: 80 },
  { lat: 58.195575, lon: 26.570206, q: 80 },
  { lat: 58.942666, lon: 23.516566, q: 80 },
  { lat: 59.227394, lon: 26.124342 },
  { lat: 58.373311, lon: 24.496868, q: 80 },
  { lat: 58.421358, lon: 25.535231 },
  { lat: 59.123259, lon: 25.351742 },
  { lat: 57.786943, lon: 26.04778, q: 70 },
  { lat: 58.838283, lon: 26.342992, q: 30 },
  { lat: 58.553066, lon: 27.220306, q: 80 },
  { lat: 58.847747, lon: 26.95025, q: 80 },
  { lat: 59.442513, lon: 24.683935, q: 80 },
  { lat: 59.609724, lon: 26.059828 },
  { lat: 58.071112, lon: 26.592466 },
  { lat: 59.473486, lon: 24.723841, q: 80 },
  { lat: 58.093232, lon: 26.052083, q: 80 },
  { lat: 57.771153, lon: 26.309437, q: 80 },
  { lat: 58.647605, lon: 26.558013, q: 80 },
  { lat: 59.47215, lon: 24.830954, q: 80 },
  { lat: 58.618542, lon: 25.986205, q: 80 },
  { lat: 58.652698, lon: 25.973946, q: 80 },
  { lat: 58.057737, lon: 27.056723, q: 70 },
  { lat: 58.313097, lon: 26.734367, q: 30 },
  { lat: 59.186142, lon: 26.2021, q: 80 },
  { lat: 59.15498, lon: 25.733604, q: 80 },
  { lat: 58.650651, lon: 26.576216, q: 80 },
  { lat: 58.043406, lon: 26.468779, q: 80 },
  { lat: 59.265413, lon: 25.650858, q: 80 },
  { lat: 58.573247, lon: 26.292808, q: 80 },
  { lat: 58.914178, lon: 24.877819, q: 80 },
  { lat: 58.390535, lon: 24.516629 },
  { lat: 58.345333, lon: 24.559814, q: 80 },
  { lat: 58.379564, lon: 26.608227, q: 80 },
  { lat: 59.49911, lon: 24.917533, q: 80 },
  { lat: 58.981341, lon: 27.17659, q: 80 },
  { lat: 58.10134, lon: 27.456044, q: 80 },
  { lat: 58.345377, lon: 25.471325, q: 80 },
  { lat: 59.123084, lon: 25.847099, q: 80 },
  { lat: 58.305149, lon: 24.58772, q: 80 },
  { lat: 59.009684, lon: 27.540022, q: 80 },
  { lat: 59.104537, lon: 24.316919, q: 80 },
  { lat: 57.996654, lon: 25.935829, q: 80 },
  { lat: 59.564898, lon: 24.799566, q: 80 },
  { lat: 59.019924, lon: 25.697638, q: 80 },
  { lat: 59.155983, lon: 23.515941, q: 70 },
  { lat: 58.322442, lon: 26.622795, q: 80 },
  { lat: 57.729373, lon: 26.92122, q: 80 },
  { lat: 58.530132, lon: 26.696679, q: 80 },
  { lat: 58.553547, lon: 26.605741, q: 80 },
  { lat: 59.496759, lon: 25.365663 },
  { lat: 59.492698, lon: 25.384678 },
  { lat: 59.397195, lon: 27.778461, q: 80 },
  { lat: 58.413736, lon: 24.664318, q: 80 },
  { lat: 58.535061, lon: 25.469143, q: 80 },
  { lat: 57.786394, lon: 26.085932, q: 80 },
  { lat: 57.844362, lon: 26.989944, q: 80 },
  { lat: 58.921535, lon: 25.578581, q: 80 },
  { lat: 59.426864, lon: 27.53042, q: 80 },
  { lat: 58.267689, lon: 26.46966, q: 80 },
  { lat: 58.267002, lon: 26.470469, q: 80 },
  { lat: 58.818341, lon: 26.732831, q: 80 },
  { lat: 59.040092, lon: 22.688098, q: 80 },
  { lat: 59.518824, lon: 25.511703 },
  { lat: 58.601478, lon: 22.511566, q: 80 },
  { lat: 58.809914, lon: 25.439885, q: 80 },
  { lat: 58.662434, lon: 23.250499 },
  { lat: 58.377204, lon: 25.613191, q: 80 },
  { lat: 59.435825, lon: 24.351022, q: 70 },
  { lat: 58.894992, lon: 25.455812, q: 80 },
  { lat: 58.411018, lon: 26.045981 },
  { lat: 58.943582, lon: 23.52377 },
  { lat: 58.20912, lon: 26.4275 },
  { lat: 58.941691, lon: 26.088984, q: 80 },
  { lat: 59.335732, lon: 24.69233, q: 80 },
  { lat: 58.38645, lon: 24.37257, q: 80 },
  { lat: 59.494465, lon: 25.351344, q: 80 },
  { lat: 57.95883, lon: 27.050786 },
  { lat: 58.009814, lon: 25.931101, q: 80 },
  { lat: 58.378474, lon: 24.465522, q: 80 },
  { lat: 58.491256, lon: 27.242974, q: 80 },
  { lat: 57.98631, lon: 27.61934, q: 80 },
  { lat: 59.232043, lon: 24.281063 },
  { lat: 58.95386, lon: 23.520704, q: 80 },
  { lat: 59.353867, lon: 24.9403, q: 70 },
  { lat: 58.441654, lon: 25.451571, q: 80 },
  { lat: 58.229258, lon: 26.40642, q: 70 },
  { lat: 58.998873, lon: 24.812931, q: 80 },
  { lat: 57.691242, lon: 26.946361 },
  { lat: 59.448189, lon: 26.009953, q: 80 },
  { lat: 58.359861, lon: 25.605688, q: 80 },
  { lat: 58.23067, lon: 26.131615, q: 80 },
  { lat: 59.579022, lon: 25.962379, q: 80 },
];
