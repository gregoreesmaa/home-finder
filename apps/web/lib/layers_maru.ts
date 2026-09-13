// MARU per-KOV market choropleths (issue #486): kovkasv (p41 YoY
// appreciation), kovkaive (p149 quarterly deal count), kovedas (p43
// resale composite), kovkiirus (p484 deal-velocity QoQ, weak flip,
// cap 70).
//
// FOUR exact-join choropleths, never kernels: every 75 m county cell
// holds its own KOV's band score (rasterized KOV polygons, no smoothing
// across borders, no interpolation, no forward-fill). A KOV whose
// quarterly row (or required quarter pair) is absent stays 255 unknown
// (EI OLE) -- the map twin of the dims_overturn_maru.py NULLs. Bands
// mirror services/scoring/dims_overturn_maru.py EXACTLY (drift-pinned
// by scripts/build/test_batch_maru_choropleth.py, which parses this
// file and fails on drift).
//
// p421 is REFUSED for the map (pinned in test): the appraisal-gap band
// needs the LISTING asking price (asking vs KOV median), so no per-KOV
// cell value exists -- every cell would be NULL. Painting KOV medians
// as gap scores would fake the join (IA028 national-grain refusal
// precedent, #485). p421 stays a per-listing registry join in
// dims_overturn_maru.py; the KOV-median leg is shared with the p41/p43
// paints (same table, disjoint questions).
//
// This file owns ALL maru runtime data; shared files (lib/layers.ts,
// lib/server/snapshot.ts, lib/overlays.ts, app/layers/page.tsx) touch it
// only through small marked `MARUKOV-HOOK (#486)` blocks, so the sibling
// batches stay disjoint.
//
// This module imports ./layers ONLY as types (BonusSpec, LayerDef):
// no runtime cycle (layers.ts imports values from here).
//
// HONESTY (load-bearing): titles, legends and sources say "hinnang" and
// name what is NOT in the join -- the units are MARU quarterly KOV
// aggregates (median EUR/m2 + deal count), never per-address truth:
// * kovkasv needs the SAME quarter a year apart (no annualised guess).
// * kovedas needs BOTH legs (depth + direction); a missing leg NULLs.
// * kovkiirus is the WEAK velocity leg only (cap 70): months-of-supply
//   needs the KV-adapter inventory leg, named EI OLE, never guessed.
// * paramIds carry the real parameters3 numbers (41/149/43/484): these
//   ARE the flipped G16 params (OSMDAILY #482 empty-paramIds precedent
//   does NOT apply -- that was the parameters4 namespace).
//
// Overlap (documented, same table different question -- #479 precedent):
// dims_overturn_maru.py already scores these bands per-LISTING (p41 YoY
// pair, p149 depth, p43 composite, p484 QoQ pair, p421 gap). Those answer
// "this deal vs its KOV"; these layers answer "which KOV". Same join
// SHAPE, disjoint questions -- the rebalance follow-up must weight only
// one leg per question. GROUP16A/B verdict files (no-MAP for gradients,
// #205/#206) are deliberately untouched: a gradient calibrated against
// nothing stays refused; the exact KOV fill is the overturn's new shape
// (final docs-index PR owns nomap.md).
//
// Polygons: open KOV multipolygons, OSM admin_level=7, local 2026-09-12
// snapshot extract (same osmium pre-step as #485: estonia PBF, 16 Harju
// KOV relations, TEHAK:code does not survive export so the join is the
// normalised name, asserted both ways fail-closed in the builder).
// Values: quarterly MARU KOV export in OUR import schema
// (kov;quarter;median_eur_m2;deals -- see parse_maru_kov_csv), placed by
// the maintainer (form-driven query env, no bulk contract --
// docs/overturn_maru.md). Until the export is placed, masters stay
// unbuilt and the layers render honestly unknown; the committed
// scripts/build/maru_kov_tables.example.json is SYNTHETIC demo data
// under fake KOV names (never MARU numbers, never joinable to real
// polygons -- fail-closed by construction).
//
// Calibration (locked 2026-09-13 from dims_overturn_maru.py -- mirrors
// scripts/build/batch_maru_choropleth.py MARU_BANDS exactly):
//   kovkasv YoY%: <=-5 -> 75, <0 -> 65, <=+5 -> 50, <=+10 -> 40, else 30
//   kovkaive deals: >=300 -> 80, >=100 -> 65, >=30 -> 50, else 35
//   kovedas (deals>=100, yoy>=0): TT -> 70, TF -> 55, FT -> 50, FF -> 35
//   kovkiirus QoQ%: >=+10 -> 70, >=-10 -> 55, else 40 (cap 70)

import type { BonusSpec, LayerDef } from "./layers";

export type MaruKovLayerId = "kovkasv" | "kovkaive" | "kovedas" | "kovkiirus";

export const MARUKOV_LAYER_IDS: MaruKovLayerId[] = [
  "kovkasv",
  "kovkaive",
  "kovedas",
  "kovkiirus",
];

/** parameters3.md G16 number per MARU layer (the flipped params). */
export const MARUKOV_PARAMS: Record<MaruKovLayerId, number> = {
  kovkasv: 41,
  kovkaive: 149,
  kovedas: 43,
  kovkiirus: 484,
};

/**
 * Single-rate band thresholds: first threshold met from the top wins,
 * otherwise the per-layer default below. Comparators are per-layer
 * (mirroring the dim if/elif chains -- pinned by boundary tests in
 * scripts/build/test_batch_maru_choropleth.py):
 * * kovkasv (YoY%, p41 dim_appreciation_p41): <=-5 -> 75, <0 -> 65,
 *   <=+5 -> 50, <=+10 -> 40, else 30.
 * * kovkaive (deals, p149 dim_market_liquidity_p149): >=300 -> 80,
 *   >=100 -> 65, >=30 -> 50, else 35.
 * * kovkiirus (QoQ%, p484 dim_absorption_p484, weak flip cap 70):
 *   >=+10 -> 70, >=-10 -> 55, else 40.
 * kovedas is a TWO-input composite (see MARUKOV_RESALE_RULE) and has no
 * row here -- a single-rate row for it would fake the join.
 */
export const MARUKOV_BANDS: Record<
  Exclude<MaruKovLayerId, "kovedas">,
  Array<[number, number]>
> = {
  kovkasv: [[-5, 75], [0, 65], [5, 50], [10, 40]],
  kovkaive: [[300, 80], [100, 65], [30, 50]],
  kovkiirus: [[10, 70], [-10, 55]],
};

/** Fallback band when no threshold is met (None stays 255 unknown). */
export const MARUKOV_DEFAULTS: Record<
  Exclude<MaruKovLayerId, "kovedas">,
  number
> = {
  kovkasv: 30,
  kovkaive: 35,
  kovkiirus: 40,
};

/**
 * kovedas composite rule (p43 dim_resale_appeal_p43): depth (p149 leg,
 * deals >= 100) + direction (p41 leg, yoy >= 0). Both legs present or
 * the cell is 255 (no half-comps):
 * deep+rising/stable -> 70, deep+cooling -> 55, thin+stable -> 50,
 * thin+falling -> 35.
 */
export const MARUKOV_RESALE_RULE =
  "kovedas = composite (deals>=100, yoy>=0): TT->70, TF->55, FT->50, " +
  "FF->35; a missing leg NULLs (no half-comps)";

const SNAP = "kohalik hetktõmmis 2026-09-12";
const MARU =
  "MARU kvartali KOV-väljavõte (haldaja paigaldatud eksport, " +
  "haldusüksuse täpsus; vormipõhine päringukeskkond, hulgi-lepingut EI OLE)";

export const MARUKOV_DEFS: LayerDef[] = [
  {
    id: "kovkasv",
    paramIds: [41],
    title: "KOV mediaanhinna aastakasv (p41 hinnang)",
    goodLabel: "roheline = KOV mediaan jahtub/langeb (ostjal ruumi, hinnang)",
    badLabel: "punane = KOV mediaan kasvab kiiresti või aastapaar puudub (hinnang — EI OLE)",
    source:
      `${MARU}: sama kvartali mediaanide aastapaar; ` +
      `KOV-polügoonid OSM admin_level=7 (${SNAP}). ` +
      `Kõrvutikvartalite annualiseerimist EI OLE (hooajaline ` +
      `uusehitus võltsiks trendi) — paaritu KOV on EI OLE, ` +
      `iga lahter oma KOV väärtus, silumist EI OLE`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Tallinn-kesk (tihe tehinguturg)
      { lat: 59.2, lon: 24.5 }, // Hõre Harjumaa (aastapaar sageli puudu)
    ],
  },
  {
    id: "kovkaive",
    paramIds: [149],
    title: "KOV tehingukäive kvartalis (p149 hinnang)",
    goodLabel: "roheline = sügav turg (palju tehinguid, hinnang)",
    badLabel: "punane = õhuke turg või rida puudub (edasimüügi-risk, hinnang — EI OLE)",
    source:
      `${MARU}: kvartali tehingute arv (jooksev kvartal, ` +
      `esmalõike Harju-ribad); KOV-polügoonid OSM admin_level=7 ` +
      `(${SNAP}). Tehingu-KIIRUSE (QoQ) jalga EI OLE siin (see on ` +
      `kovkiirus), maakleri võrdlustehingute jalga EI OLE — ` +
      `iga lahter oma KOV väärtus, silumist EI OLE`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Tallinn-kesk (tuhanded tehingut/kv)
      { lat: 59.2, lon: 24.5 }, // Hõre Harjumaa (tehinguid kümnetes)
    ],
  },
  {
    id: "kovedas",
    paramIds: [43],
    title: "KOV edasimüügi-atraktiivsus (p43 hinnang)",
    goodLabel: "roheline = sügav + kasvav/stabiilne turg (hinnang)",
    badLabel: "punane = õhuke + langev või poolik jalapaar (hinnang — EI OLE)",
    source:
      `${MARU}: sügavus (tehingud, p149 jalg) + suund (aastakasv, ` +
      `p41 jalg) samast tabelist; KOV-polügoonid OSM admin_level=7 ` +
      `(${SNAP}). Puuduva jalaga hinnangut EI FEIGITA (poolik ` +
      `komposiit on EI OLE), maakleri võrdlustehingute jalga EI OLE — ` +
      `iga lahter oma KOV väärtus, silumist EI OLE`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Tallinn-kesk (sügav turg)
      { lat: 59.2, lon: 24.5 }, // Hõre Harjumaa (suuna-jalga sageli pole)
    ],
  },
  {
    id: "kovkiirus",
    paramIds: [484],
    title: "KOV tehingukäibe muutus (p484 NÕRK hinnang, lagi 70)",
    goodLabel: "roheline = käive kasvab (hinnang, lagi 70)",
    badLabel: "punane = käive langeb või kvartalipaar puudub (hinnang — EI OLE)",
    source:
      `${MARU}: tehingute arvu QoQ-muutus (jooksev vs eelmine ` +
      `kvartal, KÄIBE-kiirus üksi); KOV-polügoonid OSM admin_level=7 ` +
      `(${SNAP}). Pakkumiste laoseisu KV-adapteri jalga EI OLE — ` +
      `täis-imemist EI FEIGITA, lagi 70`,
    fallbackPoints: [
      { lat: 59.4364, lon: 24.7536 }, // Tallinn-kesk
      { lat: 59.2, lon: 24.5 }, // Hõre Harjumaa (paaritu kvartal = EI OLE)
    ],
  },
];

/**
 * Overpass QL fragment (documents the polygon source; the app serves
 * the frozen snapshot, never live Overpass). Relation shape: the
 * shared overpassQueryFor() rewrites only n[ fragments, so r[ passes
 * through to a valid relation query.
 */
export const MARUKOV_TAGS: Record<MaruKovLayerId, string> = {
  kovkasv: 'r["boundary"="administrative"];r["admin_level"="7"];',
  kovkaive: 'r["boundary"="administrative"];r["admin_level"="7"];',
  kovedas: 'r["boundary"="administrative"];r["admin_level"="7"];',
  kovkiirus: 'r["boundary"="administrative"];r["admin_level"="7"];',
};

/**
 * Fallback kernel width in km (== wire sigma). The master itself is
 * exact-fill with no kernel; this only sizes the Euclidean fallback
 * when the raster is missing (mobile/"cover" precedent).
 */
export const MARUKOV_DECAY: Record<MaruKovLayerId, number> = {
  kovkasv: 0.5,
  kovkaive: 0.5,
  kovedas: 0.5,
  kovkiirus: 0.5,
};

/**
 * Self-scaling KOV bands (mobile/"cover" precedent): the per-KOV band
 * scores ARE the calibration (no half); sigma is the Euclidean
 * fallback kernel width. Contract-checked against the wire
 * (half null, sigma 0.5) by loadLayerRaster.
 */
export const MARUKOV_BONUS: Record<MaruKovLayerId, BonusSpec> = {
  kovkasv: { kind: "cover", sigma: 0.5 },
  kovkaive: { kind: "cover", sigma: 0.5 },
  kovedas: { kind: "cover", sigma: 0.5 },
  kovkiirus: { kind: "cover", sigma: 0.5 },
};

/** Type guard for the bonusSpecFor hook in layers.ts. */
export function isMaruKovLayerId(layer: string): layer is MaruKovLayerId {
  return (MARUKOV_LAYER_IDS as string[]).includes(layer);
}

/**
 * Maru bonus lookup for the bonusSpecFor() hook in ./layers.
 * Undefined for other layers (their switch/hooks handle them).
 */
export function bonusSpecForMaruKov(layer: string): BonusSpec | undefined {
  return (MARUKOV_BONUS as Record<string, BonusSpec>)[layer];
}

/** Raster master files (built by scripts/build/batch_maru_choropleth.py). */
export const MARUKOV_RASTER_FILE: Record<MaruKovLayerId, string> = {
  kovkasv: "kovkasv-walk-raster.json",
  kovkaive: "kovkaive-walk-raster.json",
  kovedas: "kovedas-walk-raster.json",
  kovkiirus: "kovkiirus-walk-raster.json",
};

/**
 * NO metro masters (documented): exact KOV fills at 9.375 m cells
 * would be fake precision on top of a 75 m fill. The window route
 * serves county everywhere for these layers (G02B/G03/G03D/G08B/G05C/
 * G17A/G17B/parking precedent).
 */
export const MARUKOV_NO_METRO = true;

/** Hook marker, pinned by test so the wiring contract stays greppable. */
export const MARUKOV_HOOK =
  "MARUKOV-HOOK (#486): kovkasv + kovkaive + kovedas + kovkiirus wired " +
  "into layers/overlays/snapshot; MARU quarterly KOV exact fills, cover " +
  "sigma 0.5, p421 refused (needs the listing asking price).";
