// Statamet per-KOV choropleths (issue #485): kovmigr (RVR02 2025 net
// migration), kovehit (EH44U 2025 completions), kovfisc (RR300 2025
// operating margin).
//
// THREE exact-join choropleths, never kernels: every 75 m county cell
// holds its own KOV's band score (rasterized KOV polygons, no smoothing
// across borders, no interpolation). A KOV whose series row is absent
// stays 255 unknown (EI OLE) -- the map twin of the dims_p4_stat.py
// NULLs. IA028 (dwelling-price index) is REFUSED for the map: NATIONAL
// grain only (no area dimension, verified 2026-09-13) -- a national
// constant painted per-KOV would be one flat colour (MARU/Euribor
// PR #475 precedent). EH permits are REFUSED as a ratio leg (no KOV
// grain: EH04 national, EH045 county) -- kovehit scores completions
// only, capped at 70 (MARU p484 weak-flip precedent).
//
// This file owns ALL statkov runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts, app/layers/page.tsx) touch it
// only through small marked `STATKOV-HOOK (#485)` blocks, so the sibling
// P4 batches stay disjoint (#479 parking, #481 roadsafety, #482 osmdaily).
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef):
// no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): titles, legends and sources say "hinnang" and
// name what is NOT in the join -- the units are PX-table aggregates
// (annual, KOV grain), never per-address truth:
// * kovmigr names the missing age/vacancy-grid + school-plan + turnover
//   legs (sibling modules), like dims_p4_stat.dim_micro_liquidity_stat.
// * kovehit names the missing permits pipeline (cap 70).
// * kovfisc names the missing debt-stock/investment legs (cap 70).
// paramIds stays EMPTY (parameters4 namespace -- OSMDAILY #482 precedent:
// 19/50-style numbers belong to the parameters3 audit and two of the
// nearest numbers are taken map layers).
//
// Overlap (documented, same source different question -- #479 precedent):
// dims_p4_stat.py already scores these series per-LISTING (P4-001/002/
// 003/019/025/038/043/050/051/061 legs off KK11-shaped area medians).
// Those answer "this deal vs its area"; these layers answer "which KOV".
// Same join SHAPE, disjoint questions -- the rebalance follow-up must
// weight only one leg per question.
//
// Polygon verification (2026-09-13, local snapshot PBF -- no network):
//   osmium getid ~/hf-data/2026-09-12/osm/estonia-260911.osm.pbf
//     -r r350208 r350346 r350633 r350740 r350902 r351474 r351602 r352021
//        r352240 r352559 r352581 r352935 r353192 r355398 r350547 r7692055
//     -o kov16.osm.pbf && osmium export kov16.osm.pbf -o kov16.geojson
// 16 admin_level=7 KOV multipolygons (Tallinn 9 polys/10480 pts ...
// Viimsi 55 polys/20958 pts); island side-products (place=island, no
// admin_level) excluded -- the KOV MPs already carry their islands.
// TEHAK:code does not survive export, so the join is the normalised
// name, asserted 16/16 both ways (fail-closed) in the builder.
//
// Calibration (locked 2026-09-13 from the real fixture -- mirrors
// scripts/build/batch_statkov_choropleth.py STATKOV_BANDS exactly;
// scripts/build/test_batch_statkov_choropleth.py parses this file and
// fails on drift):
//   Tallinn-kesk (24.7536,59.4364) -> migr 45 / ehit 60 / fisc 60
//   Viimsi (24.8311,59.5412)       -> migr 60 / ehit 45 / fisc 70
//   Keila-Joa (24.29,59.40)        -> migr 60 / ehit 60 / fisc 60
//   Keila (24.4212,59.3134)        -> migr 60 / ehit 45 / fisc 60
//   Kuusalu (25.4417,59.4461)      -> migr 75 / ehit 70 / fisc 60
//   Gulf of Finland (24.7,59.72)   -> 255 (sea, honestly unknown)
// Loksa town sits past the shared county grid edge (25.5E) and renders
// 255 on every raster layer (platform-wide clip, documented in the
// builder); its fixture rows stay shipped for a future grid extension.

import type { BonusSpec, LayerDef } from "./layers";

export type StatKovLayerId = "kovmigr" | "kovehit" | "kovfisc";

export const STATKOV_LAYER_IDS: StatKovLayerId[] = [
  "kovmigr",
  "kovehit",
  "kovfisc",
];

/**
 * Band thresholds (rate -> score): first threshold met from the top
 * wins, otherwise the per-layer default below. Rates: kovmigr net
 * migration /1000 (mid-2025 pop), kovehit completions /1000, kovfisc
 * operating margin tulem/tulud %.
 */
export const STATKOV_BANDS: Record<StatKovLayerId, Array<[number, number]>> = {
  kovmigr: [[10, 75], [-5, 60], [-20, 45]],
  kovehit: [[20, 30], [10, 45], [4, 60]],
  kovfisc: [[10, 70], [5, 60], [0, 45]],
};

/** Fallback band when no threshold is met (None stays 255 unknown). */
export const STATKOV_DEFAULTS: Record<StatKovLayerId, number> = {
  kovmigr: 30,
  kovehit: 70,
  kovfisc: 30,
};

const SNAP = "kohalik hetktõmmis 2026-09-12";
const PX = "Statamet PX-Web (võtmeta, tõmmatud 2026-09-13)";

export const STATKOV_DEFS: LayerDef[] = [
  {
    id: "kovmigr",
    paramIds: [],
    title: "Rändesaldo KOV-is 2025 (P4-025 proksi-hinnang)",
    goodLabel: "roheline = KOV-i rändesaldo positiivne (sissevool, hinnang)",
    badLabel: "punane = KOV-ist väljavool või rida puudub (hinnang — EI OLE)",
    source:
      `${PX}: RVR02 2025 rändesaldo (sise- + välisränne, haldusüksuse ` +
      `täpsus) / RV0291U rahvaarv (keskmine 01.01.2025 + 01.01.2026); ` +
      `KOV-polügoonid OSM admin_level=7 (${SNAP}). Vanuse/vakantsi-` +
      `ruudustiku + kooliplaanide + tehingukäibe jalga EI OLE ` +
      `(sõsarmoodulid) — iga lahter oma KOV väärtus, silumist EI OLE`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Tallinn-kesk (band 45)
      { lat: 59.5833, lon: 25.7167 }, // Loksa (data band 60; past grid edge)
    ],
  },
  {
    id: "kovehit",
    paramIds: [],
    title: "Valminud eluruumid KOV-is 2025 (P4-050 proksi-hinnang, lagi 70)",
    goodLabel: "roheline = vähe valminuid elaniku kohta (hinnang)",
    badLabel: "punane = palju valminuid elaniku kohta (hinnalanguse risk, hinnang)",
    source:
      `${PX}: EH44U 2025 kasutusse lubatud eluruumid (haldusüksus) / ` +
      `RV0291U rahvaarv; KOV-polügoonid OSM admin_level=7 (${SNAP}). ` +
      `EHITUSLUBADE (torustiku) KOV-ridu EI OLE (EH04 riiklik, EH045 ` +
      `maakondlik) — lubade/valmimiste suhet EI FEIGITA, lagi 70`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Tallinn (band 60)
      { lat: 59.5412, lon: 24.8311 }, // Viimsi (kõrge sisend, band 45)
    ],
  },
  {
    id: "kovfisc",
    paramIds: [],
    title: "KOV põhitegevuse tulem 2025 (P4-019 proksi-hinnang, lagi 70)",
    goodLabel: "roheline = põhitegevuse ülejääk (terve eelarve, hinnang)",
    badLabel: "punane = puudujääk või rida puudub (hinnang — EI OLE)",
    source:
      `${PX}: RR300 2025 põhitegevuse tulud + tulem (haldusüksus); ` +
      `KOV-polügoonid OSM admin_level=7 (${SNAP}). Võlakoormuse + ` +
      `investeeringute jalga EI OLE — marginaal üksi, lagi 70`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Tallinn (marginaal 8.9%, band 60)
      { lat: 59.5412, lon: 24.8311 }, // Viimsi (marginaal 14.0%, band 70)
    ],
  },
];

/**
 * Overpass QL fragment (documents the polygon source; the app serves
 * the frozen snapshot, never live Overpass). Relation shape: the
 * shared overpassQueryFor() rewrites only n[ fragments, so r[ passes
 * through to a valid relation query.
 */
export const STATKOV_TAGS: Record<StatKovLayerId, string> = {
  kovmigr: 'r["boundary"="administrative"];r["admin_level"="7"];',
  kovehit: 'r["boundary"="administrative"];r["admin_level"="7"];',
  kovfisc: 'r["boundary"="administrative"];r["admin_level"="7"];',
};

/**
 * Fallback kernel width in km (== wire sigma). The master itself is
 * exact-fill with no kernel; this only sizes the Euclidean fallback
 * when the raster is missing (mobile/"cover" precedent).
 */
export const STATKOV_DECAY: Record<StatKovLayerId, number> = {
  kovmigr: 0.5,
  kovehit: 0.5,
  kovfisc: 0.5,
};

/**
 * Self-scaling KOV bands (mobile/"cover" precedent): the per-KOV band
 * scores ARE the calibration (no half); sigma is the Euclidean
 * fallback kernel width. Contract-checked against the wire
 * (half null, sigma 0.5) by loadLayerRaster.
 */
export const STATKOV_BONUS: Record<StatKovLayerId, BonusSpec> = {
  kovmigr: { kind: "cover", sigma: 0.5 },
  kovehit: { kind: "cover", sigma: 0.5 },
  kovfisc: { kind: "cover", sigma: 0.5 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isStatKovLayerId(layer: string): layer is StatKovLayerId {
  return (STATKOV_LAYER_IDS as string[]).includes(layer);
}

/**
 * Statkov bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForStatKov(layer: string): BonusSpec | undefined {
  return (STATKOV_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files (built by scripts/build/batch_statkov_choropleth.py). */
export const STATKOV_RASTER_FILE: Record<StatKovLayerId, string> = {
  kovmigr: "kovmigr-walk-raster.json",
  kovehit: "kovehit-walk-raster.json",
  kovfisc: "kovfisc-walk-raster.json",
};

/**
 * NO metro masters (documented): exact KOV fills at 9.375 m cells
 * would be fake precision on top of a 75 m fill. The window route
 * serves county everywhere for these layers (G02B/G03/G03D/G08B/G05C/
 * G17A/G17B/parking precedent).
 */
export const STATKOV_NO_METRO = true;

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const STATKOV_HOOK =
  "STATKOV-HOOK (#485): kovmigr + kovehit + kovfisc wired into " +
  "layers/overlays/snapshot; PX-Web RVR02/EH44U/RR300 2025 exact KOV " +
  "fills, cover sigma 0.5, IA028 refused (national grain).";
