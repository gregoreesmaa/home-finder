// Group 8 flood/climate-B layers (parameters3.md §5.8, issue #168):
// p255 ships as an honest tall-building proximity hinnang
// ("windtunnel"), p333 ships as an honest sea-distance hinnang
// ("saltspray"); p118/p182 are documented no-map with scorer dims
// (see G08B_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = calm (green = sheltered/clean, red = exposed); unknown
// stays 255 (renders red). This file owns ALL G08B runtime data; shared
// files (lib/layers.ts, lib/server/snapshot.ts, lib/overlays.ts) touch
// it only through small marked `G08B-HOOK (#168)` blocks, so the sibling
// batches stay disjoint (issue #167 owns layers_group08a / G08A-HOOK —
// different file, different ids, different params).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): no Ilmateenistus/ERA5 wind field, no
// Maa-amet mullakaart soil survey and no coastal corrosion register
// exist in the 2026-09-12 snapshot, so NEITHER shipped layer is
// measured data:
// * windtunnel is a mapped-cause *hinnang* — nearness to OSM-mapped
//   5+-storey buildings, whose street canyons channel wind. The
//   buildings are the mapped CAUSE, never an anemometer reading:
//   titles/legends/sources say "hinnang", never m/s or gust claims.
// * saltspray is distance to the MAPPED SEA shore (natural=coastline
//   only) — salt spray decays with distance from surf, the param's
//   own ST_Distance shape — never a corrosion-rate ruling. Lake/pond
//   spray is not salty, so standing water is OUT by design: this is
//   what keeps saltspray from re-skinning p340 shoredist (#154,
//   shore + lakes, halfM 100). Green = far inland (low exposure),
//   red = at the sea (check facade/windows/roof).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p118 drought tolerance: needs a soil survey (water retention /
//   mullakaart). The whole snapshot PBF carries ZERO soil,
//   irrigation, drought or moisture keys, so there is nothing to
//   calibrate against — not even a weak proxy. Scorer dim stays
//   NULL with a mullakaart reason (dims_group08b.dim_drought).
// * p182 prevailing wind direction: Harjumaa prevailing wind is a
//   uniform regional SW flow (Ilmateenistus climate normals) — a
//   0..100 per-parcel gradient of a uniform field would be fake
//   precision by construction. Direction is not goodness: no
//   orientation scores higher. The 6 monitoring:weather objects are
//   station points, not a direction raster. Scorer dim stays NULL
//   with an on-site orientation reason (dims_group08b.dim_winddir).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/building:levels   (+ export -u type_id)
//   33311 features; the keep_tall predicate (first ;-value >= 5, see
//   scripts/build/batch_g08b_flood.py) keeps 5622 county-wide (4
//   Points + 2794 closed footprint rings + 2824 MultiPolygons), 5512
//   in the Tallinn window (Õismäe/Mustamäe slabs, Lasnamäe,
//   Kesklinn towers). building:height is OUT by design (metres
//   confound a tall villa with a tower); building:part sections are
//   IN (same tower, merged by the 20 m dedupe). Closed footprint
//   rings are NOT relation twins — footprints carry their own
//   levels tags; untagged members drop out in keep_tall.
//   osmium tags-filter ... nwr/natural=coastline   (+ export)
//   968 features; the keep_sea predicate (coastline only) keeps 885
//   (620 lines + 265 islet/island MultiPolygons). Closed coastline
//   rings are REAL island shores (Aegna, Naissaar, Malusi), never
//   twins — densified, not dropped. 83 coast points carry no
//   natural=coastline (place=islet nodes) and drop out; their
//   island multipolygons cover them.
//
// Calibration (judgment calls, documented for the reviewer): both
// layers are nearest-source distance fields, quiet-kind calmness
// (100·d/(d+halfM)), the same kind the G07 batches add — identical
// semantics (0 on the source, 50 at halfM), shared on purpose.
// windtunnel halves at 200 m (canyon acceleration is block-scale);
// saltspray halves at 500 m (spray deposition is surf-zone scale —
// significant within hundreds of metres, negligible past ~1 km).
// Sigmas equal the Euclidean fallback decay (DECAY hook) and the
// raster contract (matchesContract). Halves live in G08B_CAL below
// and in scripts/build/batch_g08b_flood.py G08B_CAL (kept in sync by
// test). Measured county-raster reads (2026-09-12 full build,
// --probe): windtunnel Viru/Õismäe/Lasnamäe 0, Balti 27, Viimsi 43,
// Kadriorg 71, Paljassaare/Pirita 75-76, Nõmme 80, rural 99;
// saltspray Pirita 0, Paljassaare 40, Kadriorg 51, Viimsi/Balti
// 64-65, Lasnamäe 73, Viru 76, Õismäe 80, Nõmme 94, rural 98.
// Tower districts and seaside read low BY DESIGN — slab canyons DO
// channel wind and spray IS a surf-zone effect.

import type { BonusSpec, LayerDef } from "./layers";

export type Group08BLayerId = "windtunnel" | "saltspray";

export const GROUP08B_LAYER_IDS: Group08BLayerId[] = ["windtunnel", "saltspray"];

/** parameters3.md number per Group-8B layer (no-map params have no layer). */
export const GROUP08B_PARAM_IDS: Record<Group08BLayerId, number> = {
  windtunnel: 255,
  saltspray: 333,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP08B_ALL_PARAMS = [118, 182, 255, 333] as const;

export type Group08BParam = (typeof GROUP08B_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP08B_LAYERS: LayerDef[] = [
  {
    id: "windtunnel",
    paramIds: [255],
    title: "Kõrghoonete tuuletunnel (hinnang)",
    goodLabel: "roheline = kõrghoonetest kaugel, tuulevaikne (hinnang)",
    badLabel: "punane = kõrghoonete vahel, kanjoniefekt võimalik (hinnang)",
    source: `${SNAP} (kaardistatud 5+-korruselised hooned 5622, sh Tallinnas 5512; PROKSI-hinnang hoonete läheduse järgi, mitte tuulemõõtmine — see EI OLE ilmajaama mõõtmine)`,
    fallbackPoints: [
      { lat: 59.412, lon: 24.655 }, // Õismäe paneelelamud (proksi)
      { lat: 59.36, lon: 24.66 }, // Nõmme eramud (kõrghoonetest kaugel)
    ],
  },
  {
    id: "saltspray",
    paramIds: [333],
    title: "Mere soolapritse (kauguse-hinnang)",
    goodLabel: "roheline = merest kaugel, soolapritsmest väljas (hinnang)",
    badLabel: "punane = mere ääres — kontrolli fassaadi/aknaid/katust (hinnang)",
    source: `${SNAP} (kaardistatud MERERANNAJOON 885 joont/saart, järved välja — soolapritsme kauguse-hinnang; see EI OLE korrosioonikiiruse mõõtmine)`,
    fallbackPoints: [
      { lat: 59.468, lon: 24.821 }, // Pirita rand (mere ääres)
      { lat: 59.36, lon: 24.66 }, // Nõmme (merest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 8B layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped towers and the coastline). The builder
 * consumes the same predicate offline (see keep_tall / keep_sea); the
 * >= 5 levels check lives in the scorer mapping (kinds_from_tags), so
 * the fragment stays a plain source-tags query like sibling batches.
 */
export const GROUP08B_TAGS: Record<Group08BLayerId, string> = {
  windtunnel: 'n["building:levels"];',
  saltspray: 'n["natural"="coastline"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP08B_DECAY: Record<Group08BLayerId, number> = {
  windtunnel: 0.2,
  saltspray: 0.5,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g08b_flood.py G08B_CAL exactly — a pytest
 * parses this file and fails on drift).
 */
export const G08B_CAL = {
  windtunnel: { halfM: 200, sigma: 0.2 },
  saltspray: { halfM: 500, sigma: 0.5 },
} as const;

/**
 * windtunnel + saltspray: nearest-source calmness 100·d/(d+halfM)
 * (quiet-kind, G07 precedent).
 */
export const GROUP08B_BONUS: Record<Group08BLayerId, BonusSpec> = {
  windtunnel: { kind: "quiet", halfM: 200 },
  saltspray: { kind: "quiet", halfM: 500 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup08BLayerId(layer: string): layer is Group08BLayerId {
  return (GROUP08B_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-8B bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup08B(layer: string): BonusSpec | undefined {
  return (GROUP08B_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 8B layer (built by batch_g08b_flood.py). */
export const G08B_RASTER_FILE: Record<Group08BLayerId, string> = {
  windtunnel: "windtunnel-walk-raster.json",
  saltspray: "saltspray-walk-raster.json",
};

/**
 * NO metro masters (documented): smooth distance-decay fields at
 * 9.375 m cells would be fake precision. The window route serves
 * county everywhere for these layers (metro slot stays empty, like
 * G07B/G03D).
 */
export const G08B_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group08bHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function group08bQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group08BPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM per layer).
 */
export function group08bQuietnessAt(
  layer: Group08BLayerId,
  lat: number,
  lon: number,
  points: Group08BPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group08bHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group08bQuietFromHalf(best * 1000, G08B_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group08bMatchesContract(
  layer: Group08BLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G08B_CAL[layer].halfM && doc.sigma === G08B_CAL[layer].sigma;
}

export type Group08BVerdictKind = "proxy" | "real" | "no-map";

export interface Group08BVerdict {
  param: Group08BParam;
  name: string;
  kind: Group08BVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 8 batch B (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group08b.py).
 */
export const G08B_VERDICTS: Group08BVerdict[] = [
  {
    param: 118,
    name: "Drought tolerance",
    kind: "no-map",
    reason:
      "Needs a soil survey (water retention / mullakaart); the whole snapshot PBF carries zero soil, irrigation, drought or moisture keys — nothing to calibrate even a weak proxy against.",
  },
  {
    param: 182,
    name: "Prevailing wind direction",
    kind: "no-map",
    reason:
      "Harjumaa prevailing wind is a uniform regional SW flow, so a 0..100 per-parcel gradient would be fake precision by construction — and direction is not goodness. The 6 monitoring:weather objects are station points, not a direction raster.",
  },
  {
    param: 255,
    name: "Wind tunneling effects",
    kind: "proxy",
    reason:
      "Shipped as windtunnel: nearness to 5622 mapped 5+-storey buildings (5512 in Tallinn) as a canyon-effect hinnang — the buildings are the mapped cause, honestly labelled, never an anemometer reading.",
  },
  {
    param: 333,
    name: "Salt air corrosion exposure",
    kind: "proxy",
    reason:
      "Shipped as saltspray: distance to the mapped SEA shore only (885 coastline lines/islands, lakes out) is the param's own ST_Distance shape — honestly labelled, never a corrosion-rate ruling, and never a re-skin of p340 shoredist.",
  },
];

/** Batch-B params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP08B_NO_MAP_PARAMS: number[] = G08B_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP08B_HOOK =
  "G08B-HOOK (#168): windtunnel + saltspray wired into layers/overlays/snapshot; p118/p182 verdicts + dims only.";
