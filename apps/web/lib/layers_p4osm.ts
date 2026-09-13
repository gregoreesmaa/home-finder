// P4 OSM walkability + darkness layers (parameters4.md P4-029/P4-035,
// issue #480). First P4 buyer params to ship as map layers (docs/
// layers.md §4 tracks the exception): blockwalk is the P4-029 block-
// observer proxy, darkness the P4-035 December-darkness proxy.
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100; unknown stays 255 (renders red). This file owns ALL P4OSM
// runtime data; shared files (lib/layers.ts, lib/overlays.ts) touch it
// only through small marked `P4OSM-HOOK (#480)` blocks, so the sibling
// batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef):
// no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): NEITHER layer is a measurement.
// * blockwalk is a mapped walkability *hinnang* — nearness to OSM-
//   mapped footways, sidewalks, asphalt surfaces and lit objects,
//   never eye-level facade truth. The P4-029 primaries (Mapillary /
//   KartaView frames) are NOT in the snapshot: no frame dates, no
//   facade verdicts — stated in the title, legend and source.
// * darkness is a mapped lighting *hinnang* — nearness to OSM-mapped
//   lit=yes objects, never a lamp count. The P4-035 primaries
//   (Tallinna tänavavalgustuse kaart, VIIRS night lights) are NOT in
//   the snapshot — stated in the legend and source.
// Titles, legends and sources say "kaardistatud" (mapped) and
// "hinnang"/"proksi" (estimate/proxy). "EI OLE" never appears in a
// proxy string (pinned by test — same invariant as dims_p4_osm.py).
//
// Tag verification (2026-09-13, local snapshot PBF — no network;
// docs/p4_osm.md §3, osmium tags-filter Harjumaa 2026-09-11 PBF):
//   lit=yes 145 725; sidewalk key 16 846; highway=footway 166 990;
//   surface=asphalt 303 336 -> P4-029/P4-035/P4-040 viable.
// Counts are Harjumaa-wide; Tallinn subsets are smaller. Presence
// establishes proxy viability (same verdict the scorer dims use).
//
// Calibration (judgment calls, documented for the reviewer): both
// layers are unweighted count kernels, area-kind saturating scores
// (100·S/(S+half)), mirroring the grocery/waste path. Sigma is 0.5 km
// for both — the issue AC pins the block-observer kernel at <=500 m,
// matching the scorer radii (BLOCK_RADIUS_M / DARKNESS_RADIUS_M).
// Halves are DENSITY halves, locked 2026-09-13 from extract probes
// (mirrors scripts/build/batch_p4_osmwalk.py P4OSM_CAL exactly — a
// pytest parses this file and fails on drift):
// * blockwalk half 1000: footway+surface evidence is the densest
//   mapped signal in the batch (246k feed points); ~1000 nearby
//   evidence dots read 50, so Vanalinn/Mustamae top out at 83-86
//   (the scorer presence cap) while side streets still discriminate
//   instead of blobbing green. A small half saturates the whole
//   county to ~99 (verified probe: half=20 reads Vanalinn 100,
//   Nomme 89, rural 96) and the field answers nothing.
// * darkness half 500: lit-only evidence (59k feed points, 2058
//   mapped lamps as nodes) is sparser than the combined blockwalk
//   set; ~500 nearby lit dots read 50 (Vanalinn 81, Lasnamae 64,
//   Nomme 10).
// Measured built-master probes (2026-09-13, 75 m grid): blockwalk
// Vanalinn 83, Mustamae 86, Lasnamae 74, Kalamaja 76, Oismae 73,
// Viimsi 47, Pirita 40, rural 36, Nomme 15; darkness Vanalinn 81,
// Mustamae 79, Lasnamae 64, Nomme 10, rural 18. Both mirror the
// scorer shapes:
// presence caps (85/80 — mapped is not measured) and weak-neutral
// absences (50/45 — unmapped is not absent).
//
// PARAM NAMESPACE (read before renumbering): these layers carry NO
// parameters3.md id. P3 p29 (lot size) is a documented no-map with a
// GLOBAL verdict lock (layers_group02 locks 35 too —
// layers_group02.test.ts fails any LAYERS row claiming them), so
// paramIds stays [] and paramLabel carries the buyer-param slice
// ("P4-029"/"P4-035") for the layer button. Same shape as the #484
// senscom layer (paramLabel twin — see layerParamTag in ./layers).

import type { BonusSpec, LayerDef } from "./layers";

export type P4OSMLayerId = "blockwalk" | "darkness";

export const P4OSM_LAYER_IDS: P4OSMLayerId[] = ["blockwalk", "darkness"];

/** Buyer-param slice per layer (NOT a parameters3 id — see note above). */
export const P4OSM_PARAM_LABELS: Record<P4OSMLayerId, string> = {
  blockwalk: "P4-029",
  darkness: "P4-035",
};

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const P4OSM_LAYERS: LayerDef[] = [
  {
    id: "blockwalk",
    paramIds: [],
    paramLabel: "P4-029",
    title: "Kvartali kõnnitavus (silmakõrguse-hinnang)",
    goodLabel: "roheline = kaardistatud kõnnitee/kate/valgusti lähedal (hinnang)",
    badLabel: "punane = kaardistatud kõnniteed/katet/valgustit lähedal pole (hinnang)",
    source: `${SNAP} (OSM footway/sidewalk/asphalt/lit, P4-029 — silmakõrguse-hinnang, mitte fassaadi-tõde; Mapillary/KartaView kaadreid snapshots pole)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe kõnnitee/valgusti)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (hõre kaardistus)
    ],
  },
  {
    id: "darkness",
    paramIds: [],
    paramLabel: "P4-035",
    title: "Tänavavalgustus (detsembri-pimeduse hinnang)",
    goodLabel: "roheline = lit-märgistus lähedal (hinnang)",
    badLabel: "punane = lit-märgistust lähedal pole (hinnang)",
    source: `${SNAP} (OSM lit=yes, P4-035 — detsembri-pimeduse hinnang, mitte lampide loendus; Tallinna valgustuskaarti ja VIIRS-i snapshots pole)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe valgustus)
      { lat: 59.2, lon: 24.5 }, // Maapiirkond (pime)
    ],
  },
];

/**
 * Overpass QL fragments per P4OSM layer (document the verified source
 * tags; the app serves the frozen snapshot, never live Overpass). n/
 * shape: the shared overpassQueryFor() rewrites n[ to nwr/ (node-only
 * would silently drop way-mapped footways and lit streets).
 */
export const P4OSM_TAGS: Record<P4OSMLayerId, string> = {
  blockwalk: 'n["highway"="footway"];n["sidewalk"];n["surface"="asphalt"];n["lit"="yes"];',
  darkness: 'n["lit"="yes"];',
};

/** Influence radii in km (== wire sigma == Euclidean fallback decay). */
export const P4OSM_DECAY: Record<P4OSMLayerId, number> = {
  blockwalk: 0.5,
  darkness: 0.5,
};

/**
 * Calibration locked 2026-09-13 from extract probes (mirrors
 * scripts/build/batch_p4_osmwalk.py P4OSM_CAL exactly — a pytest
 * parses this file and fails on drift). Both carry the area-kind
 * half (saturating count).
 */
export const P4OSM_CAL = {
  blockwalk: { half: 1000, sigma: 0.5 },
  darkness: { half: 500, sigma: 0.5 },
} as const;

/**
 * blockwalk + darkness: nearby-evidence count 100·S/(S+half)
 * (area-kind, grocery/waste precedent).
 */
export const P4OSM_BONUS: Record<P4OSMLayerId, BonusSpec> = {
  blockwalk: { kind: "area", half: 1000 },
  darkness: { kind: "area", half: 500 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isP4OSMLayerId(layer: string): layer is P4OSMLayerId {
  return (P4OSM_LAYER_IDS as string[]).includes(layer);
}

/**
 * P4OSM bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForP4OSM(layer: string): BonusSpec | undefined {
  return (P4OSM_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per P4OSM layer (built by batch_p4_osmwalk.py). */
export const P4OSM_RASTER_FILE: Record<P4OSMLayerId, string> = {
  blockwalk: "blockwalk-walk-raster.json",
  darkness: "darkness-walk-raster.json",
};

/**
 * NO metro masters (documented): sparse count kernels at 9.375 m
 * cells would be fake precision. The window route serves county
 * everywhere for these layers (metro slot stays empty, like
 * G02B/G03/G03D/G05B).
 */
export const P4OSM_NO_METRO = true;

export type P4OSMVerdictKind = "proxy";

/** P4 params this batch owns (both ship as capped mapped proxies). */
export interface P4OSMVerdict {
  /** Buyer-param slice (string: P4 numbers are not parameters3 ids). */
  param: string;
  name: string;
  kind: P4OSMVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts (the docs evidence; scorer dims live in
 * services/scoring/dims_p4_osm.py — dim_block_observer/dim_darkness).
 */
export const P4OSM_VERDICTS: P4OSMVerdict[] = [
  {
    param: "P4-029",
    name: "Street-imagery block observer",
    kind: "proxy",
    reason:
      "Shipped as blockwalk: nearness to mapped footway/sidewalk/asphalt/lit evidence (166 990 + 16 846 + 303 336 + 145 725 county-wide) as eye-level hinnang — honestly labelled, never facade truth; Mapillary/KartaView frames stay out of the snapshot.",
  },
  {
    param: "P4-035",
    name: "December darkness",
    kind: "proxy",
    reason:
      "Shipped as darkness: nearness to 145 725 mapped lit=yes objects as December-darkness hinnang — honestly labelled, never a lamp count; Tallinna valgustuskaart and VIIRS stay out of the snapshot.",
  },
];
