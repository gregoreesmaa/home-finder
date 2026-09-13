// Group 5 plans-F layers (parameters3.md §5.5, issue #166): p485 ships
// as an honest derelict-stock proximity hinnang ("upcycle"); p389 is
// a documented no-map with a scorer dim (see G05F_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = reuse potential nearby (green = opportunity pocket,
// red = stable/no mapped stock); unknown stays 255 (renders red).
// This file owns ALL G05F runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts) touch it only through small
// marked `G05F-HOOK (#166)` blocks, so the sibling batches stay
// disjoint (issues #161/#162/#163/#164 own G05A/G05B/G05C/G05D,
// #165 owns G05E — different files, different ids, different params).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Rahandusministeerium PLANK register and
// the Tallinna Planeeringute Register are NOT in the 2026-09-12
// snapshot, so the shipped layer is NOT a rezoning readout:
// * upcycle is a mapped-stock *hinnang* — nearness to OSM-mapped
//   abandoned/disused buildings (the reuse candidate STOCK), never a
//   KOV decision that any parcel WILL be rezoned. A rezoning ruling
//   itself is a per-parcel legal fact; the layer scores where the
//   stock sits, honestly labelled. Green near the stock reads as
//   opportunity the way buildout green reads as growth (G05B #162:
//   a buyer wanting stillness reads HIGH as "busy" — the reason
//   names the derelict stock so both readings stay honest).
//
// NO-MAP VERDICT (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p389 dark sky community designation: a designation-register fact
//   (DarkSky International places program). The whole snapshot PBF
//   carries ZERO dark-sky keys (verified: dark_sky/darksky/lighting
//   filters match 0 features), and the only mappable darkness signal
//   (lit-density) is already owned by p63's darksky proxy
//   (layers_genv.ts) — a second gradient would re-skin that layer.
//   Sibling p188 (dark sky compliance, same IDA register) already
//   went no-map for exactly these reasons (#162). Scorer dim stays
//   NULL with an IDA-register reason (dims_group05f.dim_darksky).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/abandoned nwr/disused nwr/abandoned:building
//     nwr/disused:building nwr/abandoned:landuse
//   336 features; the keep_upcycle predicate (abandoned=yes or
//   disused=yes WITH a building key, or abandoned:building with a
//   building-ish value — see scripts/build/batch_g05f_plans.py) keeps
//   202 county-wide (114 after the 20 m dedupe, 77 in the Tallinn
//   window). The raw extract is way-mapped (69 outlines + 69 building
//   lines in the window, zero points), so nwr/ parity is
//   load-bearing (PR #118). Dropped BY DESIGN (documented, not
//   hidden): 84 forest/military bunkers (building=bunker or
//   abandoned:building=bunker — a bunker field is not rezoning
//   stock), bare disused=yes without a building key (stale flags —
//   incl. the ACTIVE Reisisadama A-terminal, which carries
//   disused=yes), abandoned=tunnel/highway fragments (infrastructure,
//   not buildings), abandoned:landuse=quarry/landfill (quarries are
//   already scored as nuisance in p408 lowspec; landfills are
//   env-health), untagged relation members, and mistagged
//   abandoned:building=roof/level_crossing (not building types).
//   Zero overlap with landuse=industrial/brownfield (verified), so
//   industprox (G07) and brownsoil (G07B) are never re-skinned.
//
// Calibration (judgment call, documented for the reviewer): upcycle
// is an area-kind count kernel (Gaussian sigma 0.3, score
// 100·S/(S+half), moorage precedent) with half=2 — the buildout
// precedent (#162) at the same city scale (138 deduped Tallinn
// sites, clustered): TWO nearby derelict buildings read 50, so a
// single fenced ruin does not paint the block green alone. Sigmas
// equal the Euclidean fallback decay (DECAY hook) and the raster
// contract (matchesContract). Half lives in G05F_CAL below and in
// scripts/build/batch_g05f_plans.py G05F_CAL (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group05FLayerId = "upcycle";

export const GROUP05F_LAYER_IDS: Group05FLayerId[] = ["upcycle"];

/** parameters3.md number per Group-5F layer (no-map params have no layer). */
export const GROUP05F_PARAM_IDS: Record<Group05FLayerId, number> = {
  upcycle: 485,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP05F_ALL_PARAMS = [389, 485] as const;

export type Group05FParam = (typeof GROUP05F_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP05F_LAYERS: LayerDef[] = [
  {
    id: "upcycle",
    paramIds: [485],
    title: "Ümberarenduse potentsiaal (mahajäetud hoonete hinnang)",
    goodLabel: "roheline = mahajäetud hooned lähedal, ümberarenduse potentsiaal (hinnang)",
    badLabel: "punane = mahajäetud hooned kaugel või andmed puuduvad — stabiilne hoonestus (hinnang)",
    source: `${SNAP} (kaardistatud 202 mahajäetud/kasutusest väljas hoonet, sh Tallinnas 77 (20 m dubleerimiseta) — punkrid, kai-terminali vanalipud ja karjäärid VÄLJA; taaskasutuskõlbliku fondi läheduse hinnang, küllastus 2 — see EI OLE KOV ümberarendamisotsus)`,
    fallbackPoints: [
      { lat: 59.43205, lon: 24.76142 }, // Kesklinna kasutusest väljas tööstushoone (fondi ääres)
      { lat: 59.36, lon: 24.66 }, // Nõmme keskus (mahajäetud hoonetest kaugel)
    ],
  },
];

/**
 * Overpass QL fragment per Group 5F layer (documents the source tags;
 * the app serves the frozen snapshot, never live Overpass). n/ shape:
 * the shared overpassQueryFor() rewrites n[ to nwr/ (PR #118:
 * node-only silently drops way-mapped building outlines — the whole
 * Tallinn window here is ways, zero points). The builder consumes the
 * same predicate offline (see keep_upcycle); the bunker/stale-flag
 * exclusions live in the scorer mapping (kinds_from_tags), so the
 * fragment stays a plain source-tags query like sibling batches.
 */
export const GROUP05F_TAGS: Record<Group05FLayerId, string> = {
  upcycle: 'n["abandoned"];n["disused"];n["abandoned:building"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP05F_DECAY: Record<Group05FLayerId, number> = {
  upcycle: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g05f_plans.py G05F_CAL exactly — a pytest
 * parses this file and fails on drift). upcycle carries the area-kind
 * half (saturating count, buildout precedent).
 */
export const G05F_CAL = {
  upcycle: { half: 2, sigma: 0.3 },
} as const;

/**
 * upcycle: nearby-stock count 100·S/(S+half) (area-kind, G05B
 * buildout precedent — green NEAR the stock).
 */
export const GROUP05F_BONUS: Record<Group05FLayerId, BonusSpec> = {
  upcycle: { kind: "area", half: 2 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup05FLayerId(layer: string): layer is Group05FLayerId {
  return (GROUP05F_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-5F bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup05F(layer: string): BonusSpec | undefined {
  return (GROUP05F_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master file per Group 5F layer (built by batch_g05f_plans.py). */
export const G05F_RASTER_FILE: Record<Group05FLayerId, string> = {
  upcycle: "upcycle-walk-raster.json",
};

/**
 * NO metro master (documented): a sparse count kernel at 9.375 m
 * cells would be fake precision. The window route serves county
 * everywhere for this layer (metro slot stays empty, like
 * G07B/G03D/G08B/G05B/G05C/G05D/G05A).
 */
export const G05F_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group05fHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface Group05FPoint {
  lat: number;
  lon: number;
}

/** Area-kind saturating score 100·S/(S+half) (mirrors walk_raster.saturate). */
export function group05fAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group05fMatchesContract(
  layer: Group05FLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G05F_CAL[layer].half && doc.sigma === G05F_CAL[layer].sigma;
}

export type Group05FVerdictKind = "proxy" | "real" | "no-map";

export interface Group05FVerdict {
  param: Group05FParam;
  name: string;
  kind: Group05FVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 5 batch F (the no-map row is the docs
 * evidence; scorer dims live in services/scoring/dims_group05f.py).
 */
export const G05F_VERDICTS: Group05FVerdict[] = [
  {
    param: 389,
    name: "Dark sky community designation",
    kind: "no-map",
    reason:
      "A designation-register fact (DarkSky International places program); the whole snapshot PBF carries zero dark-sky keys, and the only mappable darkness signal is already owned by p63's darksky proxy — a second gradient would re-skin that layer (sibling p188, same IDA register, already no-map #162).",
  },
  {
    param: 485,
    name: "Zoning upcycling potential",
    kind: "proxy",
    reason:
      "Shipped as upcycle: count of 202 mapped abandoned/disused buildings nearby (77 deduped in Tallinn) as reuse-stock hinnang, area-kind like buildout — honestly labelled, never a KOV rezoning ruling; bunkers, stale disused flags and quarries are out by design.",
  },
];

/** Batch-F params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP05F_NO_MAP_PARAMS: number[] = G05F_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP05F_HOOK =
  "G05F-HOOK (#166): upcycle wired into layers/overlays/snapshot; p389 verdict + dim only.";
