// Group 5 plans-A layers (parameters3.md §5.5, issue #161): p42 ships
// as an honest construction-activity hinnang ("ehitus"), p44 ships as
// an honest apartment-stock hinnang ("korterstock"); p45/p47/p74 are
// documented no-map with scorer dims (see G05A_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = developing/liquid (green = cranes/apartments near,
// red = none mapped); unknown stays 255 (renders red). This file owns
// ALL G05A runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts) touch it only through small
// marked `G05A-HOOK (#161)` blocks, so the sibling batches stay
// disjoint (G08B owns layers_group08b / G08B-HOOK — different file,
// different ids, different params).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): the Rahandusministeerium PLANK register and
// the Tallinna Planeeringute Register (TPR) are NOT in the snapshot,
// so NEITHER shipped layer is a planning decision:
// * ehitus is a mapped-activity *hinnang* — nearness to OSM-mapped
//   construction sites (landuse=construction areas + building=
//   construction footprints), where development is visibly happening.
//   The sites are the mapped CAUSE, never a plan ruling:
//   titles/legends/sources say "hinnang", never detailplaneering or
//   kehtestatud claims. Construction is lumpy by nature — most of the
//   county reads honestly unknown.
// * korterstock is a mapped-stock *hinnang* — nearness to OSM-mapped
//   apartment buildings (building=apartments footprints), the stock
//   an established rental market needs. The buildings are the mapped
//   CAUSE, never a rent register: titles/legends/sources say
//   "hinnang", never euros. Student-pressure tags (dormitory,
//   university) are OUT by design: they belong to p386 rentbleed
//   (#133) — korterstock never re-skins it (zero tag overlap).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p45 adaptability: a per-BUILDING structural fact (EHR series,
//   load-bearing walls, floor-plan flexibility — can THIS flat be
//   remodeled?). OSM maps footprints, never remodelability, so an
//   area gradient cannot answer the question (G02 EHR precedent,
//   #136: building attributes are not place fields). Scorer dim
//   stays NULL with an EHR/listing reason (dims_group05a.dim_adapt).
// * p47 zoning laws: a per-PARCEL prescriptive fact (the PLANK/TPR
//   designated use — what is ALLOWED). OSM landuse=* is descriptive
//   (what is BUILT), never the decree, so painting it as zoning
//   would be fake precision. Commercial-zone nearness stays
//   p223's proxy (commercial zoning bleed, later batch), never p47's.
//   Scorer dim stays NULL with a register reason
//   (dims_group05a.dim_zoning).
// * p74 rental restrictions: a per-PARCEL decree fact (KOV
//   üüripiirangud, Riigi Teataja). The 25 tourism=apartment objects
//   are short-stay SUPPLY, not restriction — zero signal by
//   construction. Scorer dim stays NULL with a KOV-check reason
//   (dims_group05a.dim_rentrestr).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/landuse=construction nwr/building=construction
//     (+ export -u type_id)
//   1084 features; the dev predicate (landuse=construction OR
//   building=construction, see scripts/build/batch_g05a_plans.py
//   is_devsite) keeps 1053 county-wide = 360 building rings + 360
//   building MultiPolygons (export duals of the same 360 closed ways)
//   + 166 landuse rings + 166 landuse MultiPolygons (duals of the
//   same 166 areas) + 1 point. read_site_points collapses each dual
//   to one bbox center, so the 20 m dedupe merges them: 518 deduped
//   sites, 156 in the Tallinn window. 31 untagged referrer nodes drop
//   out in the predicate.
//   osmium tags-filter ... nwr/building=apartments   (+ export)
//   17409 features; the apt predicate (building=apartments ONLY, see
//   is_apartstock) keeps 13952, merging to 6842 deduped footprints,
//   5827 in the Tallinn window. Staircase entrances and ADS address
//   points carry no building tag, so one footprint casts exactly one
//   vote — no entrance multi-count by construction. 3457 untagged
//   referrer nodes drop out.
//
// Calibration (judgment calls, documented for the reviewer): both
// layers are Euclidean Gaussian count kernels (sigma 0.3 km, cutoff
// 4 sigma), area-kind saturating score 100·S/(S+half), null below 3 —
// the same kind moorage (#154) adds, identical semantics (one site
// reads 50 on its own cell under half=1). ehitus halves at 1 (not 2):
// with 518 county sites a single mapped crane already reads 50
// instead of vanishing. korterstock halves at 15 (not 1): with 6842
// footprints half=1 would pin slab districts at 100 — half=15 keeps
// Lasnamäe 68 / Õismäe 72, town centre 84-87, Viimsi 41 mid,
// Paljassaare/Pirita 10 low and detached Nõmme honestly unknown.
// Halves live in G05A_CAL below and in
// scripts/build/batch_g05a_plans.py G05A_CAL (kept in sync by test).
// Measured county-raster reads (2026-09-12 full build, --probe):
// ehitus Balti 68, Viru 56, Pirita 50, Õismäe 42, Lasnamäe 16,
// Kadriorg/Viimsi/Nõmme/Paljassaare/rural unknown; korterstock Balti
// 87, Viru 84, Õismäe 72, Lasnamäe 68, Kadriorg 65, Viimsi 41,
// Paljassaare/Pirita 10, Nõmme/rural unknown. Cranes cluster BY
// DESIGN — the map shows where building happens, never a promise.

import type { BonusSpec, LayerDef } from "./layers";

export type Group05ALayerId = "ehitus" | "korterstock";

export const GROUP05A_LAYER_IDS: Group05ALayerId[] = ["ehitus", "korterstock"];

/** parameters3.md number per Group-5A layer (no-map params have no layer). */
export const GROUP05A_PARAM_IDS: Record<Group05ALayerId, number> = {
  ehitus: 42,
  korterstock: 44,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP05A_ALL_PARAMS = [42, 44, 45, 47, 74] as const;

export type Group05AParam = (typeof GROUP05A_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP05A_LAYERS: LayerDef[] = [
  {
    id: "ehitus",
    paramIds: [42],
    title: "Ehitusaktiivsus lähedal (arengu-hinnang)",
    goodLabel: "roheline = ehitus lähedal, piirkond areneb (hinnang)",
    badLabel: "punane = ehitust kaardistamata või andmed puuduvad (hinnang)",
    source: `${SNAP} (kaardistatud ehitusplatsid 518, sh Tallinnas 156; ARENGU-hinnang platside läheduse järgi, mitte planeeringuotsus — see EI OLE PLANK/TPR väljavõte)`,
    fallbackPoints: [
      { lat: 59.4405, lon: 24.7369 }, // Balti jaama ümbrus (ehitusaktiivsus)
      { lat: 59.36, lon: 24.66 }, // Nõmme eramud (ehitust kaardistamata)
    ],
  },
  {
    id: "korterstock",
    paramIds: [44],
    title: "Korterelamute tihedus (üürituru-hinnang)",
    goodLabel: "roheline = korterelamuid tihedalt, likviidne üüriturg (hinnang)",
    badLabel: "punane = korterelamuid hõredalt või andmed puuduvad (hinnang)",
    source: `${SNAP} (kaardistatud korterelamud 6842, sh Tallinnas 5827; ÜÜRITURU-hinnang hoonete tiheduse järgi, mitte üüriregister — see EI OLE üürihind eurodes)`,
    fallbackPoints: [
      { lat: 59.44, lon: 24.82 }, // Lasnamäe paneelelamud (tihe korterelamustik)
      { lat: 59.36, lon: 24.66 }, // Nõmme eramud (korterelamuid hõredalt)
    ],
  },
];

/**
 * Overpass QL fragments per Group 5A layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped footprints and construction areas). The
 * builder consumes the same predicate offline (see is_devsite /
 * is_apartstock); the landuse-vs-building split lives in the scorer
 * mapping (kinds_from_tags), so the fragment stays a plain
 * source-tags query like sibling batches.
 */
export const GROUP05A_TAGS: Record<Group05ALayerId, string> = {
  ehitus: 'n["landuse"="construction"];n["building"="construction"];',
  korterstock: 'n["building"="apartments"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP05A_DECAY: Record<Group05ALayerId, number> = {
  ehitus: 0.3,
  korterstock: 0.3,
};

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g05a_plans.py G05A_CAL exactly — a pytest
 * parses this file and fails on drift). Both carry the area-kind
 * half (saturating count).
 */
export const G05A_CAL = {
  ehitus: { half: 1, sigma: 0.3 },
  korterstock: { half: 15, sigma: 0.3 },
} as const;

/**
 * ehitus + korterstock: nearby-site count 100·S/(S+half) (area-kind,
 * moorage #154 precedent — one site reads 50 on its own cell under
 * half=1).
 */
export const GROUP05A_BONUS: Record<Group05ALayerId, BonusSpec> = {
  ehitus: { kind: "area", half: 1 },
  korterstock: { kind: "area", half: 15 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup05ALayerId(layer: string): layer is Group05ALayerId {
  return (GROUP05A_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-5A bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup05A(layer: string): BonusSpec | undefined {
  return (GROUP05A_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 5A layer (built by batch_g05a_plans.py). */
export const G05A_RASTER_FILE: Record<Group05ALayerId, string> = {
  ehitus: "ehitus-walk-raster.json",
  korterstock: "korterstock-walk-raster.json",
};

/**
 * NO metro masters (documented): smooth count-kernel fields at
 * 9.375 m cells would be fake precision. The window route serves
 * county everywhere for these layers (metro slot stays empty, like
 * G02B/G03/G03D).
 */
export const G05A_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group05aHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Area-kind saturating score 100·S/(S+half) (mirrors walk_raster.saturate). */
export function group05aAreaScore(count: number, half: number): number {
  return (100 * count) / (count + half);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group05aMatchesContract(
  layer: Group05ALayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G05A_CAL[layer].half && doc.sigma === G05A_CAL[layer].sigma;
}

export type Group05AVerdictKind = "proxy" | "real" | "no-map";

export interface Group05AVerdict {
  param: Group05AParam;
  name: string;
  kind: Group05AVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 5 batch A (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group05a.py).
 */
export const G05A_VERDICTS: Group05AVerdict[] = [
  {
    param: 42,
    name: "Future development",
    kind: "proxy",
    reason:
      "Shipped as ehitus: nearness to 518 mapped construction sites (156 in Tallinn) as a development-activity hinnang — the sites are the mapped cause, honestly labelled, never a PLANK/TPR plan ruling.",
  },
  {
    param: 44,
    name: "Rental potential",
    kind: "proxy",
    reason:
      "Shipped as korterstock: nearness to 6842 mapped apartment buildings (5827 in Tallinn) as a rental-market hinnang — the stock is the mapped cause, honestly labelled, never a rent register or euros, and never a re-skin of p386 rentbleed (zero tag overlap).",
  },
  {
    param: 45,
    name: "Adaptability",
    kind: "no-map",
    reason:
      "Per-building structural fact (EHR series, load-bearing walls, floor-plan flexibility); OSM maps footprints, never remodelability, so an area gradient cannot answer the question — building attributes are not place fields (G02 precedent).",
  },
  {
    param: 47,
    name: "Zoning laws",
    kind: "no-map",
    reason:
      "Per-parcel prescriptive fact (the PLANK/TPR designated use); OSM landuse is descriptive (what is built), never the decree — painting it as zoning would be fake precision. Commercial-zone nearness stays p223's proxy, never p47's.",
  },
  {
    param: 74,
    name: "Rental restrictions",
    kind: "no-map",
    reason:
      "Per-parcel decree fact (KOV üüripiirangud, Riigi Teataja); the 25 tourism=apartment objects are short-stay supply, not restriction — zero signal by construction.",
  },
];

/** Batch-A params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP05A_NO_MAP_PARAMS: number[] = G05A_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP05A_HOOK =
  "G05A-HOOK (#161): ehitus + korterstock wired into layers/overlays/snapshot; p45/p47/p74 verdicts + dims only.";
