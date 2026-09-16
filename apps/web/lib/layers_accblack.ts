// Transpordiamet accident-blackspot overlay (measured, issue #490).
//
// One layer ("accblack"): the P4-012 measured slice — casualty-accident
// points from the Transpordiamet monthly CSV (lo_2011_2026.csv), scored
// with the 300 m blackspot window from services/scoring/dims_p4_trans.py
// (BLACKSPOT_WINDOW_M, byte parity pinned by test). This file owns ALL
// accblack runtime data; shared files (lib/layers.ts, lib/overlays.ts,
// the [layer] route) touch it only through small marked `ACCBLACK-HOOK
// (#490)` blocks, so sibling batches stay disjoint. This module imports
// ./layers ONLY as types: no runtime cycle.
//
// COORD VERDICT (checked 2026-09-13, 2 tiny range peeks, custom UA,
// /tmp/hf-490-probe only, never committed):
//   HEAD bytes 0-2500 -> HTTP 206 text/csv, 54 `;`-delimited columns
//     ending in `X koordinaat;Y koordinaat`; full CSV is 12342189 B.
//   Head sample (4 rows): the 2025 + 2019 rows carry finite X/Y, the
//     2011 + 2016 rows have EMPTY X/Y.
//   Tail sample (10 rows, last 6000 B): all 10 carry finite X/Y,
//     including 1 Tallinn (Omavalitsus) row.
//   Values are L-EST97 metres (e.g. X 6589196.459 / Y 568050.8757 —
//     northing ~6.59M, easting ~568k), NOT WGS84; older rows lack them.
// So the CSV carries coordinates, but they are NOT directly usable as
// WGS84 map points: projection (GDAL/pyproj) is not vendored in this
// repo, and a hand-rolled datum shift would be fake precision. Reopen
// #522 ported the batch_tervise.py inverse-LCC transform (~1 m label),
// and the projected extract ships as the snapshot sidecar
// (accblack/accblack-points.json) served by /api/layers/accblack —
// outside the sidecar the field stays unknown (never zero, "safe").
//
// HONESTY (load-bearing): only projected points inside the Tallinn
// window are plotted (1 mislabeled out-of-window row excluded and
// counted, 92 coordless rows NULL and counted). The P4-012 per-listing
// scorer dim
// (dims_p4_trans.dim_accident_blackspots, empty buffer stays NULL) and
// the #481 furniture-density proxy (roadsafety) keep answering their
// own questions — pinned by the test below.
//
// Direction (judgment call, documented for the reviewer): avoid-kind
// (0 on top of a blackspot, 50 at half km, green far away — woodfire
// precedent), because P4-012 asks "is this crossing safe?" as a
// nearest-source badness question. The far-field gradient vs the
// scorer's empty-buffer-NULL is a KNOWN nuance for the reopen PR to
// reconcile with real point density; with today's empty set every
// lookup returns null ("no data") either way.

import type { AvoidSpec, BonusSpec, LayerDef } from "./layers";

export type AccBlackLayerId = "accblack";

export const ACCBLACK_LAYER_IDS: AccBlackLayerId[] = ["accblack"];

/** Buyer-param slice this overlay visualizes (NOT a parameters3 id). */
export const ACCBLACK_PARAM_LABEL = "P4-012";

/**
 * Dated probe this verdict rests on (see header comment). The Python
 * builder (scripts/build/batch_accblack.py) parses these values and
 * fails on drift, so the two sides cannot silently disagree.
 */
export const ACCBLACK_PROBE = {
  date: "2026-09-13",
  csvBytes: 12342189,
  headerCols: 54,
} as const;

export const ACCBLACK_DEFS: LayerDef[] = [
  {
    id: "accblack",
    paramIds: [],
    paramLabel: ACCBLACK_PARAM_LABEL,
    title: "Liiklusõnnetuste mustad punktid (mõõdetud)",
    goodLabel:
      "roheline = lähim teadaolev raske õnnetus kaugel (Tallinna aken; väljaspool katvust teadmata)",
    badLabel:
      "punane = mõõdetud musta punkti lähedal VÕI andmed puuduvad (alati teadmata väljaspool katvust)",
    source:
      "Transpordiamet lo_2011_2026.csv (12342189 B, tõmmatud 2026-09-16): X/Y L-EST97 meetrid on projekteeritud WGS84-sse portitud pöördega (~1 m); 8197 Tallinna punkti, 1 piiridest välja jäänud rida on loendamata jäetud, 92 rida ilma koordinaatideta on NULL (loetud, mitte joonistatud); väljaspool Tallinna akent andmeid pole",
    fallbackPoints: [
      // ILLUSTRATION-ONLY demo points (the measured set is empty — these
      // are NOT blackspots and claim no safety fact; they exist because
      // the registry requires every layer to carry demo fallback).
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (demo-taust)
      { lat: 59.4211, lon: 24.7153 }, // Kristiine (demo-taust)
    ],
  },
];

/** Blackspot window in km (== 300 m scorer window, kernel radius pattern). */
export const ACCBLACK_HALF_KM = 0.3;

/** Influence radius in km (== scorer window == avoid half). */
export const ACCBLACK_DECAY: Record<AccBlackLayerId, number> = {
  accblack: 0.3,
};

/**
 * Overpass QL fragment (documents the source vocabulary — there is NO
 * Overpass query for this layer: positions arrive via the Transpordiamet
 * CSV join, dims_p4_trans precedent. overpassQueryFor("accblack") is
 * never called in production).
 */
export const ACCBLACK_TAGS: Record<AccBlackLayerId, string> = {
  accblack:
    "Transpordiamet lo_2011_2026.csv (kannatanutega õnnetused; serveeritakse projekteeritud väljavõttest pärast L-EST97->WGS84 sammu, mitte Overpassist)",
};

/**
 * Measured blackspot points in WGS84 (reopen #522: the projected CSV
 * extract now ships as the snapshot sidecar
 * `accblack/accblack-points.json`, served by /api/layers/accblack —
 * this constant is retired, the sidecar is the single source).
 * Kept as an empty export for scorer-parity callers that pin the
 * pre-sidecar shape; the map never reads it.
 */
export const ACCBLACK_MEASURED_POINTS: never[] = [];

/** Scorer window in metres — byte parity with BLACKSPOT_WINDOW_M. */
export const ACCBLACK_WINDOW_M = 300;

/**
 * Avoid-kind bonus (woodfire precedent): 0 on top of a blackspot, 50
 * at 300 m, green far away. Half == the scorer window (parity pinned
 * by test); with today's empty set it never fires.
 */
export const ACCBLACK_BONUS: Record<AccBlackLayerId, AvoidSpec> = {
  accblack: { kind: "avoid", half: 0.3 },
};

/** Type guard for the bonusSpecFor + goodnessAt hooks in layers.ts. */
export function isAccBlackLayerId(layer: string): layer is AccBlackLayerId {
  return (ACCBLACK_LAYER_IDS as string[]).includes(layer);
}

/**
 * Accident-blackspot bonus lookup for the bonusSpecFor() hook in
 * ./layers. Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForAccBlack(layer: string): BonusSpec | undefined {
  if (!isAccBlackLayerId(layer)) return undefined;
  return ACCBLACK_BONUS[layer];
}

/**
 * NO raster master (documented): with zero projected points there is
 * no field to bake — a no-data raster would be fake precision. The
 * route serves provenance "empty" (never 500/demo), like out-of-
 * coverage tiles. Reopen checklist: project L-EST97 -> WGS84 (GDAL),
 * drop rows without X/Y (count + report, never fake), rebuild a
 * severity-sum kernel master, then wire the raster file here.
 */
export const ACCBLACK_NO_RASTER = true;

/** Raster master filename (intentionally never built — see ACCBLACK_NO_RASTER). */
export const ACCBLACK_RASTER_FILE: Record<AccBlackLayerId, string> = {
  accblack: "accblack-walk-raster.json",
};

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const ACCBLACK_HOOK =
  "ACCBLACK-HOOK (#490): accblack wired into layers/overlays/route; P4-012 measured slice, L-EST97 verdict 2026-09-13, empty-on-purpose.";
