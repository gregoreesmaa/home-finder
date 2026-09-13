// Group 8 flood/climate layers, batch A (parameters3.md §5.8, issue
// #167): p69 ships as an honest forest-clearance hinnang
// ("wildfire"); p46/p112/p117 are documented no-map with scorer dims
// (see G08A_VERDICTS below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100; unknown stays 255 (renders red). This file owns ALL G08A
// runtime data; shared files (lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts) touch it only through small marked `G08A-HOOK (#167)`
// blocks, so the sibling batches stay disjoint.
//
// HONESTY (load-bearing): the Keskkonnaagentuur flood-hazard WFS
// (Üleujutusohuga alad return-period polygons), Ilmateenistus/ERA5
// archives, any flood-event register, any DEM/elevation grid and any
// sea-level projection are NOT in the snapshot (MANIFEST gaps say
// registries "not yet pulled"), so p69 MUST NOT be presented as
// measured fire risk, burn probability or a fire-service verdict. It
// is a mapped-vegetation clearance *hinnang* — the title, legend and
// source say "tuleohutusproksi (hinnang)". Green = far from mapped
// flammable vegetation (defensible-space assumption), red =
// inside/adjacent (no clearance — check on site).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p46 environmental risks: a composite incident-per-capita INDEX
//   (Weighted incident per capita, KOV-table fallback). No incident
//   register exists in the snapshot, and every mappable hazard source
//   already scores under its own layer — a composite gradient would
//   re-skin the whole registry. Scorer dim stays NULL with a
//   KOV-table reason (dims_group08a.dim_envrisk).
// * p112 flood history and elevation: needs an event archive (WHAT
//   flooded before) plus elevation (HOW high). The snapshot has
//   neither: flood_prone=yes is mapped on 8 LineString segments
//   county-wide (verified 2026-09-12, see below) — far too thin to
//   carry a gradient — and any water-proximity field would re-skin
//   the p50 drainage layer (#151), which already consumes the full
//   hydro extract (coast + inland water + wetlands + waterways).
//   Scorer dim stays NULL with an archive/DEM-check reason
//   (dims_group08a.dim_floodhist).
// * p117 sea level rise projections: needs a DEM plus a projection
//   curve (CMEMS/IPCC); the snapshot has neither. A coastline-distance
//   gradient would re-skin the p340 shoredist layer (#154, same half)
//   while faking projection precision. Scorer dim stays NULL with a
//   DEM/projection reason (dims_group08a.dim_searise).
//
// Boundary with sibling batches (reviewable per AGENTS.md §7.5):
// * p356 woodfire (#139) scores distance to mapped WOODEN HOUSES
//   (building:material=wood — structure-to-structure fire spread).
//   This batch scores distance to mapped FLAMMABLE VEGETATION
//   (landuse=forest, natural=wood/scrub/heath — wildland fuel around
//   the structure). Different sources, different buyer question
//   (defensible clearance vs wooden-neighbour spread); shared "fire"
//   family flagged for the integrator.
// * p257 vectorhabitat (#142) shares the forest sources but answers
//   ticks/mosquitoes at halfM 300 m over habitat polygons INCLUDING
//   meadow/wetland. This batch is forest-fuel ONLY (meadow/wetland
//   excluded — a hayfield is not wildfire fuel) at the tighter
//   defensible-space halfM 100 m. Same shared-source flag.
// * p88/p101 forage (#134) scores forest proximity POSITIVE (green =
//   near forest, count kernel for mushroom/berry ground). Opposite
//   polarity, different question — no conflict.
// * p50 drainage (#151) and p340 shoredist (#154) own the water
//   side; this batch touches no water tag (p112/p117 stay no-map for
//   exactly that reason).
//
// Tag verification (2026-09-12, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/landuse=forest nwr/natural=wood nwr/natural=scrub
//     nwr/natural=heath -o /tmp/hf-fuel.pbf
//   20682 features; tagged areas (kept by the reader): forest 4525 +
//   wood 3625 + scrub 1652 + heath 171 MultiPolygons (~10k fuel
//   polygons, matching the #134 forage count). Closed-way LineString
//   twins dropped by the reader; ~100 Points + ~600 untagged member
//   objects dropped. natural=grassland (86 areas: lawns/parks, not
//   fuel) and natural=water twins pulled in by relation members are
//   DELIBERATELY excluded by the keeper.
//   flood_prone probe (p112 evidence):
//   osmium tags-filter $PBF 'nwr/flood_prone' -> 30 features, only 8
//   with flood_prone=yes (all LineString river segments) — no polygon
//   signal, gradient impossible.
//
// Calibration (judgment call, documented for the reviewer):
// nearest-fuel quietness 100·d/(d+100), sigma 0.3 km. halfM=100 m is
// the defensible-space scale (structure clearance is won or lost in
// the first hundred metres) AND the grid-honest minimum (75 m county
// step — a 30 m half would be sub-cell fake precision); sigma 0.3
// keeps Euclidean-fallback parity with the shoredist layer (#154),
// the other halfM-100 quiet layer. Measured snapshot probes
// (ring-sample distances, 2026-09-12): Nõmme-mets 12 m -> 11,
// Nõmme-keskus 26 m -> 21, Lasnamäe 58 m -> 37, Vanalinn 141 m -> 59,
// Pirita 277 m -> 73, Kalamaja 347 m -> 78. The city spreads across
// the ramp (forest-edge red, built-up mid-green) instead of blobbing.
// Mirrors scripts/build/batch_g08a_flood.py G08A_CAL exactly (a
// pytest parses this file and fails on drift).

import type { BonusSpec, LayerDef, LayerId } from "./layers";

export type G08ALayerId = "wildfire";

export const G08A_LAYER_IDS: G08ALayerId[] = ["wildfire"];

/** parameters3.md parameter numbers per shipped layer. */
export const G08A_PARAM_IDS: Record<G08ALayerId, number[]> = {
  wildfire: [69],
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const G08A_ALL_PARAMS = [46, 69, 112, 117] as const;

export type G08AParam = (typeof G08A_ALL_PARAMS)[number];

export const G08A_LAYERS: LayerDef[] = [
  {
    id: "wildfire",
    paramIds: [69],
    title: "Metsatuleohu puhver (tuleohutusproksi, hinnang)",
    goodLabel: "roheline = metsast kaugel, kaitseruum olemas (proksi, hinnang)",
    badLabel: "punane = metsa servas või sees, kaitseruum puudub (proksi, hinnang)",
    source:
      "kohalik hetktõmmis 2026-09-12 (OSM mets/puistu/võsa/nõmm ~10 tuhat polügooni; PROKSI-hinnang, mitte mõõdetud risk — heina-/niidumaad välja, need pole kütus)",
    fallbackPoints: [
      { lat: 59.3862, lon: 24.6611 }, // Nõmme mets (kütuse servas)
      { lat: 59.45, lon: 24.75 }, // Kalamaja (metsast kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per G08A layer (documents the source tags; the
 * snapshot builder consumes them offline — no live fetch in code/tests).
 * n/ shape: the shared overpassQueryFor() rewrites n[ to nwr/ (PR #118:
 * node-only would drop way-mapped forest polygons). Meadow/wetland stay
 * OUT by design (p257 vectorhabitat owns the habitat reading; hayfields
 * and bogs are not wildfire fuel).
 */
export const G08A_TAGS: Record<G08ALayerId, string> = {
  wildfire: 'n["landuse"="forest"];n["natural"~"wood|scrub|heath"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const G08A_RASTER_FILE: Record<G08ALayerId, string> = {
  wildfire: "wildfire-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay proxy is smooth at
 * the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for this layer (G02B/G03
 * precedent).
 */
export const G08A_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same
 * scale story as the raster sigma): steep enough that forest-edge
 * pockets beat background.
 */
export const G08A_DECAY_KM: Record<G08ALayerId, number> = {
  wildfire: 0.3,
};

export function g08aRadiusKmFor(layer: G08ALayerId): number {
  return G08A_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g08a_flood.py G08A_CAL exactly — a pytest
 * parses this file and fails on drift).
 */
export const G08A_CAL = {
  wildfire: { halfM: 100, sigma: 0.3 },
} as const;

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isG08ALayerId(layer: LayerId): layer is G08ALayerId {
  return (G08A_LAYER_IDS as string[]).includes(layer);
}

/**
 * G08A bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup08A(layer: string): BonusSpec | undefined {
  if (layer === "wildfire") return { kind: "quiet", halfM: G08A_CAL.wildfire.halfM };
  return undefined;
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function g08aHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-fuel clearance 0..100: 0 in the fuel, 50 at halfM. */
export function g08aQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface G08APoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback wildfire clearance 0..100 (raster missing). Null
 * when there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM).
 */
export function g08aQuietnessAt(
  lat: number,
  lon: number,
  points: G08APoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = g08aHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(g08aQuietFromHalf(best * 1000, G08A_CAL.wildfire.halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function g08aMatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: G08ALayerId,
): boolean {
  if (!doc) return false;
  if (doc.sigma !== G08A_DECAY_KM[layer]) return false;
  return doc.half === G08A_CAL[layer].halfM;
}

export type G08AVerdictKind = "proxy" | "real" | "no-map";

export interface G08AVerdict {
  param: G08AParam;
  name: string;
  kind: G08AVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 8 batch A (the no-map rows are the docs
 * evidence; scorer dims live in services/scoring/dims_group08a.py).
 */
export const G08A_VERDICTS: G08AVerdict[] = [
  {
    param: 46,
    name: "Environmental risks",
    kind: "no-map",
    reason:
      "Composite incident-per-capita index (KOV-table fallback); no incident register exists in the snapshot, and every mappable hazard already scores under its own layer — a composite gradient would re-skin the whole registry.",
  },
  {
    param: 69,
    name: "Wildfire defensible space",
    kind: "proxy",
    reason:
      "Shipped as wildfire: clearance to ~10k mapped forest/wood/scrub/heath fuel polygons as defensible-space hinnang at halfM 100 m — honestly labelled, never fire surveillance (wooden houses stay on p356 woodfire, ticks on p257).",
  },
  {
    param: 112,
    name: "Flood history and elevation",
    kind: "no-map",
    reason:
      "Needs an event archive plus a DEM; the snapshot has neither (flood_prone=yes sits on 8 LineString segments county-wide — no polygon signal), and any water-proximity field would re-skin p50 drainage.",
  },
  {
    param: 117,
    name: "Sea level rise projections",
    kind: "no-map",
    reason:
      "Needs a DEM plus a projection curve (CMEMS/IPCC); the snapshot has neither, and a coastline-distance gradient would re-skin p340 shoredist at the same half while faking projection precision.",
  },
];

/** Batch-A params with no honest map (dims-only, OTA PR #131 precedent). */
export const G08A_NO_MAP_PARAMS: number[] = G08A_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const G08A_HOOK =
  "G08A-HOOK (#167): wildfire wired into layers/overlays/snapshot; p46/p112/p117 verdicts + dims only.";
