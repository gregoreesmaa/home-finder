// Group 18 rest-A layers (parameters3.md §5.18, issue #172): p34 ships
// as an honest tall-mass openness hinnang ("dayopen"), p305 ships as
// an honest glass-facade distance hinnang ("glassglare"); p100/p231/
// p287 are documented no-map with scorer dims (see G18A_VERDICTS
// below).
//
// Harjumaa scope, local 2026-09-12 snapshot ONLY. Scores are absolute
// 0..100, high = calm (green = open/glare-free, red = shadowed/glare-
// exposed); both layers are total fields (far-from-source reads calm,
// honestly). This file owns ALL G18A runtime data; shared files
// (lib/layers.ts, lib/server/snapshot.ts, lib/overlays.ts) touch
// it only through small marked `G18A-HOOK (#172)` blocks, so the sibling
// batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef,
// LayerId): no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): Maa-amet LoD2 3D meshes, PVLib ray-tracing,
// sun-hour measurements, lux meters and floorplans are NOT in the
// 2026-09-12 snapshot, so NEITHER shipped layer is measured data:
// * dayopen is a mapped-mass *hinnang* — nearness to OSM-mapped tall
//   buildings (levels >= 4, sol_tall precedent from #123), never sun
//   hours. Untagged buildings read as low-rise BY DESIGN (levels
//   coverage is sparse); trees are OUT by design (leafy low-rise
//   streets have good daylight — only tall masses count).
// * glassglare is a mapped-facade *hinnang* — distance to OSM-mapped
//   glass/mirror facades, the param's own exposure shape — never a
//   lux reading. Plaster/wood/brick drop out BY DESIGN (not
//   reflective); polygons feed rings with NO fill (glare is an
//   outside-view fact).
//
// NO-MAP VERDICTS (documented, OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate):
// * p100 window placement/cross-ventilation: a per-FLOORPLAN fact
//   (window positions, through-ventilation needs the unit layout).
//   Exactly 1 window tag exists county-wide — zero area signal.
//   Scorer dim stays NULL with a floorplan reason
//   (dims_group18resta.dim_crossvent).
// * p231 driveway incline angle: a per-parcel CONSTRUCTION fact (the
//   driveway is graded at build time; street grade != driveway
//   grade). The snapshot holds NO DEM/DTM/contours (zero contour
//   objects), and incline tags are 75% pedestrian steps + up/down
//   directionals with no magnitude (~0 driveways carry a grade).
//   Scorer dim stays NULL with a site-visit reason
//   (dims_group18resta.dim_driveway).
// * p287 zoom-ready lighting: a per-ROOM interior fact (lamp
//   placement, window behind/in front of the desk). OSM carries no
//   indoor-light signal by construction. Scorer dim stays NULL with
//   an evening-viewing reason (dims_group18resta.dim_zoomlight).
//
// Tag verification (2026-09-13, local snapshot PBF — no network):
//   osmium tags-filter ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf
//     nwr/building:levels
//   levels-tagged buildings parse to integers; the keep_tall
//   predicate (levels >= 4, see scripts/build/batch_g18_resta.py)
//   keeps 7808 county-wide (7404 in the Tallinn window: Lasnamäe,
//   Mustamäe, Õismäe, Kesklinn tower blocks). 25504 low-rise /
//   untagged-member features drop out (untagged reads low-rise BY
//   DESIGN — absence is weak evidence of lowness).
//   osmium tags-filter ... nwr/building:material=glass
//     nwr/building:material=mirror
//   382 features; the keep_glass predicate (glass/mirror first
//   value) keeps 349 county-wide (337 glass + 12 mirror, 337 in the
//   Tallinn window: Tornimäe/City/Ülemiste glass). 33 untagged
//   relation members drop out. Plaster/wood/brick/concrete are OUT
//   by design (not reflective).
//   osmium tags-filter ... nwr/window → 1 feature county-wide
//   (p100 has no signal); nwr/incline → 1430 ways, of which 1068
//   highway=steps, 1342 carry only up/down directionals, 83
//   highway=service, ~0 driveways with a numeric grade (p231 has
//   no driveway signal); nwr/contour → 0 objects (no elevation).
//
// Calibration (judgment calls, documented for the reviewer): dayopen
// + glassglare are nearest-source distance fields, quiet-kind
// calmness (100·d/(d+halfM)), the same kind the G05C/G07/G08 batches
// add — identical semantics (0 on the source, 50 at halfM), shared
// on purpose. dayopen halves at 150 m (a 15 m block 150 m away
// subtends ~6° of sky — minor loss; adjacency is severe);
// glassglare halves at 200 m (reflected glare is street/plaza-scale
// line-of-sight, low winter sun extends its reach). Halves live in
// G18A_CAL below and in scripts/build/batch_g18_resta.py G18A_CAL
// (kept in sync by test).

import type { BonusSpec, LayerDef } from "./layers";

export type Group18ARestALayerId = "dayopen" | "glassglare";

export const GROUP18ARESTA_LAYER_IDS: Group18ARestALayerId[] = ["dayopen", "glassglare"];

/** parameters3.md number per Group-18-rest-A layer (no-map params have no layer). */
export const GROUP18ARESTA_PARAM_IDS: Record<Group18ARestALayerId, number> = {
  dayopen: 34,
  glassglare: 305,
};

/** parameters3.md numbers this batch owns incl. documented no-maps. */
export const GROUP18ARESTA_ALL_PARAMS = [34, 100, 231, 287, 305] as const;

export type Group18ARestAParam = (typeof GROUP18ARESTA_ALL_PARAMS)[number];

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const GROUP18ARESTA_LAYERS: LayerDef[] = [
  {
    id: "dayopen",
    paramIds: [34],
    title: "Päevavalguse avatus (hinnang)",
    goodLabel: "roheline = avatud taevas, kõrghooned kaugel (hinnang)",
    badLabel: "punane = kõrghoone varjus — kontrolli varjutust (hinnang)",
    source: `${SNAP} (kaardistatud 7808 kõrghoonet korruseid ≥4, sh Tallinnas 7404 — Lasnamäe/Mustamäe/Kesklinna tornplokid; märgistamata hooned loevad madalaks, puud VÄLJA — leherikas madalhoonestus on valge; PROKSI-hinnang läheduse järgi — see EI OLE mõõdetud päikesetunnid)`,
    fallbackPoints: [
      { lat: 59.44, lon: 24.82 }, // Lasnamäe paneelplokid (tornmassi ääres)
      { lat: 59.36, lon: 24.66 }, // Nõmme eramupiirkond (tornmassist kaugel)
    ],
  },
  {
    id: "glassglare",
    paramIds: [305],
    title: "Klaasfassaadide peegeldus (hinnang)",
    goodLabel: "roheline = klaasfassaadidest kaugel, peegeldusvaba (hinnang)",
    badLabel: "punane = klaasfassaadi lähedal — kontrolli pimestust madala päiksega (hinnang)",
    source: `${SNAP} (kaardistatud 349 klaas/peegelfassaadi — 337 klaasi + 12 peeglit, sh Tallinnas 337; krohv/puit/telliskivi VÄLJA — ei peegelda; PROKSI-hinnang — see EI OLE mõõdetud luksid)`,
    fallbackPoints: [
      { lat: 59.4313, lon: 24.7619 }, // Tornimäe klaastornid (fassaadi lähedal, proksi)
      { lat: 59.36, lon: 24.66 }, // Nõmme (klaasfassaadidest kaugel)
    ],
  },
];

/**
 * Overpass QL fragments per Group 18 rest-A layer (document the source tags; the
 * app serves the frozen snapshot, never live Overpass). n/ shape: the
 * shared overpassQueryFor() rewrites n[ to nwr/ (PR #118: node-only
 * silently drops way-mapped tower footprints and facade polygons). The builder
 * consumes the same predicate offline (see keep_tall / keep_glass);
 * the levels->=4 and glass/mirror checks live in the scorer mapping
 * (kinds_from_tags), so the fragments stay plain source-tags queries
 * like sibling batches.
 */
export const GROUP18ARESTA_TAGS: Record<Group18ARestALayerId, string> = {
  dayopen: 'n["building"];n["building:levels"];',
  glassglare: 'n["building:material"~"glass|mirror"];',
};

/** Influence radius in km (== wire sigma == Euclidean fallback decay). */
export const GROUP18ARESTA_DECAY: Record<Group18ARestALayerId, number> = {
  dayopen: 0.3,
  glassglare: 0.3,
};

/**
 * Calibration locked 2026-09-13 from snapshot probes (mirrors
 * scripts/build/batch_g18_resta.py G18A_CAL exactly — a pytest
 * parses this file and fails on drift). Both carry the quiet-kind
 * halfM (metres).
 */
export const G18A_CAL = {
  dayopen: { halfM: 150, sigma: 0.3 },
  glassglare: { halfM: 200, sigma: 0.3 },
} as const;

/**
 * dayopen + glassglare: nearest-source calmness 100·d/(d+halfM)
 * (quiet-kind, G05C/G07/G08 precedent).
 */
export const GROUP18ARESTA_BONUS: Record<Group18ARestALayerId, BonusSpec> = {
  dayopen: { kind: "quiet", halfM: 150 },
  glassglare: { kind: "quiet", halfM: 200 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isGroup18ARestALayerId(layer: string): layer is Group18ARestALayerId {
  return (GROUP18ARESTA_LAYER_IDS as string[]).includes(layer);
}

/**
 * Group-18-rest-A bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForGroup18ARestA(layer: string): BonusSpec | undefined {
  return (GROUP18ARESTA_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files per Group 18 rest-A layer (built by batch_g18_resta.py). */
export const G18A_RASTER_FILE: Record<Group18ARestALayerId, string> = {
  dayopen: "dayopen-walk-raster.json",
  glassglare: "glassglare-walk-raster.json",
};

/**
 * NO metro masters (documented): smooth distance-decay fields at
 * 9.375 m cells would be fake precision. The window route serves
 * county everywhere for these layers (metro slot stays empty, like
 * G07B/G03D/G08B/G05C).
 */
export const G18A_NO_METRO = true;

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function group18aHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function group18aQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return (100 * dM) / (dM + halfM);
}

export interface Group18ARestAPoint {
  lat: number;
  lon: number;
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when
 * there is nothing to score — never a faked zero. Mirrors the
 * Python builder's score_distance exactly (same halfM per layer).
 */
export function group18aQuietnessAt(
  layer: Group18ARestALayerId,
  lat: number,
  lon: number,
  points: Group18ARestAPoint[],
): number | null {
  if (points.length === 0) return null;
  let best = Infinity;
  for (const p of points) {
    const d = group18aHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return Math.round(group18aQuietFromHalf(best * 1000, G18A_CAL[layer].halfM));
}

/** True when a raster doc's baked calibration matches the live spec. */
export function group18aMatchesContract(
  layer: Group18ARestALayerId,
  doc: { half: number | null; sigma: number } | null,
): boolean {
  if (!doc) return false;
  return doc.half === G18A_CAL[layer].halfM && doc.sigma === G18A_CAL[layer].sigma;
}

export type Group18ARestAVerdictKind = "proxy" | "real" | "no-map";

export interface Group18ARestAVerdict {
  param: Group18ARestAParam;
  name: string;
  kind: Group18ARestAVerdictKind;
  /** Why this verdict: snapshot evidence, never judgment alone. */
  reason: string;
}

/**
 * Per-param verdicts for Group 18 rest batch A (the no-map rows are the
 * docs evidence; scorer dims live in services/scoring/dims_group18resta.py).
 */
export const G18A_VERDICTS: Group18ARestAVerdict[] = [
  {
    param: 34,
    name: "Natural light",
    kind: "proxy",
    reason:
      "Shipped as dayopen: nearness to 7808 mapped tall buildings (levels >= 4, 7404 in Tallinn) as sky-openness hinnang — honestly labelled, never sun hours; untagged buildings read low-rise and trees are out (leafy low-rise stays bright).",
  },
  {
    param: 100,
    name: "Window placement and cross-ventilation",
    kind: "no-map",
    reason:
      "A per-floorplan fact (window positions, through-ventilation needs the unit layout); exactly 1 window tag exists county-wide — zero area signal, so a proximity gradient would be fake precision.",
  },
  {
    param: 231,
    name: "Driveway incline angle",
    kind: "no-map",
    reason:
      "A per-parcel construction fact (the driveway is graded at build time); the snapshot holds no DEM/DTM/contours, and incline tags are 75% pedestrian steps plus up/down directionals with no magnitude (~0 driveways carry a grade).",
  },
  {
    param: 287,
    name: "Zoom-ready lighting",
    kind: "no-map",
    reason:
      "A per-room interior fact (lamp placement, window behind/in front of the desk); OSM carries no indoor-light signal by construction — never mappable from an area snapshot.",
  },
  {
    param: 305,
    name: "Exterior reflective glare",
    kind: "proxy",
    reason:
      "Shipped as glassglare: distance to 349 mapped glass/mirror facades (337 in Tallinn — Tornimäe/City/Ülemiste) as glare-exposure hinnang, unfilled rings (glare is an outside-view fact) — honestly labelled, never lux.",
  },
];

/** Batch-A params with no honest map (dims-only, OTA PR #131 precedent). */
export const GROUP18ARESTA_NO_MAP_PARAMS: number[] = G18A_VERDICTS.filter((v) => v.kind === "no-map").map(
  (v) => v.param,
);

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const GROUP18A_HOOK =
  "G18A-HOOK (#172): dayopen + glassglare wired into layers/overlays/snapshot; p100/p231/p287 verdicts + dims only.";
