// Group 7 environmental-health layers, batch C (parameters3.md §5.7,
// issue #142): p257, p260, p316, p401, p402. Self-contained on purpose:
// it mirrors the shapes in lib/layers.ts (LayerDef, decay specs, Overpass
// TAGS, walk-raster wire doc) WITHOUT importing that file, so this batch
// lands and tests green on its own. Shared-file wiring is marked
// G07C-HOOK (see HOOKS below) and IS applied in this PR (one shipped
// layer only, additive spread/guard lines).
//
// PER-PARAM VERDICTS (load-bearing honesty, AGENTS.md §7):
//   p257 endemic local pests -> SHIPPED honest proxy ("vectorhabitat"):
//     nearest mapped disease-vector habitat (tick: wood/forest/scrub/
//     heath/meadow; mosquito: wetland). Green = far, red = at/inside.
//     No pest-surveillance registry exists in the 2026-09-12 snapshot, so
//     the title/legend/source say "proksi (hinnang)" — NEVER trap counts,
//     incidence, or risk classes.
//   p260 ambient dust/pollen -> DOCUMENTED NO-MAP (OTA PR #131 precedent):
//     the dust side (heavy roads/quarry/industry) is already mapped by the
//     lowspec p408 layer, and the pollen side belongs to sibling p137
//     (issue #140). A third map would duplicate, not inform; sensor data
//     (Õhuseire PM10/pollen counts) is not in the snapshot. Scorer dim
//     only (dust side; reason defers pollen to p137).
//   p316 municipal water treatment -> DOCUMENTED NO-MAP: Tallinn water is
//     centrally treated (one mapped man_made=water_works in Harju); any
//     distance gradient would be fake precision. Scorer dim only.
//   p401 VOC off-gassing -> DOCUMENTED NO-MAP: indoor phenomenon (fresh
//     finishes/furnishings), no outdoor OSM source exists. Scorer dim from
//     listing age/renovation attributes only, None when unknown.
//   p402 water hardness -> DOCUMENTED NO-MAP: no hardness registry in the
//     snapshot. Scorer dim only (Tallinn central surface water reads soft).
// Unknown stays null/255 (renders red, never a faked score).
//
// Boundary with sibling batches (reviewable per AGENTS.md §7.5):
// p67 (issue #140, larger wildlife) may share wood/forest sources —
// different question (nuisance animals vs disease vectors), shared sources
// flagged for the integrator. p137 (issue #140, seasonal allergens) owns
// the pollen side of p260; this batch scores dust only. p450/wildcorr
// (issue #143) shares forest/wetland sources — different question
// (corridor connectivity vs vector proximity), same shared-source flag.
//
// HOOKS (applied in this PR, each marked G07C-HOOK(#142)):
//   layers.ts: import the G07C tables; LayerId union adds G07CLayerId
//     ("vectorhabitat"); TAG_ALLOWLIST adds "natural", "landuse"
//     (habitat tags); LAYERS/TAGS/DECAY_KM spread ...G07C_*; bonusSpecFor
//     routes via g07cBonusSpec. NO BonusSpec union edit: kind "quiet"
//     already exists (shared with G07-A/B/D, identical 100·d/(d+halfM)
//     semantics, kept as one kind on purpose).
//   snapshot.ts: import G07C_RASTER_FILE; RASTER_FILE spreads it; the
//     METRO_PREFIX entry resolves to an absent file by design (see
//     G07C_NO_METRO; the window route serves county). NO matchesContract
//     / half-echo edit: kind "quiet" is already handled generically.
//   distanceField.ts: NO edit — the generic "quiet" branch already
//     implements g07cScoreAt semantics (100·d/(d+halfM), null when empty).
//   overlays.ts overlayColorFor/overlayLegendFor: add the vectorhabitat
//     case (habitat-edge sample dots, halfM 300 m; color #a21caf —
//     #365314 is already taken by sibling wildcorr, and the suite pins
//     distinct marker colors).
// No other shared file needs edits: the window route, fetchWindow and
// the layers page are all generic over the registry.

export type G07CLayerId = "vectorhabitat";

export const G07C_LAYER_IDS: G07CLayerId[] = ["vectorhabitat"];

/** parameters3.md parameter numbers per shipped layer. */
export const G07C_PARAM_IDS: Record<G07CLayerId, number[]> = {
  vectorhabitat: [257],
};

/**
 * Params in this batch with NO map layer (documented no-map, OTA #131
 * precedent). Every one still gets a scorer dim in
 * services/scoring/dims_group07c.py.
 */
export const G07C_NO_MAP: Record<number, string> = {
  260: "tolm dubleeriks lowspec-p408; õietolm kuulub p137 (sibling #140); seireandmed puuduvad",
  316: "tsentraalne puhastus — kaugusgradient oleks võlts (1 kaardistatud water_works)",
  401: "siseruumi nähtus (viimistlus/sisustus) — väline OSM-allikas puudub",
  402: "kareduse register hetktõmmises puudub",
};

export interface G07CPoint {
  lat: number;
  lon: number;
  tags?: Record<string, string>;
}

export interface G07CLayerDef {
  id: G07CLayerId;
  /** parameters3.md parameter numbers this layer implements. */
  paramIds: number[];
  title: string;
  /** Legend text: what green means. */
  goodLabel: string;
  /** Legend text: what red means. */
  badLabel: string;
  /** Provenance shown next to the map. */
  source: string;
  /** Honestly-labeled demo points used only when live fetch fails. */
  fallbackPoints: G07CPoint[];
}

const SNAP = "kohalik hetktõmmis 2026-09-12";

export const G07C_LAYERS: G07CLayerDef[] = [
  {
    id: "vectorhabitat",
    paramIds: [257],
    title: "Puugi- ja sääseelupaik (proksi, hinnang)",
    goodLabel: "roheline = kaardistatud elupaigast kaugel (proksi)",
    badLabel: "punane = metsa/võsa/niidu/soo servas või sees (proksi, MITTE seireandmed)",
    source: `${SNAP} (mets/puistu/võsa/nõmm/niit/soo elupaigapolügoonid; PROKSI, mitte puugi-/sääseseire)`,
    fallbackPoints: [
      { lat: 59.4374, lon: 24.7454 }, // Vanalinn (elupaikadest kaugel)
      { lat: 59.3862, lon: 24.6611 }, // Nõmme mets (elupaiga servas)
    ],
  },
];

/**
 * Overpass QL per shipped layer (documents the source tags; the snapshot
 * builder consumes them offline — no live fetch in code/tests).
 * Linear tree rows stay OUT: only area-like habitat (polygons + closed
 * ways) feeds the interior fill; open LineStrings score edge-only.
 */
export const G07C_TAGS: Record<G07CLayerId, string> = {
  vectorhabitat:
    'nwr["natural"~"wood|scrub|heath|wetland"];nwr["landuse"~"forest|meadow"];',
};

/** Raster master filenames next to the base masters (gitignored artifacts). */
export const G07C_RASTER_FILE: Record<G07CLayerId, string> = {
  vectorhabitat: "vectorhabitat-walk-raster.json",
};

/**
 * NO metro masters (documented): a distance-decay proxy is smooth at
 * the 75 m county step; 9.375 m cells would be fake precision. The
 * window route serves county everywhere for this layer.
 */
export const G07C_NO_METRO = true;

/**
 * Distance (km) at which the Euclidean fallback field decays (same scale
 * story as the raster sigma): habitat edges bite locally, the city
 * centre reads calm.
 */
export const G07C_DECAY_KM: Record<G07CLayerId, number> = {
  vectorhabitat: 0.3,
};

export function g07cRadiusKmFor(layer: G07CLayerId): number {
  return G07C_DECAY_KM[layer];
}

/**
 * Calibration locked 2026-09-12 from snapshot probes (mirrors
 * scripts/build/batch_g07c_envhealth.py G07C_CAL exactly — a pytest
 * parses this file and fails on drift).
 */
export const G07C_CAL = {
  vectorhabitat: { halfM: 300, sigma: 0.3 },
} as const;

export type G07CBonusSpec = { kind: "quiet"; halfM: number };

export const G07C_BONUS: Record<G07CLayerId, G07CBonusSpec> = {
  vectorhabitat: { kind: "quiet", halfM: 300 },
};

export function g07cBonusSpec(layer: G07CLayerId): G07CBonusSpec {
  return G07C_BONUS[layer];
}

/** True for this batch's ids (called from the bonusSpecFor hook). */
export function isG07CLayerId(layer: string): layer is G07CLayerId {
  return (G07C_LAYER_IDS as string[]).includes(layer);
}

/** Equirectangular km (same 57.29/110.57 constants as walk_graph.hav_km). */
export function g07cHavKm(lon1: number, lat1: number, lon2: number, lat2: number): number {
  return Math.hypot((lon2 - lon1) * 57.29, (lat2 - lat1) * 110.57);
}

/** Nearest-source calmness 0..100: 0 on the source, 50 at halfM. */
export function g07cQuietFromHalf(dM: number, halfM: number): number {
  if (!Number.isFinite(dM)) return 100;
  return Math.round((100 * dM) / (dM + halfM));
}

/**
 * Euclidean fallback calmness 0..100 (raster missing). Null when there is
 * nothing to score — never a faked zero. Edge-sample points stand in for
 * polygon interiors, so deep-habitat fallback reads nearer the edge than
 * truth: degraded mode only, documented (the raster fills interiors).
 */
export function g07cScoreAt(
  layer: G07CLayerId,
  lat: number,
  lon: number,
  points: G07CPoint[],
): number | null {
  if (points.length === 0) return null;
  const spec = g07cBonusSpec(layer);
  let best = Infinity;
  for (const p of points) {
    const d = g07cHavKm(lon, lat, p.lon, p.lat);
    if (d < best) best = d;
  }
  return g07cQuietFromHalf(best * 1000, spec.halfM);
}

/** True when a raster doc's baked calibration matches the live spec. */
export function g07cMatchesContract(
  doc: { half: number | null; sigma: number } | null,
  layer: G07CLayerId,
): boolean {
  if (!doc) return false;
  const spec = g07cBonusSpec(layer);
  if (doc.sigma !== G07C_DECAY_KM[layer]) return false;
  return doc.half === spec.halfM;
}
