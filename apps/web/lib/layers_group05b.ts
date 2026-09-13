// Group 5 plans-B layers (parameters3.md §5.5, issue #162): p106 ships
// as an honest community-garden/allotment proximity hinnang
// ("gardens"), p146 ships as an honest construction-activity proximity
// hinnang ("buildout"); p107/p186/p188 are documented no-map with
// scorer dims (see G05B_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100; unknown stays 255 (renders red). This file owns ALL G05B
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `G05B-HOOK (#162)`
// blocks, so the sibling batches stay disjoint (issue #161 owns
// layers_group05a / G05A-HOOK, #163 owns G05C, #164 owns G05D —
// different files, different ids, different params).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the PLANK WFS (planeeringud.ee) and the
// Tallinna Planeeringute Register are NOT in the snapshot, so NEITHER
// shipped layer is a planning-register readout:
// * gardens is a mapped-facility *hinnang* — nearness to OSM-mapped
//   community gardens (garden:type=community) and allotments
//   (landuse=allotments: aiandusühistud), never a soil/capability
//   survey. A capability rating itself is a per-parcel agronomic
//   fact; the layer scores growing OPPORTUNITY (existing gardens
//   nearby), honestly labelled.
// * buildout is a mapped-activity *hinnang* — nearness to OSM-mapped
//   construction sites (landuse=construction: Hipodroomi kvartal,
//   City Plaza 2, Reaalkooli juurdeehitus...), never the plan's
//   target density. Sites under construction ARE the density being
//   added, so nearness reads as densification pressure; green =
//   developing/growing, red = built-out/quiet (judgment call, see
//   below — a buyer wanting stillness reads red as calm).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p107 livestock/equestrian zoning: a per-parcel LEGAL fact (is
//   livestock allowed on THIS parcel?). OSM maps facility LOCATIONS,
//   and the whole Tallinn window holds exactly ONE mapped site
//   (Veskimetsa, Paldiski mnt 135: 2 pitches + buildings, exported
//   as 8 ring/pitch twins) — a 0..100 city gradient off a single
//   site would be fake precision by construction. County sites
//   (Niitvälja, Lagedi, Järve...) lie outside the buyer window.
//   Scorer dim stays NULL with a KOV-check reason
//   (dims_group05b.dim_livestock).
// * p186 gray-water system legality: a per-parcel legal fact (KOV
//   ehitusmäärus + Veevärk connection terms). The whole snapshot PBF
//   carries ZERO graywater/greywater/wastewater-gray keys
//   (verified: graywater/greywater/wastewater=graywater filters
//   match 0 features), so there is nothing to calibrate even a
//   weak proxy against. Scorer dim stays NULL with a KOV-table
//   reason (dims_group05b.dim_graywater).
// * p188 dark sky compliance: compliance is an IDA-designation legal
//   fact, and the only mappable signal (lit=yes + street_lamp) is
//   already owned by p63's darksky proxy (layers_genv.ts, unwired
//   GENV batch — same tags, same darksky-walk-raster.json). A
//   second gradient on identical tags would re-skin that layer.
//   Scorer dim stays NULL with an IDA-register reason
//   (dims_group05b.dim_darksky).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/leisure=garden nwr/landuse=allotments
//   gardens predicate (keep_garden in scripts/build/batch_g05b_plans.py:
//   landuse=allotments OR (leisure=garden AND (garden:type=community
//   OR garden:style=kitchen))) keeps 155 + 198 = 353 features
//   county-wide, 115 in the Tallinn window (76 after the 20 m
//   dedupe): Raadiku kogukonna peenrad, Kalamaja ürdiaed, Krulli
//   aed, Pääsküla aed, EKA ülikooliaed... Untagged relation members
//   (addr:*, barrier=gate fragments — thousands in the raw garden
//   extract) carry no garden tags, so they drop out in keep_garden.
//   leisure=garden WITHOUT garden:type (2988 residential gardens in
//   the window) is OUT by design: a private backyard is not growing
//   opportunity. landuse=orchard is OUT by design: p409 agrifield
//   (#143) already scores farmland/meadow/orchard proximity —
//   keeping it here would re-skin that layer.
//   osmium tags-filter ... nwr/landuse=construction
//   363 features; keep_buildout (landuse=construction) keeps 332
//   county-wide, 177 in the Tallinn window (138 after the 20 m
//   dedupe): Hipodroomi kvartal, City Plaza 2, Reaalkooli
//   juurdeehitus... Untagged construction-relation members
//   (barrier=gate/access fragments) drop out in keep_buildout.
//
// Calibration (judgment calls, documented for the reviewer):
// * gardens (p106): Euclidean Gaussian count kernel (sigma 0.3 km),
//   area-kind saturating score 100·S/(S+half), half=1 (moorage #154
//   precedent: facilities are sparse — 76 deduped Tallinn sites —
//   so ONE mapped garden already reads 50 on its own cell
//   instead of vanishing).
// * buildout (p146): same kernel, half=2: construction polygons are
//   denser (138 deduped Tallinn sites) and cluster (one development
//   maps several polygons), so TWO nearby sites read 50 — a single
//   fenced pit does not paint the block green alone.
//   Mirrors scripts/build/batch_g05b_plans.py G05B_CAL exactly (a
//   pytest parses this file and fails on drift).
//
// Measured county-raster reads (2026-09-12 full build, --probe):
// gardens Kalamaja 81 (Kalamaja ürdiaed), Raadiku 65, Hipodroom 43,
// Viru 39, Lasnamäe 16, Nõmme/Pirita/rural unknown (255, renders
// red — honestly no mapped garden within 1.2 km, never zero).
// buildout Hipodroom 41 (Hipodroomi kvartal), Viru 51, Kalamaja 36,
// Nõmme/Lasnamäe/Pirita 16-17, Raadiku/rural unknown. Most of the
// county reads unknown BY DESIGN — sparse kernels cover ~1.5% of
// cells; the map shows opportunity pockets, not a city wash.

import type { BonusSpec, LayerDef } from "./layers";

export type Group05BLayerId = "gardens" | "buildout";

export const GROUP05B_LAYER_IDS: Group05BLayerId[] = ["gardens", "buildout"];

/** parameters3.md number per Group-5B layer (no-map params have no layer). */
export const GROUP05B_PARAM_IDS: Record<Group05BLayerId, number> = {
  gardens: 106,
  buildout: 146,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP05B_ALL_PARAMS = [106, 107, 146, 186, 188] as const;

export type Group05BParam = (typeof GROUP05B_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP05B_LAYERS: LayerDef[] = [
  {
    id: "gardens",
    paramIds: [106],
    title: "Kogukonnaaiad ja aiandusühistud (kasvatusvõimaluse hinnang)",
    goodLabel: "roheline = kogukonnaaed või aiandusühistu lähedal (hinnang)",
    badLabel: "punane = kasvatuskohad kaugel või andmed puuduvad (hinnang)",
    source: `${SNAP} (OSM kogukonnaaiad + aiandusühistud, Tallinnas 76 paika — kasvatusvõimaluse läheduse hinnang; viljakuse hinnang ise on krundi-põhine fakt — see EI OLE mullauuring)`,
    fallbackPoints: [
      { lat: 59.44757, lon: 24.74131 }, // Kalamaja ürdiaed (aianduse ääres)
      { lat: 59.36, lon: 24.66 }, // Nõmme keskus (aedadest kaugel)
    ],
  },
  {
    id: "buildout",
    paramIds: [146],
    title: "Ehitustegevus (tulevase tiheduse hinnang)",
    goodLabel: "roheline = ehitus lähedal, piirkond tiheneb (hinnang)",
    badLabel: "punane = ehitustegevus kaugel — valmis/rahulik piirkond (hinnang)",
    source: `${SNAP} (OSM ehitusplatsid landuse=construction, Tallinnas 138 paika: Hipodroomi kvartal, City Plaza 2... — tihenemissurve hinnang; see EI OLE planeeringu sihttihedus)`,
    fallbackPoints: [
      { lat: 59.43249, lon: 24.70261 }, // Hipodroomi kvartal (ehituse ääres)
      { lat: 59.36, lon: 24.66 }, // Nõmme keskus (suurehitusteta)
    ],
  },
];

/**
 * Overpass QL fragments per Group 5B layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped garden areas and construction polygons).
 * The builder consumes the same predicate offline (see keep_garden /
 * keep_buildout); the garden:type/community check lives in the scorer
 * mapping (kinds_from_tags), so the fragment stays a plain source-tags
 * query like sibling batches.
 */
export const GROUP05B_TAGS: Record<Group05BLayerId, string> = {
  gardens: 'n["leisure"="garden"];n["landuse"="allotments"];',
  buildout: 'n["landuse"="construction"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP05B_DECAY: Record<Group05BLayerId, number> = {
  gardens: 0.3,
  buildout: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g05b_plans.py G05B_CAL exactly — a pytest
 * parses this file and fails on drift). Both carry the area-kind
 * half (saturating count).
 */
export const G05B_CAL = {
  gardens: { half: 1, sigma: 0.3 },
  buildout: { half: 2, sigma: 0.3 },
} as const;

/**
 * gardens + buildout: nearby-facility count 100·S/(S+half) (area-kind,
 * G03D moorage precedent).
 */
export const GROUP05B_BONUS: Record<Group05BLayerId, BonusSpec> = {
  gardens: { kind: "area", half: 1 },
  buildout: { kind: "area", half: 2 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup05BLayerId(layer: string): layer is Group05BLayerId {
  return (GROUP05B_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-5B bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup05B(layer: string): BonusSpec | undefined {
  return (GROUP05B_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 5B layer (built by batch_g05b_plans.py). */
export const G05B_RASTER_FILE: Record<Group05BLayerId, string> = {
  gardens: "gardens-walk-raster.json",
  buildout: "buildout-walk-raster.json",
};

/**
 * NO metro masters (documented): sparse count kernels at 9.375 m
 * cells would be fake precision. The window route serves county
 * everywhere for these layers (metro slot stays empty, like
 * G02B/G03/G03D).
 */
export const G05B_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group05bHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

export interface Group05BPoint {
  lat: number;
  lon: number;
}

/** Area-kind saturating score 100·S/(S+half) (mirrors walk_raster.saturate). */
export function group05bAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group05bMatchesContract(
  layer: Group05BLayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G05B_CAL[layer].half && doc.sigma === G05B_CAL[layer].sigma;
}

export type Group05BVerdictKind = "proxy" | "real" | "no-map";

export interface Group05BVerdict {
  param: Group05BParam;
  name: string;
  kind: Group05BVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 5 batch B (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group05b.py).
 */
export const G05B_VERDICTS: Group05BVerdict[] = [
  {
    param: 106,
    name: "Urban farming capability",
    kind: "proxy",
    reason:
      "Shipped as gardens: nearness to 76 mapped community gardens/allotments in Tallinn (155 + 198 kept county-wide) as growing-opportunity hinnang — honestly labelled, never a soil survey; private backyards and orchards stay out so it never re-skins p409 agrifield.",
  },
  {
    param: 107,
    name: "Livestock/equestrian zoning",
    kind: "no-map",
    reason:
      "Per-parcel legal fact (is livestock allowed HERE?); the whole Tallinn window holds exactly one mapped site (Veskimetsa, 8 ring/pitch twins) — a 0..100 city gradient off a single site would be fake precision by construction.",
  },
  {
    param: 146,
    name: "Future neighborhood density",
    kind: "proxy",
    reason:
      "Shipped as buildout: nearness to 138 mapped construction sites in Tallinn (332 kept county-wide, e.g. Hipodroomi kvartal) as densification-pressure hinnang — sites under construction ARE the density being added, honestly labelled, never the plan's target density.",
  },
  {
    param: 186,
    name: "Gray-water system legality",
    kind: "no-map",
    reason:
      "Per-parcel legal fact (KOV ehitusmäärus + connection terms); the whole snapshot PBF carries zero graywater/greywater keys — nothing to calibrate even a weak proxy against.",
  },
  {
    param: 188,
    name: "Dark sky compliance",
    kind: "no-map",
    reason:
      "Compliance is an IDA-designation legal fact, and the only mappable signal (lit=yes + street_lamp) is already owned by p63's darksky proxy (layers_genv.ts) — a second gradient on identical tags would re-skin that layer.",
  },
];

/** Batch-B params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP05B_NO_MAP_PARAMS: number[] = G05B_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP05B_HOOK =
  "G05B-HOOK (#162): gardens + buildout wired into layers/overlays/snapshot; p107/p186/p188 verdicts + dims only.";
