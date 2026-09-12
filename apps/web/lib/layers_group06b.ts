// Group 6 heritage leftovers, batch G06B (parameters3.md §5.6, issue #139).
//
// Three MAP layers (p352/p353/p356) + four documented no-maps
// (p354/p355/p359/p360). Harjumaa scope, local 2026-09-12 snapshot ONLY.
// Scores are absolute 0..100; unknown stays 255 (renders red). This file
// owns ALL G06B runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts, lib/distanceField.ts) touch it
// only through small marked `G06B-HOOK (#139)` blocks, so the sibling
// batches (incl. #138 layers_group06.ts, which owns p72/p158/p272/p320/
// p351) stay disjoint.
//
// HONESTY (load-bearing): the Muinsuskaitseamet heritage registry
// (register.muinsuskaitseamet.ee) and the Maa-amet mka:ehitis /
// mka:kaitsevoond WFS layers are NOT in the snapshot, so none of these
// layers is a registry verdict. p352/p356 score MAPPED building-material
// density (building:material=plaster/wood — the parameters3.md §5.6
// graceful-fallback family: mapped OSM craft/material evidence, never a
// conservation decision), p353 scores mapped antiques-shop proximity.
// Titles, legends and sources all say proksi/hinnang (pinned by test).
// Green = good for the buyer question, red = bad OR honestly-unknown.
//
// Per-param verdicts (see GROUP06B_NO_MAP; mirrors the OTA #131 precedent
// — a gradient map that cannot be honestly built stays a scorer dim in
// services/scoring/dims_group06b.py, never a faked layer):
//   p352 SHIP  "plaster": plaster-facade count kernel (this file).
//   p353 SHIP  "antiques": antiques-shop proximity kernel (this file).
//        Judgment call (AGENTS.md §7.5, reviewable): 14 mapped shops is
//        thin and a shop is not hardware stock — but the param IS
//        availability (BOOLEAN, "Default FALSE; mark unverified"), and
//        nearby dealers are the only mapped availability signal. The
//        legend says kauplus, never ladu; the scorer dim keeps the
//        0/1 + unverified semantics.
//   p354 NO-MAP: foundation settling is geotechnical (soil/water); mapped
//        heritage density does not predict it — scorer None stub (needs
//        an inspection/survey, like p158/p272/p351 in #138).
//   p355 NO-MAP (map): society friction is the same field as the p320
//        commission heuristic (#138) — a second inverse-density gradient
//        would be fake differentiation. Lives as a scorer heuristic only.
//   p356 SHIP  "woodfire": INVERSE nearest-wood distance (this file, kind
//        "avoid"): green = far from mapped wooden houses = lower
//        fire-spread attention. See the AvoidSpec note below.
//   p359 NO-MAP: verified ZERO building:material=asbestos tags in the
//        snapshot PBF — no signal at all. Scorer None stub (needs a
//        lab/survey; unmapped != absent).
//   p360 NO-MAP: deed provenance is an archive chain (kinnistusraamat /
//        muinsuskaitse register); start_date is not provenance. Scorer
//        None stub.
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/building:material ... -> 11371 features: plaster 4396,
//     wood 2376, brick 1969, asbestos 0. nwr/shop=antiques -> 14 (13
//     Tallinn Old Town + 1 Rapla). resolve_pois centroids every geometry
//     and dedupe_points merges node+area pairs in ~20 m cells.
//
// Calibration (judgment calls, documented for the reviewer; Euclidean
// Gaussian probe /tmp/hf-probe-g06b.py over a Tallinn grid):
//   plaster: unweighted count kernel, sigma 0.5 km (neighbourhood scale,
//     like pets/community), half 6 (Tallinn-grid median 14 / p75 84 —
//     near grocery 17; a lone plaster house caps at 100/7 = 14, low
//     teens like the B1 singletons: one house is not a craft district).
//   antiques: count kernel, sigma 0.5 km (shop scale), half 1 (Old Town
//     cluster peaks 85; a lone dealer caps at 50 = amber "maybe" — the
//     BOOLEAN verdict lives in the scorer dim, the map shows proximity).
//   woodfire: INVERSE distance, sigma 0.3 km (fire-spread attention is
//     hyper-local: the nearest wooden neighbour matters), half 0.21 km
//     (the walk-km scoring 50 == sigma*ln2; score = 100*(1-2^(-d/half))).
//     Small sigma is deliberate honesty: wood-material mapping is THIN
//     (Kalamaja's wooden houses are mostly untagged — nearest MAPPED
//     wood to Kalamaja centre is 2.4 km), so beyond 1.2 km (4 sigma) the
//     map reads unknown-red instead of fake-green. A wider sigma would
//     paint Kalamaja confidently safe — the worst possible error here.
//     Nõmme (mapped, 358 m) discriminates properly; Lasnamäe (1.1 km)
//     reads ~97 green. half/sigma live in one dict below and in
//     scripts/build/batch_g06b_heritage.py LAYER_DEFAULTS (kept in sync
//     by test).

import type { AvoidSpec, BonusSpec, LayerDef } from "./layers";

export type Group06BLayerId = "plaster" | "antiques" | "woodfire";

export const GROUP06B_LAYER_IDS: Group06BLayerId[] = ["plaster", "antiques", "woodfire"];

/** parameters3.md number per Group-6B map layer. */
export const GROUP06B_PARAMS: Record<Group06BLayerId, number> = {
  plaster: 352,
  antiques: 353,
  woodfire: 356,
};

/**
 * Documented no-map verdicts (OTA PR #131 precedent): params whose
 * source registry is absent from the snapshot AND whose OSM fallback
 * cannot honestly carry a gradient. Scorer dims live in
 * services/scoring/dims_group06b.py; the map stays silent rather than
 * painting faked precision.
 */
export const GROUP06B_NO_MAP: { param: number; reason: string }[] = [
  {
    param: 354,
    reason:
      "Vundamendi vajumine on geotehniline fakt (pinnas/vesi): kaardistatud muinsustihedus seda ei ennusta — skoorija tagastab None (vajab ekspertiisi/uuringut).",
  },
  {
    param: 355,
    reason:
      "Seltsiliikumise hõõre on sama väli mis p320 komisjoni-heuristik (#138): teine pöörd-tiheduse gradient oleks võlts-eristus — elab ainult skoorija-heuristikuna.",
  },
  {
    param: 359,
    reason:
      "Asbesti hetktõmmises pole (kontrollitud: 0 building:material=asbestos silti) — signaal puudub täielikult; skoorija None-stub (vajab laborit/uuringut, kaardistamata ≠ puudub).",
  },
  {
    param: 360,
    reason:
      "Kinnistu päritoluahel on arhiiviakt (kinnistusraamat/muinsuskaitse register): start_date ei ole päritolutõend — skoorija None-stub.",
  },
];

export const GROUP06B_DEFS: LayerDef[] = [
  {
    id: "plaster",
    paramIds: [352],
    title: "Krohvfassaadid (proksi, hinnang)",
    goodLabel: "roheline = krohvfassaadiga hooneid tihedalt (käsitöö-hinnang)",
    badLabel: "punane = krohvhooneid vähe või pole (hinnang, MITTE registriotsus)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM building:material=plaster 4396 hoonet; Muinsuskaitseameti register hetktõmmises pole — lähedushinnang, mitte seisukorraotsus)",
    fallbackPoints: [
      { lat: 59.428, lon: 24.698 }, // krohvhooned Kristiines (snapshot)
      { lat: 59.4276, lon: 24.6764 }, // krohvhooned (snapshot)
    ],
  },
  {
    id: "antiques",
    paramIds: [353],
    title: "Antiigipoed (proksi, hinnang)",
    goodLabel: "roheline = antiigipood jalutuskäigu kaugusel (hinnang)",
    badLabel: "punane = antiigipoode pole lähedal (hinnang — kauplus ≠ furnituuriladu)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM shop=antiques 14 kauplust; Muinsuskaitseameti register hetktõmmises pole — lähedushinnang, saadavus täpsustamata)",
    fallbackPoints: [
      { lat: 59.439, lon: 24.7464 }, // Baltik Antik (snapshot)
      { lat: 59.4403, lon: 24.7499 }, // Old House (snapshot)
    ],
  },
  {
    id: "woodfire",
    paramIds: [356],
    title: "Puithoonete tuleohutus (proksi, hinnang)",
    goodLabel: "roheline = lähikonnas vähe kaardistatud puithooneid (väiksem tuleleviku-hinnang)",
    badLabel: "punane = tihe kaardistatud puithooneala VÕI andmed puuduvad (hinnang, MITTE konstruktsiooniuuring)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM building:material=wood 2376 hoonet, pöörd-kaugus; puitmaterjali kaardistus on hõre — kaardistamata puithooned ei loe; Muinsuskaitseameti register hetktõmmises pole)",
    fallbackPoints: [
      { lat: 59.4295, lon: 24.7138 }, // puithoone (snapshot)
      { lat: 59.4425, lon: 24.6846 }, // Stroomi Rannahoone (snapshot)
    ],
  },
];

/** Influence radii in km (== walk-kernel sigma == Euclidean fallback decay). */
export const GROUP06B_DECAY: Record<Group06BLayerId, number> = {
  plaster: 0.5,
  antiques: 0.5,
  woodfire: 0.3,
};

/**
 * Overpass QL fragments per layer inside the bbox. Snapshot-only serving
 * never queries live; these document the source tags (nwr/ parity via
 * overpassQueryFor, which rewrites `n[` — extraction used nwr/ everywhere
 * so way-mapped buildings survive).
 */
export const GROUP06B_TAGS: Record<Group06BLayerId, string> = {
  plaster: 'n["building:material"="plaster"];',
  antiques: 'n["shop"="antiques"];',
  woodfire: 'n["building:material"="wood"];',
};

/**
 * Saturation midpoints (area-kind) / 50-score walk-km (avoid-kind).
 * woodfire half 0.21 == sigma*ln2 (see calibration note above).
 */
export const GROUP06B_HALVES: Record<Group06BLayerId, number> = {
  plaster: 6,
  antiques: 1,
  woodfire: 0.21,
};

export const GROUP06B_BONUS: Record<Group06BLayerId, BonusSpec> = {
  plaster: { kind: "area", half: 6 },
  antiques: { kind: "area", half: 1 },
  woodfire: { kind: "avoid", half: 0.21 } satisfies AvoidSpec,
};

/**
 * Layers scored INVERSELY (kind "avoid"): score falls with proximity.
 * Currently only woodfire (p356 fire-spread attention). Kept as an
 * explicit set (not kind-sniffing the bonus table) so a future second
 * inverse layer is a one-line addition here, and so goodnessAt /
 * buildScoredField share one predicate with the registry.
 */
const GROUP06B_AVOID: ReadonlySet<string> = new Set(["woodfire"]);

/** True for G06B inverse ("avoid") layers. Used by the goodness hooks. */
export function isGroup06BAvoidLayer(layer: string): boolean {
  return GROUP06B_AVOID.has(layer);
}

/**
 * Group-6B bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for every other layer (their switch/handlers own them).
 */
export function bonusSpecForGroup06B(layer: string): BonusSpec | undefined {
  return (GROUP06B_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per G06B layer (built by batch_g06b_heritage.py). */
export const GROUP06B_RASTER_FILES: Record<Group06BLayerId, string> = {
  plaster: "plaster-walk-raster.json",
  antiques: "antiques-walk-raster.json",
  woodfire: "woodfire-walk-raster.json",
};

/**
 * Metro master file prefixes per G06B layer (county-only like B5: no
 * metro masters are built — 9.375 m cells would be fake precision for
 * these kernels — and windows fall back to county cleanly).
 */
export const GROUP06B_METRO_PREFIXES: Record<Group06BLayerId, string> = {
  plaster: "plaster-metro",
  antiques: "antiques-metro",
  woodfire: "woodfire-metro",
};
