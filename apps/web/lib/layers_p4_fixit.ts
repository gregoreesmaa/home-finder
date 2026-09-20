// annateada report-pin overlay (issue #623, P4 fix-it pins; Group-Y
// verify-first POSITIVE verdict docs/p4_fixit.md §"Layer verdict
// #623"). This file owns ALL fixit overlay runtime tables; shared
// files (lib/layers.ts, lib/distanceField.ts, lib/overlays.ts,
// lib/server/snapshot.ts, components/ValueHeatMap.tsx,
// app/api/layers/[layer]/route.ts, app/layers/page.tsx) touch it only
// through small marked `FIXIT-HOOK (#623)` blocks, so sibling batches
// stay disjoint. This module imports ./layers ONLY as types: no
// runtime cycle.
//
// FEED VERDICT (2026-09-17, polite harvest, custom UA
// `home-finder-623-fixit-ask/1.0`, one bbox POST per 24 h TTL, HTTP
// 429 as stop, raw JSON in /tmp only — never committed): the keyless
// annateada ask endpoint serves the rolling ~19-day pin window
// (2026-08-28 -> 2026-09-17: 300 pins, 173 Tallinn / 127 neighbours,
// 120 handled green-stat + 180 unhandled red-stat). Parser + pin
// builder are REUSED from services/scoring/dims_p4_fixit.py (one
// tested implementation; #623 added the ts carry for map expiry).
//
// TRANSFORM (labeled, reviewable): pins keep the feed's WGS84 lat/lng
// (magnitudes checked); the wire carries lat/lon/handled/ts ONLY —
// category/msg/photo/region never leave the builder (report text can
// identify people). Pins without a parseable ts are dropped + counted
// (fail closed: timeless pins can never prove freshness).
//
// HONESTY (load-bearing, maintainer decision #623): the map shows
// PINS with reporting-bias labeling — complaints measure reporting
// activity, NOT place quality. The `pins` kernel paints NO field
// (all-NaN direct; ValueHeatMap clears it so the viewport stays
// clean); markers ride selectOverlayPoints. Expiry is enforced at
// serve time (pins older than 19 days never render as current), so a
// stale sidecar degrades to honestly-empty. The legend states the
// bias caveat + the rolling window + the pull vintage on every view.
// #807 NO-SCORE DECISION (2026-09-20, re-affirmed): pins stay `pins`
// — complaint density ranks reporting activity, never place goodness
// (a silent street is unknown, not fine). No band table exists and
// none is invented here.
//
// The layer carries NO parameters3.md id: the fix-it dims are
// parameters4 buyer params (tervise #494 precedent). paramIds stays []
// and paramLabel carries "P4-kaebused" for the layer button.

import type { BBoxLike, BonusSpec, LayerDef, LayerId } from "./layers";

export type FixitLayerId = "fixit";

export const FIXIT_LAYER_IDS: FixitLayerId[] = ["fixit"];

/**
 * Dated harvest this layer rests on (see header). The Python builder
 * (scripts/build/batch_fixit.py) and its pytest pin the same numbers,
 * so the two sides cannot silently disagree.
 */
export const FIXIT_PROBE = {
  date: "2026-09-17",
  windowDays: 19,
  totalPins: 300,
  tallinnPins: 173,
  handledPins: 120,
  unhandledPins: 180,
} as const;

/** Vintage label stamped on the sidecar build (daily harvest, 24 h TTL). */
export const FIXIT_VINTAGE = "2026-09-17";

/** Rolling-window length in days (server keeps ~19 days of pins). */
export const FIXIT_WINDOW_DAYS = 19;

/** Attribution — surfaced in the layer source note. */
export const FIXIT_ATTRIBUTION = "annateada.ee report pins (rolling window)";

/**
 * Sidecar pin (wire shape: lat/lon/handled/ts only — category/msg/
 * photo/region never leave the builder).
 */
export interface FixitPoint {
  lat: number;
  lon: number;
  handled: boolean;
  /** Report epoch seconds (always present — timeless pins never ship). */
  ts: number;
}

export const FIXIT_LAYERS: LayerDef[] = [
  {
    id: "fixit",
    paramIds: [],
    paramLabel: "P4-kaebused",
    title: "Teated lähedal (kaebuste tihedus, hinnang)",
    goodLabel:
      "oranž täpp = üks teade (annateada-hinnang linnulennult; tihedus mõõdab TEATAMIST, mitte elukvaliteeti — vaata legendi)",
    badLabel:
      "tühi kaart = teateid pole (teadmata, mitte korras — teatamata jätmine pole kiitus)",
    source:
      "annateada.ee teatetahvel (libisev ~19 päeva aken, seis 2026-09-17; 300 teadet, sh 120 lahendatud; kategooria/foto/kirjeldus kaarti ei jõua; kaebused, mitte kvaliteet)",
    fallbackPoints: [
      // Real pin, DEMO fallback only (live pins are served from the
      // snapshot sidecar, never committed twice).
      { lat: 59.4372, lon: 24.7536 }, // Tallinn demo pin
    ],
  },
];

/**
 * Source-vocabulary note (NOT an Overpass fragment — annateada pins
 * are not OSM data; inventing amenity=* plumbing would be dishonest,
 * paaste #493 precedent). overpassQueryFor("fixit") is never called
 * in production; the string only satisfies the registry shape.
 */
export const FIXIT_TAGS: Record<FixitLayerId, string> = {
  fixit:
    "annateada.ee teatetahvel (serveeritakse snapshot-sidecarist, mitte Overpassist)",
};

/** Raster master filename (intentionally never built — see FIXIT_NO_RASTER). */
export const FIXIT_RASTER_FILE: Record<FixitLayerId, string> = {
  fixit: "fixit-pins-raster.json",
};

/**
 * NO raster master (documented): markers-only layers have no field to
 * stamp. The window route serves 500 and the client renders markers
 * (designed path, ehis precedent).
 */
export const FIXIT_NO_RASTER = true;

/**
 * Euclidean fallback decay in km (== the scorer's 500 m fix-it
 * window scale: the pins story is the doorstep window, even though
 * no field is painted).
 */
export const FIXIT_DECAY: Record<FixitLayerId, number> = {
  fixit: 0.5,
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isFixitLayerId(layer: LayerId): layer is FixitLayerId {
  return (FIXIT_LAYER_IDS as string[]).includes(layer);
}

/** Marker-only spec for the fixit layer (called from the bonusSpecFor hook). */
export function fixitBonusSpecFor(layer: FixitLayerId): BonusSpec {
  void layer;
  return { kind: "pins" };
}

/**
 * Live pins inside a bbox at serve time (pure): finite coords inside
 * the view AND ts within the rolling window (nowMs - ts <=
 * windowDays). Expired pins never render as current — a stale
 * sidecar degrades to honestly-empty. nowMs defaults to Date.now()
 * (the route passes it explicitly; tests freeze it).
 */
export function fixitPointsIn(
  points: FixitPoint[],
  bbox: BBoxLike,
  nowMs: number = Date.now(),
  windowDays: number = FIXIT_WINDOW_DAYS,
): { lat: number; lon: number }[] {
  const cutoffS = nowMs / 1000 - windowDays * 86400;
  return points
    .filter(
      (p) =>
        Number.isFinite(p.lat) &&
        Number.isFinite(p.lon) &&
        typeof p.ts === "number" &&
        Number.isFinite(p.ts) &&
        p.ts >= cutoffS &&
        p.lon >= bbox.minlon &&
        p.lon <= bbox.maxlon &&
        p.lat >= bbox.minlat &&
        p.lat <= bbox.maxlat,
    )
    .map((p) => ({ lat: p.lat, lon: p.lon }));
}
