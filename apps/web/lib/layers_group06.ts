// Group 6 heritage layers (parameters3.md §5.6, issue #138).
//
// One MAP layer (p72) + four documented no-maps (p158/p272/p320/p351).
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100; unknown stays 255 (renders red). This file owns ALL Group-6
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `G06-HOOK (#138)`
// blocks, so the sibling batches stay disjoint.
//
// HONESTY (load-bearing): the Muinsuskaitseamet heritage registry
// (register.muinsuskaitseamet.ee) and the Maa-amet mka:ehitis /
// mka:kaitsevoond WFS layers are NOT in the snapshot, so p72 MUST NOT
// be presented as an official conservation-zone decision. It is a
// mapped-heritage-object-density *hinnang* (estimate) built from the
// parameters3.md §5.6 graceful-fallback source (OSM historic=* /
// heritage=* / unesco=*) — the title, legend and source say so, and the
// test below pins those markers. Green = heritage-rich surroundings
// (district-guideline character applies nearby); red = few or no mapped
// objects (hinnang, never a registry verdict).
//
// Per-param verdicts (see GROUP06_NO_MAP below; mirrors the OTA #131
// precedent — a gradient map that cannot be honestly built stays a
// scorer dim, never a faked layer):
//   p72  SHIP  "heritage": heritage-object count kernel (this file).
//   p158 NO-MAP: historical tax credits are a fiscal instrument (EUR) —
//        no registry, no OSM signal; scorer returns None (abort-deal
//        semantics per parameters3.md) — see dims_group06.py.
//   p272 NO-MAP: facade easements are parcel-legal facts; OSM maps no
//        easements. A second heritage-proximity gradient next to p72
//        would be fake differentiation — scorer None stub.
//   p320 NO-MAP (map): commission friction is a process heuristic, not a
//        place field; lives as an inverse-density scorer heuristic in
//        dims_group06.py, never as a map.
//   p351 NO-MAP: lead-glass window preservation is building-component
//        level; OSM has no window register — scorer None stub.
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf \
//     nwr/heritage nwr/historic nwr/unesco -o /tmp/hf-g06-heritage.pbf
//   1003 features; resolve_pois keeps 926, ~20 m dedupe leaves 781
//   stamped points (275 inside the Tallinn window). Top values:
//   memorial 274, ruins 170, manor 147, yes 133, archaeological_site 40,
//   wreck 36 (sea cells, harmless), fort 21, building 21. heritage=1/yes
//   are nearly absent (4) — the registry is NOT in OSM, hence hinnang.
//
// Calibration (judgment call, documented for the reviewer): unweighted
// count kernel, area-kind saturating score (100·S/(S+half)), mirroring
// the emergency path. sigma 0.8 km (coverage scale, like healthcare /
// emergency — a district is an area, not a point) and half 2, locked
// from a Tallinn-window histogram over the real foot graph (probe
// /tmp/hf-g06-probe.py): median 19 / max 97 (Old Town core). half 2,
// not 1: a lone rural manor then caps at 100/(1+2) = 33, not 50 —
// one manor is not a district. Sigma equals the Euclidean fallback
// decay (DECAY hook) and the raster contract (matchesContract).
// Recalibrate from Tallinn histograms if a county build shows
// blobbing — half/sigma live in one dict below and in
// scripts/build/batch_g06_heritage.py LAYER_DEFAULTS (kept in sync
// by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group06LayerId = "heritage";

export const GROUP06_LAYER_IDS: Group06LayerId[] = ["heritage"];

/** parameters3.md number per Group-6 map layer. */
export const GROUP06_PARAMS: Record<Group06LayerId, number> = {
  heritage: 72,
};

/**
 * Documented no-map verdicts (OTA PR #131 precedent): params whose
 * source registry is absent from the snapshot AND whose OSM fallback
 * cannot honestly carry a gradient. Scorer dims live in
 * services/scoring/dims_group06.py; the map stays silent rather than
 * painting faked precision.
 */
export const GROUP06_NO_MAP: { param: number; reason: string }[] = [
  {
    param: 158,
    reason:
      "Maksusoodustus on fiskaal-instrument (EUR): registrit snapshots pole, OSM-signaal puudub — skoorija tagastab None (Abort deal score if missing).",
  },
  {
    param: 272,
    reason:
      "Fassaadi servituut on katastriseaduslik fakt: OSM-is servituudiandmeid pole; teine pärand-tiheduse gradient p72 kõrval oleks võlts-eristus.",
  },
  {
    param: 320,
    reason:
      "Komisjoni menetlus on protsessiheuristik, mitte kohaväli: elab pöörd-tiheduse skoorija-heuristikuna (dims_group06.py), mitte kaardikihina.",
  },
  {
    param: 351,
    reason:
      "Akende säilivus on hoonekomponendi tase: OSM-is aknaregistrit pole — skoorija None-stub.",
  },
];

export const GROUP06_DEFS: LayerDef[] = [
  {
    id: "heritage",
    paramIds: [72],
    title: "Muinsusala lähedus (proksi, hinnang)",
    goodLabel: "roheline = kaardistatud muinsusobjekte tihedalt lähedal (hinnang)",
    badLabel: "punane = muinsusobjekte vähe või pole (hinnang, MITTE registriotsus)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM historic=*/heritage=*/unesco=* 781 objekti; Muinsuskaitseameti register hetktõmmises pole — lähedushinnang, mitte kaitsevööndiotsus)",
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (tihe muinsusala)
      { lat: 59.4386, lon: 24.7912 }, // Kadriorg (loss + park)
    ],
  },
];

/** Influence radius in km (== walk-kernel sigma == Euclidean fallback decay). */
export const GROUP06_DECAY: Record<Group06LayerId, number> = {
  heritage: 0.8,
};

/**
 * Overpass QL fragment for the layer inside the bbox. Snapshot-only
 * serving never queries live; this documents the source tags (nwr/
 * parity via overpassQueryFor, which rewrites `n[` — extraction used
 * nwr/heritage + nwr/historic + nwr/unesco throughout so way-mapped
 * manors/castles survive, PR #118).
 */
export const GROUP06_TAGS: Record<Group06LayerId, string> = {
  heritage: 'n["historic"];n["heritage"];n["unesco"];',
};

/** Saturation midpoint (area-kind), see calibration note above. */
export const GROUP06_HALVES: Record<Group06LayerId, number> = {
  heritage: 2,
};

export const GROUP06_BONUS: Record<Group06LayerId, BonusSpec> = {
  heritage: { kind: "area", half: 2 },
};

/**
 * Group-6 bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for every other layer (their switch/handlers own them).
 */
export function bonusSpecForGroup06(layer: string): BonusSpec | undefined {
  return (GROUP06_BONUS as Record<string, BonusSpec>)[layer];
}
