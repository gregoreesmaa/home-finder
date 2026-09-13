// Group 18 rest-C verdicts (parameters3.md §5.18, issue #197):
// p132 window views — the only Group 5.18 param with zero implementation
// (coverage audit 2026-09-13).
//
// VERDICT: documented NO-MAP (OTA PR #131 precedent — gradient map
// rejected where honest calibration cannot discriminate) with a scorer
// dim in services/scoring/dims_group18restc.py. This file owns the
// verdict registry; it is self-contained on purpose (mirrors the Group
// 3-E file shape, #155) and lands + tests green on its own.
//
// WHY no layer ships (evidence, verified 2026-09-13 against the local
// Harjumaa PBF ~/hf-data/2026-09-12/osm/harjumaa-260911.osm.pbf — no
// network; see GROUP18C_EVIDENCE):
// * p132 asks what a buyer sees from THEIR windows (floor + window
//   orientation + what stands directly in front) — a per-unit
//   view-shed fact, same class as the same-group p394 patio-sun
//   azimuth verdict (#173, rest-B). The snapshot carries building
//   CENTROIDS only (252,140 bare lon/lat pairs, re-counted — no
//   footprints, no heights, no orientation), and exactly ONE object
//   county-wide carries a window=* key. A cell-average gradient cannot
//   tell a buyer where THEIR view falls — inventing one from
//   centroids would be fake precision.
// * Every area signal a view proxy could lean on is ALREADY consumed:
//   openness by daylight p405 (inverted count of all 252,140 mapped
//   buildings, #173) and by dayopen p34 (tall-mass nearness from
//   7,853 levels≥4 buildings of 33,311 levels-tagged, #172);
//   mapped viewpoints by viewshed p225 (88, #163); shore nearness by
//   shoredist p340 (#154). A third openness gradient on the same
//   building inventory would re-skin daylight/dayopen (p222 precedent,
//   #163: no third gradient where two already score it).
// * The param's own Tier-3 pipeline (Maa-amet LoD2 3D CityGML +
//   PVLib/Trimesh ray-tracing) is NOT in the snapshot. Area openness
//   context stays on daylight/dayopen/viewshed; the window question
//   stays a NULL per-listing dim with a viewing-visit check.
//
// G18C-HOOK (#197): NO shared-file edits. No layers ship, so there is
// nothing to wire into lib/layers.ts, lib/server/snapshot.ts,
// lib/overlays.ts or lib/distanceField.ts — this marker (and the
// GROUP18C_HOOK export below) is the whole hook. A future central
// integrator only needs services/scoring/dims_group18restc.py.

/** parameters3.md numbers this batch owns (all documented no-map). */
export const GROUP18C_ALL_PARAMS = [132] as const;

export type Group18CParam = (typeof GROUP18C_ALL_PARAMS)[number];

/**
 * Shipped params: intentionally EMPTY. Pinned by test — a layer added
 * here must also add registry wiring, a raster master and a screenshot.
 */
export const GROUP18C_SHIPPED_PARAMS: readonly Group18CParam[] = [];

export interface Group18CVerdict {
  /** parameters3.md parameter number. */
  param: Group18CParam;
  /** Scorer dim in services/scoring/dims_group18restc.py carrying this param. */
  dim: string;
  /** Nearest shipped map signal a buyer can open today (if any). */
  nearestMap: string;
  /** Why no gradient map ships (Estonian, shown in PR + reviewable). */
  reason: string;
}

export const GROUP18C_NO_MAP: Group18CVerdict[] = [
  {
    param: 132,
    dim: "dim_windowviews",
    nearestMap:
      "daylight (p405) avarus + dayopen (p34) kõrghoonestuse vari + viewshed (p225) vaatekaitse + shoredist (p340) kaldalähedus: piirkonna avaruskontekst, MITTE akna vaade",
    reason:
      "Aknavaade on korruse- ja suunapõhine vaatefakt (hinnang): hetktõmmises " +
      "on ainult 252 140 hoonekeskme — jalajäljed, kõrgused ja asimuudid " +
      "puuduvad ning aknamärgendeid on terves maakonnas ÜKS, nii et " +
      "keskmistatud gradient ei ütle, mida OSTJA aknast näeb. Ainsat " +
      "pindmist signaali (hoonestuse tihedus/avarus) tarbivad juba daylight " +
      "ja dayopen, vaatepunkte viewshed — kolmas gradient samast " +
      "inventuurist dubleeriks neid. Suunda ei saa kalibreerida ilma " +
      "Maa-ameti LoD2-mudelita. Dim jääb NULLiks kohapealse külastuse " +
      "kontrolli põhjusega — ära feigi.",
  },
];

/**
 * Snapshot counts backing the verdict (osmium tags-filter nwr/ + export
 * on harjumaa-260911.osm.pbf, 2026-09-13; derived-buildings.json is a
 * bare [{lon, lat}] list, counted directly):
 * window=* keys on 1 object county-wide (zero window signal);
 * building:levels on 33,311 features, of which 7,853 parse to levels≥4
 * (the tall-mass signal dayopen already consumes, #172); 252,140 bare
 * building centroids with no footprints/heights/orientation (the
 * openness inventory daylight already inverts, #173).
 */
export const GROUP18C_EVIDENCE = {
  windowTags: 1,
  levelsTagged: 33311,
  tallLevels4: 7853,
  buildingCentroids: 252140,
} as const;

/**
 * OSM tags evaluated for p132 and rejected for a gradient map
 * (documents the source tags for the record; the NULL dim needs no
 * fetch — the app serves the frozen snapshot, never live Overpass).
 */
export const GROUP18C_CONSIDERED_TAGS: Record<Group18CParam, string> = {
  132: 'nwr/window (1 objekt — nullisignaal); nwr/building:levels (33 311, sh 7853 ≥4 — juba dayopen #172); 252 140 hoonekeskme (juba daylight #173); tourism=viewpoint (juba viewshed #163)',
};

/** Hook marker, pinned by test so the no-wiring contract stays greppable. */
export const GROUP18C_HOOK =
  "G18C-HOOK (#197): no shared-file wiring — no layers ship, verdicts + dims only.";
