// Group 2 (Ehitisregister/EHR) batch-B layers (parameters3.md §5.2, issue #137).
//
// One layer per shippable Group 2 batch-B parameter, Harjumaa scope, local
// 2026-09-12 snapshot ONLY. Scores are absolute 0..100; unknown stays 255
// (renders red). This file owns ALL batch-G02B runtime data; shared files
// (lib/layers.ts, lib/server/snapshot.ts, lib/overlays.ts) touch it only
// through small marked `G02B-HOOK (#137)` blocks, so the parallel batch A
// (issue #136, ./layers_group02.ts) and the nine sibling batches stay
// disjoint.
//
// Per-param verdicts (snapshot evidence, 2026-09-12 — see G02B_VERDICTS):
//   p79  building permit history .... NO-MAP (per-building EHR record; OSM
//        start_date=996 county-wide is fake precision for permit history).
//   p154 builder warranties ......... NO-MAP (per-developer legal record;
//        zero spatial signal exists in any snapshot source).
//   p196 residential elevators ...... HONEST PROXY (shipped as "liftproxy":
//        5+ storey mapped-building density as lift-likelihood hinnang).
//   p495 unpermitted sunroom addition  NO-MAP (per-building violation
//        record; sunrooms/conservatories are not a mapped OSM tag).
// No-map params get scorer dims only (services/scoring/dims_group02b.py,
// OTA PR #131 precedent); their verdict rows below are the docs evidence.
//
// HONESTY (load-bearing): the EHR registry (~/hf-data/2026-09-12/
// registries/) is EMPTY, so p196 MUST NOT be presented as measured EHR
// lift data. It is a mapped-high-rise *hinnang* (estimate) — the title,
// legend and source say so, and the test below pins those markers.
// 5+ storeys is the lift-plausible cutoff (Estonian practice: new 5+
// storey blocks have lifts; note older 5-storey panel blocks often do
// NOT — the layer scores high-rise *density*, never a per-flat promise).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-count ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
//     building building:levels start_date building:flats
//   252146  building
//   14622   building:levels            (nwr recount incl. relations: 26911
//   996     start_date                  with any levels value, 5023 with
//   105     building:flats              levels>=5 — the proxy source set)
// start_date (996) is two orders of magnitude too sparse for a p79 age/
// permit-history proxy, and building:flats (105) says nothing usable —
// both verdicts above follow from these counts, not from judgment.
//
// Calibration (judgment call, documented for the reviewer): unweighted
// count kernel, area-kind saturating score (100·S/(S+half)), mirroring
// the grocery/hydrant path at block scale (sigma 0.3 km). Mapped
// high-rises are hyper-clustered (panel districts vs detached suburbs),
// so the field is bimodal BY DESIGN: half=2 keeps a lone tower visible
// (100·1/3 = 33, amber — the safety-layer lone-station idea) while
// Lasnamäe/Mustamäe/Õismäe saturate green. Tallinn-window Euclidean
// histogram (2026-09-12 export, 0.005° grid): median 0.2 / p75 72.8 /
// p90 91.2 / max 97.7, 34% of cells above 30 — streets discriminate
// instead of blobbing. The walk kernel runs slightly narrower (true
// walks exceed crow-flies), so the shipped raster skews a touch redder
// than this probe. Recalibrate from Tallinn histograms if a county
// build shows blobbing — half lives in G02B_HALVES below and in
// scripts/build/batch_g02b_lift.py LAYER_DEFAULTS (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group02bLayerId = "liftproxy";

export const G02B_LAYER_IDS: Group02bLayerId[] = ["liftproxy"];

/** parameters3.md number per batch-G02B layer. */
export const G02B_PARAMS: Record<Group02bLayerId, number> = {
  liftproxy: 196,
};

export const G02B_DEFS: LayerDef[] = [
  {
    id: "liftproxy",
    paramIds: [196],
    title: "Liftiga hooned (kõrghoonete läheduse hinnang)",
    goodLabel: "roheline = 5+ korrusega hooned lähedal (hinnang, lift tõenäoline)",
    badLabel: "punane = kõrghooned kaugel või andmed puuduvad (hinnang)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM building:levels≥5, 5023 hoonet — kõrghoonete läheduse hinnang; EHR liftiandmeid hetktõmmises pole — see EI OLE mõõdetud liftide register)",
    fallbackPoints: [
      { lat: 59.4438, lon: 24.8117 }, // Lasnamäe (9-korruselised paneelmajad)
      { lat: 59.4125, lon: 24.6583 }, // Õismäe (paneelrajoon)
    ],
  },
];

/** Influence radius in km (== walk-kernel sigma == Euclidean fallback decay). */
export const G02B_DECAY: Record<Group02bLayerId, number> = {
  liftproxy: 0.3,
};

/**
 * Overpass QL fragment for the layer inside the bbox. Snapshot-only
 * serving never queries live; this documents the source tags (the
 * builder consumes them offline — no live fetch in code/tests).
 * Levels compare numerically in the builder (float moles "5;6" edge:
 * first value wins); the QL regex below is the bbox-prefilter shape.
 */
export const G02B_TAGS: Record<Group02bLayerId, string> = {
  liftproxy: 'n["building:levels"~"^([5-9]|[1-9][0-9]+)$"];',
};

/** Saturation midpoint (area-kind), see calibration note above. */
export const G02B_HALVES: Record<Group02bLayerId, number> = {
  liftproxy: 2,
};

export const G02B_BONUS: Record<Group02bLayerId, BonusSpec> = {
  liftproxy: { kind: "area", half: 2 },
};

/**
 * Batch-G02B bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for every other layer (their own hooks handle them).
 */
export function bonusSpecForGroup02b(layer: string): BonusSpec | undefined {
  return (G02B_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master filename next to the base masters (gitignored artifact). */
export const G02B_RASTER_FILE: Record<Group02bLayerId, string> = {
  liftproxy: "liftproxy-walk-raster.json",
};

/**
 * NO metro master (documented): a sparse count kernel is smooth at the
 * 75 m county step; 9.375 m cells would be fake precision. The window
 * route serves county everywhere for this layer (B10C precedent).
 */
export const G02B_NO_METRO = true;

export type G02bVerdictKind = "proxy" | "no-map";

export interface G02bVerdict {
  param: number;
  name: string;
  kind: G02bVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 2 batch B (issues #137 docs evidence for
 * the no-map rows; scorer dims live in services/scoring/dims_group02b.py).
 */
export const G02B_VERDICTS: G02bVerdict[] = [
  {
    param: 79,
    name: "Building permit history",
    kind: "no-map",
    reason:
      "Per-building EHR record; snapshot registries/ is empty and OSM start_date (996 county-wide) is fake precision for permit history — no honest area proxy exists.",
  },
  {
    param: 154,
    name: "Builder warranties",
    kind: "no-map",
    reason:
      "Per-developer legal record (warranty terms per builder/project); zero spatial signal exists in any snapshot source — no honest area proxy exists.",
  },
  {
    param: 196,
    name: "Residential elevators",
    kind: "proxy",
    reason:
      "Shipped as liftproxy: 5+ storey mapped-building density (5023 buildings with building:levels≥5) as lift-likelihood hinnang — honestly labelled, never EHR lift data.",
  },
  {
    param: 495,
    name: "Unpermitted sunroom addition",
    kind: "no-map",
    reason:
      "Per-building violation record; sunrooms/conservatories are not a mapped OSM tag and no snapshot source records permit status — no honest area proxy exists.",
  },
];

/** Batch-B params with no honest map (dims-only, OTA PR #131 precedent). */
export const G02B_NO_MAP_PARAMS: number[] = G02B_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);
