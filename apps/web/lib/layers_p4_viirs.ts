// VIIRS Black Marble night-brightness overlay (issue #719, P4-035
// brightness-proxy slice; follow-up of the POSITIVE probe #699).
// This file owns ALL viirs overlay runtime data; shared files
// (lib/layers.ts, lib/distanceField.ts, lib/overlays.ts,
// lib/server/snapshot.ts, app/api/layers/[layer]/route.ts,
// app/layers/page.tsx) touch it only through small marked
// `VIIRS-HOOK (#719)` blocks, so sibling batches stay disjoint.
// This module imports ./layers ONLY as types: no runtime cycle.
//
// SOURCE BASIS (2026-09-19, polite keyless GETs, probe UA
// `home-finder-research/0.1`, `--max-time` 30, paced, 429 as stop,
// raw PNGs in /tmp only — full evidence in docs/p4_viirs_build.md
// §6): NASA GIBS WMTS serves VIIRS_Black_Marble PNG tiles keyless
// (z8 y75 x145 over Tallinn → 200, 55 KB; annual composite,
// vintage 2016 per the caps Time dimension). EOG direct downloads
// stay login-walled and are never touched (NO credential
// workarounds, out of scope).
//
// BRIGHTNESS PROXY (load-bearing honesty, user-visible): GIBS
// serves visualization PNGs, NOT numeric radiance — cell means are
// a brightness proxy, never radiometry. The title, legend, source
// and scorer reason all say heledusproksi; the 2016 composite
// vintage is stamped on every surface. Spot-check before ranking
// (2026-09-19, pinned by test): saturated city centre 5px mean
// 255.0 vs dark Soomaa bog window 11.6 (≈22× contrast) — the proxy
// resolves the gradient it claims, at city-glow scale.
// LIMITATIONS (disclosed, never silently corrected): cells are
// ≈2.75 km (z8 tops the matrix set — no street-level); open water
// carries no lights so coastal cells read darker than the sky is;
// the 2016 composite predates new developments.
//
// TRANSFORM (labeled, reviewable): scripts/build/batch_viirs.py
// crops the Tallinn metro bbox from the z8 tile and aggregates
// nearest-pixel block means (no resampling, no smoothing); q below
// is the builder's brightness_band ladder (changing the builder
// without changing VIIRS_CELLS, or vice versa, is a drift bug —
// pinned by the probe test). Regenerate, never hand-edit:
//   python3 scripts/build/batch_viirs.py --pull --build \
//     --cache-dir DIR --out pole-grid.json
// (raw PNGs stay in cache//tmp, never committed).
//
// The layer carries NO parameters3.md id: P4-035 is a parameters4
// buyer param (senscom #484 precedent). paramIds stays [] and
// paramLabel carries the slice ("P4-035") for the layer button.
// Sibling slices (veebi/ilm/lidar/ehr/osm + the login-walled EOG
// radiance NULL in dims_p4_viirs.py) are owned elsewhere,
// untouched — this module owns ONLY the GIBS brightness-proxy leg.

import type { BBoxLike, BonusSpec, LayerDef, LayerId, LayerPoint } from "./layers";

export type ViirsLayerId = "viirs";

export const VIIRS_LAYER_IDS: ViirsLayerId[] = ["viirs"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const VIIRS_PARAM_LABEL = "P4-035";

/**
 * Composite vintage (GIBS caps Time dimension: 2012 + 2016
 * annuals, default 2016-01-01). Stamped on every user surface.
 */
export const VIIRS_VINTAGE = "2016";

/**
 * Dated build this layer rests on (see header). The Python builder
 * (scripts/build/batch_viirs.py) and its pytest pin the same
 * numbers, so the two sides cannot silently disagree.
 */
export const VIIRS_PROBE = {
  date: "2026-09-19",
  tile: "8/75/145",
  tileBytes: 55225,
  centerMean: 255.0,
  bogMean: 11.6,
  cells: 96,
} as const;

/**
 * Hard join radius in metres — city-glow scale (cells are ≈2.75 km;
 * a glow cell 3 km away still says something about the night sky,
 * past that it says nothing about the backyard).
 */
export const VIIRS_RADIUS_M = 3000;

export const VIIRS_LAYERS: LayerDef[] = [
  {
    id: "viirs",
    paramIds: [],
    paramLabel: VIIRS_PARAM_LABEL,
    title: "Öötaeva heledus (proksi, hinnang)",
    goodLabel:
      "roheline = pime öötaevas 3 km raadiuses (heledusproksi-hinnang 2016 komposiidist)",
    badLabel:
      "punane = linnakuma 3 km raadiuses VÕI pimedus teadmata (heleduspilt, mitte mõõdetud radiomeetria)",
    source:
      "NASA GIBS VIIRS Black Marble (keyless WMTS, 2016 aastakomposiit, z8 plaat; kesklinna 5px 255.0 vs Soomaa soo 11.6 — heledusproksi, MITTE radiomeetria; ~2.75 km ruudud, avavesi loeb pimedana, 2016. aasta seis)",
    fallbackPoints: [
      // Bright-centre / dark-bog demo pair (real sampled means, DEMO
      // fallback only — real cells are served from VIIRS_CELLS
      // below, never committed twice).
      { lat: 59.437, lon: 24.745, q: 10 }, // kesklinn (saturatsioon)
      { lat: 59.5075, lon: 24.475, q: 90 }, // pime äär (proksi)
    ],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — night
 * brightness is not OSM data; inventing plumbing would be
 * dishonest, paaste #493 precedent). overpassQueryFor("viirs") is
 * never called in production; the string only satisfies the
 * registry shape.
 */
export const VIIRS_TAGS: Record<ViirsLayerId, string> = {
  viirs:
    "NASA GIBS VIIRS_Black_Marble WMTS (keyless z8 plaadid, 2016 komposiit; serveeritakse plokk-keskmiste väljavõttest, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see VIIRS_NO_RASTER). */
export const VIIRS_RASTER_FILE: Record<ViirsLayerId, string> = {
  viirs: "viirs-walk-raster.json",
};

/**
 * NO raster master (documented): the points-splat quality kernel IS
 * the field (tervise #494 precedent). The window route serves the
 * committed cells with snapshot provenance and the client falls
 * back to the splat (designed path).
 */
export const VIIRS_NO_RASTER = true;

/**
 * NO metro master (documented): overlay-only — the metro name
 * resolves absent so windows fall back cleanly.
 */
export const VIIRS_NO_METRO = true;

/**
 * Euclidean fallback decay in km (== the 3 km join radius: the scale
 * story is the city-glow window, same as the kernel).
 */
export const VIIRS_DECAY: Record<ViirsLayerId, number> = {
  viirs: 3.0,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isViirsLayerId(layer: LayerId): layer is ViirsLayerId {
  return (VIIRS_LAYER_IDS as string[]).includes(layer);
}

/** Quality-band spec for the viirs layer (called from the bonusSpecFor hook). */
export function viirsBonusSpecFor(layer: ViirsLayerId): BonusSpec {
  void layer;
  return { kind: "qbands", radiusM: VIIRS_RADIUS_M };
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function viirsHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface ViirsPoint {
  lat: number;
  lon: number;
  /** Darkness band off the block mean (proxy ladder, never radiometry). */
  q?: number;
}

/**
 * Nearest brightness cell within the hard glow radius, nearest
 * first (pure). No averaging, no smoothing — mirrors the qbands
 * kernel in distanceField.ts (same hard cutoff, same nearest rule).
 */
export function viirsNearby(
  lat: number,
  lon: number,
  points: ViirsPoint[],
  radiusM: number = VIIRS_RADIUS_M,
): { point: ViirsPoint; distM: number }[] {
  const out: { point: ViirsPoint; distM: number }[] = [];
  for (const p of points) {
    if (!Number.isFinite(p.lat) || !Number.isFinite(p.lon)) continue;
    const distM = viirsHavKm(lon, lat, p.lon, p.lat) * 1000;
    if (distM <= radiusM) out.push({ point: p, distM });
  }
  out.sort((a, b) => a.distM - b.distM);
  return out;
}

/**
 * Darkness hinnang at one address: the NEAREST cell's band, null
 * where no cell covers the address (unknown, never zero, never a
 * faked score).
 */
export function viirsBandAt(
  lat: number,
  lon: number,
  points: ViirsPoint[],
  radiusM: number = VIIRS_RADIUS_M,
): number | null {
  const near = viirsNearby(lat, lon, points, radiusM);
  if (near.length === 0) return null;
  const q = near[0].point.q;
  return typeof q === "number" && Number.isFinite(q) ? q : null;
}

/** Extract points clipped to the view bbox (same inBBox contract as senscom). */
export function viirsPointsIn(points: ViirsPoint[], bbox: BBoxLike): LayerPoint[] {
  return points.filter(
    (p) =>
      p.lon >= bbox.minlon && p.lon <= bbox.maxlon && p.lat >= bbox.minlat && p.lat <= bbox.maxlat,
  );
}

/**
 * Sampled brightness cells in WGS84 (96 block means, 2016 annual
 * composite, Tallinn metro crop). Built offline by
 * scripts/build/batch_viirs.py from the /tmp tile harvest (means
 * stay in the builder sidecar — the wire carries lat/lon/q only).
 * Regenerate, never hand-edit.
 */
export const VIIRS_CELLS: LayerPoint[] = [
  { lat: 59.3325, lon: 24.4750, q: 70 }, // mean 37.9
  { lat: 59.3325, lon: 24.5250, q: 50 }, // mean 51.8
  { lat: 59.3325, lon: 24.5750, q: 50 }, // mean 94.6
  { lat: 59.3325, lon: 24.6250, q: 30 }, // mean 130.8
  { lat: 59.3325, lon: 24.6750, q: 50 }, // mean 60.7
  { lat: 59.3325, lon: 24.7250, q: 50 }, // mean 40.7
  { lat: 59.3325, lon: 24.7750, q: 50 }, // mean 67.0
  { lat: 59.3325, lon: 24.8250, q: 50 }, // mean 74.7
  { lat: 59.3325, lon: 24.8750, q: 50 }, // mean 50.2
  { lat: 59.3325, lon: 24.9250, q: 70 }, // mean 39.9
  { lat: 59.3325, lon: 24.9750, q: 70 }, // mean 18.7
  { lat: 59.3325, lon: 25.0250, q: 90 }, // mean 13.9
  { lat: 59.3575, lon: 24.4750, q: 70 }, // mean 20.7
  { lat: 59.3575, lon: 24.5250, q: 70 }, // mean 30.3
  { lat: 59.3575, lon: 24.5750, q: 50 }, // mean 74.8
  { lat: 59.3575, lon: 24.6250, q: 10 }, // mean 228.0
  { lat: 59.3575, lon: 24.6750, q: 30 }, // mean 107.2
  { lat: 59.3575, lon: 24.7250, q: 50 }, // mean 89.6
  { lat: 59.3575, lon: 24.7750, q: 50 }, // mean 84.3
  { lat: 59.3575, lon: 24.8250, q: 50 }, // mean 88.5
  { lat: 59.3575, lon: 24.8750, q: 10 }, // mean 183.5
  { lat: 59.3575, lon: 24.9250, q: 30 }, // mean 128.9
  { lat: 59.3575, lon: 24.9750, q: 70 }, // mean 26.0
  { lat: 59.3575, lon: 25.0250, q: 70 }, // mean 15.5
  { lat: 59.3825, lon: 24.4750, q: 70 }, // mean 17.1
  { lat: 59.3825, lon: 24.5250, q: 50 }, // mean 41.6
  { lat: 59.3825, lon: 24.5750, q: 30 }, // mean 115.2
  { lat: 59.3825, lon: 24.6250, q: 30 }, // mean 167.1
  { lat: 59.3825, lon: 24.6750, q: 10 }, // mean 248.0
  { lat: 59.3825, lon: 24.7250, q: 10 }, // mean 219.1
  { lat: 59.3825, lon: 24.7750, q: 30 }, // mean 100.9
  { lat: 59.3825, lon: 24.8250, q: 10 }, // mean 187.1
  { lat: 59.3825, lon: 24.8750, q: 30 }, // mean 109.6
  { lat: 59.3825, lon: 24.9250, q: 50 }, // mean 91.6
  { lat: 59.3825, lon: 24.9750, q: 70 }, // mean 38.1
  { lat: 59.3825, lon: 25.0250, q: 70 }, // mean 17.7
  { lat: 59.4075, lon: 24.4750, q: 70 }, // mean 18.0
  { lat: 59.4075, lon: 24.5250, q: 50 }, // mean 80.6
  { lat: 59.4075, lon: 24.5750, q: 30 }, // mean 139.1
  { lat: 59.4075, lon: 24.6250, q: 10 }, // mean 210.6
  { lat: 59.4075, lon: 24.6750, q: 10 }, // mean 255.0
  { lat: 59.4075, lon: 24.7250, q: 10 }, // mean 250.1
  { lat: 59.4075, lon: 24.7750, q: 10 }, // mean 196.5
  { lat: 59.4075, lon: 24.8250, q: 10 }, // mean 222.2
  { lat: 59.4075, lon: 24.8750, q: 30 }, // mean 139.1
  { lat: 59.4075, lon: 24.9250, q: 30 }, // mean 126.7
  { lat: 59.4075, lon: 24.9750, q: 50 }, // mean 65.1
  { lat: 59.4075, lon: 25.0250, q: 70 }, // mean 24.9
  { lat: 59.4325, lon: 24.4750, q: 70 }, // mean 37.9
  { lat: 59.4325, lon: 24.5250, q: 30 }, // mean 118.9
  { lat: 59.4325, lon: 24.5750, q: 30 }, // mean 156.5
  { lat: 59.4325, lon: 24.6250, q: 10 }, // mean 193.0
  { lat: 59.4325, lon: 24.6750, q: 10 }, // mean 205.0
  { lat: 59.4325, lon: 24.7250, q: 10 }, // mean 254.4
  { lat: 59.4325, lon: 24.7750, q: 10 }, // mean 252.2
  { lat: 59.4325, lon: 24.8250, q: 10 }, // mean 254.6
  { lat: 59.4325, lon: 24.8750, q: 10 }, // mean 237.2
  { lat: 59.4325, lon: 24.9250, q: 10 }, // mean 183.9
  { lat: 59.4325, lon: 24.9750, q: 30 }, // mean 125.0
  { lat: 59.4325, lon: 25.0250, q: 50 }, // mean 44.2
  { lat: 59.4575, lon: 24.4750, q: 50 }, // mean 59.9
  { lat: 59.4575, lon: 24.5250, q: 70 }, // mean 34.0
  { lat: 59.4575, lon: 24.5750, q: 50 }, // mean 82.0
  { lat: 59.4575, lon: 24.6250, q: 50 }, // mean 81.5
  { lat: 59.4575, lon: 24.6750, q: 10 }, // mean 198.1
  { lat: 59.4575, lon: 24.7250, q: 10 }, // mean 210.9
  { lat: 59.4575, lon: 24.7750, q: 30 }, // mean 133.0
  { lat: 59.4575, lon: 24.8250, q: 10 }, // mean 228.7
  { lat: 59.4575, lon: 24.8750, q: 10 }, // mean 229.8
  { lat: 59.4575, lon: 24.9250, q: 10 }, // mean 247.6
  { lat: 59.4575, lon: 24.9750, q: 10 }, // mean 223.2
  { lat: 59.4575, lon: 25.0250, q: 50 }, // mean 92.2
  { lat: 59.4825, lon: 24.4750, q: 90 }, // mean 13.5
  { lat: 59.4825, lon: 24.5250, q: 70 }, // mean 16.9
  { lat: 59.4825, lon: 24.5750, q: 70 }, // mean 26.2
  { lat: 59.4825, lon: 24.6250, q: 70 }, // mean 37.1
  { lat: 59.4825, lon: 24.6750, q: 50 }, // mean 63.5
  { lat: 59.4825, lon: 24.7250, q: 50 }, // mean 83.6
  { lat: 59.4825, lon: 24.7750, q: 50 }, // mean 66.8
  { lat: 59.4825, lon: 24.8250, q: 30 }, // mean 159.3
  { lat: 59.4825, lon: 24.8750, q: 10 }, // mean 208.6
  { lat: 59.4825, lon: 24.9250, q: 10 }, // mean 195.5
  { lat: 59.4825, lon: 24.9750, q: 10 }, // mean 218.3
  { lat: 59.4825, lon: 25.0250, q: 30 }, // mean 136.1
  { lat: 59.5075, lon: 24.4750, q: 90 }, // mean 9.4
  { lat: 59.5075, lon: 24.5250, q: 90 }, // mean 9.4
  { lat: 59.5075, lon: 24.5750, q: 90 }, // mean 10.8
  { lat: 59.5075, lon: 24.6250, q: 90 }, // mean 14.7
  { lat: 59.5075, lon: 24.6750, q: 70 }, // mean 25.3
  { lat: 59.5075, lon: 24.7250, q: 70 }, // mean 30.3
  { lat: 59.5075, lon: 24.7750, q: 50 }, // mean 41.8
  { lat: 59.5075, lon: 24.8250, q: 10 }, // mean 209.6
  { lat: 59.5075, lon: 24.8750, q: 30 }, // mean 121.3
  { lat: 59.5075, lon: 24.9250, q: 30 }, // mean 108.1
  { lat: 59.5075, lon: 24.9750, q: 50 }, // mean 78.4
  { lat: 59.5075, lon: 25.0250, q: 50 }, // mean 48.0
];

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const VIIRS_HOOK =
  "VIIRS-HOOK (#719): viirs wired into layers/overlays/snapshot/route/page; P4-035 brightness-proxy leg, labelled proxy (never radiometry).";
